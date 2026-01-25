"""
X12 855 Purchase Order Acknowledgment Mapper.

Maps between X12 855 and semantic OrderResponse model.
"""

from typing import TYPE_CHECKING

from ...models import (
    Amount,
    CustomerParty,
    Delivery,
    Identifier,
    Item,
    ItemIdentification,
    OrderReference,
    OrderResponse,
    OrderResponseLine,
    Party,
    PartyIdentification,
    PartyName,
    Price,
    Quantity,
    SupplierParty,
)
from ..base import Format, SemanticMapper
from .utils import (
    find_all_loops,
    find_segment,
    find_segment_in_loop,
    get_element_value,
    map_id_qualifier,
    map_product_id_qualifier,
    parse_decimal,
    parse_x12_date,
)

if TYPE_CHECKING:
    from edi_schema.x12.ast import LoopInstance, TransactionSetInstance


class X12OrderResponseMapper(SemanticMapper[OrderResponse]):
    """
    Maps X12 855 Purchase Order Acknowledgment to/from semantic OrderResponse model.

    X12 855 Structure:
    - BAK: Beginning Segment (PO Acknowledgment)
    - CUR: Currency (optional)
    - REF: References
    - DTM: Date/Time References
    - N1 Loop: Party Information
    - PO1 Loop: Line Items with acknowledgment status
    - CTT: Transaction Totals
    """

    @property
    def semantic_type(self) -> type[OrderResponse]:
        return OrderResponse

    @property
    def source_format(self) -> Format:
        return Format.X12

    @property
    def transaction_id(self) -> str:
        return "855"

    def to_semantic(self, source: "TransactionSetInstance") -> OrderResponse:
        """Convert X12 855 to semantic OrderResponse."""
        if source.transaction_id != "855":
            raise ValueError(f"Expected 855, got {source.transaction_id}")

        content = source.content

        # Extract BAK segment (required)
        bak = find_segment(content, "BAK")
        if not bak:
            raise ValueError("Missing required BAK segment")

        # Parse basic fields
        response_code = get_element_value(bak, 1)  # BAK01 - response type (AC, AD, RD, etc.)
        po_number = get_element_value(bak, 3)  # BAK03 - PO number being acknowledged
        ack_date = parse_x12_date(get_element_value(bak, 4))  # BAK04 - date
        ack_number = get_element_value(bak, 8)  # BAK08 - acknowledgment number

        if not ack_date:
            raise ValueError("Missing or invalid date in BAK04")

        # Currency (default USD)
        currency = "USD"
        cur = find_segment(content, "CUR")
        if cur:
            currency = get_element_value(cur, 2) or "USD"

        # Create order response
        response = OrderResponse(
            id=ack_number or po_number or "",
            issue_date=ack_date,
            document_currency_code=currency,
            order_response_code=response_code,
            order_reference=OrderReference(id=po_number) if po_number else None,
            order_lines=[],
        )

        # Parse N1 loops for parties
        for n1_loop in find_all_loops(content, "N1"):
            self._parse_party_loop(response, n1_loop)

        # Parse PO1 loops for line items
        for po1_loop in find_all_loops(content, "PO1"):
            line = self._parse_line_item(po1_loop, currency)
            if line:
                response.order_lines.append(line)

        # Parse CTT for line count
        ctt = find_segment(content, "CTT")
        if ctt:
            count = get_element_value(ctt, 1)
            if count:
                response.line_count = int(count)

        response._source_format = "x12"
        response._source_version = source.version
        return response

    def _parse_party_loop(self, response: OrderResponse, loop: "LoopInstance") -> None:
        """Parse N1 loop and add party to response."""
        n1 = find_segment_in_loop(loop, "N1")
        if not n1:
            return

        party_code = get_element_value(n1, 1)
        party = self._build_party(loop)

        if party_code == "BY":
            response.buyer_customer_party = CustomerParty(party=party)
        elif party_code in ("SE", "VN"):
            response.seller_supplier_party = SupplierParty(party=party)
        elif party_code == "ST":
            response.delivery.append(Delivery(delivery_party=party))

    def _build_party(self, loop: "LoopInstance") -> Party:
        """Build Party from N1 loop."""
        n1 = find_segment_in_loop(loop, "N1")
        n3 = find_segment_in_loop(loop, "N3")
        n4 = find_segment_in_loop(loop, "N4")

        party = Party()

        if n1:
            name = get_element_value(n1, 2)
            if name:
                party.party_names.append(PartyName(name=name))

            id_qual = get_element_value(n1, 3)
            id_val = get_element_value(n1, 4)
            if id_val:
                party.party_identifications.append(
                    PartyIdentification(
                        id=Identifier(
                            value=id_val,
                            scheme_id=map_id_qualifier(id_qual) if id_qual else None,
                        )
                    )
                )

        if n3 or n4:
            from ...models import Address

            party.postal_address = Address(
                street_name=get_element_value(n3, 1) if n3 else None,
                additional_street_name=get_element_value(n3, 2) if n3 else None,
                city_name=get_element_value(n4, 1) if n4 else None,
                country_subentity=get_element_value(n4, 2) if n4 else None,
                postal_zone=get_element_value(n4, 3) if n4 else None,
                country_code=get_element_value(n4, 4) if n4 else None,
            )

        return party

    def _parse_line_item(self, loop: "LoopInstance", currency: str) -> OrderResponseLine | None:
        """Parse PO1 loop into OrderResponseLine."""
        po1 = find_segment_in_loop(loop, "PO1")
        if not po1:
            return None

        line_num = get_element_value(po1, 1) or "1"
        quantity = parse_decimal(get_element_value(po1, 2))
        unit_code = get_element_value(po1, 3) or "EA"
        unit_price = parse_decimal(get_element_value(po1, 4))

        # Build item
        item = Item()

        # Product IDs in PO1 (pairs at positions 6-7, 8-9, etc.)
        for i in range(6, 26, 2):
            qual = get_element_value(po1, i)
            val = get_element_value(po1, i + 1)
            if qual and val:
                self._set_item_id(item, qual, val)

        # PID segment for description
        pid = find_segment_in_loop(loop, "PID")
        if pid:
            item.description = get_element_value(pid, 5)

        # ACK segment for line status
        line_status = None
        ack = find_segment_in_loop(loop, "ACK")
        if ack:
            line_status = get_element_value(ack, 1)  # ACK01 - line item status

        line = OrderResponseLine(
            id=line_num,
            line_status_code=line_status,
            quantity=Quantity(value=quantity, unit_code=unit_code) if quantity else None,
            item=item,
        )

        if unit_price:
            line.price = Price(price_amount=Amount(value=unit_price, currency=currency))

        return line

    def _set_item_id(self, item: Item, qualifier: str, value: str) -> None:
        """Set item identifier based on X12 qualifier code."""
        scheme = map_product_id_qualifier(qualifier)
        identification = ItemIdentification(id=Identifier(value=value, scheme_id=scheme))

        if qualifier in ("UP", "EN", "UK"):
            item.standard_item_identification = identification
        elif qualifier in ("VP", "SK"):
            item.sellers_item_identification = identification
        elif qualifier in ("BP", "IN"):
            item.buyers_item_identification = identification
        elif qualifier == "MG":
            item.manufacturers_item_identification = identification

    def from_semantic(self, model: OrderResponse) -> object:
        """Convert semantic OrderResponse to X12 855."""
        segments = []

        # BAK segment
        segments.append(
            {
                "tag": "BAK",
                "elements": [
                    model.order_response_code or "AC",  # BAK01 - Acknowledgment Type
                    "00",  # BAK02 - Purpose Code (Original)
                    model.order_reference.id if model.order_reference else "",  # BAK03
                    model.issue_date.strftime("%Y%m%d"),  # BAK04
                    "",  # BAK05
                    "",  # BAK06
                    "",  # BAK07
                    model.id,  # BAK08 - Acknowledgment number
                ],
            }
        )

        # CUR segment if non-USD
        if model.document_currency_code != "USD":
            segments.append(
                {
                    "tag": "CUR",
                    "elements": [
                        "SE",  # Selling Party
                        model.document_currency_code,
                    ],
                }
            )

        # N1 loops for parties
        if model.seller_supplier_party:
            segments.extend(self._build_party_segments("SE", model.seller_supplier_party.party))
        if model.buyer_customer_party:
            segments.extend(self._build_party_segments("BY", model.buyer_customer_party.party))

        # PO1 loops for line items
        for line in model.order_lines:
            segments.extend(self._build_line_segments(line, model.document_currency_code))

        # CTT segment
        segments.append(
            {
                "tag": "CTT",
                "elements": [str(len(model.order_lines))],
            }
        )

        return segments

    def _build_party_segments(self, code: str, party: Party) -> list[dict]:
        """Build N1/N3/N4 segments for a party."""
        segments = []

        n1_elements = [code]

        if party.party_names:
            n1_elements.append(party.party_names[0].name)
        else:
            n1_elements.append("")

        if party.party_identifications:
            pid = party.party_identifications[0]
            n1_elements.append(pid.id.scheme_id or "92")
            n1_elements.append(pid.id.value)

        segments.append({"tag": "N1", "elements": n1_elements})

        if party.postal_address:
            addr = party.postal_address
            if addr.street_name:
                segments.append(
                    {
                        "tag": "N3",
                        "elements": [
                            addr.street_name,
                            addr.additional_street_name or "",
                        ],
                    }
                )

            if addr.city_name or addr.country_subentity or addr.postal_zone:
                segments.append(
                    {
                        "tag": "N4",
                        "elements": [
                            addr.city_name or "",
                            addr.country_subentity or "",
                            addr.postal_zone or "",
                            addr.country_code or "",
                        ],
                    }
                )

        return segments

    def _build_line_segments(self, line: OrderResponseLine, currency: str) -> list[dict]:
        """Build PO1/PID/ACK segments for a line item."""
        segments = []

        po1_elements = [line.id]

        if line.quantity:
            po1_elements.append(str(line.quantity.value))
            po1_elements.append(line.quantity.unit_code)
        else:
            po1_elements.extend(["", ""])

        if line.price:
            po1_elements.append(str(line.price.price_amount.value))
        else:
            po1_elements.append("")

        po1_elements.append("")  # PO105 - Basis of unit price

        # Add item IDs
        if line.item.standard_item_identification:
            scheme = line.item.standard_item_identification.id.scheme_id or "UP"
            po1_elements.extend([scheme, line.item.standard_item_identification.id.value])
        elif line.item.sellers_item_identification:
            po1_elements.extend(["VP", line.item.sellers_item_identification.id.value])
        elif line.item.buyers_item_identification:
            po1_elements.extend(["BP", line.item.buyers_item_identification.id.value])

        segments.append({"tag": "PO1", "elements": po1_elements})

        # PID segment for description
        if line.item.description:
            segments.append(
                {
                    "tag": "PID",
                    "elements": [
                        "F",  # Free-form
                        "",
                        "",
                        "",
                        line.item.description,
                    ],
                }
            )

        # ACK segment for line status
        if line.line_status_code:
            segments.append(
                {
                    "tag": "ACK",
                    "elements": [
                        line.line_status_code,
                    ],
                }
            )

        return segments
