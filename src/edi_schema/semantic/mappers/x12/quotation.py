"""
X12 843 Response to Request for Quotation Mapper.

Maps between X12 843 and semantic Quotation model.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from ...models import (
    Address,
    Amount,
    CustomerParty,
    Identifier,
    Item,
    ItemIdentification,
    Party,
    PartyIdentification,
    PartyName,
    Price,
    Quantity,
    Quotation,
    QuotationLine,
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


class X12QuotationMapper(SemanticMapper[Quotation]):
    """
    Maps X12 843 Response to Request for Quotation to/from semantic Quotation model.

    X12 843 Structure:
    - BQT: Beginning Segment for Quote
    - CUR: Currency
    - REF: References
    - DTM: Date/Time Reference
    - N1 Loop: Party Information (BY, SE, ST)
    - PO1 Loop: Line Items
      - PO1: Baseline Item Data
      - PID: Product Description
      - PO4: Item Physical Details
    - CTT: Transaction Totals
    """

    @property
    def semantic_type(self) -> type[Quotation]:
        return Quotation

    @property
    def source_format(self) -> Format:
        return Format.X12

    @property
    def transaction_id(self) -> str:
        return "843"

    def to_semantic(self, source: "TransactionSetInstance") -> Quotation:
        """Convert X12 843 to semantic Quotation."""
        if source.transaction_id != "843":
            raise ValueError(f"Expected 843, got {source.transaction_id}")

        content = source.content

        # Extract BQT segment (required)
        bqt = find_segment(content, "BQT")
        if not bqt:
            raise ValueError("Missing required BQT segment")

        # Parse BQT fields
        quote_number = get_element_value(bqt, 3) or ""
        issue_date = parse_x12_date(get_element_value(bqt, 4))
        if not issue_date:
            raise ValueError("Missing or invalid date in BQT04")

        quote_type_code = get_element_value(bqt, 2)

        # Extract currency from CUR segment
        cur = find_segment(content, "CUR")
        currency = "USD"
        if cur:
            currency = get_element_value(cur, 2) or "USD"

        # Create base quotation
        quotation = Quotation(
            id=quote_number,
            issue_date=issue_date,
            document_currency_code=currency,
            quotation_type_code=quote_type_code,
            quotation_lines=[],
        )

        # Extract parties from N1 loops
        for n1_loop in find_all_loops(content, "N1"):
            self._parse_party_loop(quotation, n1_loop)

        # Extract line items from PO1 loops
        for i, po1_loop in enumerate(find_all_loops(content, "PO1"), 1):
            line = self._parse_line_loop(po1_loop, i, currency)
            quotation.quotation_lines.append(line)

        # Extract CTT for line count validation
        ctt = find_segment(content, "CTT")
        if ctt:
            count_str = get_element_value(ctt, 1)
            if count_str:
                quotation.line_count = int(count_str)

        quotation._source_format = "x12"
        quotation._source_version = source.version
        return quotation

    def _parse_party_loop(self, quotation: Quotation, loop: "LoopInstance") -> None:
        """Parse N1 loop and add party to quotation."""
        n1 = find_segment_in_loop(loop, "N1")
        if not n1:
            return

        party_code = get_element_value(n1, 1)
        party = self._build_party(loop)

        if party_code == "SE":  # Seller/Quoting Party
            quotation.seller_supplier_party = SupplierParty(party=party)
        elif party_code == "BY":  # Buyer
            quotation.buyer_customer_party = CustomerParty(party=party)

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
            party.postal_address = Address(
                street_name=get_element_value(n3, 1) if n3 else None,
                additional_street_name=get_element_value(n3, 2) if n3 else None,
                city_name=get_element_value(n4, 1) if n4 else None,
                country_subentity=get_element_value(n4, 2) if n4 else None,
                postal_zone=get_element_value(n4, 3) if n4 else None,
                country_code=get_element_value(n4, 4) if n4 else None,
            )

        return party

    def _parse_line_loop(
        self, loop: "LoopInstance", line_num: int, currency: str
    ) -> QuotationLine:
        """Parse PO1 loop into QuotationLine."""
        po1 = find_segment_in_loop(loop, "PO1")
        if not po1:
            raise ValueError(f"PO1 loop {line_num} missing PO1 segment")

        line_id = get_element_value(po1, 1) or str(line_num)
        quantity = parse_decimal(get_element_value(po1, 2)) or Decimal("1")
        unit_code = get_element_value(po1, 3) or "EA"
        unit_price = parse_decimal(get_element_value(po1, 4))

        # Build item
        item = Item()
        for i in range(6, 26, 2):
            qual = get_element_value(po1, i)
            val = get_element_value(po1, i + 1)
            if qual and val:
                self._set_item_id(item, qual, val)

        # PID segment for description
        pid = find_segment_in_loop(loop, "PID")
        if pid:
            item.description = get_element_value(pid, 5)

        # Calculate line amount
        line_amount = quantity * (unit_price or Decimal("0"))

        line = QuotationLine(
            id=line_id,
            quantity=Quantity(value=quantity, unit_code=unit_code),
            line_extension_amount=Amount(value=line_amount, currency=currency),
            item=item,
        )

        if unit_price:
            line.price = Price(price_amount=Amount(value=unit_price, currency=currency))

        return line

    def _set_item_id(self, item: Item, qualifier: str, value: str) -> None:
        """Set item identifier based on X12 qualifier code."""
        field_type, scheme = map_product_id_qualifier(qualifier)
        identification = ItemIdentification(id=Identifier(value=value, scheme_id=scheme))

        if field_type == "standard":
            item.standard_item_identification = identification
        elif field_type == "sellers":
            item.sellers_item_identification = identification
        elif field_type == "buyers":
            item.buyers_item_identification = identification
        elif field_type == "manufacturers":
            item.manufacturers_item_identification = identification

    def from_semantic(self, model: Quotation) -> object:
        """Convert semantic Quotation to X12 843."""
        segments = []

        # BQT segment
        segments.append(
            {
                "tag": "BQT",
                "elements": [
                    "00",  # BQT01 - Transaction Set Purpose Code
                    model.quotation_type_code or "01",  # BQT02 - Quote Type Code
                    model.id,  # BQT03 - Quote Number
                    model.issue_date.strftime("%Y%m%d"),  # BQT04 - Date
                ],
            }
        )

        # CUR segment if non-USD
        if model.document_currency_code != "USD":
            segments.append(
                {
                    "tag": "CUR",
                    "elements": ["SE", model.document_currency_code],
                }
            )

        # N1 loops for parties
        if model.seller_supplier_party:
            segments.extend(self._build_party_segments("SE", model.seller_supplier_party.party))
        if model.buyer_customer_party:
            segments.extend(self._build_party_segments("BY", model.buyer_customer_party.party))

        # PO1 loops for line items
        for line in model.quotation_lines:
            segments.extend(self._build_line_segments(line, model.document_currency_code))

        # CTT segment
        segments.append(
            {
                "tag": "CTT",
                "elements": [str(len(model.quotation_lines))],
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

    def _build_line_segments(self, line: QuotationLine, currency: str) -> list[dict]:
        """Build PO1/PID segments for a quotation line."""
        segments = []

        po1_elements = [line.id]
        po1_elements.append(str(line.quantity.value))
        po1_elements.append(line.quantity.unit_code)

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
                    "elements": ["F", "", "", "", line.item.description],
                }
            )

        return segments
