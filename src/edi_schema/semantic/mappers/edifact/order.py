"""
EDIFACT Order Mapper.

Maps between EDIFACT ORDERS and semantic Order model.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from ...models import (
    Address,
    Amount,
    Contact,
    CustomerParty,
    Identifier,
    Item,
    ItemIdentification,
    Order,
    OrderLine,
    Party,
    PartyIdentification,
    PartyName,
    Price,
    Quantity,
    SupplierParty,
)
from ..base import Format, SemanticMapper
from .utils import (
    find_all_segment_groups,
    find_all_segments,
    find_segment,
    find_segment_in_group,
    format_edifact_date,
    get_component_value,
    get_dtm_date,
    get_element_value,
    map_nad_party_qualifier,
    map_product_id_qualifier,
    parse_decimal,
)

if TYPE_CHECKING:
    from edi_schema.edifact.ast import (
        MessageInstance,
        ParsedSegment,
        SegmentGroupInstance,
    )


class EdifactOrderMapper(SemanticMapper[Order]):
    """
    Maps EDIFACT ORDERS to/from semantic Order model.

    EDIFACT ORDERS Structure:
    - UNH: Message header
    - BGM: Beginning of message (C002=document type, C106=document ID)
    - DTM: Date/time (137=document date, 171=reference date)
    - FTX: Free text
    - SG1: Reference segment group (RFF+DTM)
    - SG2: Party segment group (NAD+LOC+FII+SG3+SG4+SG5)
    - SG7: Currency segment group (CUX)
    - SG25: Line item segment group (LIN+PIA+IMD+MEA+QTY+DTM+MOA+FTX+SG26+SG29+SG30+SG35)
    - UNS: Section control
    - MOA: Monetary amounts summary
    - UNT: Message trailer
    """

    @property
    def semantic_type(self) -> type[Order]:
        return Order

    @property
    def source_format(self) -> Format:
        return Format.EDIFACT

    @property
    def transaction_id(self) -> str:
        return "ORDERS"

    def to_semantic(self, source: "MessageInstance") -> Order:
        """Convert EDIFACT ORDERS to semantic Order."""
        # Verify message type
        if source.message_type != "ORDERS":
            raise ValueError(f"Expected ORDERS, got {source.message_type}")

        content = source.content

        # Parse BGM segment for document ID
        bgm = find_segment(content, "BGM")
        if not bgm:
            raise ValueError("Missing required BGM segment")

        order_id = get_component_value(bgm, 2, 1) or ""  # C106 Document ID
        order_type = get_component_value(bgm, 1, 1)  # C002 Document type

        # Parse DTM for issue date (qualifier 137 = document date)
        issue_date = get_dtm_date(content, "137")
        if not issue_date:
            raise ValueError("Missing document date (DTM+137)")

        # Parse CUX for currency (if present, typically in SG7)
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

        # Create order
        order = Order(
            id=order_id,
            issue_date=issue_date,
            document_currency_code=currency,
            order_type_code=order_type,
        )

        # Parse FTX for notes
        for ftx in find_all_segments(content, "FTX"):
            text = get_element_value(ftx, 4)
            if text:
                order.note.append(text)

        # Parse parties from SG2 groups
        for sg2 in find_all_segment_groups(content, 2):
            nad = find_segment_in_group(sg2, "NAD")
            if nad:
                party_qualifier = get_element_value(nad, 1)
                party = self._build_party_from_nad(nad, sg2)

                role = map_nad_party_qualifier(party_qualifier or "")
                if role == "buyer":
                    order.buyer_customer_party = CustomerParty(party=party)
                elif role in ("supplier", "seller"):
                    order.seller_supplier_party = SupplierParty(party=party)

        # Parse line items from SG25/SG26 groups
        line_groups = find_all_segment_groups(content, 25)
        if not line_groups:
            # Try SG28 as alternative line item group
            line_groups = find_all_segment_groups(content, 28)

        for i, lin_group in enumerate(line_groups, 1):
            line = self._parse_line_group(lin_group, str(i), currency)
            order.order_lines.append(line)

        order.line_count = len(order.order_lines)

        # Source tracking
        order._source_format = "edifact"
        order._source_version = f"{source.version}{source.release}"

        return order

    def from_semantic(self, model: Order) -> dict:
        """
        Convert semantic Order to EDIFACT ORDERS structure.

        Returns a dictionary representation that can be used to generate
        EDIFACT segments.
        """
        segments = []

        # BGM - Beginning of message
        segments.append({
            "tag": "BGM",
            "elements": [
                {"value": model.order_type_code or "220"},  # Document type
                {"components": [model.id]},  # Document ID
                "9",  # Original
            ],
        })

        # DTM - Document date
        segments.append({
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
        })

        # CUX - Currency
        if model.document_currency_code:
            segments.append({
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
            })

        # NAD - Buyer
        if model.buyer_customer_party:
            segments.extend(
                self._build_nad_segments("BY", model.buyer_customer_party.party)
            )

        # NAD - Seller
        if model.seller_supplier_party:
            segments.extend(
                self._build_nad_segments("SU", model.seller_supplier_party.party)
            )

        # LIN groups - Line items
        for i, line in enumerate(model.order_lines, 1):
            segments.extend(self._build_line_segments(line, i, model.document_currency_code))

        # UNS - Section control
        segments.append({"tag": "UNS", "elements": ["S"]})

        # CNT - Control total (line count)
        segments.append({
            "tag": "CNT",
            "elements": [
                {"components": ["2", str(len(model.order_lines))]},
            ],
        })

        return {"message_type": "ORDERS", "segments": segments}

    def _build_party_from_nad(
        self, nad: "ParsedSegment", group: "SegmentGroupInstance"
    ) -> Party:
        """Build Party from NAD segment and its group."""
        party = Party()

        # Party identification from NAD C082
        party_id = get_component_value(nad, 2, 1)
        party_id_qualifier = get_component_value(nad, 2, 3)
        if party_id:
            party.party_identifications.append(
                PartyIdentification(
                    id=Identifier(value=party_id, scheme_id=party_id_qualifier)
                )
            )

        # Party name from NAD C080 or element 4
        party_name = get_component_value(nad, 3, 1)
        if not party_name:
            party_name = get_element_value(nad, 4)
        if party_name:
            party.party_names.append(PartyName(name=party_name))

        # Address from NAD elements 5-9
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

        # Contact from CTA/COM in nested group (SG3, SG4, SG5)
        # Look for CTA segment
        for child in group.children:
            cta = find_segment_in_group(child, "CTA")
            if cta:
                contact_name = get_component_value(cta, 2, 2)
                com = find_segment_in_group(child, "COM")
                phone = None
                email = None
                if com:
                    comm_number = get_component_value(com, 1, 1)
                    comm_type = get_component_value(com, 1, 2)
                    if comm_type == "TE":
                        phone = comm_number
                    elif comm_type == "EM":
                        email = comm_number

                if contact_name or phone or email:
                    party.contact = Contact(
                        name=contact_name,
                        telephone=phone,
                        electronic_mail=email,
                    )
                break

        return party

    def _parse_line_group(
        self,
        group: "SegmentGroupInstance",
        line_id: str,
        currency: str,
    ) -> OrderLine:
        """Parse a line item group into OrderLine."""
        lin = find_segment_in_group(group, "LIN")

        # Line ID from LIN
        line_number = get_element_value(lin, 1) if lin else line_id

        # Item from LIN C212 and PIA
        item = self._build_item_from_group(group)

        # Quantity from QTY
        qty = Quantity(value=Decimal("1"), unit_code="EA")
        for qty_seg in find_all_segments_in_group(group, "QTY"):
            qty_qualifier = get_component_value(qty_seg, 1, 1)
            if qty_qualifier in ("21", "47"):  # Ordered qty or invoiced qty
                qty_value = get_component_value(qty_seg, 1, 2)
                qty_unit = get_component_value(qty_seg, 1, 3)
                if qty_value:
                    qty = Quantity(
                        value=parse_decimal(qty_value) or Decimal("1"),
                        unit_code=qty_unit or "EA",
                    )
                break

        line = OrderLine(
            id=line_number or line_id,
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
                break

        # Amount from MOA
        for moa in find_all_segments_in_group(group, "MOA"):
            moa_qualifier = get_component_value(moa, 1, 1)
            if moa_qualifier in ("203", "66"):  # Line item amount
                amount_val = get_component_value(moa, 1, 2)
                if amount_val:
                    line.line_extension_amount = Amount(
                        value=parse_decimal(amount_val) or Decimal("0"),
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
                ident = ItemIdentification(
                    id=Identifier(value=item_id, scheme_id=scheme)
                )
                if field_type == "standard":
                    item.standard_item_identification = ident
                elif field_type == "sellers":
                    item.sellers_item_identification = ident
                elif field_type == "buyers":
                    item.buyers_item_identification = ident

        # Additional IDs from PIA
        for pia in find_all_segments_in_group(group, "PIA"):
            pia_id = get_component_value(pia, 2, 1)
            pia_type = get_component_value(pia, 2, 2)
            if pia_id:
                field_type, scheme = map_product_id_qualifier(pia_type or "")
                ident = ItemIdentification(
                    id=Identifier(value=pia_id, scheme_id=scheme)
                )
                if field_type == "standard" and not item.standard_item_identification:
                    item.standard_item_identification = ident
                elif field_type == "sellers" and not item.sellers_item_identification:
                    item.sellers_item_identification = ident
                elif field_type == "buyers" and not item.buyers_item_identification:
                    item.buyers_item_identification = ident

        # Description from IMD
        for imd in find_all_segments_in_group(group, "IMD"):
            description = get_component_value(imd, 3, 4)
            if not description:
                description = get_component_value(imd, 3, 5)
            if description:
                item.description = description
                break

        return item

    def _build_nad_segments(
        self, qualifier: str, party: Party
    ) -> list[dict]:
        """Build NAD segment(s) for a party."""
        segments = []

        elements = [qualifier]

        # C082 - Party identification
        if party.party_identifications:
            pi = party.party_identifications[0]
            elements.append({
                "components": [
                    pi.id.value,
                    "",
                    pi.id.scheme_id or "92",  # Assigned by buyer
                ],
            })
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

    def _build_line_segments(
        self, line: OrderLine, line_num: int, currency: str
    ) -> list[dict]:
        """Build segment dicts for a line item."""
        segments = []

        # LIN - Line item
        lin_elements = [
            str(line_num),  # Line number
            "",  # Action request
        ]

        # C212 - Item number
        if line.item.standard_item_identification:
            si = line.item.standard_item_identification
            lin_elements.append({
                "components": [
                    si.id.value,
                    "EN" if si.id.scheme_id == "EAN" else "SA",
                ],
            })
        elif line.item.sellers_item_identification:
            si = line.item.sellers_item_identification
            lin_elements.append({
                "components": [si.id.value, "SA"],
            })
        else:
            lin_elements.append("")

        segments.append({"tag": "LIN", "elements": lin_elements})

        # IMD - Item description
        if line.item.description:
            segments.append({
                "tag": "IMD",
                "elements": [
                    "F",  # Free-form
                    "",
                    {"components": ["", "", "", line.item.description]},
                ],
            })

        # QTY - Quantity
        segments.append({
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
        })

        # PRI - Price
        if line.price:
            segments.append({
                "tag": "PRI",
                "elements": [
                    {
                        "components": [
                            "AAA",  # Calculation net
                            str(line.price.price_amount.value),
                        ]
                    },
                ],
            })

        return segments


def find_all_segments_in_group(
    group: "SegmentGroupInstance", tag: str
) -> "list[ParsedSegment]":
    """Find all segments with given tag in a group."""
    return [seg for seg in group.segments if seg.tag == tag]
