"""
UBL DespatchAdvice Mapper.

Maps between UBL DespatchAdvice and semantic DespatchAdvice model.
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
    TransportHandlingUnit,
)
from ..base import Format, SemanticMapper
from .utils import (
    format_date,
    format_time,
    get_child_value,
    get_identifier_with_scheme,
    get_quantity_with_unit,
    parse_date,
    parse_decimal,
    parse_time,
)

if TYPE_CHECKING:
    from edi_schema.ubl.ast import ParsedDocument, ParsedElement


class UBLDespatchAdviceMapper(SemanticMapper[DespatchAdvice]):
    """
    Maps UBL DespatchAdvice to/from semantic DespatchAdvice model.

    UBL DespatchAdvice Structure:
    - cbc:ID, cbc:UUID, cbc:IssueDate, cbc:IssueTime
    - cbc:Note (multiple)
    - cac:OrderReference (multiple)
    - cac:DespatchSupplierParty
    - cac:DeliveryCustomerParty
    - cac:Shipment
    - cac:DespatchLine (multiple)
    """

    @property
    def semantic_type(self) -> type[DespatchAdvice]:
        return DespatchAdvice

    @property
    def source_format(self) -> Format:
        return Format.UBL

    @property
    def transaction_id(self) -> str:
        return "DespatchAdvice"

    def to_semantic(self, source: "ParsedDocument") -> DespatchAdvice:
        """Convert UBL DespatchAdvice to semantic DespatchAdvice."""
        root = source.root

        if source.document_type != "DespatchAdvice":
            raise ValueError(f"Expected DespatchAdvice, got {source.document_type}")

        # Parse basic fields
        advice_id = get_child_value(root, "ID") or ""
        issue_date = parse_date(get_child_value(root, "IssueDate"))
        if not issue_date:
            raise ValueError("Missing or invalid IssueDate")

        issue_time = parse_time(get_child_value(root, "IssueTime"))
        uuid = get_child_value(root, "UUID")

        # Create despatch advice
        advice = DespatchAdvice(
            id=advice_id,
            uuid=uuid,
            issue_date=issue_date,
            issue_time=issue_time,
        )

        # Notes
        for note_elem in root.find_all_children("Note"):
            if note_elem.value:
                advice.note.append(note_elem.value)

        # Order references
        for or_elem in root.find_all_children("OrderReference"):
            advice.order_references.append(self._parse_order_reference(or_elem))

        # Despatch supplier party
        dsp_elem = root.find_child("DespatchSupplierParty")
        if dsp_elem:
            advice.despatch_supplier_party = self._parse_supplier_party(dsp_elem)

        # Delivery customer party
        dcp_elem = root.find_child("DeliveryCustomerParty")
        if dcp_elem:
            advice.delivery_customer_party = self._parse_customer_party(dcp_elem)

        # Shipment
        ship_elem = root.find_child("Shipment")
        if ship_elem:
            advice.shipment = self._parse_shipment(ship_elem)

        # Despatch lines
        for line_elem in root.find_all_children("DespatchLine"):
            line = self._parse_despatch_line(line_elem)
            advice.despatch_lines.append(line)

        # Source tracking
        advice._source_format = "ubl"
        advice._source_version = source.version

        return advice

    def from_semantic(self, model: DespatchAdvice) -> dict:
        """Convert semantic DespatchAdvice to UBL structure."""
        ns_da = "urn:oasis:names:specification:ubl:schema:xsd:DespatchAdvice-2"
        ns_cac = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
        ns_cbc = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"

        doc = {
            "DespatchAdvice": {
                "@xmlns": ns_da,
                "@xmlns:cac": ns_cac,
                "@xmlns:cbc": ns_cbc,
                "cbc:ID": model.id,
                "cbc:IssueDate": format_date(model.issue_date),
            }
        }

        advice = doc["DespatchAdvice"]

        if model.uuid:
            advice["cbc:UUID"] = model.uuid

        if model.issue_time:
            advice["cbc:IssueTime"] = format_time(model.issue_time)

        # Notes
        if model.note:
            advice["cbc:Note"] = model.note

        # Order references
        if model.order_references:
            advice["cac:OrderReference"] = [
                self._build_order_reference(ref) for ref in model.order_references
            ]

        # Despatch supplier party
        if model.despatch_supplier_party:
            advice["cac:DespatchSupplierParty"] = self._build_supplier_party(
                model.despatch_supplier_party
            )

        # Delivery customer party
        if model.delivery_customer_party:
            advice["cac:DeliveryCustomerParty"] = self._build_customer_party(
                model.delivery_customer_party
            )

        # Shipment
        if model.shipment:
            advice["cac:Shipment"] = self._build_shipment(model.shipment)

        # Despatch lines
        if model.despatch_lines:
            advice["cac:DespatchLine"] = [
                self._build_despatch_line(line) for line in model.despatch_lines
            ]

        return doc

    # Parse methods
    def _parse_order_reference(self, elem: "ParsedElement") -> OrderReference:
        """Parse an OrderReference element."""
        return OrderReference(
            id=get_child_value(elem, "ID") or "",
            sales_order_id=get_child_value(elem, "SalesOrderID"),
            issue_date=parse_date(get_child_value(elem, "IssueDate")),
        )

    def _parse_supplier_party(self, elem: "ParsedElement") -> SupplierParty:
        """Parse a SupplierParty element."""
        party_elem = elem.find_child("Party")
        party = self._parse_party(party_elem) if party_elem else Party()
        return SupplierParty(party=party)

    def _parse_customer_party(self, elem: "ParsedElement") -> CustomerParty:
        """Parse a CustomerParty element."""
        party_elem = elem.find_child("Party")
        party = self._parse_party(party_elem) if party_elem else Party()
        return CustomerParty(party=party)

    def _parse_party(self, elem: "ParsedElement | None") -> Party:
        """Parse a Party element."""
        if elem is None:
            return Party()

        party = Party()

        for pi_elem in elem.find_all_children("PartyIdentification"):
            id_val, scheme_id, scheme_agency = get_identifier_with_scheme(pi_elem, "ID")
            if id_val:
                ident = Identifier(
                    value=id_val,
                    scheme_id=scheme_id,
                    scheme_agency_id=scheme_agency,
                )
                party.party_identifications.append(PartyIdentification(id=ident))

        for pn_elem in elem.find_all_children("PartyName"):
            name = get_child_value(pn_elem, "Name")
            if name:
                party.party_names.append(PartyName(name=name))

        addr_elem = elem.find_child("PostalAddress")
        if addr_elem:
            party.postal_address = self._parse_address(addr_elem)

        contact_elem = elem.find_child("Contact")
        if contact_elem:
            party.contact = self._parse_contact(contact_elem)

        return party

    def _parse_address(self, elem: "ParsedElement") -> Address:
        """Parse an Address element."""
        country_elem = elem.find_child("Country")
        country_code = None
        if country_elem:
            country_code = get_child_value(country_elem, "IdentificationCode")

        return Address(
            street_name=get_child_value(elem, "StreetName"),
            additional_street_name=get_child_value(elem, "AdditionalStreetName"),
            building_number=get_child_value(elem, "BuildingNumber"),
            city_name=get_child_value(elem, "CityName"),
            postal_zone=get_child_value(elem, "PostalZone"),
            country_subentity=get_child_value(elem, "CountrySubentity"),
            country_code=country_code,
        )

    def _parse_contact(self, elem: "ParsedElement") -> Contact:
        """Parse a Contact element."""
        return Contact(
            name=get_child_value(elem, "Name"),
            telephone=get_child_value(elem, "Telephone"),
            electronic_mail=get_child_value(elem, "ElectronicMail"),
            telefax=get_child_value(elem, "Telefax"),
        )

    def _parse_shipment(self, elem: "ParsedElement") -> Shipment:
        """Parse a Shipment element."""
        shipment = Shipment(
            id=get_child_value(elem, "ID"),
            handling_code=get_child_value(elem, "HandlingCode"),
            handling_instructions=get_child_value(elem, "HandlingInstructions"),
            information=get_child_value(elem, "Information"),
        )

        # Gross weight
        gw_elem = elem.find_child("GrossWeightMeasure")
        if gw_elem and gw_elem.value:
            shipment.gross_weight_measure = Measure(
                value=parse_decimal(gw_elem.value) or Decimal("0"),
                unit_code=gw_elem.get_attribute("unitCode") or "KGM",
            )

        # Net weight
        nw_elem = elem.find_child("NetWeightMeasure")
        if nw_elem and nw_elem.value:
            shipment.net_weight_measure = Measure(
                value=parse_decimal(nw_elem.value) or Decimal("0"),
                unit_code=nw_elem.get_attribute("unitCode") or "KGM",
            )

        # Total handling units
        thu_qty = get_child_value(elem, "TotalTransportHandlingUnitQuantity")
        if thu_qty:
            shipment.total_transport_handling_unit_quantity = int(parse_decimal(thu_qty) or 0)

        # Consignor party
        consignor_elem = elem.find_child("ConsignorParty")
        if consignor_elem:
            shipment.consignor_party = self._parse_party(consignor_elem)

        # Carrier party
        carrier_elem = elem.find_child("CarrierParty")
        if carrier_elem:
            shipment.carrier_party = self._parse_party(carrier_elem)

        # Shipment stages
        for stage_elem in elem.find_all_children("ShipmentStage"):
            stage = self._parse_shipment_stage(stage_elem)
            shipment.shipment_stages.append(stage)

        # Transport handling units
        for thu_elem in elem.find_all_children("TransportHandlingUnit"):
            thu = self._parse_transport_handling_unit(thu_elem)
            shipment.transport_handling_units.append(thu)

        return shipment

    def _parse_shipment_stage(self, elem: "ParsedElement") -> ShipmentStage:
        """Parse a ShipmentStage element."""
        return ShipmentStage(
            id=get_child_value(elem, "ID"),
            transport_mode_code=get_child_value(elem, "TransportModeCode"),
            transport_means_type_code=get_child_value(elem, "TransportMeansTypeCode"),
            estimated_delivery_date=parse_date(get_child_value(elem, "EstimatedDeliveryDate")),
            estimated_delivery_time=parse_time(get_child_value(elem, "EstimatedDeliveryTime")),
        )

    def _parse_transport_handling_unit(self, elem: "ParsedElement") -> TransportHandlingUnit:
        """Parse a TransportHandlingUnit element."""
        thu = TransportHandlingUnit(
            id=get_child_value(elem, "ID"),
            transport_handling_unit_type_code=get_child_value(
                elem, "TransportHandlingUnitTypeCode"
            ),
            handling_code=get_child_value(elem, "HandlingCode"),
            handling_instructions=get_child_value(elem, "HandlingInstructions"),
        )

        # Total items
        total_items = get_child_value(elem, "TotalGoodsItemQuantity")
        if total_items:
            thu.total_goods_item_quantity = int(parse_decimal(total_items) or 0)

        # Total packages
        total_pkgs = get_child_value(elem, "TotalPackageQuantity")
        if total_pkgs:
            thu.total_package_quantity = int(parse_decimal(total_pkgs) or 0)

        return thu

    def _parse_despatch_line(self, elem: "ParsedElement") -> DespatchLine:
        """Parse a DespatchLine element."""
        line_id = get_child_value(elem, "ID") or "1"
        qty_val, qty_unit = get_quantity_with_unit(elem, "DeliveredQuantity")

        # Item
        item_elem = elem.find_child("Item")
        item = self._parse_item(item_elem)

        line = DespatchLine(
            id=line_id,
            delivered_quantity=Quantity(value=qty_val or Decimal("0"), unit_code=qty_unit or "EA"),
            item=item,
        )

        # Order line reference
        olr_elem = elem.find_child("OrderLineReference")
        if olr_elem:
            line.order_line_reference = self._parse_order_line_reference(olr_elem)

        return line

    def _parse_order_line_reference(self, elem: "ParsedElement") -> OrderLineReference:
        """Parse an OrderLineReference element."""
        line_id = get_child_value(elem, "LineID") or ""

        order_ref = None
        order_ref_elem = elem.find_child("OrderReference")
        if order_ref_elem:
            order_ref = self._parse_order_reference(order_ref_elem)

        return OrderLineReference(line_id=line_id, order_reference=order_ref)

    def _parse_item(self, elem: "ParsedElement | None") -> Item:
        """Parse an Item element."""
        if elem is None:
            return Item()

        item = Item(
            description=get_child_value(elem, "Description"),
            name=get_child_value(elem, "Name"),
        )

        std_elem = elem.find_child("StandardItemIdentification")
        if std_elem:
            id_val, scheme_id, _ = get_identifier_with_scheme(std_elem, "ID")
            if id_val:
                item.standard_item_identification = ItemIdentification(
                    id=Identifier(value=id_val, scheme_id=scheme_id)
                )

        seller_elem = elem.find_child("SellersItemIdentification")
        if seller_elem:
            id_val, scheme_id, _ = get_identifier_with_scheme(seller_elem, "ID")
            if id_val:
                item.sellers_item_identification = ItemIdentification(
                    id=Identifier(value=id_val, scheme_id=scheme_id)
                )

        buyer_elem = elem.find_child("BuyersItemIdentification")
        if buyer_elem:
            id_val, scheme_id, _ = get_identifier_with_scheme(buyer_elem, "ID")
            if id_val:
                item.buyers_item_identification = ItemIdentification(
                    id=Identifier(value=id_val, scheme_id=scheme_id)
                )

        return item

    # Build methods
    def _build_order_reference(self, ref: OrderReference) -> dict:
        """Build an OrderReference element."""
        result = {"cbc:ID": ref.id}
        if ref.sales_order_id:
            result["cbc:SalesOrderID"] = ref.sales_order_id
        if ref.issue_date:
            result["cbc:IssueDate"] = format_date(ref.issue_date)
        return result

    def _build_supplier_party(self, sp: SupplierParty) -> dict:
        """Build a SupplierParty element."""
        return {"cac:Party": self._build_party(sp.party)}

    def _build_customer_party(self, cp: CustomerParty) -> dict:
        """Build a CustomerParty element."""
        return {"cac:Party": self._build_party(cp.party)}

    def _build_party(self, party: Party) -> dict:
        """Build a Party element."""
        result = {}

        if party.party_identifications:
            result["cac:PartyIdentification"] = [
                {"cbc:ID": pi.id.value} for pi in party.party_identifications
            ]

        if party.party_names:
            result["cac:PartyName"] = [{"cbc:Name": pn.name} for pn in party.party_names]

        if party.postal_address:
            result["cac:PostalAddress"] = self._build_address(party.postal_address)

        if party.contact:
            result["cac:Contact"] = self._build_contact(party.contact)

        return result

    def _build_address(self, addr: Address) -> dict:
        """Build an Address element."""
        result = {}
        if addr.street_name:
            result["cbc:StreetName"] = addr.street_name
        if addr.city_name:
            result["cbc:CityName"] = addr.city_name
        if addr.postal_zone:
            result["cbc:PostalZone"] = addr.postal_zone
        if addr.country_code:
            result["cac:Country"] = {"cbc:IdentificationCode": addr.country_code}
        return result

    def _build_contact(self, contact: Contact) -> dict:
        """Build a Contact element."""
        result = {}
        if contact.name:
            result["cbc:Name"] = contact.name
        if contact.telephone:
            result["cbc:Telephone"] = contact.telephone
        if contact.electronic_mail:
            result["cbc:ElectronicMail"] = contact.electronic_mail
        return result

    def _build_shipment(self, shipment: Shipment) -> dict:
        """Build a Shipment element."""
        result = {}

        if shipment.id:
            result["cbc:ID"] = shipment.id

        if shipment.handling_code:
            result["cbc:HandlingCode"] = shipment.handling_code

        if shipment.handling_instructions:
            result["cbc:HandlingInstructions"] = shipment.handling_instructions

        if shipment.gross_weight_measure:
            result["cbc:GrossWeightMeasure"] = {
                "@unitCode": shipment.gross_weight_measure.unit_code,
                "#text": str(shipment.gross_weight_measure.value),
            }

        if shipment.total_transport_handling_unit_quantity:
            result["cbc:TotalTransportHandlingUnitQuantity"] = str(
                shipment.total_transport_handling_unit_quantity
            )

        if shipment.carrier_party:
            result["cac:CarrierParty"] = self._build_party(shipment.carrier_party)

        if shipment.shipment_stages:
            result["cac:ShipmentStage"] = [
                self._build_shipment_stage(s) for s in shipment.shipment_stages
            ]

        if shipment.transport_handling_units:
            result["cac:TransportHandlingUnit"] = [
                self._build_transport_handling_unit(thu)
                for thu in shipment.transport_handling_units
            ]

        return result

    def _build_shipment_stage(self, stage: ShipmentStage) -> dict:
        """Build a ShipmentStage element."""
        result = {}
        if stage.id:
            result["cbc:ID"] = stage.id
        if stage.transport_mode_code:
            result["cbc:TransportModeCode"] = stage.transport_mode_code
        if stage.estimated_delivery_date:
            result["cbc:EstimatedDeliveryDate"] = format_date(stage.estimated_delivery_date)
        return result

    def _build_transport_handling_unit(self, thu: TransportHandlingUnit) -> dict:
        """Build a TransportHandlingUnit element."""
        result = {}
        if thu.id:
            result["cbc:ID"] = thu.id
        if thu.transport_handling_unit_type_code:
            result["cbc:TransportHandlingUnitTypeCode"] = thu.transport_handling_unit_type_code
        if thu.total_goods_item_quantity:
            result["cbc:TotalGoodsItemQuantity"] = str(thu.total_goods_item_quantity)
        return result

    def _build_despatch_line(self, line: DespatchLine) -> dict:
        """Build a DespatchLine element."""
        result = {
            "cbc:ID": line.id,
            "cbc:DeliveredQuantity": {
                "@unitCode": line.delivered_quantity.unit_code,
                "#text": str(line.delivered_quantity.value),
            },
            "cac:Item": self._build_item(line.item),
        }

        if line.order_line_reference:
            result["cac:OrderLineReference"] = {"cbc:LineID": line.order_line_reference.line_id}

        return result

    def _build_item(self, item: Item) -> dict:
        """Build an Item element."""
        result = {}
        if item.description:
            result["cbc:Description"] = item.description
        if item.name:
            result["cbc:Name"] = item.name
        if item.standard_item_identification:
            result["cac:StandardItemIdentification"] = {
                "cbc:ID": item.standard_item_identification.id.value
            }
        if item.sellers_item_identification:
            result["cac:SellersItemIdentification"] = {
                "cbc:ID": item.sellers_item_identification.id.value
            }
        return result
