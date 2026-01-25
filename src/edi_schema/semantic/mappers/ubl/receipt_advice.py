"""
UBL ReceiptAdvice Mapper.

Maps between UBL ReceiptAdvice and semantic ReceiptAdvice model.
"""

from typing import TYPE_CHECKING

from ...models import (
    Address,
    CustomerParty,
    DocumentReference,
    Identifier,
    Item,
    ItemIdentification,
    OrderLineReference,
    OrderReference,
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
    format_date,
    format_time,
    get_child_value,
    get_identifier_with_scheme,
    get_quantity_with_unit,
    parse_date,
    parse_time,
)

if TYPE_CHECKING:
    from edi_schema.ubl.ast import ParsedDocument, ParsedElement


class UBLReceiptAdviceMapper(SemanticMapper[ReceiptAdvice]):
    """
    Maps UBL ReceiptAdvice to/from semantic ReceiptAdvice model.

    UBL ReceiptAdvice Structure:
    - cbc:ID, cbc:UUID, cbc:IssueDate, cbc:IssueTime
    - cbc:ReceiptAdviceTypeCode
    - cac:OrderReference
    - cac:DespatchDocumentReference
    - cac:DeliveryCustomerParty
    - cac:DespatchSupplierParty
    - cac:ReceiptLine (multiple)
    """

    @property
    def semantic_type(self) -> type[ReceiptAdvice]:
        return ReceiptAdvice

    @property
    def source_format(self) -> Format:
        return Format.UBL

    @property
    def transaction_id(self) -> str:
        return "ReceiptAdvice"

    def to_semantic(self, source: "ParsedDocument") -> ReceiptAdvice:
        """Convert UBL ReceiptAdvice to semantic ReceiptAdvice."""
        root = source.root

        # Check document type
        if source.document_type != "ReceiptAdvice":
            raise ValueError(f"Expected ReceiptAdvice, got {source.document_type}")

        # Parse basic fields
        receipt_id = get_child_value(root, "ID") or ""
        issue_date = parse_date(get_child_value(root, "IssueDate"))
        if not issue_date:
            raise ValueError("Missing or invalid IssueDate")

        issue_time = parse_time(get_child_value(root, "IssueTime"))
        uuid = get_child_value(root, "UUID")
        receipt_type_code = get_child_value(root, "ReceiptAdviceTypeCode")

        # Create receipt advice
        receipt = ReceiptAdvice(
            id=receipt_id,
            issue_date=issue_date,
            issue_time=issue_time,
            uuid=uuid,
            receipt_advice_type_code=receipt_type_code,
            receipt_lines=[],
        )

        # Parse notes
        for note_elem in root.children_by_name("Note"):
            note_text = note_elem.value
            if note_text:
                receipt.note.append(note_text)

        # Parse order references
        for order_ref_elem in root.children_by_name("OrderReference"):
            order_ref = OrderReference(
                id=get_child_value(order_ref_elem, "ID") or "",
                issue_date=parse_date(get_child_value(order_ref_elem, "IssueDate")),
            )
            receipt.order_references.append(order_ref)

        # Parse despatch document references
        for despatch_ref_elem in root.children_by_name("DespatchDocumentReference"):
            despatch_ref = DocumentReference(
                id=get_child_value(despatch_ref_elem, "ID") or "",
                issue_date=parse_date(get_child_value(despatch_ref_elem, "IssueDate")),
            )
            receipt.despatch_document_references.append(despatch_ref)

        # Parse parties
        delivery_elem = root.first_child_by_name("DeliveryCustomerParty")
        if delivery_elem:
            receipt.delivery_customer_party = self._parse_customer_party(delivery_elem)

        despatch_elem = root.first_child_by_name("DespatchSupplierParty")
        if despatch_elem:
            receipt.despatch_supplier_party = self._parse_supplier_party(despatch_elem)

        buyer_elem = root.first_child_by_name("BuyerCustomerParty")
        if buyer_elem:
            receipt.buyer_customer_party = self._parse_customer_party(buyer_elem)

        seller_elem = root.first_child_by_name("SellerSupplierParty")
        if seller_elem:
            receipt.seller_supplier_party = self._parse_supplier_party(seller_elem)

        # Parse receipt lines
        for line_elem in root.children_by_name("ReceiptLine"):
            line = self._parse_receipt_line(line_elem)
            if line:
                receipt.receipt_lines.append(line)

        receipt.line_count = len(receipt.receipt_lines)

        receipt._source_format = "ubl"
        receipt._source_version = "2.5"
        return receipt

    def _parse_customer_party(self, elem: "ParsedElement") -> CustomerParty:
        """Parse CustomerParty element."""
        party_elem = elem.first_child_by_name("Party")
        party = self._parse_party(party_elem) if party_elem else Party()
        return CustomerParty(party=party)

    def _parse_supplier_party(self, elem: "ParsedElement") -> SupplierParty:
        """Parse SupplierParty element."""
        party_elem = elem.first_child_by_name("Party")
        party = self._parse_party(party_elem) if party_elem else Party()
        return SupplierParty(party=party)

    def _parse_party(self, elem: "ParsedElement") -> Party:
        """Parse Party element."""
        party = Party()

        # Party names
        for name_elem in elem.children_by_name("PartyName"):
            name = get_child_value(name_elem, "Name")
            if name:
                party.party_names.append(PartyName(name=name))

        # Party identifications
        for id_elem in elem.children_by_name("PartyIdentification"):
            identifier = get_identifier_with_scheme(id_elem, "ID")
            if identifier:
                party.party_identifications.append(PartyIdentification(id=identifier))

        # Postal address
        addr_elem = elem.first_child_by_name("PostalAddress")
        if addr_elem:
            party.postal_address = Address(
                street_name=get_child_value(addr_elem, "StreetName"),
                additional_street_name=get_child_value(addr_elem, "AdditionalStreetName"),
                city_name=get_child_value(addr_elem, "CityName"),
                postal_zone=get_child_value(addr_elem, "PostalZone"),
                country_subentity=get_child_value(addr_elem, "CountrySubentity"),
            )
            country_elem = addr_elem.first_child_by_name("Country")
            if country_elem:
                party.postal_address.country_code = get_child_value(
                    country_elem, "IdentificationCode"
                )

        return party

    def _parse_receipt_line(self, elem: "ParsedElement") -> ReceiptLine | None:
        """Parse ReceiptLine element."""
        line_id = get_child_value(elem, "ID") or "1"

        # Received quantity
        received_qty = get_quantity_with_unit(elem, "ReceivedQuantity")
        if not received_qty:
            received_qty = Quantity(value=1, unit_code="EA")

        # Item
        item_elem = elem.first_child_by_name("Item")
        item = self._parse_item(item_elem) if item_elem else Item()

        line = ReceiptLine(
            id=line_id,
            received_quantity=received_qty,
            item=item,
        )

        # Short quantity
        short_qty = get_quantity_with_unit(elem, "ShortQuantity")
        if short_qty:
            line.short_quantity = short_qty

        # Rejected quantity
        reject_qty = get_quantity_with_unit(elem, "RejectedQuantity")
        if reject_qty:
            line.rejected_quantity = reject_qty

        # Reject reason
        line.reject_reason_code = get_child_value(elem, "RejectReasonCode")
        line.reject_reason = get_child_value(elem, "RejectReason")

        # Oversupply quantity
        oversupply_qty = get_quantity_with_unit(elem, "OversupplyQuantity")
        if oversupply_qty:
            line.oversupply_quantity = oversupply_qty

        # Received date
        received_date = parse_date(get_child_value(elem, "ReceivedDate"))
        if received_date:
            line.received_date = received_date

        # Order line reference
        order_line_ref_elem = elem.first_child_by_name("OrderLineReference")
        if order_line_ref_elem:
            line.order_line_reference = OrderLineReference(
                line_id=get_child_value(order_line_ref_elem, "LineID") or ""
            )

        return line

    def _parse_item(self, elem: "ParsedElement") -> Item:
        """Parse Item element."""
        item = Item(
            description=get_child_value(elem, "Description"),
            name=get_child_value(elem, "Name"),
        )

        # Identifications
        buyers_id = elem.first_child_by_name("BuyersItemIdentification")
        if buyers_id:
            item.buyers_item_identification = ItemIdentification(
                id=get_identifier_with_scheme(buyers_id, "ID") or Identifier(value="")
            )

        sellers_id = elem.first_child_by_name("SellersItemIdentification")
        if sellers_id:
            item.sellers_item_identification = ItemIdentification(
                id=get_identifier_with_scheme(sellers_id, "ID") or Identifier(value="")
            )

        standard_id = elem.first_child_by_name("StandardItemIdentification")
        if standard_id:
            item.standard_item_identification = ItemIdentification(
                id=get_identifier_with_scheme(standard_id, "ID") or Identifier(value="")
            )

        return item

    def from_semantic(self, model: ReceiptAdvice) -> dict:
        """Convert semantic ReceiptAdvice to UBL structure."""
        ns_ra = "urn:oasis:names:specification:ubl:schema:xsd:ReceiptAdvice-2"
        ns_cac = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
        ns_cbc = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"

        doc = {
            "ReceiptAdvice": {
                "@xmlns": ns_ra,
                "@xmlns:cac": ns_cac,
                "@xmlns:cbc": ns_cbc,
                "cbc:ID": model.id,
                "cbc:IssueDate": format_date(model.issue_date),
            }
        }

        advice = doc["ReceiptAdvice"]

        if model.uuid:
            advice["cbc:UUID"] = model.uuid

        if model.issue_time:
            advice["cbc:IssueTime"] = format_time(model.issue_time)

        if model.receipt_advice_type_code:
            advice["cbc:ReceiptAdviceTypeCode"] = model.receipt_advice_type_code

        # Notes
        for note in model.note:
            if "cbc:Note" not in advice:
                advice["cbc:Note"] = []
            advice["cbc:Note"].append(note)

        # Order references
        for order_ref in model.order_references:
            if "cac:OrderReference" not in advice:
                advice["cac:OrderReference"] = []
            ref_dict = {"cbc:ID": order_ref.id}
            if order_ref.issue_date:
                ref_dict["cbc:IssueDate"] = format_date(order_ref.issue_date)
            advice["cac:OrderReference"].append(ref_dict)

        # Despatch document references
        for despatch_ref in model.despatch_document_references:
            if "cac:DespatchDocumentReference" not in advice:
                advice["cac:DespatchDocumentReference"] = []
            ref_dict = {"cbc:ID": despatch_ref.id}
            if despatch_ref.issue_date:
                ref_dict["cbc:IssueDate"] = format_date(despatch_ref.issue_date)
            advice["cac:DespatchDocumentReference"].append(ref_dict)

        # Parties
        if model.delivery_customer_party:
            advice["cac:DeliveryCustomerParty"] = self._build_customer_party(
                model.delivery_customer_party
            )

        if model.despatch_supplier_party:
            advice["cac:DespatchSupplierParty"] = self._build_supplier_party(
                model.despatch_supplier_party
            )

        if model.buyer_customer_party:
            advice["cac:BuyerCustomerParty"] = self._build_customer_party(
                model.buyer_customer_party
            )

        if model.seller_supplier_party:
            advice["cac:SellerSupplierParty"] = self._build_supplier_party(
                model.seller_supplier_party
            )

        # Receipt lines
        if model.receipt_lines:
            advice["cac:ReceiptLine"] = [
                self._build_receipt_line(line) for line in model.receipt_lines
            ]

        return doc

    def _build_customer_party(self, party: CustomerParty) -> dict:
        """Build CustomerParty structure."""
        return {"cac:Party": self._build_party(party.party)}

    def _build_supplier_party(self, party: SupplierParty) -> dict:
        """Build SupplierParty structure."""
        return {"cac:Party": self._build_party(party.party)}

    def _build_party(self, party: Party) -> dict:
        """Build Party structure."""
        result = {}

        if party.party_identifications:
            result["cac:PartyIdentification"] = [
                {"cbc:ID": pid.id.value} for pid in party.party_identifications
            ]

        if party.party_names:
            result["cac:PartyName"] = [{"cbc:Name": name.name} for name in party.party_names]

        if party.postal_address:
            addr = party.postal_address
            addr_dict = {}
            if addr.street_name:
                addr_dict["cbc:StreetName"] = addr.street_name
            if addr.additional_street_name:
                addr_dict["cbc:AdditionalStreetName"] = addr.additional_street_name
            if addr.city_name:
                addr_dict["cbc:CityName"] = addr.city_name
            if addr.postal_zone:
                addr_dict["cbc:PostalZone"] = addr.postal_zone
            if addr.country_subentity:
                addr_dict["cbc:CountrySubentity"] = addr.country_subentity
            if addr.country_code:
                addr_dict["cac:Country"] = {"cbc:IdentificationCode": addr.country_code}
            if addr_dict:
                result["cac:PostalAddress"] = addr_dict

        return result

    def _build_receipt_line(self, line: ReceiptLine) -> dict:
        """Build ReceiptLine structure."""
        result = {
            "cbc:ID": line.id,
            "cbc:ReceivedQuantity": {
                "@unitCode": line.received_quantity.unit_code,
                "#text": str(line.received_quantity.value),
            },
        }

        if line.short_quantity:
            result["cbc:ShortQuantity"] = {
                "@unitCode": line.short_quantity.unit_code,
                "#text": str(line.short_quantity.value),
            }

        if line.rejected_quantity:
            result["cbc:RejectedQuantity"] = {
                "@unitCode": line.rejected_quantity.unit_code,
                "#text": str(line.rejected_quantity.value),
            }

        if line.reject_reason_code:
            result["cbc:RejectReasonCode"] = line.reject_reason_code

        if line.reject_reason:
            result["cbc:RejectReason"] = line.reject_reason

        if line.oversupply_quantity:
            result["cbc:OversupplyQuantity"] = {
                "@unitCode": line.oversupply_quantity.unit_code,
                "#text": str(line.oversupply_quantity.value),
            }

        if line.received_date:
            result["cbc:ReceivedDate"] = format_date(line.received_date)

        # Order line reference
        if line.order_line_reference:
            result["cac:OrderLineReference"] = {"cbc:LineID": line.order_line_reference.line_id}

        # Item
        result["cac:Item"] = self._build_item(line.item)

        return result

    def _build_item(self, item: Item) -> dict:
        """Build Item structure."""
        result = {}

        if item.description:
            result["cbc:Description"] = item.description

        if item.name:
            result["cbc:Name"] = item.name

        if item.buyers_item_identification:
            result["cac:BuyersItemIdentification"] = {
                "cbc:ID": item.buyers_item_identification.id.value
            }

        if item.sellers_item_identification:
            result["cac:SellersItemIdentification"] = {
                "cbc:ID": item.sellers_item_identification.id.value
            }

        if item.standard_item_identification:
            result["cac:StandardItemIdentification"] = {
                "cbc:ID": item.standard_item_identification.id.value
            }

        return result
