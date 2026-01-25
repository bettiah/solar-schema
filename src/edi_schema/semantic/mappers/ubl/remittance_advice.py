"""
UBL RemittanceAdvice Mapper.

Maps between UBL RemittanceAdvice and semantic RemittanceAdvice model.
"""

from typing import TYPE_CHECKING

from ...models import (
    Address,
    BillingReference,
    CustomerParty,
    DocumentReference,
    Party,
    PartyIdentification,
    PartyName,
    PaymentMeans,
    Period,
    RemittanceAdvice,
    RemittanceAdviceLine,
    SupplierParty,
)
from ..base import Format, SemanticMapper
from .utils import (
    format_date,
    format_time,
    get_amount_with_currency,
    get_child_value,
    get_identifier_with_scheme,
    parse_date,
    parse_time,
)

if TYPE_CHECKING:
    from edi_schema.ubl.ast import ParsedDocument, ParsedElement


class UBLRemittanceAdviceMapper(SemanticMapper[RemittanceAdvice]):
    """
    Maps UBL RemittanceAdvice to/from semantic RemittanceAdvice model.

    UBL RemittanceAdvice Structure:
    - cbc:ID, cbc:UUID, cbc:IssueDate, cbc:IssueTime
    - cbc:DocumentCurrencyCode
    - cbc:TotalDebitAmount, cbc:TotalCreditAmount, cbc:TotalPaymentAmount
    - cac:AccountingCustomerParty (payer)
    - cac:AccountingSupplierParty (payee)
    - cac:PayeeParty
    - cac:PaymentMeans
    - cac:RemittanceAdviceLine (multiple)
    """

    @property
    def semantic_type(self) -> type[RemittanceAdvice]:
        return RemittanceAdvice

    @property
    def source_format(self) -> Format:
        return Format.UBL

    @property
    def transaction_id(self) -> str:
        return "RemittanceAdvice"

    def to_semantic(self, source: "ParsedDocument") -> RemittanceAdvice:
        """Convert UBL RemittanceAdvice to semantic RemittanceAdvice."""
        root = source.root

        # Check document type
        if source.document_type != "RemittanceAdvice":
            raise ValueError(f"Expected RemittanceAdvice, got {source.document_type}")

        # Parse basic fields
        remittance_id = get_child_value(root, "ID") or ""
        issue_date = parse_date(get_child_value(root, "IssueDate"))
        if not issue_date:
            raise ValueError("Missing or invalid IssueDate")

        issue_time = parse_time(get_child_value(root, "IssueTime"))
        uuid = get_child_value(root, "UUID")
        currency = get_child_value(root, "DocumentCurrencyCode") or "USD"

        # Create remittance advice
        remittance = RemittanceAdvice(
            id=remittance_id,
            issue_date=issue_date,
            issue_time=issue_time,
            uuid=uuid,
            document_currency_code=currency,
            remittance_advice_lines=[],
        )

        # Parse amounts
        remittance.total_debit_amount = get_amount_with_currency(root, "TotalDebitAmount")
        remittance.total_credit_amount = get_amount_with_currency(root, "TotalCreditAmount")
        remittance.total_payment_amount = get_amount_with_currency(root, "TotalPaymentAmount")

        # Parse notes
        for note_elem in root.children_by_name("Note"):
            note_text = note_elem.value
            if note_text:
                remittance.note.append(note_text)

        # Parse parties
        customer_elem = root.first_child_by_name("AccountingCustomerParty")
        if customer_elem:
            remittance.accounting_customer_party = self._parse_customer_party(customer_elem)

        supplier_elem = root.first_child_by_name("AccountingSupplierParty")
        if supplier_elem:
            remittance.accounting_supplier_party = self._parse_supplier_party(supplier_elem)

        payee_elem = root.first_child_by_name("PayeeParty")
        if payee_elem:
            remittance.payee_party = self._parse_party(payee_elem)

        # Parse payment means
        payment_means_elem = root.first_child_by_name("PaymentMeans")
        if payment_means_elem:
            remittance.payment_means = self._parse_payment_means(payment_means_elem)

        # Parse remittance lines
        for line_elem in root.children_by_name("RemittanceAdviceLine"):
            line = self._parse_remittance_line(line_elem, currency)
            if line:
                remittance.remittance_advice_lines.append(line)

        remittance.line_count = len(remittance.remittance_advice_lines)

        remittance._source_format = "ubl"
        remittance._source_version = "2.5"
        return remittance

    def _parse_customer_party(self, elem: "ParsedElement") -> CustomerParty:
        """Parse AccountingCustomerParty element."""
        party_elem = elem.first_child_by_name("Party")
        party = self._parse_party(party_elem) if party_elem else Party()
        return CustomerParty(party=party)

    def _parse_supplier_party(self, elem: "ParsedElement") -> SupplierParty:
        """Parse AccountingSupplierParty element."""
        party_elem = elem.first_child_by_name("Party")
        party = self._parse_party(party_elem) if party_elem else Party()
        return SupplierParty(party=party)

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
                city_name=get_child_value(addr_elem, "CityName"),
                postal_zone=get_child_value(addr_elem, "PostalZone"),
            )

        return party

    def _parse_payment_means(self, elem: "ParsedElement") -> PaymentMeans:
        """Parse PaymentMeans element."""
        return PaymentMeans(
            payment_means_code=get_child_value(elem, "PaymentMeansCode"),
            payment_id=get_child_value(elem, "PaymentID"),
        )

    def _parse_remittance_line(
        self, elem: "ParsedElement", currency: str
    ) -> RemittanceAdviceLine | None:
        """Parse RemittanceAdviceLine element."""
        line_id = get_child_value(elem, "ID") or "1"

        line = RemittanceAdviceLine(
            id=line_id,
            debit_line_amount=get_amount_with_currency(elem, "DebitLineAmount"),
            credit_line_amount=get_amount_with_currency(elem, "CreditLineAmount"),
            balance_amount=get_amount_with_currency(elem, "BalanceAmount"),
        )

        # Parse notes
        for note_elem in elem.children_by_name("Note"):
            note_text = note_elem.value
            if note_text:
                line.note.append(note_text)

        # Parse billing references
        for billing_ref_elem in elem.children_by_name("BillingReference"):
            billing_ref = self._parse_billing_reference(billing_ref_elem)
            if billing_ref:
                line.billing_references.append(billing_ref)

        # Parse invoice period
        for period_elem in elem.children_by_name("InvoicePeriod"):
            period = self._parse_period(period_elem)
            if period:
                line.invoice_period.append(period)

        return line

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

    def _parse_period(self, elem: "ParsedElement") -> Period | None:
        """Parse Period element."""
        start_date = parse_date(get_child_value(elem, "StartDate"))
        end_date = parse_date(get_child_value(elem, "EndDate"))
        if start_date or end_date:
            return Period(start_date=start_date, end_date=end_date)
        return None

    def from_semantic(self, model: RemittanceAdvice) -> dict:
        """Convert semantic RemittanceAdvice to UBL structure."""
        ns_ra = "urn:oasis:names:specification:ubl:schema:xsd:RemittanceAdvice-2"
        ns_cac = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
        ns_cbc = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"

        doc = {
            "RemittanceAdvice": {
                "@xmlns": ns_ra,
                "@xmlns:cac": ns_cac,
                "@xmlns:cbc": ns_cbc,
                "cbc:ID": model.id,
                "cbc:IssueDate": format_date(model.issue_date),
                "cbc:DocumentCurrencyCode": model.document_currency_code,
            }
        }

        advice = doc["RemittanceAdvice"]

        if model.uuid:
            advice["cbc:UUID"] = model.uuid

        if model.issue_time:
            advice["cbc:IssueTime"] = format_time(model.issue_time)

        # Notes
        for note in model.note:
            if "cbc:Note" not in advice:
                advice["cbc:Note"] = []
            advice["cbc:Note"].append(note)

        # Amounts
        if model.total_debit_amount:
            advice["cbc:TotalDebitAmount"] = {
                "@currencyID": model.total_debit_amount.currency,
                "#text": str(model.total_debit_amount.value),
            }

        if model.total_credit_amount:
            advice["cbc:TotalCreditAmount"] = {
                "@currencyID": model.total_credit_amount.currency,
                "#text": str(model.total_credit_amount.value),
            }

        if model.total_payment_amount:
            advice["cbc:TotalPaymentAmount"] = {
                "@currencyID": model.total_payment_amount.currency,
                "#text": str(model.total_payment_amount.value),
            }

        # Parties
        if model.accounting_customer_party:
            advice["cac:AccountingCustomerParty"] = self._build_customer_party(
                model.accounting_customer_party
            )

        if model.accounting_supplier_party:
            advice["cac:AccountingSupplierParty"] = self._build_supplier_party(
                model.accounting_supplier_party
            )

        if model.payee_party:
            advice["cac:PayeeParty"] = self._build_party(model.payee_party)

        # Payment means
        if model.payment_means:
            advice["cac:PaymentMeans"] = self._build_payment_means(model.payment_means)

        # Lines
        if model.remittance_advice_lines:
            advice["cac:RemittanceAdviceLine"] = [
                self._build_remittance_line(line, model.document_currency_code)
                for line in model.remittance_advice_lines
            ]

        return doc

    def _build_customer_party(self, party: CustomerParty) -> dict:
        """Build AccountingCustomerParty structure."""
        return {"cac:Party": self._build_party(party.party)}

    def _build_supplier_party(self, party: SupplierParty) -> dict:
        """Build AccountingSupplierParty structure."""
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
            if addr_dict:
                result["cac:PostalAddress"] = addr_dict

        return result

    def _build_payment_means(self, payment_means: PaymentMeans) -> dict:
        """Build PaymentMeans structure."""
        result = {}
        if payment_means.payment_means_code:
            result["cbc:PaymentMeansCode"] = payment_means.payment_means_code
        if payment_means.payment_id:
            result["cbc:PaymentID"] = payment_means.payment_id
        return result

    def _build_remittance_line(self, line: RemittanceAdviceLine, currency: str) -> dict:
        """Build RemittanceAdviceLine structure."""
        result = {"cbc:ID": line.id}

        if line.debit_line_amount:
            result["cbc:DebitLineAmount"] = {
                "@currencyID": line.debit_line_amount.currency,
                "#text": str(line.debit_line_amount.value),
            }

        if line.credit_line_amount:
            result["cbc:CreditLineAmount"] = {
                "@currencyID": line.credit_line_amount.currency,
                "#text": str(line.credit_line_amount.value),
            }

        if line.balance_amount:
            result["cbc:BalanceAmount"] = {
                "@currencyID": line.balance_amount.currency,
                "#text": str(line.balance_amount.value),
            }

        # Billing references
        if line.billing_references:
            result["cac:BillingReference"] = [
                self._build_billing_reference(ref) for ref in line.billing_references
            ]

        return result

    def _build_billing_reference(self, ref: BillingReference) -> dict:
        """Build BillingReference structure."""
        result = {}
        if ref.invoice_document_reference:
            inv_ref = {"cbc:ID": ref.invoice_document_reference.id}
            if ref.invoice_document_reference.issue_date:
                inv_ref["cbc:IssueDate"] = format_date(ref.invoice_document_reference.issue_date)
            result["cac:InvoiceDocumentReference"] = inv_ref
        return result
