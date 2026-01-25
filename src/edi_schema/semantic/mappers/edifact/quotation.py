"""
EDIFACT QUOTES Quotation Mapper.

Maps between EDIFACT QUOTES and semantic Quotation model.
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


class EdifactQuotationMapper(SemanticMapper[Quotation]):
    """
    Maps EDIFACT QUOTES to/from semantic Quotation model.

    EDIFACT QUOTES Structure:
    - BGM: Beginning of message
    - DTM: Date/time/period
    - CUX: Currencies
    - SG2 (NAD): Name and address (parties)
    - SG26 (LIN): Line item group
      - LIN: Line item
      - PIA: Additional product id
      - IMD: Item description
      - QTY: Quantity
      - PRI: Price details
    """

    @property
    def semantic_type(self) -> type[Quotation]:
        return Quotation

    @property
    def source_format(self) -> Format:
        return Format.EDIFACT

    @property
    def transaction_id(self) -> str:
        return "QUOTES"

    def to_semantic(self, source: "MessageInstance") -> Quotation:
        """Convert EDIFACT QUOTES to semantic Quotation."""
        if source.message_type != "QUOTES":
            raise ValueError(f"Expected QUOTES, got {source.message_type}")

        content = source.content

        # Extract BGM segment
        bgm = find_segment(content, "BGM")
        if not bgm:
            raise ValueError("Missing required BGM segment")

        # Parse BGM fields
        quote_id = get_component_value(bgm, 2, 1) or ""  # C106 Document ID

        # Extract dates from DTM (qualifier 137 = document date)
        issue_date = get_dtm_date(content, "137")
        if not issue_date:
            raise ValueError("Missing document date (DTM+137)")

        # Extract currency from CUX (typically in SG7)
        currency = "USD"
        for sg7 in find_all_segment_groups(content, 7):
            cux = find_segment_in_group(sg7, "CUX")
            if cux:
                currency = get_component_value(cux, 1, 2) or "USD"
                break

        # Also check top-level CUX
        cux = find_segment(content, "CUX")
        if cux:
            currency = get_component_value(cux, 1, 2) or currency

        # Create quotation
        quotation = Quotation(
            id=quote_id,
            issue_date=issue_date,
            document_currency_code=currency,
            quotation_lines=[],
        )

        # Parse parties from SG2 groups
        for sg2 in find_all_segment_groups(content, 2):
            nad = find_segment_in_group(sg2, "NAD")
            if nad:
                self._parse_party(quotation, nad)

        # Parse line items from SG25 or SG26 groups
        line_groups = find_all_segment_groups(content, 25)
        if not line_groups:
            line_groups = find_all_segment_groups(content, 26)
        if not line_groups:
            line_groups = find_all_segment_groups(content, 28)

        for i, lin_group in enumerate(line_groups, 1):
            line = self._parse_line_group(lin_group, i, currency)
            if line:
                quotation.quotation_lines.append(line)

        quotation.line_count = len(quotation.quotation_lines)

        quotation._source_format = "edifact"
        quotation._source_version = f"{source.version}{source.release}"
        return quotation

    def _parse_party(self, quotation: Quotation, nad: "ParsedSegment") -> None:
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

        if party_qualifier == "SU":  # Supplier
            quotation.seller_supplier_party = SupplierParty(party=party)
        elif party_qualifier == "BY":  # Buyer
            quotation.buyer_customer_party = CustomerParty(party=party)

    def _parse_line_group(
        self, group: "SegmentGroupInstance", line_num: int, currency: str
    ) -> QuotationLine | None:
        """Parse LIN group into QuotationLine."""
        lin = find_segment_in_group(group, "LIN")
        if not lin:
            return None

        line_id = get_element_value(lin, 1) or str(line_num)

        # Item from LIN C212 and PIA
        item = self._build_item_from_group(group)

        # Quantity from QTY
        qty = Quantity(value=Decimal("1"), unit_code="EA")
        for qty_seg in _find_all_segments_in_group(group, "QTY"):
            qty_qualifier = get_component_value(qty_seg, 1, 1)
            if qty_qualifier in ("21", "47"):  # Ordered/invoiced qty
                qty_value = get_component_value(qty_seg, 1, 2)
                qty_unit = get_component_value(qty_seg, 1, 3)
                if qty_value:
                    qty = Quantity(
                        value=parse_decimal(qty_value) or Decimal("1"),
                        unit_code=qty_unit or "EA",
                    )
                break

        line = QuotationLine(
            id=line_id,
            quantity=qty,
            item=item,
        )

        # Price from nested PRI group (SG29)
        for child in group.children:
            if child.group_number == 29:
                pri = find_segment_in_group(child, "PRI")
                if pri:
                    price_val = get_component_value(pri, 1, 2)
                    if price_val:
                        line.price = Price(
                            price_amount=Amount(
                                value=parse_decimal(price_val) or Decimal("0"),
                                currency=currency,
                            )
                        )
                        # Calculate line extension
                        line.line_extension_amount = Amount(
                            value=qty.value * (parse_decimal(price_val) or Decimal("0")),
                            currency=currency,
                        )
                break

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

    def from_semantic(self, model: Quotation) -> dict:
        """Convert semantic Quotation to EDIFACT QUOTES structure."""
        segments = []

        # BGM - Beginning of message
        segments.append(
            {
                "tag": "BGM",
                "elements": [
                    {"value": "310"},  # Document type - Quotation
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

        # CUX - Currency
        if model.document_currency_code:
            segments.append(
                {
                    "tag": "CUX",
                    "elements": [
                        {
                            "components": [
                                "2",  # Reference currency
                                model.document_currency_code,
                                "4",  # Invoicing currency
                            ]
                        },
                    ],
                }
            )

        # NAD - Seller
        if model.seller_supplier_party:
            segments.extend(self._build_nad_segments("SU", model.seller_supplier_party.party))

        # NAD - Buyer
        if model.buyer_customer_party:
            segments.extend(self._build_nad_segments("BY", model.buyer_customer_party.party))

        # LIN groups - Line items
        for i, line in enumerate(model.quotation_lines, 1):
            segments.extend(self._build_line_segments(line, i, model.document_currency_code))

        # UNS - Section control
        segments.append({"tag": "UNS", "elements": ["S"]})

        # CNT - Control total
        segments.append(
            {
                "tag": "CNT",
                "elements": [
                    {"components": ["2", str(len(model.quotation_lines))]},
                ],
            }
        )

        return {"message_type": "QUOTES", "segments": segments}

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

    def _build_line_segments(self, line: QuotationLine, line_num: int, currency: str) -> list[dict]:
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

        # QTY - Quantity
        segments.append(
            {
                "tag": "QTY",
                "elements": [
                    {
                        "components": [
                            "21",  # Ordered quantity
                            str(line.quantity.value),
                            line.quantity.unit_code,
                        ]
                    },
                ],
            }
        )

        # PRI - Price
        if line.price:
            segments.append(
                {
                    "tag": "PRI",
                    "elements": [
                        {
                            "components": [
                                "AAA",  # Calculation net
                                str(line.price.price_amount.value),
                            ]
                        },
                    ],
                }
            )

        return segments


def _find_all_segments_in_group(group: "SegmentGroupInstance", tag: str) -> "list[ParsedSegment]":
    """Find all segments with given tag in a group."""
    return [seg for seg in group.segments if seg.tag == tag]
