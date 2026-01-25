"""
X12 861 Receiving Advice Mapper.

Maps between X12 861 and semantic ReceiptAdvice model.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from ...models import (
    Address,
    CustomerParty,
    Identifier,
    Item,
    ItemIdentification,
    Party,
    PartyIdentification,
    PartyName,
    Quantity,
    ReceiptAdvice,
    ReceiptLine,
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


class X12ReceiptAdviceMapper(SemanticMapper[ReceiptAdvice]):
    """
    Maps X12 861 Receiving Advice to/from semantic ReceiptAdvice model.

    X12 861 Structure:
    - BRA: Beginning Segment for Receiving Advice
    - CUR: Currency
    - REF: References
    - DTM: Date/Time Reference
    - N1 Loop: Party Information
    - RCD Loop: Receiving Conditions (line items)
      - RCD: Receiving Conditions
      - LIN: Item Identification
      - SN1: Item Detail
      - PID: Product Description
    - CTT: Transaction Totals
    """

    @property
    def semantic_type(self) -> type[ReceiptAdvice]:
        return ReceiptAdvice

    @property
    def source_format(self) -> Format:
        return Format.X12

    @property
    def transaction_id(self) -> str:
        return "861"

    def to_semantic(self, source: "TransactionSetInstance") -> ReceiptAdvice:
        """Convert X12 861 to semantic ReceiptAdvice."""
        if source.transaction_id != "861":
            raise ValueError(f"Expected 861, got {source.transaction_id}")

        content = source.content

        # Extract BRA segment (required)
        bra = find_segment(content, "BRA")
        if not bra:
            raise ValueError("Missing required BRA segment")

        # Parse BRA fields
        receipt_id = get_element_value(bra, 2) or ""
        issue_date = parse_x12_date(get_element_value(bra, 3))
        if not issue_date:
            raise ValueError("Missing or invalid date in BRA03")

        receipt_type_code = get_element_value(bra, 4)

        # Create receipt advice
        receipt = ReceiptAdvice(
            id=receipt_id,
            issue_date=issue_date,
            receipt_advice_type_code=receipt_type_code,
            receipt_lines=[],
        )

        # Extract parties from N1 loops
        for n1_loop in find_all_loops(content, "N1"):
            self._parse_party_loop(receipt, n1_loop)

        # Extract line items from RCD loops
        for i, rcd_loop in enumerate(find_all_loops(content, "RCD"), 1):
            line = self._parse_line_loop(rcd_loop, i)
            if line:
                receipt.receipt_lines.append(line)

        # Also check SN1 loops (alternative structure)
        for i, sn1_loop in enumerate(find_all_loops(content, "SN1"), 1):
            line = self._parse_sn1_loop(sn1_loop, i)
            if line:
                receipt.receipt_lines.append(line)

        # Extract CTT for line count validation
        ctt = find_segment(content, "CTT")
        if ctt:
            count_str = get_element_value(ctt, 1)
            if count_str:
                receipt.line_count = int(count_str)

        receipt._source_format = "x12"
        receipt._source_version = source.version
        return receipt

    def _parse_party_loop(self, receipt: ReceiptAdvice, loop: "LoopInstance") -> None:
        """Parse N1 loop and add party to receipt."""
        n1 = find_segment_in_loop(loop, "N1")
        if not n1:
            return

        party_code = get_element_value(n1, 1)
        party = self._build_party(loop)

        if party_code == "SF":  # Ship From (Supplier)
            receipt.despatch_supplier_party = SupplierParty(party=party)
        elif party_code == "ST":  # Ship To (Receiver)
            receipt.delivery_customer_party = CustomerParty(party=party)
        elif party_code == "BY":  # Buyer
            receipt.buyer_customer_party = CustomerParty(party=party)
        elif party_code == "SE":  # Seller
            receipt.seller_supplier_party = SupplierParty(party=party)

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

    def _parse_line_loop(self, loop: "LoopInstance", line_num: int) -> ReceiptLine | None:
        """Parse RCD loop into ReceiptLine."""
        rcd = find_segment_in_loop(loop, "RCD")
        if not rcd:
            return None

        line_id = str(line_num)
        quantity = parse_decimal(get_element_value(rcd, 2)) or Decimal("1")
        unit_code = get_element_value(rcd, 3) or "EA"

        # Cumulative received quantity
        received_qty = parse_decimal(get_element_value(rcd, 5))
        if received_qty is not None:
            quantity = received_qty

        # Build item
        item = Item()

        # LIN segment for item identification
        lin = find_segment_in_loop(loop, "LIN")
        if lin:
            for i in range(2, 32, 2):
                qual = get_element_value(lin, i)
                val = get_element_value(lin, i + 1)
                if qual and val:
                    self._set_item_id(item, qual, val)

        # PID segment for description
        pid = find_segment_in_loop(loop, "PID")
        if pid:
            item.description = get_element_value(pid, 5)

        line = ReceiptLine(
            id=line_id,
            received_quantity=Quantity(value=quantity, unit_code=unit_code),
            item=item,
        )

        # Short quantity
        short_qty = parse_decimal(get_element_value(rcd, 8))
        if short_qty is not None:
            line.short_quantity = Quantity(value=short_qty, unit_code=unit_code)

        # Rejected quantity
        reject_qty = parse_decimal(get_element_value(rcd, 11))
        if reject_qty is not None:
            line.rejected_quantity = Quantity(value=reject_qty, unit_code=unit_code)

        return line

    def _parse_sn1_loop(self, loop: "LoopInstance", line_num: int) -> ReceiptLine | None:
        """Parse SN1 loop into ReceiptLine."""
        sn1 = find_segment_in_loop(loop, "SN1")
        if not sn1:
            return None

        line_id = get_element_value(sn1, 1) or str(line_num)
        quantity = parse_decimal(get_element_value(sn1, 2)) or Decimal("1")
        unit_code = get_element_value(sn1, 3) or "EA"

        # Build item
        item = Item()

        # LIN segment for item identification
        lin = find_segment_in_loop(loop, "LIN")
        if lin:
            for i in range(2, 32, 2):
                qual = get_element_value(lin, i)
                val = get_element_value(lin, i + 1)
                if qual and val:
                    self._set_item_id(item, qual, val)

        # PID segment for description
        pid = find_segment_in_loop(loop, "PID")
        if pid:
            item.description = get_element_value(pid, 5)

        return ReceiptLine(
            id=line_id,
            received_quantity=Quantity(value=quantity, unit_code=unit_code),
            item=item,
        )

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

    def from_semantic(self, model: ReceiptAdvice) -> object:
        """Convert semantic ReceiptAdvice to X12 861."""
        segments = []

        # BRA segment
        segments.append(
            {
                "tag": "BRA",
                "elements": [
                    "00",  # BRA01 - Transaction Set Purpose Code
                    model.id,  # BRA02 - Reference Identification
                    model.issue_date.strftime("%Y%m%d"),  # BRA03 - Date
                    model.receipt_advice_type_code or "P",  # BRA04 - Transaction Type Code
                ],
            }
        )

        # N1 loops for parties
        if model.despatch_supplier_party:
            segments.extend(self._build_party_segments("SF", model.despatch_supplier_party.party))
        if model.delivery_customer_party:
            segments.extend(self._build_party_segments("ST", model.delivery_customer_party.party))
        if model.buyer_customer_party:
            segments.extend(self._build_party_segments("BY", model.buyer_customer_party.party))
        if model.seller_supplier_party:
            segments.extend(self._build_party_segments("SE", model.seller_supplier_party.party))

        # RCD loops for line items
        for line in model.receipt_lines:
            segments.extend(self._build_line_segments(line))

        # CTT segment
        segments.append(
            {
                "tag": "CTT",
                "elements": [str(len(model.receipt_lines))],
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

    def _build_line_segments(self, line: ReceiptLine) -> list[dict]:
        """Build RCD/LIN/PID segments for a receipt line."""
        segments = []

        # RCD segment
        rcd_elements = [
            "",  # RCD01
            str(line.received_quantity.value),  # RCD02
            line.received_quantity.unit_code,  # RCD03
        ]

        # Add short/rejected quantities
        rcd_elements.extend(["", ""])  # RCD04-05
        if line.short_quantity:
            rcd_elements.extend(
                ["", "", str(line.short_quantity.value), line.short_quantity.unit_code]
            )
        else:
            rcd_elements.extend(["", "", "", ""])

        if line.rejected_quantity:
            rcd_elements.append(str(line.rejected_quantity.value))
        else:
            rcd_elements.append("")

        segments.append({"tag": "RCD", "elements": rcd_elements})

        # LIN segment for item identification
        lin_elements = [line.id]
        if line.item.standard_item_identification:
            scheme = line.item.standard_item_identification.id.scheme_id or "UP"
            lin_elements.extend([scheme, line.item.standard_item_identification.id.value])
        elif line.item.sellers_item_identification:
            lin_elements.extend(["VP", line.item.sellers_item_identification.id.value])
        elif line.item.buyers_item_identification:
            lin_elements.extend(["BP", line.item.buyers_item_identification.id.value])

        if len(lin_elements) > 1:
            segments.append({"tag": "LIN", "elements": lin_elements})

        # PID segment for description
        if line.item.description:
            segments.append(
                {
                    "tag": "PID",
                    "elements": ["F", "", "", "", line.item.description],
                }
            )

        return segments
