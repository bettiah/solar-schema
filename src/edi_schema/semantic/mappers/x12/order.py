"""
X12 850 Purchase Order Mapper.

Maps between X12 850 Purchase Order and semantic Order model.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from ...models import (
    Address,
    AllowanceCharge,
    Amount,
    Contact,
    CustomerParty,
    Delivery,
    Identifier,
    Item,
    ItemIdentification,
    Order,
    OrderLine,
    Party,
    PartyIdentification,
    PartyName,
    PaymentTerms,
    Price,
    Quantity,
    SupplierParty,
)
from ..base import Format, SemanticMapper
from .utils import (
    find_all_loops,
    find_all_segments_in_loop,
    find_segment,
    find_segment_in_loop,
    get_element_value,
    map_id_qualifier,
    map_product_id_qualifier,
    parse_decimal,
    parse_x12_date,
)

if TYPE_CHECKING:
    from edi_schema.x12.ast import LoopInstance, ParsedSegment, TransactionSetInstance


class X12OrderMapper(SemanticMapper[Order]):
    """
    Maps X12 850 Purchase Order to/from semantic Order model.

    X12 850 Structure:
    - BEG: Beginning Segment (PO number, date, type)
    - CUR: Currency (optional)
    - REF: References (repeating)
    - DTM: Date/Time References (repeating)
    - N1 Loop: Party Information (BY, SE, ST, etc.)
      - N1: Party Identification
      - N2: Additional Name
      - N3: Address Lines
      - N4: Geographic Location
      - PER: Contact Information
    - PO1 Loop: Line Items
      - PO1: Baseline Item Data
      - PID: Product Description
      - SAC: Allowances/Charges
      - DTM: Line-level dates
    - CTT: Transaction Totals

    Semantic Order Mapping:
    - BEG → id, issue_date, order_type_code
    - CUR → document_currency_code
    - N1 BY → buyer_customer_party
    - N1 SE → seller_supplier_party
    - N1 ST → delivery
    - PO1 Loop → order_lines
    - CTT → line_count
    """

    @property
    def semantic_type(self) -> type[Order]:
        return Order

    @property
    def source_format(self) -> Format:
        return Format.X12

    @property
    def transaction_id(self) -> str:
        return "850"

    def to_semantic(self, source: "TransactionSetInstance") -> Order:
        """Convert X12 850 to semantic Order."""
        if source.transaction_id != "850":
            raise ValueError(f"Expected 850, got {source.transaction_id}")

        content = source.content

        # Extract BEG segment (required)
        beg = find_segment(content, "BEG")
        if not beg:
            raise ValueError("Missing required BEG segment")

        # Parse BEG fields
        po_number = get_element_value(beg, 3) or ""
        issue_date = parse_x12_date(get_element_value(beg, 5))
        if not issue_date:
            raise ValueError("Missing or invalid date in BEG05")

        purpose_code = get_element_value(beg, 1)  # 00=Original, 05=Replace
        po_type_code = get_element_value(beg, 2)  # SA, NE, etc.

        # Extract currency from CUR segment
        cur = find_segment(content, "CUR")
        currency = "USD"  # Default
        if cur:
            currency = get_element_value(cur, 2) or "USD"

        # Create base order
        order = Order(
            id=po_number,
            issue_date=issue_date,
            document_currency_code=currency,
            order_type_code=po_type_code,
            document_purpose_code=purpose_code,
        )

        # Extract parties from N1 loops
        n1_loops = find_all_loops(content, "N1")
        for n1_loop in n1_loops:
            self._process_n1_loop(n1_loop, order)

        # Extract payment terms from ITD segments
        itd_loops = find_all_loops(content, "ITD")
        for itd_loop in itd_loops:
            terms = self._parse_itd_loop(itd_loop)
            if terms:
                order.payment_terms.append(terms)

        # Also check for ITD at header level (non-loop)
        itd_seg = find_segment(content, "ITD")
        if itd_seg:
            terms = self._parse_itd_segment(itd_seg)
            if terms:
                order.payment_terms.append(terms)

        # Extract line items from PO1 loops
        po1_loops = find_all_loops(content, "PO1")
        for i, po1_loop in enumerate(po1_loops, 1):
            line = self._parse_po1_loop(po1_loop, i, currency)
            order.order_lines.append(line)

        # Extract CTT for line count validation
        ctt = find_segment(content, "CTT")
        if ctt:
            count_str = get_element_value(ctt, 1)
            if count_str:
                order.line_count = int(count_str)

        # Set source tracking
        order._source_format = "x12"
        order._source_version = "005010"

        return order

    def from_semantic(self, model: Order) -> object:
        """
        Convert semantic Order to X12 850.

        Returns a list of segment dictionaries that can be used to
        generate X12 output.
        """
        segments = []

        # BEG segment
        segments.append({
            "tag": "BEG",
            "elements": [
                model.document_purpose_code or "00",  # BEG01
                model.order_type_code or "SA",  # BEG02
                model.id,  # BEG03
                "",  # BEG04 - Release Number
                model.issue_date.strftime("%Y%m%d"),  # BEG05
            ],
        })

        # CUR segment if non-USD
        if model.document_currency_code != "USD":
            segments.append({
                "tag": "CUR",
                "elements": [
                    "BY",  # CUR01 - Entity Identifier Code
                    model.document_currency_code,  # CUR02
                ],
            })

        # N1 loops for parties
        if model.buyer_customer_party:
            segments.extend(
                self._build_n1_loop("BY", model.buyer_customer_party.party)
            )
        if model.seller_supplier_party:
            segments.extend(
                self._build_n1_loop("SE", model.seller_supplier_party.party)
            )
        for delivery in model.delivery:
            if delivery.delivery_party:
                segments.extend(
                    self._build_n1_loop("ST", delivery.delivery_party)
                )

        # PO1 loops for line items
        for line in model.order_lines:
            segments.extend(self._build_po1_loop(line, model.document_currency_code))

        # CTT segment
        segments.append({
            "tag": "CTT",
            "elements": [str(len(model.order_lines))],
        })

        return segments

    def _process_n1_loop(self, n1_loop: "LoopInstance", order: Order) -> None:
        """Process an N1 loop and add party to appropriate order field."""
        n1_seg = find_segment_in_loop(n1_loop, "N1")
        if not n1_seg:
            return

        party_code = get_element_value(n1_seg, 1)
        party = self._build_party_from_n1_loop(n1_loop)

        if party_code == "BY":
            # Buyer
            order.buyer_customer_party = CustomerParty(party=party)
            # Check for buyer contact (PER segment)
            per = find_segment_in_loop(n1_loop, "PER")
            if per:
                order.buyer_customer_party.buyer_contact = self._parse_per_segment(per)

        elif party_code == "SE":
            # Seller
            order.seller_supplier_party = SupplierParty(party=party)
            per = find_segment_in_loop(n1_loop, "PER")
            if per:
                order.seller_supplier_party.seller_contact = self._parse_per_segment(per)

        elif party_code == "ST":
            # Ship To
            delivery = Delivery(
                delivery_party=party,
                delivery_location=party.postal_address,
            )
            order.delivery.append(delivery)

        elif party_code == "BT":
            # Bill To
            order.accounting_customer_party = CustomerParty(party=party)

    def _build_party_from_n1_loop(self, n1_loop: "LoopInstance") -> Party:
        """Build a Party from an N1 loop."""
        party = Party()

        # N1 segment - name and identifier
        n1 = find_segment_in_loop(n1_loop, "N1")
        if n1:
            name = get_element_value(n1, 2)
            if name:
                party.party_names.append(PartyName(name=name))

            id_qualifier = get_element_value(n1, 3)
            id_value = get_element_value(n1, 4)
            if id_value:
                scheme = map_id_qualifier(id_qualifier) if id_qualifier else None
                party.party_identifications.append(
                    PartyIdentification(
                        id=Identifier(value=id_value, scheme_id=scheme)
                    )
                )

        # N2 segment - additional name
        n2 = find_segment_in_loop(n1_loop, "N2")
        if n2:
            name2 = get_element_value(n2, 1)
            if name2:
                party.party_names.append(PartyName(name=name2))

        # N3/N4 segments - address
        n3 = find_segment_in_loop(n1_loop, "N3")
        n4 = find_segment_in_loop(n1_loop, "N4")

        if n3 or n4:
            party.postal_address = Address(
                street_name=get_element_value(n3, 1) if n3 else None,
                additional_street_name=get_element_value(n3, 2) if n3 else None,
                city_name=get_element_value(n4, 1) if n4 else None,
                country_subentity=get_element_value(n4, 2) if n4 else None,
                postal_zone=get_element_value(n4, 3) if n4 else None,
                country_code=get_element_value(n4, 4) if n4 else None,
            )

        # PER segment - contact
        per = find_segment_in_loop(n1_loop, "PER")
        if per:
            party.contact = self._parse_per_segment(per)

        return party

    def _parse_per_segment(self, per: "ParsedSegment") -> Contact:
        """Parse a PER segment into a Contact."""
        contact = Contact(name=get_element_value(per, 2))

        # PER03-08 are qualifier/value pairs
        for i in range(3, 9, 2):
            qualifier = get_element_value(per, i)
            value = get_element_value(per, i + 1)
            if qualifier and value:
                if qualifier == "TE":
                    contact.telephone = value
                elif qualifier == "EM":
                    contact.electronic_mail = value
                elif qualifier == "FX":
                    contact.telefax = value

        return contact

    def _parse_itd_loop(self, itd_loop: "LoopInstance") -> PaymentTerms | None:
        """Parse an ITD loop into PaymentTerms."""
        itd = find_segment_in_loop(itd_loop, "ITD")
        if itd:
            return self._parse_itd_segment(itd)
        return None

    def _parse_itd_segment(self, itd: "ParsedSegment") -> PaymentTerms:
        """Parse an ITD segment into PaymentTerms."""
        discount_percent = parse_decimal(get_element_value(itd, 5))
        _net_days = get_element_value(itd, 7)  # noqa: F841 Parsed for future use
        description = get_element_value(itd, 12)

        return PaymentTerms(
            settlement_discount_percent=discount_percent,
            note=description,
        )

    def _parse_po1_loop(
        self, po1_loop: "LoopInstance", line_num: int, currency: str
    ) -> OrderLine:
        """Parse a PO1 loop into an OrderLine."""
        po1 = find_segment_in_loop(po1_loop, "PO1")
        if not po1:
            raise ValueError(f"PO1 loop {line_num} missing PO1 segment")

        # Line ID
        line_id = get_element_value(po1, 1) or str(line_num)

        # Quantity
        qty_value = parse_decimal(get_element_value(po1, 2)) or Decimal("0")
        unit_code = get_element_value(po1, 3) or "EA"

        # Unit price
        price_value = parse_decimal(get_element_value(po1, 4))

        # Build item with product IDs
        item = self._build_item_from_po1(po1, po1_loop)

        # Create order line
        line = OrderLine(
            id=line_id,
            quantity=Quantity(value=qty_value, unit_code=unit_code),
            item=item,
        )

        # Set price if present
        if price_value is not None:
            line.price = Price(
                price_amount=Amount(value=price_value, currency=currency)
            )
            # Calculate line extension
            line.line_extension_amount = Amount(
                value=qty_value * price_value, currency=currency
            )

        # Parse SAC segments (allowances/charges)
        for sac in find_all_segments_in_loop(po1_loop, "SAC"):
            ac = self._parse_sac_segment(sac, currency)
            if ac:
                line.allowance_charges.append(ac)

        return line

    def _build_item_from_po1(
        self, po1: "ParsedSegment", po1_loop: "LoopInstance"
    ) -> Item:
        """Build an Item from PO1 segment and loop."""
        item = Item()

        # Product IDs come in pairs: qualifier (06, 08, 10...) + value (07, 09, 11...)
        for i in range(6, 26, 2):
            qualifier = get_element_value(po1, i)
            value = get_element_value(po1, i + 1)
            if qualifier and value:
                field_type, scheme = map_product_id_qualifier(qualifier)
                item_id = ItemIdentification(
                    id=Identifier(value=value, scheme_id=scheme)
                )

                if field_type == "standard":
                    item.standard_item_identification = item_id
                elif field_type == "sellers":
                    item.sellers_item_identification = item_id
                elif field_type == "buyers":
                    item.buyers_item_identification = item_id
                elif field_type == "manufacturers":
                    item.manufacturers_item_identification = item_id
                else:
                    item.additional_item_identifications.append(item_id)

        # PID segment - description
        pid = find_segment_in_loop(po1_loop, "PID")
        if pid:
            item.description = get_element_value(pid, 5)

        return item

    def _parse_sac_segment(
        self, sac: "ParsedSegment", currency: str
    ) -> AllowanceCharge | None:
        """Parse a SAC segment into AllowanceCharge."""
        indicator = get_element_value(sac, 1)
        if not indicator:
            return None

        is_charge = indicator == "C"
        amount_value = parse_decimal(get_element_value(sac, 5))
        if amount_value is None:
            return None

        reason = get_element_value(sac, 12)
        reason_code = get_element_value(sac, 4)

        return AllowanceCharge(
            charge_indicator=is_charge,
            amount=Amount(value=amount_value, currency=currency),
            allowance_charge_reason=reason,
            allowance_charge_reason_code=reason_code,
        )

    def _build_n1_loop(self, party_code: str, party: Party) -> list[dict]:
        """Build N1 loop segments from a Party."""
        segments = []

        # N1 segment
        n1_elements = [party_code]

        if party.party_names:
            n1_elements.append(party.party_names[0].name)
        else:
            n1_elements.append("")

        if party.party_identifications:
            pid = party.party_identifications[0]
            # Map scheme back to X12 qualifier
            qualifier = self._scheme_to_n1_qualifier(pid.id.scheme_id)
            n1_elements.append(qualifier)
            n1_elements.append(pid.id.value)

        segments.append({"tag": "N1", "elements": n1_elements})

        # N3 segment (address)
        if party.postal_address:
            addr = party.postal_address
            if addr.street_name:
                n3_elements = [addr.street_name]
                if addr.additional_street_name:
                    n3_elements.append(addr.additional_street_name)
                segments.append({"tag": "N3", "elements": n3_elements})

            # N4 segment
            if any([addr.city_name, addr.country_subentity, addr.postal_zone]):
                n4_elements = [
                    addr.city_name or "",
                    addr.country_subentity or "",
                    addr.postal_zone or "",
                ]
                if addr.country_code:
                    n4_elements.append(addr.country_code)
                segments.append({"tag": "N4", "elements": n4_elements})

        return segments

    def _build_po1_loop(self, line: OrderLine, currency: str) -> list[dict]:
        """Build PO1 loop segments from an OrderLine."""
        segments = []

        # PO1 segment
        po1_elements = [
            line.id,
            str(line.quantity.value),
            line.quantity.unit_code,
        ]

        if line.price:
            po1_elements.append(str(line.price.price_amount.value))
        else:
            po1_elements.append("")

        po1_elements.append("")  # PO105 - Basis of Unit Price

        # Add product IDs
        self._add_product_ids_to_po1(line.item, po1_elements)

        segments.append({"tag": "PO1", "elements": po1_elements})

        # PID segment (description)
        if line.item.description:
            segments.append({
                "tag": "PID",
                "elements": ["F", "", "", "", line.item.description],
            })

        # SAC segments (allowances/charges)
        for ac in line.allowance_charges:
            segments.append(self._build_sac_segment(ac))

        return segments

    def _add_product_ids_to_po1(self, item: Item, elements: list) -> None:
        """Add product ID qualifier/value pairs to PO1 elements."""
        # Standard ID (UPC, EAN)
        if item.standard_item_identification:
            scheme = item.standard_item_identification.id.scheme_id
            qualifier = "UP" if scheme == "UPC" else "EN" if scheme == "EAN" else "UK"
            elements.extend([qualifier, item.standard_item_identification.id.value])

        # Seller's ID
        if item.sellers_item_identification:
            elements.extend(["VP", item.sellers_item_identification.id.value])

        # Buyer's ID
        if item.buyers_item_identification:
            elements.extend(["BP", item.buyers_item_identification.id.value])

    def _build_sac_segment(self, ac: AllowanceCharge) -> dict:
        """Build SAC segment from AllowanceCharge."""
        return {
            "tag": "SAC",
            "elements": [
                "C" if ac.charge_indicator else "A",
                "",  # SAC02
                "",  # SAC03
                ac.allowance_charge_reason_code or "",
                str(ac.amount.value) if ac.amount else "",
                "",  # SAC06
                "",  # SAC07
                "",  # SAC08
                "",  # SAC09
                "",  # SAC10
                "",  # SAC11
                ac.allowance_charge_reason or "",
            ],
        }

    def _scheme_to_n1_qualifier(self, scheme: str | None) -> str:
        """Map scheme ID back to X12 N1*03 qualifier."""
        if not scheme:
            return "ZZ"
        reverse_map = {
            "DUNS": "1",
            "DUNS+4": "9",
            "Phone": "12",
            "SellerAssigned": "91",
            "BuyerAssigned": "92",
        }
        return reverse_map.get(scheme, "ZZ")
