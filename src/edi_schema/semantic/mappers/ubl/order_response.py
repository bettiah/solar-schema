"""
UBL OrderResponse Mapper.

Maps between UBL OrderResponse and semantic OrderResponse model.
"""

from typing import TYPE_CHECKING

from ...models import (
    Address,
    Contact,
    CustomerParty,
    Identifier,
    Item,
    ItemIdentification,
    OrderLineReference,
    OrderReference,
    OrderResponse,
    OrderResponseLine,
    Party,
    PartyIdentification,
    PartyName,
    Price,
    SupplierParty,
)
from ..base import Format, SemanticMapper
from .utils import (
    format_date,
    format_time,
    get_amount_with_currency,
    get_child_value,
    get_identifier_with_scheme,
    get_quantity_with_unit,
    parse_date,
    parse_time,
)

if TYPE_CHECKING:
    from edi_schema.ubl.ast import ParsedDocument, ParsedElement


class UBLOrderResponseMapper(SemanticMapper[OrderResponse]):
    """
    Maps UBL OrderResponse to/from semantic OrderResponse model.

    UBL OrderResponse Structure:
    - cbc:ID, cbc:UUID, cbc:IssueDate, cbc:IssueTime
    - cbc:OrderResponseCode
    - cbc:DocumentCurrencyCode
    - cac:OrderReference
    - cac:SellerSupplierParty
    - cac:BuyerCustomerParty
    - cac:OrderLine (multiple)
    """

    @property
    def semantic_type(self) -> type[OrderResponse]:
        return OrderResponse

    @property
    def source_format(self) -> Format:
        return Format.UBL

    @property
    def transaction_id(self) -> str:
        return "OrderResponse"

    def to_semantic(self, source: "ParsedDocument") -> OrderResponse:
        """Convert UBL OrderResponse to semantic OrderResponse."""
        root = source.root

        # Check document type
        if source.document_type != "OrderResponse":
            raise ValueError(f"Expected OrderResponse, got {source.document_type}")

        # Parse basic fields
        response_id = get_child_value(root, "ID") or ""
        issue_date = parse_date(get_child_value(root, "IssueDate"))
        if not issue_date:
            raise ValueError("Missing or invalid IssueDate")

        issue_time = parse_time(get_child_value(root, "IssueTime"))
        uuid = get_child_value(root, "UUID")
        currency = get_child_value(root, "DocumentCurrencyCode") or "USD"
        response_code = get_child_value(root, "OrderResponseCode")

        # Create order response
        response = OrderResponse(
            id=response_id,
            issue_date=issue_date,
            issue_time=issue_time,
            uuid=uuid,
            document_currency_code=currency,
            order_response_code=response_code,
            order_lines=[],
        )

        # Parse notes
        for note_elem in root.children_by_name("Note"):
            note_text = note_elem.value
            if note_text:
                response.note.append(note_text)

        # Parse order reference
        order_ref_elem = root.first_child_by_name("OrderReference")
        if order_ref_elem:
            response.order_reference = OrderReference(
                id=get_child_value(order_ref_elem, "ID") or "",
                issue_date=parse_date(get_child_value(order_ref_elem, "IssueDate")),
            )

        # Parse parties
        seller_elem = root.first_child_by_name("SellerSupplierParty")
        if seller_elem:
            response.seller_supplier_party = self._parse_supplier_party(seller_elem)

        buyer_elem = root.first_child_by_name("BuyerCustomerParty")
        if buyer_elem:
            response.buyer_customer_party = self._parse_customer_party(buyer_elem)

        # Parse order lines
        for line_elem in root.children_by_name("OrderLine"):
            line = self._parse_order_line(line_elem, currency)
            if line:
                response.order_lines.append(line)

        response._source_format = "ubl"
        response._source_version = "2.5"
        return response

    def _parse_supplier_party(self, elem: "ParsedElement") -> SupplierParty:
        """Parse SupplierParty element."""
        party_elem = elem.first_child_by_name("Party")
        party = self._parse_party(party_elem) if party_elem else Party()
        return SupplierParty(party=party)

    def _parse_customer_party(self, elem: "ParsedElement") -> CustomerParty:
        """Parse CustomerParty element."""
        party_elem = elem.first_child_by_name("Party")
        party = self._parse_party(party_elem) if party_elem else Party()
        return CustomerParty(party=party)

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

        # Contact
        contact_elem = elem.first_child_by_name("Contact")
        if contact_elem:
            party.contact = Contact(
                name=get_child_value(contact_elem, "Name"),
                telephone=get_child_value(contact_elem, "Telephone"),
                electronic_mail=get_child_value(contact_elem, "ElectronicMail"),
            )

        return party

    def _parse_order_line(self, elem: "ParsedElement", currency: str) -> OrderResponseLine | None:
        """Parse OrderLine element."""
        line_item_elem = elem.first_child_by_name("LineItem")
        if not line_item_elem:
            return None

        line_id = get_child_value(line_item_elem, "ID") or "1"

        # Quantity
        quantity = get_quantity_with_unit(line_item_elem, "Quantity")

        # Line status
        line_status = get_child_value(line_item_elem, "LineStatusCode")

        # Item
        item_elem = line_item_elem.first_child_by_name("Item")
        item = self._parse_item(item_elem) if item_elem else Item()

        # Price
        price = None
        price_elem = line_item_elem.first_child_by_name("Price")
        if price_elem:
            price_amount = get_amount_with_currency(price_elem, "PriceAmount")
            if price_amount:
                price = Price(price_amount=price_amount)

        line = OrderResponseLine(
            id=line_id,
            line_status_code=line_status,
            quantity=quantity,
            item=item,
            price=price,
        )

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

    def from_semantic(self, model: OrderResponse) -> dict:
        """Convert semantic OrderResponse to UBL structure."""
        ns_or = "urn:oasis:names:specification:ubl:schema:xsd:OrderResponse-2"
        ns_cac = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
        ns_cbc = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"

        doc = {
            "OrderResponse": {
                "@xmlns": ns_or,
                "@xmlns:cac": ns_cac,
                "@xmlns:cbc": ns_cbc,
                "cbc:ID": model.id,
                "cbc:IssueDate": format_date(model.issue_date),
                "cbc:DocumentCurrencyCode": model.document_currency_code,
            }
        }

        response = doc["OrderResponse"]

        if model.uuid:
            response["cbc:UUID"] = model.uuid

        if model.issue_time:
            response["cbc:IssueTime"] = format_time(model.issue_time)

        if model.order_response_code:
            response["cbc:OrderResponseCode"] = model.order_response_code

        # Notes
        for note in model.note:
            if "cbc:Note" not in response:
                response["cbc:Note"] = []
            response["cbc:Note"].append(note)

        # Order reference
        if model.order_reference:
            order_ref = {"cbc:ID": model.order_reference.id}
            if model.order_reference.issue_date:
                order_ref["cbc:IssueDate"] = format_date(model.order_reference.issue_date)
            response["cac:OrderReference"] = order_ref

        # Parties
        if model.seller_supplier_party:
            response["cac:SellerSupplierParty"] = self._build_supplier_party(
                model.seller_supplier_party
            )

        if model.buyer_customer_party:
            response["cac:BuyerCustomerParty"] = self._build_customer_party(
                model.buyer_customer_party
            )

        # Order lines
        if model.order_lines:
            response["cac:OrderLine"] = [
                self._build_order_line(line, model.document_currency_code)
                for line in model.order_lines
            ]

        return doc

    def _build_supplier_party(self, party: SupplierParty) -> dict:
        """Build SupplierParty structure."""
        return {"cac:Party": self._build_party(party.party)}

    def _build_customer_party(self, party: CustomerParty) -> dict:
        """Build CustomerParty structure."""
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

        if party.contact:
            contact_dict = {}
            if party.contact.name:
                contact_dict["cbc:Name"] = party.contact.name
            if party.contact.telephone:
                contact_dict["cbc:Telephone"] = party.contact.telephone
            if party.contact.electronic_mail:
                contact_dict["cbc:ElectronicMail"] = party.contact.electronic_mail
            if contact_dict:
                result["cac:Contact"] = contact_dict

        return result

    def _build_order_line(self, line: OrderResponseLine, currency: str) -> dict:
        """Build OrderLine structure."""
        line_item = {
            "cbc:ID": line.id,
        }

        if line.line_status_code:
            line_item["cbc:LineStatusCode"] = line.line_status_code

        if line.quantity:
            line_item["cbc:Quantity"] = {
                "@unitCode": line.quantity.unit_code,
                "#text": str(line.quantity.value),
            }

        # Item
        line_item["cac:Item"] = self._build_item(line.item)

        # Price
        if line.price:
            line_item["cac:Price"] = {
                "cbc:PriceAmount": {
                    "@currencyID": line.price.price_amount.currency,
                    "#text": str(line.price.price_amount.value),
                }
            }

        result = {"cac:LineItem": line_item}

        # Order line reference
        if line.order_line_reference:
            result["cac:OrderLineReference"] = {"cbc:LineID": line.order_line_reference.line_id}

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
