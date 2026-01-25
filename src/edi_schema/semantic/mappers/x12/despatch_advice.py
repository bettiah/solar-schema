"""
X12 856 ASN (Advance Ship Notice) Mapper.

Maps between X12 856 ASN and semantic DespatchAdvice model.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from ...models import (
    Address,
    CustomerParty,
    DespatchAdvice,
    DespatchLine,
    Identifier,
    Item,
    ItemIdentification,
    Measure,
    OrderLineReference,
    OrderReference,
    Party,
    PartyIdentification,
    PartyName,
    Quantity,
    Shipment,
    ShipmentStage,
    SupplierParty,
    TransportEquipment,
    TransportHandlingUnit,
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
    parse_x12_time,
)

if TYPE_CHECKING:
    from edi_schema.x12.ast import (
        HLNode,
        LoopInstance,
        ParsedSegment,
        TransactionSetInstance,
    )


class X12DespatchAdviceMapper(SemanticMapper[DespatchAdvice]):
    """
    Maps X12 856 ASN to/from semantic DespatchAdvice model.

    X12 856 uses HL (Hierarchical Level) structure:
    - S (Shipment): Top level - carrier, ship dates, totals
    - O (Order): Order reference level
    - P (Pack): Packing unit (pallet, carton)
    - I (Item): Individual line items

    Structure:
    - BSN: Beginning Segment (ASN number, date, time)
    - DTM: Date/Time References
    - HL Loop: Hierarchical structure
      - S Level: TD1, TD5, TD3, N1 (SF/ST), REF
      - O Level: PRF (PO reference)
      - P Level: MAN (marks/numbers), PO4 (packaging)
      - I Level: LIN, SN1, PID
    - CTT: Transaction Totals
    """

    @property
    def semantic_type(self) -> type[DespatchAdvice]:
        return DespatchAdvice

    @property
    def source_format(self) -> Format:
        return Format.X12

    @property
    def transaction_id(self) -> str:
        return "856"

    def to_semantic(self, source: "TransactionSetInstance") -> DespatchAdvice:
        """Convert X12 856 to semantic DespatchAdvice."""
        if source.transaction_id != "856":
            raise ValueError(f"Expected 856, got {source.transaction_id}")

        content = source.content

        # Extract BSN segment (required)
        bsn = find_segment(content, "BSN")
        if not bsn:
            raise ValueError("Missing required BSN segment")

        # Parse BSN fields
        shipment_id = get_element_value(bsn, 2) or ""
        issue_date = parse_x12_date(get_element_value(bsn, 3))
        issue_time = parse_x12_time(get_element_value(bsn, 4))

        if not issue_date:
            raise ValueError("Missing or invalid date in BSN03")

        # Create base despatch advice
        asn = DespatchAdvice(
            id=shipment_id,
            issue_date=issue_date,
            issue_time=issue_time,
        )

        # Process HL hierarchy if available
        if source.hl_root:
            self._process_hl_tree(source.hl_root, asn)
        else:
            # Fall back to loop-based processing
            self._process_loops(content, asn)

        # Extract CTT for line count
        ctt = find_segment(content, "CTT")
        if ctt:
            count_str = get_element_value(ctt, 1)
            if count_str:
                asn.line_count = int(count_str)

        # Set source tracking
        asn._source_format = "x12"
        asn._source_version = "005010"

        return asn

    def from_semantic(self, model: DespatchAdvice) -> object:
        """Convert semantic DespatchAdvice to X12 856."""
        segments = []

        # BSN segment
        segments.append(
            {
                "tag": "BSN",
                "elements": [
                    "00",  # BSN01 - Purpose Code (Original)
                    model.id,
                    model.issue_date.strftime("%Y%m%d"),
                    model.issue_time.strftime("%H%M") if model.issue_time else "",
                    "0001",  # BSN05 - Hierarchical Structure Code
                ],
            }
        )

        # Build HL hierarchy
        hl_counter = [1]  # Mutable counter for HL IDs

        # Shipment level
        if model.shipment:
            segments.extend(self._build_shipment_hl(model, hl_counter))

        # Order references and lines
        for order_ref in model.order_references:
            segments.extend(self._build_order_hl(order_ref, model.despatch_lines, hl_counter))

        # CTT segment
        segments.append(
            {
                "tag": "CTT",
                "elements": [str(len(model.despatch_lines))],
            }
        )

        return segments

    def _process_hl_tree(self, hl_root: "HLNode", asn: DespatchAdvice) -> None:
        """Process the HL hierarchy tree."""
        # Process all root HL nodes
        self._process_hl_node(hl_root, asn, None)

        # Also process children recursively
        for child in hl_root.children:
            self._process_hl_node(child, asn, hl_root)

    def _process_hl_node(
        self, node: "HLNode", asn: DespatchAdvice, parent: "HLNode | None"
    ) -> None:
        """Process a single HL node and its children."""
        level_code = node.level_code

        if level_code == "S":
            # Shipment level
            self._process_shipment_hl(node, asn)
        elif level_code == "O":
            # Order level
            self._process_order_hl(node, asn)
        elif level_code == "P":
            # Pack level - add to transport handling units
            self._process_pack_hl(node, asn)
        elif level_code == "I":
            # Item level
            self._process_item_hl(node, asn, parent)

        # Process children
        for child in node.children:
            self._process_hl_node(child, asn, node)

    def _process_shipment_hl(self, node: "HLNode", asn: DespatchAdvice) -> None:
        """Process shipment-level HL node."""
        shipment = Shipment(id=asn.id)

        for seg in node.segments:
            tag = seg.tag

            if tag == "TD1":
                # Carrier details - packaging
                lading_qty = parse_decimal(get_element_value(seg, 2))
                weight = parse_decimal(get_element_value(seg, 7))
                weight_unit = get_element_value(seg, 8)

                if lading_qty:
                    shipment.total_transport_handling_unit_quantity = int(lading_qty)
                if weight and weight_unit:
                    shipment.gross_weight_measure = Measure(value=weight, unit_code=weight_unit)

            elif tag == "TD5":
                # Carrier details - transport
                carrier_id = get_element_value(seg, 3)
                transport_mode = get_element_value(seg, 4)

                if carrier_id:
                    shipment.carrier_party = Party(
                        party_identifications=[
                            PartyIdentification(id=Identifier(value=carrier_id, scheme_id="SCAC"))
                        ]
                    )

                if transport_mode:
                    stage = ShipmentStage(transport_mode_code=transport_mode)
                    shipment.shipment_stages.append(stage)

            elif tag == "TD3":
                # Equipment details
                equip_type = get_element_value(seg, 1)
                equip_number = get_element_value(seg, 3)

                if equip_type or equip_number:
                    equip = TransportEquipment(
                        transport_equipment_type_code=equip_type,
                        id=equip_number,
                    )
                    # Add to handling units if present
                    if shipment.transport_handling_units:
                        shipment.transport_handling_units[0].transport_equipment.append(equip)

            elif tag == "N1":
                party_code = get_element_value(seg, 1)
                party = self._build_party_from_segments(node.segments, seg)

                if party_code == "SF":
                    shipment.shipper_party = party
                    asn.despatch_supplier_party = SupplierParty(party=party)
                elif party_code == "ST":
                    shipment.consignee_party = party
                    asn.delivery_customer_party = CustomerParty(party=party)

        asn.shipment = shipment

    def _process_order_hl(self, node: "HLNode", asn: DespatchAdvice) -> None:
        """Process order-level HL node."""
        for seg in node.segments:
            if seg.tag == "PRF":
                po_number = get_element_value(seg, 1)
                po_date = parse_x12_date(get_element_value(seg, 4))

                if po_number:
                    order_ref = OrderReference(id=po_number, issue_date=po_date)
                    asn.order_references.append(order_ref)

    def _process_pack_hl(self, node: "HLNode", asn: DespatchAdvice) -> None:
        """Process pack-level HL node."""
        thu = TransportHandlingUnit()

        for seg in node.segments:
            if seg.tag == "MAN":
                # Marks and numbers (e.g., SSCC barcode)
                qualifier = get_element_value(seg, 1)
                value = get_element_value(seg, 2)

                if qualifier == "GM" and value:  # SSCC-18
                    thu.id = value
                elif value:
                    thu.id = value

            elif seg.tag == "PO4":
                # Item physical details
                pack_qty = parse_decimal(get_element_value(seg, 1))
                if pack_qty:
                    thu.total_goods_item_quantity = int(pack_qty)

        if thu.id or thu.total_goods_item_quantity:
            if asn.shipment:
                asn.shipment.transport_handling_units.append(thu)

    def _process_item_hl(
        self, node: "HLNode", asn: DespatchAdvice, parent: "HLNode | None"
    ) -> None:
        """Process item-level HL node."""
        line = DespatchLine(
            id=str(len(asn.despatch_lines) + 1),
            delivered_quantity=Quantity(value=Decimal("0"), unit_code="EA"),
            item=Item(),
        )

        for seg in node.segments:
            tag = seg.tag

            if tag == "LIN":
                # Line identification
                line.id = get_element_value(seg, 1) or line.id
                self._parse_lin_product_ids(seg, line.item)

            elif tag == "SN1":
                # Item detail (shipment)
                qty = parse_decimal(get_element_value(seg, 2))
                unit = get_element_value(seg, 3)

                if qty:
                    line.delivered_quantity = Quantity(value=qty, unit_code=unit or "EA")

            elif tag == "PID":
                line.item.description = get_element_value(seg, 5)

            elif tag == "PRF":
                # Line-level PO reference
                po_number = get_element_value(seg, 1)
                line_id = get_element_value(seg, 5)  # PO line number

                if po_number:
                    line.order_line_reference = OrderLineReference(
                        line_id=line_id or "1",
                        order_reference=OrderReference(id=po_number),
                    )

        asn.despatch_lines.append(line)

    def _parse_lin_product_ids(self, lin: "ParsedSegment", item: Item) -> None:
        """Parse LIN segment product IDs."""
        # LIN02 is qualifier, LIN03 is value
        # Can repeat in pairs (LIN04/05, LIN06/07, etc.)
        for i in range(2, 31, 2):
            qualifier = get_element_value(lin, i)
            value = get_element_value(lin, i + 1)

            if not qualifier or not value:
                break

            field_type, scheme = map_product_id_qualifier(qualifier)
            item_id = ItemIdentification(id=Identifier(value=value, scheme_id=scheme))

            if field_type == "standard":
                item.standard_item_identification = item_id
            elif field_type == "sellers":
                item.sellers_item_identification = item_id
            elif field_type == "buyers":
                item.buyers_item_identification = item_id

    def _process_loops(self, content: list, asn: DespatchAdvice) -> None:
        """Fallback processing using loop structure instead of HL tree."""
        # This handles cases where HL parsing isn't available
        n1_loops = find_all_loops(content, "N1")
        for n1_loop in n1_loops:
            n1 = find_segment_in_loop(n1_loop, "N1")
            if not n1:
                continue

            party_code = get_element_value(n1, 1)
            party = self._build_party_from_n1_loop(n1_loop)

            if party_code == "SF":
                asn.despatch_supplier_party = SupplierParty(party=party)
            elif party_code == "ST":
                asn.delivery_customer_party = CustomerParty(party=party)

    def _build_party_from_segments(
        self, segments: list["ParsedSegment"], n1_seg: "ParsedSegment"
    ) -> Party:
        """Build party from N1 and related segments in a list."""
        party = Party()

        # N1 segment
        name = get_element_value(n1_seg, 2)
        if name:
            party.party_names.append(PartyName(name=name))

        id_qualifier = get_element_value(n1_seg, 3)
        id_value = get_element_value(n1_seg, 4)
        if id_value:
            scheme = map_id_qualifier(id_qualifier) if id_qualifier else None
            party.party_identifications.append(
                PartyIdentification(id=Identifier(value=id_value, scheme_id=scheme))
            )

        # Find N3/N4 in the same segment list
        n3 = next((s for s in segments if s.tag == "N3"), None)
        n4 = next((s for s in segments if s.tag == "N4"), None)

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

    def _build_party_from_n1_loop(self, n1_loop: "LoopInstance") -> Party:
        """Build party from N1 loop."""
        party = Party()

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
                    PartyIdentification(id=Identifier(value=id_value, scheme_id=scheme))
                )

        n3 = find_segment_in_loop(n1_loop, "N3")
        n4 = find_segment_in_loop(n1_loop, "N4")
        if n3 or n4:
            party.postal_address = Address(
                street_name=get_element_value(n3, 1) if n3 else None,
                city_name=get_element_value(n4, 1) if n4 else None,
                country_subentity=get_element_value(n4, 2) if n4 else None,
                postal_zone=get_element_value(n4, 3) if n4 else None,
                country_code=get_element_value(n4, 4) if n4 else None,
            )

        return party

    def _build_shipment_hl(self, model: DespatchAdvice, hl_counter: list[int]) -> list[dict]:
        """Build shipment-level HL segments."""
        segments = []
        shipment_hl_id = str(hl_counter[0])
        hl_counter[0] += 1

        # HL segment for shipment
        segments.append(
            {
                "tag": "HL",
                "elements": [shipment_hl_id, "", "S", "1"],
            }
        )

        # TD1 - Carrier details
        if model.shipment:
            ship = model.shipment
            td1_elements = ["CTN25"]  # Default package type

            if ship.total_transport_handling_unit_quantity:
                td1_elements.append(str(ship.total_transport_handling_unit_quantity))

            segments.append({"tag": "TD1", "elements": td1_elements})

            # TD5 - Carrier
            if ship.carrier_party and ship.carrier_party.party_identifications:
                carrier_id = ship.carrier_party.party_identifications[0].id.value
                segments.append(
                    {
                        "tag": "TD5",
                        "elements": ["", "2", carrier_id],
                    }
                )

        # N1 loops for parties
        if model.despatch_supplier_party:
            segments.extend(self._build_n1_segments("SF", model.despatch_supplier_party.party))
        if model.delivery_customer_party:
            segments.extend(self._build_n1_segments("ST", model.delivery_customer_party.party))

        return segments

    def _build_order_hl(
        self, order_ref: OrderReference, lines: list[DespatchLine], hl_counter: list[int]
    ) -> list[dict]:
        """Build order-level and item-level HL segments."""
        segments = []
        order_hl_id = str(hl_counter[0])
        hl_counter[0] += 1

        # Order level HL
        segments.append(
            {
                "tag": "HL",
                "elements": [order_hl_id, "1", "O", "1"],
            }
        )

        # PRF - Purchase Order Reference
        segments.append(
            {
                "tag": "PRF",
                "elements": [order_ref.id],
            }
        )

        # Item level HLs
        for line in lines:
            item_hl_id = str(hl_counter[0])
            hl_counter[0] += 1

            segments.append(
                {
                    "tag": "HL",
                    "elements": [item_hl_id, order_hl_id, "I", "0"],
                }
            )

            # LIN segment
            lin_elements = [line.id]
            if line.item.standard_item_identification:
                scheme = line.item.standard_item_identification.id.scheme_id
                qualifier = "UP" if scheme == "UPC" else "EN"
                lin_elements.extend([qualifier, line.item.standard_item_identification.id.value])

            segments.append({"tag": "LIN", "elements": lin_elements})

            # SN1 segment
            segments.append(
                {
                    "tag": "SN1",
                    "elements": [
                        "",
                        str(line.delivered_quantity.value),
                        line.delivered_quantity.unit_code,
                    ],
                }
            )

            # PID segment
            if line.item.description:
                segments.append(
                    {
                        "tag": "PID",
                        "elements": ["F", "", "", "", line.item.description],
                    }
                )

        return segments

    def _build_n1_segments(self, party_code: str, party: Party) -> list[dict]:
        """Build N1 loop segments."""
        segments = []

        n1_elements = [party_code]
        if party.party_names:
            n1_elements.append(party.party_names[0].name)
        else:
            n1_elements.append("")

        if party.party_identifications:
            pid = party.party_identifications[0]
            n1_elements.extend(["92", pid.id.value])

        segments.append({"tag": "N1", "elements": n1_elements})

        if party.postal_address:
            addr = party.postal_address
            if addr.street_name:
                segments.append({"tag": "N3", "elements": [addr.street_name]})
            if addr.city_name:
                segments.append(
                    {
                        "tag": "N4",
                        "elements": [
                            addr.city_name,
                            addr.country_subentity or "",
                            addr.postal_zone or "",
                        ],
                    }
                )

        return segments
