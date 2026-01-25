"""
UBL CreditNote Mapper.

Maps between UBL CreditNote and semantic CreditNote model.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from ...models import (
    Address,
    Amount,
    BillingReference,
    CreditNote,
    CreditNoteLine,
    CustomerParty,
    DocumentReference,
    Identifier,
    Item,
    ItemIdentification,
    MonetaryTotal,
    Party,
    PartyIdentification,
    PartyName,
    Price,
    Quantity,
    SupplierParty,
    TaxTotal,
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


class UBLCreditNoteMapper(SemanticMapper[CreditNote]):
    """
    Maps UBL CreditNote to/from semantic CreditNote model.

    UBL CreditNote Structure:
    - cbc:ID, cbc:UUID, cbc:IssueDate, cbc:IssueTime
    - cbc:CreditNoteTypeCode
    - cbc:DocumentCurrencyCode
    - cac:BillingReference
    - cac:AccountingSupplierParty
    - cac:AccountingCustomerParty
    - cac:TaxTotal
    - cac:LegalMonetaryTotal
    - cac:CreditNoteLine (multiple)
    """

    @property
    def semantic_type(self) -> type[CreditNote]:
        return CreditNote

    @property
    def source_format(self) -> Format:
        return Format.UBL

    @property
    def transaction_id(self) -> str:
        return "CreditNote"

    def to_semantic(self, source: "ParsedDocument") -> CreditNote:
        """Convert UBL CreditNote to semantic CreditNote."""
        root = source.root

        # Check document type
        if source.document_type != "CreditNote":
            raise ValueError(f"Expected CreditNote, got {source.document_type}")

        # Parse basic fields
        credit_note_id = get_child_value(root, "ID") or ""
        issue_date = parse_date(get_child_value(root, "IssueDate"))
        if not issue_date:
            raise ValueError("Missing or invalid IssueDate")

        issue_time = parse_time(get_child_value(root, "IssueTime"))
        uuid = get_child_value(root, "UUID")
        currency = get_child_value(root, "DocumentCurrencyCode") or "USD"
        credit_note_type = get_child_value(root, "CreditNoteTypeCode")

        # Parse parties first (required)
        supplier_elem = root.first_child_by_name("AccountingSupplierParty")
        accounting_supplier_party = (
            self._parse_supplier_party(supplier_elem)
            if supplier_elem
            else SupplierParty(party=Party())
        )

        customer_elem = root.first_child_by_name("AccountingCustomerParty")
        accounting_customer_party = (
            self._parse_customer_party(customer_elem)
            if customer_elem
            else CustomerParty(party=Party())
        )

        # Parse monetary total (required)
        monetary_total_elem = root.first_child_by_name("LegalMonetaryTotal")
        legal_monetary_total = (
            self._parse_monetary_total(monetary_total_elem)
            if monetary_total_elem
            else MonetaryTotal()
        )

        # Parse lines
        credit_note_lines: list[CreditNoteLine] = []
        for line_elem in root.children_by_name("CreditNoteLine"):
            line = self._parse_credit_note_line(line_elem, currency)
            if line:
                credit_note_lines.append(line)

        # Create credit note
        credit_note = CreditNote(
            id=credit_note_id,
            issue_date=issue_date,
            issue_time=issue_time,
            uuid=uuid,
            document_currency_code=currency,
            credit_note_type_code=credit_note_type,
            accounting_supplier_party=accounting_supplier_party,
            accounting_customer_party=accounting_customer_party,
            legal_monetary_total=legal_monetary_total,
            credit_note_lines=credit_note_lines,
        )

        # Parse notes
        for note_elem in root.children_by_name("Note"):
            note_text = note_elem.value
            if note_text:
                credit_note.note.append(note_text)

        # Parse billing references
        for billing_ref_elem in root.children_by_name("BillingReference"):
            billing_ref = self._parse_billing_reference(billing_ref_elem)
            if billing_ref:
                credit_note.billing_references.append(billing_ref)

        # Parse tax totals
        for tax_total_elem in root.children_by_name("TaxTotal"):
            tax_total = self._parse_tax_total(tax_total_elem, currency)
            if tax_total:
                credit_note.tax_total.append(tax_total)

        credit_note._source_format = "ubl"
        credit_note._source_version = "2.5"
        return credit_note

    def _parse_supplier_party(self, elem: "ParsedElement") -> SupplierParty:
        """Parse AccountingSupplierParty element."""
        party_elem = elem.first_child_by_name("Party")
        party = self._parse_party(party_elem) if party_elem else Party()
        return SupplierParty(party=party)

    def _parse_customer_party(self, elem: "ParsedElement") -> CustomerParty:
        """Parse AccountingCustomerParty element."""
        party_elem = elem.first_child_by_name("Party")
        party = self._parse_party(party_elem) if party_elem else Party()
        return CustomerParty(party=party)

    def _parse_party(self, elem: "ParsedElement") -> Party:
        """Parse Party element."""
        party = Party()

        for name_elem in elem.children_by_name("PartyName"):
            name = get_child_value(name_elem, "Name")
            if name:
                party.party_names.append(PartyName(name=name))

        for id_elem in elem.children_by_name("PartyIdentification"):
            identifier = get_identifier_with_scheme(id_elem, "ID")
            if identifier:
                party.party_identifications.append(PartyIdentification(id=identifier))

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

    def _parse_monetary_total(self, elem: "ParsedElement") -> MonetaryTotal:
        """Parse LegalMonetaryTotal element."""
        return MonetaryTotal(
            line_extension_amount=get_amount_with_currency(elem, "LineExtensionAmount"),
            tax_exclusive_amount=get_amount_with_currency(elem, "TaxExclusiveAmount"),
            tax_inclusive_amount=get_amount_with_currency(elem, "TaxInclusiveAmount"),
            allowance_total_amount=get_amount_with_currency(elem, "AllowanceTotalAmount"),
            charge_total_amount=get_amount_with_currency(elem, "ChargeTotalAmount"),
            payable_amount=get_amount_with_currency(elem, "PayableAmount"),
        )

    def _parse_billing_reference(self, elem: "ParsedElement") -> BillingReference | None:
        """Parse BillingReference element."""
        invoice_ref_elem = elem.first_child_by_name("InvoiceDocumentReference")
        if invoice_ref_elem:
            return BillingReference(
                invoice_document_reference=DocumentReference(
                    id=get_child_value(invoice_ref_elem, "ID") or "",
                    issue_date=parse_date(get_child_value(invoice_ref_elem, "IssueDate")),
                )
            )
        return None

    def _parse_tax_total(self, elem: "ParsedElement", currency: str) -> TaxTotal | None:
        """Parse TaxTotal element."""
        tax_amount = get_amount_with_currency(elem, "TaxAmount")
        if not tax_amount:
            return None

        return TaxTotal(tax_amount=tax_amount)

    def _parse_credit_note_line(
        self, elem: "ParsedElement", currency: str
    ) -> CreditNoteLine | None:
        """Parse CreditNoteLine element."""
        line_id = get_child_value(elem, "ID") or "1"

        quantity = get_quantity_with_unit(elem, "CreditedQuantity")
        if not quantity:
            quantity = Quantity(value=Decimal("1"), unit_code="EA")

        line_amount = get_amount_with_currency(elem, "LineExtensionAmount")
        if not line_amount:
            line_amount = Amount(value=Decimal("0"), currency=currency)

        item_elem = elem.first_child_by_name("Item")
        item = self._parse_item(item_elem) if item_elem else Item()

        price = None
        price_elem = elem.first_child_by_name("Price")
        if price_elem:
            price_amount = get_amount_with_currency(price_elem, "PriceAmount")
            if price_amount:
                price = Price(price_amount=price_amount)

        return CreditNoteLine(
            id=line_id,
            credited_quantity=quantity,
            line_extension_amount=line_amount,
            item=item,
            price=price,
        )

    def _parse_item(self, elem: "ParsedElement") -> Item:
        """Parse Item element."""
        item = Item(
            description=get_child_value(elem, "Description"),
            name=get_child_value(elem, "Name"),
        )

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

    def from_semantic(self, model: CreditNote) -> dict:
        """Convert semantic CreditNote to UBL structure."""
        ns_cn = "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"
        ns_cac = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
        ns_cbc = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"

        doc = {
            "CreditNote": {
                "@xmlns": ns_cn,
                "@xmlns:cac": ns_cac,
                "@xmlns:cbc": ns_cbc,
                "cbc:ID": model.id,
                "cbc:IssueDate": format_date(model.issue_date),
                "cbc:DocumentCurrencyCode": model.document_currency_code,
            }
        }

        credit_note = doc["CreditNote"]

        if model.uuid:
            credit_note["cbc:UUID"] = model.uuid

        if model.issue_time:
            credit_note["cbc:IssueTime"] = format_time(model.issue_time)

        if model.credit_note_type_code:
            credit_note["cbc:CreditNoteTypeCode"] = model.credit_note_type_code

        # Notes
        for note in model.note:
            if "cbc:Note" not in credit_note:
                credit_note["cbc:Note"] = []
            credit_note["cbc:Note"].append(note)

        # Billing references
        if model.billing_references:
            credit_note["cac:BillingReference"] = [
                self._build_billing_reference(ref) for ref in model.billing_references
            ]

        # Parties
        credit_note["cac:AccountingSupplierParty"] = self._build_supplier_party(
            model.accounting_supplier_party
        )
        credit_note["cac:AccountingCustomerParty"] = self._build_customer_party(
            model.accounting_customer_party
        )

        # Tax totals
        if model.tax_total:
            credit_note["cac:TaxTotal"] = [self._build_tax_total(tt) for tt in model.tax_total]

        # Monetary total
        credit_note["cac:LegalMonetaryTotal"] = self._build_monetary_total(
            model.legal_monetary_total
        )

        # Lines
        if model.credit_note_lines:
            credit_note["cac:CreditNoteLine"] = [
                self._build_credit_note_line(line, model.document_currency_code)
                for line in model.credit_note_lines
            ]

        return doc

    def _build_billing_reference(self, ref: BillingReference) -> dict:
        """Build BillingReference structure."""
        result = {}
        if ref.invoice_document_reference:
            inv_ref = {"cbc:ID": ref.invoice_document_reference.id}
            if ref.invoice_document_reference.issue_date:
                inv_ref["cbc:IssueDate"] = format_date(ref.invoice_document_reference.issue_date)
            result["cac:InvoiceDocumentReference"] = inv_ref
        return result

    def _build_supplier_party(self, party: SupplierParty) -> dict:
        """Build AccountingSupplierParty structure."""
        return {"cac:Party": self._build_party(party.party)}

    def _build_customer_party(self, party: CustomerParty) -> dict:
        """Build AccountingCustomerParty structure."""
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
            if addr.city_name:
                addr_dict["cbc:CityName"] = addr.city_name
            if addr.postal_zone:
                addr_dict["cbc:PostalZone"] = addr.postal_zone
            if addr.country_code:
                addr_dict["cac:Country"] = {"cbc:IdentificationCode": addr.country_code}
            if addr_dict:
                result["cac:PostalAddress"] = addr_dict

        return result

    def _build_tax_total(self, tax_total: TaxTotal) -> dict:
        """Build TaxTotal structure."""
        return {
            "cbc:TaxAmount": {
                "@currencyID": tax_total.tax_amount.currency,
                "#text": str(tax_total.tax_amount.value),
            }
        }

    def _build_monetary_total(self, total: MonetaryTotal) -> dict:
        """Build LegalMonetaryTotal structure."""
        result = {}

        if total.line_extension_amount:
            result["cbc:LineExtensionAmount"] = {
                "@currencyID": total.line_extension_amount.currency,
                "#text": str(total.line_extension_amount.value),
            }

        if total.tax_exclusive_amount:
            result["cbc:TaxExclusiveAmount"] = {
                "@currencyID": total.tax_exclusive_amount.currency,
                "#text": str(total.tax_exclusive_amount.value),
            }

        if total.tax_inclusive_amount:
            result["cbc:TaxInclusiveAmount"] = {
                "@currencyID": total.tax_inclusive_amount.currency,
                "#text": str(total.tax_inclusive_amount.value),
            }

        if total.payable_amount:
            result["cbc:PayableAmount"] = {
                "@currencyID": total.payable_amount.currency,
                "#text": str(total.payable_amount.value),
            }

        return result

    def _build_credit_note_line(self, line: CreditNoteLine, currency: str) -> dict:
        """Build CreditNoteLine structure."""
        result = {
            "cbc:ID": line.id,
            "cbc:CreditedQuantity": {
                "@unitCode": line.credited_quantity.unit_code,
                "#text": str(line.credited_quantity.value),
            },
            "cbc:LineExtensionAmount": {
                "@currencyID": line.line_extension_amount.currency,
                "#text": str(line.line_extension_amount.value),
            },
            "cac:Item": self._build_item(line.item),
        }

        if line.price:
            result["cac:Price"] = {
                "cbc:PriceAmount": {
                    "@currencyID": line.price.price_amount.currency,
                    "#text": str(line.price.price_amount.value),
                }
            }

        return result

    def _build_item(self, item: Item) -> dict:
        """Build Item structure."""
        result = {}

        if item.description:
            result["cbc:Description"] = item.description

        if item.name:
            result["cbc:Name"] = item.name

        if item.sellers_item_identification:
            result["cac:SellersItemIdentification"] = {
                "cbc:ID": item.sellers_item_identification.id.value
            }

        return result
