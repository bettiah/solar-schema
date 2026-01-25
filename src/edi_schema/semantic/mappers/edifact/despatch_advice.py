"""
EDIFACT DespatchAdvice Mapper.

Maps between EDIFACT DESADV and semantic DespatchAdvice model.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from ...models import (
    Address,
    Contact,
    CustomerParty,
    DespatchAdvice,
    DespatchLine,
    Identifier,
    Item,
    ItemIdentification,
    OrderReference,
    Party,
    PartyIdentification,
    PartyName,
    Quantity,
    Shipment,
    ShipmentStage,
    SupplierParty,
    TransportHandlingUnit,
)
from ..base import Format, SemanticMapper
from .utils import (
    find_all_segment_groups,
    find_all_segments_in_group,
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


class EdifactDespatchAdviceMapper(SemanticMapper[DespatchAdvice]):
    """
    Maps EDIFACT DESADV to/from semantic DespatchAdvice model.

    EDIFACT DESADV Structure:
    - UNH: Message header
    - BGM: Beginning of message (document type/ID)
    - DTM: Date/time (137=document date, 11=despatch date)
    - ALI: Additional info
    - MEA: Measurements
    - MOA: Monetary amounts
    - SG1: Reference segment group (RFF+DTM)
    - SG2: Party segment group (NAD+LOC+SG3+SG4+SG5)
    - SG5: Contact (CTA+COM)
    - SG10: Transport details (TDT+SG11+SG12)
    - SG15: Handling unit (PAC+MEA+QTY+SG17+SG18)
    - SG17: Package identification (PCI+RFF+DTM+GIN)
    - SG25: Line items (CPS+FTX+SG26)
    - SG26: Line item detail (LIN+PIA+IMD+MEA+QTY+ALI+DTM+FTX+SG27+SG30+SG33)
    - UNT: Message trailer
    """

    @property
    def semantic_type(self) -> type[DespatchAdvice]:
        return DespatchAdvice

    @property
    def source_format(self) -> Format:
        return Format.EDIFACT

    @property
    def transaction_id(self) -> str:
        return "DESADV"

    def to_semantic(self, source: "MessageInstance") -> DespatchAdvice:
        """Convert EDIFACT DESADV to semantic DespatchAdvice."""
        if source.message_type != "DESADV":
            raise ValueError(f"Expected DESADV, got {source.message_type}")

        content = source.content

        # Parse BGM segment for document ID
        bgm = find_segment(content, "BGM")
        if not bgm:
            raise ValueError("Missing required BGM segment")

        doc_id = get_component_value(bgm, 2, 1) or ""
        doc_type = get_component_value(bgm, 1, 1)

        # Parse DTM for issue date
        issue_date = get_dtm_date(content, "137")
        if not issue_date:
            raise ValueError("Missing document date (DTM+137)")

        # Create despatch advice
        despatch = DespatchAdvice(
            id=doc_id,
            issue_date=issue_date,
            despatch_advice_type_code=doc_type,
        )

        # Parse despatch date (DTM qualifier 11)
        despatch_date = get_dtm_date(content, "11")

        # Parse references from SG1 groups
        for sg1 in find_all_segment_groups(content, 1):
            rff = find_segment_in_group(sg1, "RFF")
            if rff:
                ref_qualifier = get_component_value(rff, 1, 1)
                ref_value = get_component_value(rff, 1, 2)
                if ref_qualifier == "ON" and ref_value:
                    despatch.order_reference = OrderReference(id=ref_value)

        # Parse parties from SG2 groups
        for sg2 in find_all_segment_groups(content, 2):
            nad = find_segment_in_group(sg2, "NAD")
            if nad:
                party_qualifier = get_element_value(nad, 1)
                party = self._build_party_from_nad(nad, sg2)

                role = map_nad_party_qualifier(party_qualifier or "")
                if role in ("buyer", "consignee"):
                    despatch.delivery_customer_party = CustomerParty(party=party)
                elif role in ("supplier", "seller", "ship_from"):
                    despatch.despatch_supplier_party = SupplierParty(party=party)

        # Build shipment from TDT, PAC, etc.
        despatch.shipment = self._build_shipment(content, despatch_date)

        # Parse line items from SG25/SG26 groups
        # DESADV uses CPS (consignment packing sequence) with nested LIN
        for sg25 in find_all_segment_groups(content, 25):
            # Look for nested SG26 with line items
            for sg26 in find_all_child_groups(sg25, 26):
                line = self._parse_line_group(sg26)
                despatch.despatch_lines.append(line)

        # Also try direct SG17 line items (simpler structure)
        if not despatch.despatch_lines:
            line_groups = find_all_segment_groups(content, 17)
            for i, group in enumerate(line_groups, 1):
                line = self._parse_line_group(group, str(i))
                despatch.despatch_lines.append(line)

        # Source tracking
        despatch._source_format = "edifact"
        despatch._source_version = f"{source.version}{source.release}"

        return despatch

    def from_semantic(self, model: DespatchAdvice) -> dict:
        """Convert semantic DespatchAdvice to EDIFACT DESADV structure."""
        segments = []

        # BGM - Beginning of message
        segments.append(
            {
                "tag": "BGM",
                "elements": [
                    {"value": model.despatch_advice_type_code or "351"},
                    {"components": [model.id]},
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
                            "137",
                            format_edifact_date(model.issue_date),
                            "102",
                        ]
                    },
                ],
            }
        )

        # RFF - Order reference
        if model.order_references:
            order_ref = model.order_references[0]
            segments.append(
                {
                    "tag": "RFF",
                    "elements": [
                        {"components": ["ON", order_ref.id]},
                    ],
                }
            )

        # NAD - Despatch party (supplier)
        if model.despatch_supplier_party:
            segments.extend(self._build_nad_segments("SF", model.despatch_supplier_party.party))

        # NAD - Delivery party (customer)
        if model.delivery_customer_party:
            segments.extend(self._build_nad_segments("UC", model.delivery_customer_party.party))

        # TDT - Transport details
        if model.shipment and model.shipment.shipment_stages:
            for stage in model.shipment.shipment_stages:
                segments.extend(self._build_transport_segments(stage))

        # PAC - Package info from transport handling units
        if model.shipment and model.shipment.transport_handling_units:
            for thu in model.shipment.transport_handling_units:
                segments.extend(self._build_package_segments(thu))

        # CPS + LIN groups - Line items
        for i, line in enumerate(model.despatch_lines, 1):
            # CPS - Consignment packing sequence
            segments.append(
                {
                    "tag": "CPS",
                    "elements": [str(i)],
                }
            )
            segments.extend(self._build_line_segments(line, i))

        # CNT - Control total
        segments.append(
            {
                "tag": "CNT",
                "elements": [
                    {"components": ["2", str(len(model.despatch_lines))]},
                ],
            }
        )

        return {"message_type": "DESADV", "segments": segments}

    def _build_party_from_nad(self, nad: "ParsedSegment", group: "SegmentGroupInstance") -> Party:
        """Build Party from NAD segment and its group."""
        party = Party()

        # Party identification from NAD C082
        party_id = get_component_value(nad, 2, 1)
        party_id_qualifier = get_component_value(nad, 2, 3)
        if party_id:
            party.party_identifications.append(
                PartyIdentification(id=Identifier(value=party_id, scheme_id=party_id_qualifier))
            )

        # Party name from NAD C080
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

        # Contact from CTA/COM in nested groups
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

    def _build_shipment(self, content: list, despatch_date) -> Shipment:
        """Build Shipment from TDT, PAC, and related segments."""
        shipment = Shipment()

        if despatch_date:
            shipment.actual_despatch_date = despatch_date

        # Parse TDT for transport details (in SG10)
        for sg10 in find_all_segment_groups(content, 10):
            tdt = find_segment_in_group(sg10, "TDT")
            if tdt:
                stage = ShipmentStage()

                # Transport stage qualifier
                stage_qual = get_element_value(tdt, 1)
                if stage_qual:
                    stage.transport_mode_code = stage_qual

                # Mode of transport (C220)
                mode = get_component_value(tdt, 3, 1)
                if mode:
                    stage.transport_mode_code = mode

                # Carrier ID (C040)
                carrier_id = get_component_value(tdt, 5, 1)
                if carrier_id:
                    stage.carrier_party = Party(
                        party_identifications=[PartyIdentification(id=Identifier(value=carrier_id))]
                    )

                # Transport means (C228)
                transport_id = get_component_value(tdt, 8, 1)
                if transport_id:
                    stage.transport_means_id = transport_id

                shipment.shipment_stages.append(stage)
                break

        # Parse PAC for package info (in SG15)
        for sg15 in find_all_segment_groups(content, 15):
            pac = find_segment_in_group(sg15, "PAC")
            if pac:
                thu = TransportHandlingUnit()

                # Number of packages
                num_packages = get_element_value(pac, 1)
                if num_packages:
                    thu.total_package_quantity = parse_decimal(num_packages)

                # Package type (C202)
                pkg_type = get_component_value(pac, 2, 1)
                if pkg_type:
                    thu.transport_handling_unit_type_code = pkg_type

                # Look for PCI (package identification) in nested SG17
                for sg17 in find_all_child_groups(sg15, 17):
                    pci = find_segment_in_group(sg17, "PCI")
                    if pci:
                        # Shipping marks in element 1 could be captured here
                        pass

                    # GIN for package identifiers
                    gin = find_segment_in_group(sg17, "GIN")
                    if gin:
                        id_val = get_component_value(gin, 2, 1)
                        if id_val:
                            thu.id = id_val

                shipment.transport_handling_units.append(thu)

        return shipment

    def _parse_line_group(
        self,
        group: "SegmentGroupInstance",
        line_id: str = "1",
    ) -> DespatchLine:
        """Parse a line item group into DespatchLine."""
        lin = find_segment_in_group(group, "LIN")

        # Line ID from LIN
        line_number = get_element_value(lin, 1) if lin else line_id

        # Item from LIN C212 and PIA
        item = self._build_item_from_group(group)

        # Quantity from QTY
        qty = Quantity(value=Decimal("1"), unit_code="EA")
        for qty_seg in find_all_segments_in_group(group, "QTY"):
            qty_qualifier = get_component_value(qty_seg, 1, 1)
            if qty_qualifier in ("12", "21"):  # Despatch qty or ordered qty
                qty_value = get_component_value(qty_seg, 1, 2)
                qty_unit = get_component_value(qty_seg, 1, 3)
                if qty_value:
                    qty = Quantity(
                        value=parse_decimal(qty_value) or Decimal("1"),
                        unit_code=qty_unit or "EA",
                    )
                break

        return DespatchLine(
            id=line_number or line_id,
            delivered_quantity=qty,
            item=item,
        )

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
        for pia in find_all_segments_in_group(group, "PIA"):
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
        for imd in find_all_segments_in_group(group, "IMD"):
            description = get_component_value(imd, 3, 4)
            if not description:
                description = get_component_value(imd, 3, 5)
            if description:
                item.description = description
                break

        return item

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

    def _build_transport_segments(self, stage: ShipmentStage) -> list[dict]:
        """Build TDT segment for transport stage."""
        segments = []

        elements = ["20"]  # Main carriage

        # C220 - Mode of transport
        if stage.transport_mode_code:
            elements.append("")  # Conveyance ref
            elements.append({"components": [stage.transport_mode_code]})
        else:
            elements.extend(["", ""])

        # C040 - Carrier
        if stage.carrier_party and stage.carrier_party.party_identifications:
            carrier_id = stage.carrier_party.party_identifications[0].id.value
            elements.extend(["", {"components": [carrier_id]}])
        else:
            elements.extend(["", ""])

        # Transit info (skipped)
        elements.extend(["", ""])

        # C228 - Transport means
        if stage.transport_means_id:
            elements.append({"components": [stage.transport_means_id]})

        segments.append({"tag": "TDT", "elements": elements})

        return segments

    def _build_package_segments(self, thu: TransportHandlingUnit) -> list[dict]:
        """Build PAC segment for transport handling unit."""
        segments = []

        elements = []

        # Number of packages
        if thu.total_package_quantity:
            elements.append(str(thu.total_package_quantity))
        else:
            elements.append("1")

        # C531 - Packaging details
        elements.append("")

        # C202 - Package type
        if thu.transport_handling_unit_type_code:
            elements.append({"components": [thu.transport_handling_unit_type_code]})

        segments.append({"tag": "PAC", "elements": elements})

        # PCI for package identification
        if thu.id:
            segments.append(
                {
                    "tag": "GIN",
                    "elements": [
                        "BJ",  # Serial shipping container code
                        {"components": [thu.id]},
                    ],
                }
            )

        return segments

    def _build_line_segments(self, line: DespatchLine, line_num: int) -> list[dict]:
        """Build segment dicts for a line item."""
        segments = []

        # LIN - Line item
        lin_elements = [
            str(line_num),
            "",
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
            lin_elements.append(
                {
                    "components": [si.id.value, "SA"],
                }
            )
        else:
            lin_elements.append("")

        segments.append({"tag": "LIN", "elements": lin_elements})

        # IMD - Item description
        if line.item.description:
            segments.append(
                {
                    "tag": "IMD",
                    "elements": [
                        "F",
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
                            "12",  # Despatch quantity
                            str(line.delivered_quantity.value),
                            line.delivered_quantity.unit_code,
                        ]
                    },
                ],
            }
        )

        return segments


def find_all_child_groups(
    group: "SegmentGroupInstance", group_number: int
) -> "list[SegmentGroupInstance]":
    """Find all child groups with given group number."""
    return [child for child in group.children if child.group_number == group_number]
