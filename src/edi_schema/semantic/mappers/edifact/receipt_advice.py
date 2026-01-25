"""
EDIFACT RECADV Receiving Advice Mapper.

Maps between EDIFACT RECADV and semantic ReceiptAdvice model.
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
    find_all_segment_groups,
    find_segment,
    find_segment_in_group,
    format_edifact_date,
    get_component_value,
    get_dtm_date,
    get_element_value,
    map_product_id_qualifier,
    parse_decimal,
)

if TYPE_CHECKING:
    from edi_schema.edifact.ast import (
        MessageInstance,
        ParsedSegment,
        SegmentGroupInstance,
    )


class EdifactReceiptAdviceMapper(SemanticMapper[ReceiptAdvice]):
    """
    Maps EDIFACT RECADV to/from semantic ReceiptAdvice model.

    EDIFACT RECADV Structure:
    - BGM: Beginning of message
    - DTM: Date/time/period
    - SG1 (RFF): References
    - SG4 (NAD): Name and address (parties)
    - SG16 (CPS): Consignment packing sequence
      - SG22 (LIN): Line item
        - LIN: Line item
        - PIA: Additional product id
        - IMD: Item description
        - QTY: Quantity
    """

    @property
    def semantic_type(self) -> type[ReceiptAdvice]:
        return ReceiptAdvice

    @property
    def source_format(self) -> Format:
        return Format.EDIFACT

    @property
    def transaction_id(self) -> str:
        return "RECADV"

    def to_semantic(self, source: "MessageInstance") -> ReceiptAdvice:
        """Convert EDIFACT RECADV to semantic ReceiptAdvice."""
        if source.message_type != "RECADV":
            raise ValueError(f"Expected RECADV, got {source.message_type}")

        content = source.content

        # Extract BGM segment
        bgm = find_segment(content, "BGM")
        if not bgm:
            raise ValueError("Missing required BGM segment")

        # Parse BGM fields
        receipt_id = get_component_value(bgm, 2, 1) or ""  # C106 Document ID

        # Extract dates from DTM (qualifier 137 = document date)
        issue_date = get_dtm_date(content, "137")
        if not issue_date:
            raise ValueError("Missing document date (DTM+137)")

        # Create receipt advice
        receipt = ReceiptAdvice(
            id=receipt_id,
            issue_date=issue_date,
            receipt_lines=[],
        )

        # Parse parties from SG4 groups
        for sg4 in find_all_segment_groups(content, 4):
            nad = find_segment_in_group(sg4, "NAD")
            if nad:
                self._parse_party(receipt, nad)

        # Also check SG2 groups (alternative structure)
        for sg2 in find_all_segment_groups(content, 2):
            nad = find_segment_in_group(sg2, "NAD")
            if nad:
                self._parse_party(receipt, nad)

        # Parse line items from SG16 (CPS groups containing SG22/LIN)
        for sg16 in find_all_segment_groups(content, 16):
            # Look for SG22 within SG16
            for sg22 in find_all_segment_groups(sg16.content if hasattr(sg16, "content") else [], 22):
                line = self._parse_line_group(sg22, len(receipt.receipt_lines) + 1)
                if line:
                    receipt.receipt_lines.append(line)
            # Also check for children
            for child in sg16.children:
                if child.group_number == 22:
                    line = self._parse_line_group(child, len(receipt.receipt_lines) + 1)
                    if line:
                        receipt.receipt_lines.append(line)

        # Also check for SG22 or SG25 directly at top level
        for sg22 in find_all_segment_groups(content, 22):
            line = self._parse_line_group(sg22, len(receipt.receipt_lines) + 1)
            if line:
                receipt.receipt_lines.append(line)

        for sg25 in find_all_segment_groups(content, 25):
            line = self._parse_line_group(sg25, len(receipt.receipt_lines) + 1)
            if line:
                receipt.receipt_lines.append(line)

        receipt.line_count = len(receipt.receipt_lines)

        receipt._source_format = "edifact"
        receipt._source_version = f"{source.version}{source.release}"
        return receipt

    def _parse_party(self, receipt: ReceiptAdvice, nad: "ParsedSegment") -> None:
        """Parse NAD segment into appropriate party."""
        party_qualifier = get_element_value(nad, 1)

        party = Party()

        # Party identification from NAD C082
        party_id = get_component_value(nad, 2, 1)
        party_id_qualifier = get_component_value(nad, 2, 3)
        if party_id:
            party.party_identifications.append(
                PartyIdentification(id=Identifier(value=party_id, scheme_id=party_id_qualifier))
            )

        # Party name from NAD C080
        name = get_component_value(nad, 3, 1)
        if not name:
            name = get_element_value(nad, 4)
        if name:
            party.party_names.append(PartyName(name=name))

        # Address
        street = get_component_value(nad, 5, 1)
        city = get_element_value(nad, 6)
        country_sub = get_element_value(nad, 7)
        postal = get_element_value(nad, 8)
        country = get_element_value(nad, 9)

        if any([street, city, country_sub, postal, country]):
            party.postal_address = Address(
                street_name=street,
                city_name=city,
                country_subentity=country_sub,
                postal_zone=postal,
                country_code=country,
            )

        if party_qualifier == "SF":  # Ship From (Supplier)
            receipt.despatch_supplier_party = SupplierParty(party=party)
        elif party_qualifier == "ST":  # Ship To (Receiver)
            receipt.delivery_customer_party = CustomerParty(party=party)
        elif party_qualifier == "BY":  # Buyer
            receipt.buyer_customer_party = CustomerParty(party=party)
        elif party_qualifier in ("SU", "SE"):  # Supplier/Seller
            receipt.seller_supplier_party = SupplierParty(party=party)
        elif party_qualifier == "DP":  # Delivery Party
            receipt.delivery_customer_party = CustomerParty(party=party)

    def _parse_line_group(
        self, group: "SegmentGroupInstance", line_num: int
    ) -> ReceiptLine | None:
        """Parse LIN group into ReceiptLine."""
        lin = find_segment_in_group(group, "LIN")
        if not lin:
            return None

        line_id = get_element_value(lin, 1) or str(line_num)

        # Item from LIN C212 and PIA
        item = self._build_item_from_group(group)

        # Quantities from QTY segments
        received_qty = Quantity(value=Decimal("1"), unit_code="EA")
        short_qty = None
        rejected_qty = None

        for qty_seg in _find_all_segments_in_group(group, "QTY"):
            qty_qualifier = get_component_value(qty_seg, 1, 1)
            qty_value = get_component_value(qty_seg, 1, 2)
            qty_unit = get_component_value(qty_seg, 1, 3)

            if qty_value:
                val = parse_decimal(qty_value) or Decimal("0")
                unit = qty_unit or "EA"

                if qty_qualifier == "48":  # Received quantity
                    received_qty = Quantity(value=val, unit_code=unit)
                elif qty_qualifier == "119":  # Short quantity
                    short_qty = Quantity(value=val, unit_code=unit)
                elif qty_qualifier == "124":  # Rejected quantity
                    rejected_qty = Quantity(value=val, unit_code=unit)
                elif qty_qualifier in ("21", "47"):  # Ordered/invoiced (fallback)
                    if received_qty.value == Decimal("1"):
                        received_qty = Quantity(value=val, unit_code=unit)

        # Create line
        line = ReceiptLine(
            id=line_id,
            received_quantity=received_qty,
            item=item,
        )

        if short_qty:
            line.short_quantity = short_qty
        if rejected_qty:
            line.rejected_quantity = rejected_qty

        return line

    def _build_item_from_group(self, group: "SegmentGroupInstance") -> Item:
        """Build Item from LIN, PIA, IMD segments."""
        item = Item()

        lin = find_segment_in_group(group, "LIN")

        # Standard item ID from LIN C212
        if lin:
            item_id = get_component_value(lin, 3, 1)
            item_id_type = get_component_value(lin, 3, 2)
            if item_id:
                field_type, scheme = map_product_id_qualifier(item_id_type or "")
                ident = ItemIdentification(id=Identifier(value=item_id, scheme_id=scheme))
                if field_type == "standard":
                    item.standard_item_identification = ident
                elif field_type == "sellers":
                    item.sellers_item_identification = ident
                elif field_type == "buyers":
                    item.buyers_item_identification = ident

        # Additional IDs from PIA
        for pia in _find_all_segments_in_group(group, "PIA"):
            pia_id = get_component_value(pia, 2, 1)
            pia_type = get_component_value(pia, 2, 2)
            if pia_id:
                field_type, scheme = map_product_id_qualifier(pia_type or "")
                ident = ItemIdentification(id=Identifier(value=pia_id, scheme_id=scheme))
                if field_type == "standard" and not item.standard_item_identification:
                    item.standard_item_identification = ident
                elif field_type == "sellers" and not item.sellers_item_identification:
                    item.sellers_item_identification = ident
                elif field_type == "buyers" and not item.buyers_item_identification:
                    item.buyers_item_identification = ident

        # Description from IMD
        for imd in _find_all_segments_in_group(group, "IMD"):
            description = get_component_value(imd, 3, 4)
            if not description:
                description = get_component_value(imd, 3, 5)
            if description:
                item.description = description
                break

        return item

    def from_semantic(self, model: ReceiptAdvice) -> dict:
        """Convert semantic ReceiptAdvice to EDIFACT RECADV structure."""
        segments = []

        # BGM - Beginning of message
        segments.append(
            {
                "tag": "BGM",
                "elements": [
                    {"value": "632"},  # Document type - Receiving advice
                    {"components": [model.id]},  # Document ID
                    "9",  # Original
                ],
            }
        )

        # DTM - Document date
        segments.append(
            {
                "tag": "DTM",
                "elements": [
                    {
                        "components": [
                            "137",  # Document date qualifier
                            format_edifact_date(model.issue_date),
                            "102",  # CCYYMMDD format
                        ]
                    },
                ],
            }
        )

        # NAD - Ship From
        if model.despatch_supplier_party:
            segments.extend(self._build_nad_segments("SF", model.despatch_supplier_party.party))

        # NAD - Ship To
        if model.delivery_customer_party:
            segments.extend(self._build_nad_segments("ST", model.delivery_customer_party.party))

        # NAD - Buyer
        if model.buyer_customer_party:
            segments.extend(self._build_nad_segments("BY", model.buyer_customer_party.party))

        # NAD - Seller
        if model.seller_supplier_party:
            segments.extend(self._build_nad_segments("SU", model.seller_supplier_party.party))

        # CPS - Consignment packing sequence
        segments.append(
            {
                "tag": "CPS",
                "elements": ["1"],  # Hierarchical ID
            }
        )

        # LIN groups - Line items
        for i, line in enumerate(model.receipt_lines, 1):
            segments.extend(self._build_line_segments(line, i))

        # UNS - Section control
        segments.append({"tag": "UNS", "elements": ["S"]})

        # CNT - Control total
        segments.append(
            {
                "tag": "CNT",
                "elements": [
                    {"components": ["2", str(len(model.receipt_lines))]},
                ],
            }
        )

        return {"message_type": "RECADV", "segments": segments}

    def _build_nad_segments(self, qualifier: str, party: Party) -> list[dict]:
        """Build NAD segment(s) for a party."""
        segments = []

        elements = [qualifier]

        # C082 - Party identification
        if party.party_identifications:
            pi = party.party_identifications[0]
            elements.append(
                {
                    "components": [
                        pi.id.value,
                        "",
                        pi.id.scheme_id or "92",
                    ],
                }
            )
        else:
            elements.append("")

        # C080 - Party name
        if party.party_names:
            elements.append({"components": [party.party_names[0].name]})
        else:
            elements.append("")

        # C059 - Street (4)
        elements.append("")

        # Address elements
        if party.postal_address:
            addr = party.postal_address
            elements.append({"components": [addr.street_name or ""]})
            elements.append(addr.city_name or "")
            elements.append(addr.country_subentity or "")
            elements.append(addr.postal_zone or "")
            elements.append(addr.country_code or "")
        else:
            elements.extend(["", "", "", "", ""])

        segments.append({"tag": "NAD", "elements": elements})

        return segments

    def _build_line_segments(self, line: ReceiptLine, line_num: int) -> list[dict]:
        """Build segment dicts for a line item."""
        segments = []

        # LIN - Line item
        lin_elements = [
            str(line_num),
            "",  # Action request
        ]

        # C212 - Item number
        if line.item.standard_item_identification:
            si = line.item.standard_item_identification
            lin_elements.append(
                {
                    "components": [
                        si.id.value,
                        "EN" if si.id.scheme_id == "EAN" else "SA",
                    ],
                }
            )
        elif line.item.sellers_item_identification:
            si = line.item.sellers_item_identification
            lin_elements.append({"components": [si.id.value, "SA"]})
        else:
            lin_elements.append("")

        segments.append({"tag": "LIN", "elements": lin_elements})

        # IMD - Item description
        if line.item.description:
            segments.append(
                {
                    "tag": "IMD",
                    "elements": [
                        "F",  # Free-form
                        "",
                        {"components": ["", "", "", line.item.description]},
                    ],
                }
            )

        # QTY - Received quantity
        segments.append(
            {
                "tag": "QTY",
                "elements": [
                    {
                        "components": [
                            "48",  # Received quantity
                            str(line.received_quantity.value),
                            line.received_quantity.unit_code,
                        ]
                    },
                ],
            }
        )

        # QTY - Short quantity
        if line.short_quantity:
            segments.append(
                {
                    "tag": "QTY",
                    "elements": [
                        {
                            "components": [
                                "119",  # Short quantity
                                str(line.short_quantity.value),
                                line.short_quantity.unit_code,
                            ]
                        },
                    ],
                }
            )

        # QTY - Rejected quantity
        if line.rejected_quantity:
            segments.append(
                {
                    "tag": "QTY",
                    "elements": [
                        {
                            "components": [
                                "124",  # Rejected quantity
                                str(line.rejected_quantity.value),
                                line.rejected_quantity.unit_code,
                            ]
                        },
                    ],
                }
            )

        return segments


def _find_all_segments_in_group(group: "SegmentGroupInstance", tag: str) -> "list[ParsedSegment]":
    """Find all segments with given tag in a group."""
    return [seg for seg in group.segments if seg.tag == tag]
