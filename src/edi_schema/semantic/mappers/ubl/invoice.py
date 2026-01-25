"""
UBL Invoice Mapper.

Maps between UBL Invoice and semantic Invoice model.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from ...models import (
    Address,
    AllowanceCharge,
    Amount,
    Contact,
    CustomerParty,
    Delivery,
    Identifier,
    Invoice,
    InvoiceLine,
    Item,
    ItemIdentification,
    MonetaryTotal,
    OrderLineReference,
    OrderReference,
    Party,
    PartyIdentification,
    PartyName,
    PaymentMeans,
    PaymentTerms,
    Price,
    Quantity,
    SupplierParty,
    TaxCategory,
    TaxSubtotal,
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
    parse_decimal,
    parse_time,
)

if TYPE_CHECKING:
    from edi_schema.ubl.ast import ParsedDocument, ParsedElement


class UBLInvoiceMapper(SemanticMapper[Invoice]):
    """
    Maps UBL Invoice to/from semantic Invoice model.

    UBL Invoice Structure:
    - cbc:ID, cbc:UUID, cbc:IssueDate, cbc:IssueTime
    - cbc:InvoiceTypeCode
    - cbc:DocumentCurrencyCode
    - cbc:Note (multiple)
    - cac:OrderReference
    - cac:AccountingSupplierParty
    - cac:AccountingCustomerParty
    - cac:PayeeParty
    - cac:Delivery (multiple)
    - cac:PaymentMeans (multiple)
    - cac:PaymentTerms (multiple)
    - cac:AllowanceCharge (multiple)
    - cac:TaxTotal (multiple)
    - cac:LegalMonetaryTotal
    - cac:InvoiceLine (multiple)
    """

    @property
    def semantic_type(self) -> type[Invoice]:
        return Invoice

    @property
    def source_format(self) -> Format:
        return Format.UBL

    @property
    def transaction_id(self) -> str:
        return "Invoice"

    def to_semantic(self, source: "ParsedDocument") -> Invoice:
        """Convert UBL Invoice to semantic Invoice."""
        root = source.root

        if source.document_type != "Invoice":
            raise ValueError(f"Expected Invoice, got {source.document_type}")

        # Parse basic fields
        invoice_id = get_child_value(root, "ID") or ""
        issue_date = parse_date(get_child_value(root, "IssueDate"))
        if not issue_date:
            raise ValueError("Missing or invalid IssueDate")

        issue_time = parse_time(get_child_value(root, "IssueTime"))
        uuid = get_child_value(root, "UUID")
        currency = get_child_value(root, "DocumentCurrencyCode") or "USD"
        invoice_type = get_child_value(root, "InvoiceTypeCode")
        due_date = parse_date(get_child_value(root, "DueDate"))

        # Parties (required for Invoice)
        supplier_elem = root.find_child("AccountingSupplierParty")
        if supplier_elem:
            supplier = self._parse_supplier_party(supplier_elem)
        else:
            supplier = SupplierParty(party=Party())

        customer_elem = root.find_child("AccountingCustomerParty")
        if customer_elem:
            customer = self._parse_customer_party(customer_elem)
        else:
            customer = CustomerParty(party=Party())

        # Monetary total (required for Invoice)
        lmt_elem = root.find_child("LegalMonetaryTotal")
        if lmt_elem:
            monetary_total = self._parse_monetary_total(lmt_elem, currency)
        else:
            monetary_total = MonetaryTotal()

        # Create invoice
        invoice = Invoice(
            id=invoice_id,
            uuid=uuid,
            issue_date=issue_date,
            issue_time=issue_time,
            due_date=due_date,
            document_currency_code=currency,
            invoice_type_code=invoice_type,
            accounting_supplier_party=supplier,
            accounting_customer_party=customer,
            legal_monetary_total=monetary_total,
        )

        # Notes
        for note_elem in root.find_all_children("Note"):
            if note_elem.value:
                invoice.note.append(note_elem.value)

        # Order reference
        order_ref_elem = root.find_child("OrderReference")
        if order_ref_elem:
            invoice.order_reference = self._parse_order_reference(order_ref_elem)

        # Payee party
        payee_elem = root.find_child("PayeeParty")
        if payee_elem:
            invoice.payee_party = self._parse_party(payee_elem)

        # Delivery
        for del_elem in root.find_all_children("Delivery"):
            invoice.delivery.append(self._parse_delivery(del_elem))

        # Payment means
        for pm_elem in root.find_all_children("PaymentMeans"):
            means = self._parse_payment_means(pm_elem)
            if means:
                invoice.payment_means.append(means)

        # Payment terms
        for pt_elem in root.find_all_children("PaymentTerms"):
            terms = self._parse_payment_terms(pt_elem)
            if terms:
                invoice.payment_terms.append(terms)

        # Allowance charges
        for ac_elem in root.find_all_children("AllowanceCharge"):
            ac = self._parse_allowance_charge(ac_elem, currency)
            invoice.allowance_charges.append(ac)

        # Tax total
        for tax_elem in root.find_all_children("TaxTotal"):
            tax = self._parse_tax_total(tax_elem, currency)
            invoice.tax_total.append(tax)

        # Invoice lines
        for line_elem in root.find_all_children("InvoiceLine"):
            line = self._parse_invoice_line(line_elem, currency)
            invoice.invoice_lines.append(line)

        invoice.line_count = len(invoice.invoice_lines)

        # Source tracking
        invoice._source_format = "ubl"
        invoice._source_version = source.version

        return invoice

    def from_semantic(self, model: Invoice) -> dict:
        """Convert semantic Invoice to UBL Invoice structure."""
        ns_inv = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
        ns_cac = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
        ns_cbc = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"

        doc = {
            "Invoice": {
                "@xmlns": ns_inv,
                "@xmlns:cac": ns_cac,
                "@xmlns:cbc": ns_cbc,
                "cbc:ID": model.id,
                "cbc:IssueDate": format_date(model.issue_date),
                "cbc:DocumentCurrencyCode": model.document_currency_code,
            }
        }

        invoice = doc["Invoice"]

        if model.uuid:
            invoice["cbc:UUID"] = model.uuid

        if model.issue_time:
            invoice["cbc:IssueTime"] = format_time(model.issue_time)

        if model.due_date:
            invoice["cbc:DueDate"] = format_date(model.due_date)

        if model.invoice_type_code:
            invoice["cbc:InvoiceTypeCode"] = model.invoice_type_code

        # Notes
        if model.note:
            invoice["cbc:Note"] = model.note

        # Order reference
        if model.order_reference:
            invoice["cac:OrderReference"] = self._build_order_reference(model.order_reference)

        # Supplier
        invoice["cac:AccountingSupplierParty"] = self._build_supplier_party(
            model.accounting_supplier_party
        )

        # Customer
        invoice["cac:AccountingCustomerParty"] = self._build_customer_party(
            model.accounting_customer_party
        )

        # Payee
        if model.payee_party:
            invoice["cac:PayeeParty"] = self._build_party(model.payee_party)

        # Delivery
        if model.delivery:
            invoice["cac:Delivery"] = [
                self._build_delivery(d) for d in model.delivery
            ]

        # Payment means
        if model.payment_means:
            invoice["cac:PaymentMeans"] = [
                self._build_payment_means(pm) for pm in model.payment_means
            ]

        # Payment terms
        if model.payment_terms:
            invoice["cac:PaymentTerms"] = [
                self._build_payment_terms(pt) for pt in model.payment_terms
            ]

        # Allowance charges
        if model.allowance_charges:
            invoice["cac:AllowanceCharge"] = [
                self._build_allowance_charge(ac) for ac in model.allowance_charges
            ]

        # Tax total
        if model.tax_total:
            invoice["cac:TaxTotal"] = [
                self._build_tax_total(tt) for tt in model.tax_total
            ]

        # Legal monetary total
        invoice["cac:LegalMonetaryTotal"] = self._build_monetary_total(
            model.legal_monetary_total
        )

        # Invoice lines
        invoice["cac:InvoiceLine"] = [
            self._build_invoice_line(line) for line in model.invoice_lines
        ]

        return doc

    # Parse methods
    def _parse_customer_party(self, elem: "ParsedElement") -> CustomerParty:
        """Parse a CustomerParty element."""
        party_elem = elem.find_child("Party")
        party = self._parse_party(party_elem) if party_elem else Party()

        buyer_contact = None
        contact_elem = elem.find_child("BuyerContact")
        if contact_elem:
            buyer_contact = self._parse_contact(contact_elem)

        return CustomerParty(party=party, buyer_contact=buyer_contact)

    def _parse_supplier_party(self, elem: "ParsedElement") -> SupplierParty:
        """Parse a SupplierParty element."""
        party_elem = elem.find_child("Party")
        party = self._parse_party(party_elem) if party_elem else Party()

        seller_contact = None
        contact_elem = elem.find_child("SellerContact")
        if contact_elem:
            seller_contact = self._parse_contact(contact_elem)

        return SupplierParty(party=party, seller_contact=seller_contact)

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

    def _parse_order_reference(self, elem: "ParsedElement") -> OrderReference:
        """Parse an OrderReference element."""
        return OrderReference(
            id=get_child_value(elem, "ID") or "",
            sales_order_id=get_child_value(elem, "SalesOrderID"),
            issue_date=parse_date(get_child_value(elem, "IssueDate")),
        )

    def _parse_delivery(self, elem: "ParsedElement") -> Delivery:
        """Parse a Delivery element."""
        delivery = Delivery(
            actual_delivery_date=parse_date(get_child_value(elem, "ActualDeliveryDate")),
            actual_delivery_time=parse_time(get_child_value(elem, "ActualDeliveryTime")),
        )

        loc_elem = elem.find_child("DeliveryLocation")
        if loc_elem:
            addr_elem = loc_elem.find_child("Address")
            if addr_elem:
                delivery.delivery_location = self._parse_address(addr_elem)

        party_elem = elem.find_child("DeliveryParty")
        if party_elem:
            delivery.delivery_party = self._parse_party(party_elem)

        return delivery

    def _parse_payment_means(self, elem: "ParsedElement") -> PaymentMeans:
        """Parse a PaymentMeans element."""
        return PaymentMeans(
            payment_means_code=get_child_value(elem, "PaymentMeansCode"),
            payment_due_date=parse_date(get_child_value(elem, "PaymentDueDate")),
            payment_id=get_child_value(elem, "PaymentID"),
        )

    def _parse_payment_terms(self, elem: "ParsedElement") -> PaymentTerms:
        """Parse a PaymentTerms element."""
        return PaymentTerms(
            note=get_child_value(elem, "Note"),
            payment_due_date=parse_date(get_child_value(elem, "PaymentDueDate")),
            settlement_discount_percent=parse_decimal(
                get_child_value(elem, "SettlementDiscountPercent")
            ),
        )

    def _parse_allowance_charge(self, elem: "ParsedElement", currency: str) -> AllowanceCharge:
        """Parse an AllowanceCharge element."""
        indicator = get_child_value(elem, "ChargeIndicator")
        is_charge = indicator and indicator.lower() == "true"

        amount_val, amount_curr = get_amount_with_currency(elem, "Amount")

        return AllowanceCharge(
            charge_indicator=is_charge,
            amount=Amount(value=amount_val or Decimal("0"), currency=amount_curr or currency),
            allowance_charge_reason=get_child_value(elem, "AllowanceChargeReason"),
            allowance_charge_reason_code=get_child_value(elem, "AllowanceChargeReasonCode"),
            multiplier_factor_numeric=parse_decimal(
                get_child_value(elem, "MultiplierFactorNumeric")
            ),
        )

    def _parse_tax_total(self, elem: "ParsedElement", currency: str) -> TaxTotal:
        """Parse a TaxTotal element."""
        amount_val, amount_curr = get_amount_with_currency(elem, "TaxAmount")

        tax_total = TaxTotal(
            tax_amount=Amount(value=amount_val or Decimal("0"), currency=amount_curr or currency)
        )

        for subtotal_elem in elem.find_all_children("TaxSubtotal"):
            subtotal = self._parse_tax_subtotal(subtotal_elem, currency)
            tax_total.tax_subtotals.append(subtotal)

        return tax_total

    def _parse_tax_subtotal(self, elem: "ParsedElement", currency: str) -> TaxSubtotal:
        """Parse a TaxSubtotal element."""
        taxable_val, taxable_curr = get_amount_with_currency(elem, "TaxableAmount")
        tax_val, tax_curr = get_amount_with_currency(elem, "TaxAmount")

        cat_elem = elem.find_child("TaxCategory")
        category = TaxCategory()
        if cat_elem:
            category.id = get_child_value(cat_elem, "ID")
            category.percent = parse_decimal(get_child_value(cat_elem, "Percent"))
            scheme_elem = cat_elem.find_child("TaxScheme")
            if scheme_elem:
                category.tax_scheme = get_child_value(scheme_elem, "ID")

        taxable_amt = None
        if taxable_val:
            taxable_amt = Amount(
                value=taxable_val or Decimal("0"),
                currency=taxable_curr or currency,
            )
        tax_amt = Amount(
            value=tax_val or Decimal("0"),
            currency=tax_curr or currency,
        )
        return TaxSubtotal(
            taxable_amount=taxable_amt,
            tax_amount=tax_amt,
            percent=category.percent,
            tax_category=category,
        )

    def _parse_monetary_total(self, elem: "ParsedElement", currency: str) -> MonetaryTotal:
        """Parse a MonetaryTotal element."""
        def get_amt(tag: str) -> Amount | None:
            val, curr = get_amount_with_currency(elem, tag)
            return Amount(value=val, currency=curr or currency) if val else None

        return MonetaryTotal(
            line_extension_amount=get_amt("LineExtensionAmount"),
            tax_exclusive_amount=get_amt("TaxExclusiveAmount"),
            tax_inclusive_amount=get_amt("TaxInclusiveAmount"),
            allowance_total_amount=get_amt("AllowanceTotalAmount"),
            charge_total_amount=get_amt("ChargeTotalAmount"),
            payable_rounding_amount=get_amt("PayableRoundingAmount"),
            payable_amount=get_amt("PayableAmount"),
        )

    def _parse_invoice_line(self, elem: "ParsedElement", currency: str) -> InvoiceLine:
        """Parse an InvoiceLine element."""
        line_id = get_child_value(elem, "ID") or "1"
        qty_val, qty_unit = get_quantity_with_unit(elem, "InvoicedQuantity")
        line_ext_val, line_ext_curr = get_amount_with_currency(elem, "LineExtensionAmount")

        # Item
        item_elem = elem.find_child("Item")
        item = self._parse_item(item_elem)

        # Price
        price_elem = elem.find_child("Price")
        price = None
        if price_elem:
            price = self._parse_price(price_elem, currency)

        inv_qty = Quantity(value=qty_val or Decimal("0"), unit_code=qty_unit or "EA")
        line_ext_amt = Amount(
            value=line_ext_val or Decimal("0"),
            currency=line_ext_curr or currency,
        )
        line = InvoiceLine(
            id=line_id,
            invoiced_quantity=inv_qty,
            line_extension_amount=line_ext_amt,
            item=item,
            price=price,
        )

        # Order line reference
        olr_elem = elem.find_child("OrderLineReference")
        if olr_elem:
            line.order_line_references.append(self._parse_order_line_reference(olr_elem))

        # Allowance charges
        for ac_elem in elem.find_all_children("AllowanceCharge"):
            line.allowance_charges.append(self._parse_allowance_charge(ac_elem, currency))

        # Tax
        for tax_elem in elem.find_all_children("TaxTotal"):
            line.tax_total.append(self._parse_tax_total(tax_elem, currency))

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

        return item

    def _parse_price(self, elem: "ParsedElement", currency: str) -> Price:
        """Parse a Price element."""
        amount_val, amount_curr = get_amount_with_currency(elem, "PriceAmount")
        base_qty, base_unit = get_quantity_with_unit(elem, "BaseQuantity")

        price_amt = Amount(
            value=amount_val or Decimal("0"),
            currency=amount_curr or currency,
        )
        base_qty_obj = None
        if base_qty:
            base_qty_obj = Quantity(value=base_qty, unit_code=base_unit or "EA")
        return Price(price_amount=price_amt, base_quantity=base_qty_obj)

    # Build methods
    def _build_customer_party(self, cp: CustomerParty) -> dict:
        """Build a CustomerParty element."""
        result = {"cac:Party": self._build_party(cp.party)}
        if cp.buyer_contact:
            result["cac:BuyerContact"] = self._build_contact(cp.buyer_contact)
        return result

    def _build_supplier_party(self, sp: SupplierParty) -> dict:
        """Build a SupplierParty element."""
        result = {"cac:Party": self._build_party(sp.party)}
        if sp.seller_contact:
            result["cac:SellerContact"] = self._build_contact(sp.seller_contact)
        return result

    def _build_party(self, party: Party) -> dict:
        """Build a Party element."""
        result = {}

        if party.party_identifications:
            pi_list = []
            for pi in party.party_identifications:
                if pi.id.scheme_id:
                    pi_list.append({
                        "cbc:ID": {"@schemeID": pi.id.scheme_id, "#text": pi.id.value}
                    })
                else:
                    pi_list.append({"cbc:ID": pi.id.value})
            result["cac:PartyIdentification"] = pi_list

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
        if addr.country_subentity:
            result["cbc:CountrySubentity"] = addr.country_subentity
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

    def _build_order_reference(self, ref: OrderReference) -> dict:
        """Build an OrderReference element."""
        result = {"cbc:ID": ref.id}
        if ref.sales_order_id:
            result["cbc:SalesOrderID"] = ref.sales_order_id
        if ref.issue_date:
            result["cbc:IssueDate"] = format_date(ref.issue_date)
        return result

    def _build_delivery(self, delivery: Delivery) -> dict:
        """Build a Delivery element."""
        result = {}
        if delivery.actual_delivery_date:
            result["cbc:ActualDeliveryDate"] = format_date(delivery.actual_delivery_date)
        if delivery.delivery_location:
            addr = self._build_address(delivery.delivery_location)
            result["cac:DeliveryLocation"] = {"cac:Address": addr}
        if delivery.delivery_party:
            result["cac:DeliveryParty"] = self._build_party(delivery.delivery_party)
        return result

    def _build_payment_means(self, pm: PaymentMeans) -> dict:
        """Build a PaymentMeans element."""
        result = {}
        if pm.payment_means_code:
            result["cbc:PaymentMeansCode"] = pm.payment_means_code
        if pm.payment_due_date:
            result["cbc:PaymentDueDate"] = format_date(pm.payment_due_date)
        if pm.payment_id:
            result["cbc:PaymentID"] = pm.payment_id
        return result

    def _build_payment_terms(self, pt: PaymentTerms) -> dict:
        """Build a PaymentTerms element."""
        result = {}
        if pt.note:
            result["cbc:Note"] = pt.note
        if pt.payment_due_date:
            result["cbc:PaymentDueDate"] = format_date(pt.payment_due_date)
        return result

    def _build_allowance_charge(self, ac: AllowanceCharge) -> dict:
        """Build an AllowanceCharge element."""
        result = {
            "cbc:ChargeIndicator": "true" if ac.charge_indicator else "false",
            "cbc:Amount": {
                "@currencyID": ac.amount.currency,
                "#text": str(ac.amount.value),
            },
        }
        if ac.allowance_charge_reason:
            result["cbc:AllowanceChargeReason"] = ac.allowance_charge_reason
        return result

    def _build_tax_total(self, tt: TaxTotal) -> dict:
        """Build a TaxTotal element."""
        result = {
            "cbc:TaxAmount": {
                "@currencyID": tt.tax_amount.currency,
                "#text": str(tt.tax_amount.value),
            }
        }
        if tt.tax_subtotals:
            result["cac:TaxSubtotal"] = [
                self._build_tax_subtotal(st) for st in tt.tax_subtotals
            ]
        return result

    def _build_tax_subtotal(self, st: TaxSubtotal) -> dict:
        """Build a TaxSubtotal element."""
        result = {
            "cbc:TaxAmount": {
                "@currencyID": st.tax_amount.currency,
                "#text": str(st.tax_amount.value),
            }
        }
        if st.taxable_amount:
            result["cbc:TaxableAmount"] = {
                "@currencyID": st.taxable_amount.currency,
                "#text": str(st.taxable_amount.value),
            }
        if st.tax_category:
            result["cac:TaxCategory"] = {"cbc:ID": st.tax_category.id or ""}
        else:
            result["cac:TaxCategory"] = {}
        return result

    def _build_monetary_total(self, mt: MonetaryTotal) -> dict:
        """Build a MonetaryTotal element."""
        result = {}

        def add_amount(key: str, amount: Amount | None):
            if amount:
                result[key] = {"@currencyID": amount.currency, "#text": str(amount.value)}

        add_amount("cbc:LineExtensionAmount", mt.line_extension_amount)
        add_amount("cbc:TaxExclusiveAmount", mt.tax_exclusive_amount)
        add_amount("cbc:TaxInclusiveAmount", mt.tax_inclusive_amount)
        add_amount("cbc:PayableAmount", mt.payable_amount)
        return result

    def _build_invoice_line(self, line: InvoiceLine) -> dict:
        """Build an InvoiceLine element."""
        qty = line.invoiced_quantity
        amt = line.line_extension_amount
        result = {
            "cbc:ID": line.id,
            "cbc:InvoicedQuantity": {
                "@unitCode": qty.unit_code,
                "#text": str(qty.value),
            },
            "cbc:LineExtensionAmount": {
                "@currencyID": amt.currency,
                "#text": str(amt.value),
            },
            "cac:Item": self._build_item(line.item),
        }
        if line.price:
            result["cac:Price"] = self._build_price(line.price)
        return result

    def _build_item(self, item: Item) -> dict:
        """Build an Item element."""
        result = {}
        if item.description:
            result["cbc:Description"] = item.description
        if item.name:
            result["cbc:Name"] = item.name
        return result

    def _build_price(self, price: Price) -> dict:
        """Build a Price element."""
        return {
            "cbc:PriceAmount": {
                "@currencyID": price.price_amount.currency,
                "#text": str(price.price_amount.value),
            }
        }
