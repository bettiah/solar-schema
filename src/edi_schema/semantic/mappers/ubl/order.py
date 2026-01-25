"""
UBL Order Mapper.

Maps between UBL Order and semantic Order model.
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
    Item,
    ItemIdentification,
    Order,
    OrderLine,
    Party,
    PartyIdentification,
    PartyName,
    PaymentTerms,
    Period,
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


class UBLOrderMapper(SemanticMapper[Order]):
    """
    Maps UBL Order to/from semantic Order model.

    UBL Order Structure:
    - cbc:ID, cbc:UUID, cbc:IssueDate, cbc:IssueTime
    - cbc:DocumentCurrencyCode
    - cbc:Note (multiple)
    - cac:ValidityPeriod
    - cac:BuyerCustomerParty
    - cac:SellerSupplierParty
    - cac:Delivery (multiple)
    - cac:PaymentTerms (multiple)
    - cac:TaxTotal (multiple)
    - cac:AnticipatedMonetaryTotal
    - cac:OrderLine (multiple)
    """

    @property
    def semantic_type(self) -> type[Order]:
        return Order

    @property
    def source_format(self) -> Format:
        return Format.UBL

    @property
    def transaction_id(self) -> str:
        return "Order"

    def to_semantic(self, source: "ParsedDocument") -> Order:
        """Convert UBL Order to semantic Order."""
        root = source.root

        # Check document type
        if source.document_type != "Order":
            raise ValueError(f"Expected Order, got {source.document_type}")

        # Parse basic fields
        order_id = get_child_value(root, "ID") or ""
        issue_date = parse_date(get_child_value(root, "IssueDate"))
        if not issue_date:
            raise ValueError("Missing or invalid IssueDate")

        issue_time = parse_time(get_child_value(root, "IssueTime"))
        uuid = get_child_value(root, "UUID")
        currency = get_child_value(root, "DocumentCurrencyCode") or "USD"
        order_type = get_child_value(root, "OrderTypeCode")

        # Create order
        order = Order(
            id=order_id,
            uuid=uuid,
            issue_date=issue_date,
            issue_time=issue_time,
            document_currency_code=currency,
            order_type_code=order_type,
        )

        # Notes
        for note_elem in root.find_all_children("Note"):
            if note_elem.value:
                order.note.append(note_elem.value)

        # Validity period
        validity = root.find_child("ValidityPeriod")
        if validity:
            order.validity_period = self._parse_period(validity)

        # Parties
        buyer = root.find_child("BuyerCustomerParty")
        if buyer:
            order.buyer_customer_party = self._parse_customer_party(buyer)

        seller = root.find_child("SellerSupplierParty")
        if seller:
            order.seller_supplier_party = self._parse_supplier_party(seller)

        # Delivery
        for delivery_elem in root.find_all_children("Delivery"):
            order.delivery.append(self._parse_delivery(delivery_elem))

        # Payment terms
        for pt_elem in root.find_all_children("PaymentTerms"):
            terms = self._parse_payment_terms(pt_elem)
            if terms:
                order.payment_terms.append(terms)

        # Tax total
        for tax_elem in root.find_all_children("TaxTotal"):
            tax = self._parse_tax_total(tax_elem, currency)
            if tax:
                order.tax_total.append(tax)

        # Anticipated monetary total
        amt = root.find_child("AnticipatedMonetaryTotal")
        if amt:
            order.anticipated_monetary_total = self._parse_monetary_total(amt, currency)

        # Order lines
        for line_elem in root.find_all_children("OrderLine"):
            line = self._parse_order_line(line_elem, currency)
            order.order_lines.append(line)

        order.line_count = len(order.order_lines)

        # Source tracking
        order._source_format = "ubl"
        order._source_version = source.version

        return order

    def from_semantic(self, model: Order) -> dict:
        """
        Convert semantic Order to UBL Order structure.

        Returns a dictionary that can be used to generate UBL XML.
        """
        ns_order = "urn:oasis:names:specification:ubl:schema:xsd:Order-2"
        ns_cac = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
        ns_cbc = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"

        doc = {
            "Order": {
                "@xmlns": ns_order,
                "@xmlns:cac": ns_cac,
                "@xmlns:cbc": ns_cbc,
                "cbc:ID": model.id,
                "cbc:IssueDate": format_date(model.issue_date),
                "cbc:DocumentCurrencyCode": model.document_currency_code,
            }
        }

        order = doc["Order"]

        if model.uuid:
            order["cbc:UUID"] = model.uuid

        if model.issue_time:
            order["cbc:IssueTime"] = format_time(model.issue_time)

        if model.order_type_code:
            order["cbc:OrderTypeCode"] = model.order_type_code

        # Notes
        if model.note:
            order["cbc:Note"] = model.note

        # Validity period
        if model.validity_period:
            order["cac:ValidityPeriod"] = self._build_period(model.validity_period)

        # Buyer
        if model.buyer_customer_party:
            order["cac:BuyerCustomerParty"] = self._build_customer_party(
                model.buyer_customer_party
            )

        # Seller
        if model.seller_supplier_party:
            order["cac:SellerSupplierParty"] = self._build_supplier_party(
                model.seller_supplier_party
            )

        # Delivery
        if model.delivery:
            order["cac:Delivery"] = [
                self._build_delivery(d) for d in model.delivery
            ]

        # Payment terms
        if model.payment_terms:
            order["cac:PaymentTerms"] = [
                self._build_payment_terms(pt) for pt in model.payment_terms
            ]

        # Tax total
        if model.tax_total:
            order["cac:TaxTotal"] = [
                self._build_tax_total(tt) for tt in model.tax_total
            ]

        # Anticipated monetary total
        if model.anticipated_monetary_total:
            order["cac:AnticipatedMonetaryTotal"] = self._build_monetary_total(
                model.anticipated_monetary_total
            )

        # Order lines
        order["cac:OrderLine"] = [
            self._build_order_line(line) for line in model.order_lines
        ]

        return doc

    def _parse_period(self, elem: "ParsedElement") -> Period:
        """Parse a Period element."""
        return Period(
            start_date=parse_date(get_child_value(elem, "StartDate")),
            end_date=parse_date(get_child_value(elem, "EndDate")),
            start_time=parse_time(get_child_value(elem, "StartTime")),
            end_time=parse_time(get_child_value(elem, "EndTime")),
        )

    def _parse_customer_party(self, elem: "ParsedElement") -> CustomerParty:
        """Parse a CustomerParty element."""
        party_elem = elem.find_child("Party")
        party = self._parse_party(party_elem) if party_elem else Party()

        buyer_contact = None
        contact_elem = elem.find_child("BuyerContact")
        if contact_elem:
            buyer_contact = self._parse_contact(contact_elem)

        delivery_contact = None
        dc_elem = elem.find_child("DeliveryContact")
        if dc_elem:
            delivery_contact = self._parse_contact(dc_elem)

        return CustomerParty(
            party=party,
            buyer_contact=buyer_contact,
            delivery_contact=delivery_contact,
        )

    def _parse_supplier_party(self, elem: "ParsedElement") -> SupplierParty:
        """Parse a SupplierParty element."""
        party_elem = elem.find_child("Party")
        party = self._parse_party(party_elem) if party_elem else Party()

        seller_contact = None
        contact_elem = elem.find_child("SellerContact")
        if contact_elem:
            seller_contact = self._parse_contact(contact_elem)

        return SupplierParty(
            party=party,
            seller_contact=seller_contact,
        )

    def _parse_party(self, elem: "ParsedElement | None") -> Party:
        """Parse a Party element."""
        if elem is None:
            return Party()

        party = Party()

        # Party identifications
        for pi_elem in elem.find_all_children("PartyIdentification"):
            id_val, scheme_id, scheme_agency = get_identifier_with_scheme(pi_elem, "ID")
            if id_val:
                party.party_identifications.append(
                    PartyIdentification(
                        id=Identifier(
                            value=id_val,
                            scheme_id=scheme_id,
                            scheme_agency_id=scheme_agency,
                        )
                    )
                )

        # Party names
        for pn_elem in elem.find_all_children("PartyName"):
            name = get_child_value(pn_elem, "Name")
            if name:
                party.party_names.append(PartyName(name=name))

        # Postal address
        addr_elem = elem.find_child("PostalAddress")
        if addr_elem:
            party.postal_address = self._parse_address(addr_elem)

        # Contact
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

    def _parse_delivery(self, elem: "ParsedElement") -> Delivery:
        """Parse a Delivery element."""
        delivery = Delivery()

        qty_val, qty_unit = get_quantity_with_unit(elem, "Quantity")
        if qty_val is not None:
            delivery.quantity = Quantity(value=qty_val, unit_code=qty_unit or "EA")

        delivery.actual_delivery_date = parse_date(
            get_child_value(elem, "ActualDeliveryDate")
        )
        delivery.actual_delivery_time = parse_time(
            get_child_value(elem, "ActualDeliveryTime")
        )
        delivery.latest_delivery_date = parse_date(
            get_child_value(elem, "LatestDeliveryDate")
        )
        delivery.tracking_id = get_child_value(elem, "TrackingID")

        # Delivery location
        loc_elem = elem.find_child("DeliveryLocation")
        if loc_elem:
            addr_elem = loc_elem.find_child("Address")
            if addr_elem:
                delivery.delivery_location = self._parse_address(addr_elem)

        # Delivery party
        party_elem = elem.find_child("DeliveryParty")
        if party_elem:
            delivery.delivery_party = self._parse_party(party_elem)

        # Requested period
        period_elem = elem.find_child("RequestedDeliveryPeriod")
        if period_elem:
            delivery.requested_delivery_period = self._parse_period(period_elem)

        return delivery

    def _parse_payment_terms(self, elem: "ParsedElement") -> PaymentTerms:
        """Parse a PaymentTerms element."""
        note_elem = elem.find_child("Note")

        return PaymentTerms(
            note=note_elem.value if note_elem else None,
            payment_due_date=parse_date(get_child_value(elem, "PaymentDueDate")),
            settlement_discount_percent=parse_decimal(
                get_child_value(elem, "SettlementDiscountPercent")
            ),
        )

    def _parse_tax_total(self, elem: "ParsedElement", currency: str) -> TaxTotal:
        """Parse a TaxTotal element."""
        amount_val, amount_curr = get_amount_with_currency(elem, "TaxAmount")

        tax_total = TaxTotal(
            tax_amount=Amount(
                value=amount_val or Decimal("0"),
                currency=amount_curr or currency,
            )
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

        return TaxSubtotal(
            taxable_amount=Amount(
                value=taxable_val or Decimal("0"),
                currency=taxable_curr or currency,
            ) if taxable_val else None,
            tax_amount=Amount(
                value=tax_val or Decimal("0"),
                currency=tax_curr or currency,
            ),
            percent=category.percent,
            tax_category=category,
        )

    def _parse_monetary_total(self, elem: "ParsedElement", currency: str):
        """Parse a MonetaryTotal element."""
        from ...models import MonetaryTotal

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

    def _parse_order_line(self, elem: "ParsedElement", currency: str) -> OrderLine:
        """Parse an OrderLine element."""
        line_item = elem.find_child("LineItem")
        if not line_item:
            raise ValueError("OrderLine missing LineItem")

        line_id = get_child_value(line_item, "ID") or "1"
        qty_val, qty_unit = get_quantity_with_unit(line_item, "Quantity")
        line_ext_val, line_ext_curr = get_amount_with_currency(
            line_item, "LineExtensionAmount"
        )

        # Item
        item_elem = line_item.find_child("Item")
        item = self._parse_item(item_elem)

        # Price
        price_elem = line_item.find_child("Price")
        price = None
        if price_elem:
            price = self._parse_price(price_elem, currency)

        line = OrderLine(
            id=line_id,
            quantity=Quantity(value=qty_val or Decimal("0"), unit_code=qty_unit or "EA"),
            item=item,
            price=price,
        )

        if line_ext_val is not None:
            line.line_extension_amount = Amount(
                value=line_ext_val,
                currency=line_ext_curr or currency,
            )

        # Allowance charges
        for ac_elem in line_item.find_all_children("AllowanceCharge"):
            ac = self._parse_allowance_charge(ac_elem, currency)
            if ac:
                line.allowance_charges.append(ac)

        # Tax
        for tax_elem in line_item.find_all_children("TaxTotal"):
            tax = self._parse_tax_total(tax_elem, currency)
            line.tax_total.append(tax)

        # Delivery
        for del_elem in line_item.find_all_children("Delivery"):
            delivery = self._parse_delivery(del_elem)
            line.delivery.append(delivery)

        return line

    def _parse_item(self, elem: "ParsedElement | None") -> Item:
        """Parse an Item element."""
        if elem is None:
            return Item()

        item = Item(
            description=get_child_value(elem, "Description"),
            name=get_child_value(elem, "Name"),
        )

        # Standard item identification
        std_elem = elem.find_child("StandardItemIdentification")
        if std_elem:
            id_val, scheme_id, _ = get_identifier_with_scheme(std_elem, "ID")
            if id_val:
                item.standard_item_identification = ItemIdentification(
                    id=Identifier(value=id_val, scheme_id=scheme_id)
                )

        # Seller's item identification
        seller_elem = elem.find_child("SellersItemIdentification")
        if seller_elem:
            id_val, scheme_id, _ = get_identifier_with_scheme(seller_elem, "ID")
            if id_val:
                item.sellers_item_identification = ItemIdentification(
                    id=Identifier(value=id_val, scheme_id=scheme_id)
                )

        # Buyer's item identification
        buyer_elem = elem.find_child("BuyersItemIdentification")
        if buyer_elem:
            id_val, scheme_id, _ = get_identifier_with_scheme(buyer_elem, "ID")
            if id_val:
                item.buyers_item_identification = ItemIdentification(
                    id=Identifier(value=id_val, scheme_id=scheme_id)
                )

        # Manufacturer's item identification
        mfr_elem = elem.find_child("ManufacturersItemIdentification")
        if mfr_elem:
            id_val, scheme_id, _ = get_identifier_with_scheme(mfr_elem, "ID")
            if id_val:
                item.manufacturers_item_identification = ItemIdentification(
                    id=Identifier(value=id_val, scheme_id=scheme_id)
                )

        return item

    def _parse_price(self, elem: "ParsedElement", currency: str) -> Price:
        """Parse a Price element."""
        amount_val, amount_curr = get_amount_with_currency(elem, "PriceAmount")
        base_qty, base_unit = get_quantity_with_unit(elem, "BaseQuantity")

        return Price(
            price_amount=Amount(
                value=amount_val or Decimal("0"),
                currency=amount_curr or currency,
            ),
            base_quantity=Quantity(value=base_qty, unit_code=base_unit or "EA")
            if base_qty else None,
        )

    def _parse_allowance_charge(
        self, elem: "ParsedElement", currency: str
    ) -> AllowanceCharge:
        """Parse an AllowanceCharge element."""
        indicator = get_child_value(elem, "ChargeIndicator")
        is_charge = indicator and indicator.lower() == "true"

        amount_val, amount_curr = get_amount_with_currency(elem, "Amount")

        return AllowanceCharge(
            charge_indicator=is_charge,
            amount=Amount(
                value=amount_val or Decimal("0"),
                currency=amount_curr or currency,
            ),
            allowance_charge_reason=get_child_value(elem, "AllowanceChargeReason"),
            allowance_charge_reason_code=get_child_value(
                elem, "AllowanceChargeReasonCode"
            ),
            multiplier_factor_numeric=parse_decimal(
                get_child_value(elem, "MultiplierFactorNumeric")
            ),
        )

    # Build methods for from_semantic
    def _build_period(self, period: Period) -> dict:
        """Build a Period element."""
        result = {}
        if period.start_date:
            result["cbc:StartDate"] = format_date(period.start_date)
        if period.end_date:
            result["cbc:EndDate"] = format_date(period.end_date)
        if period.start_time:
            result["cbc:StartTime"] = format_time(period.start_time)
        if period.end_time:
            result["cbc:EndTime"] = format_time(period.end_time)
        return result

    def _build_customer_party(self, cp: CustomerParty) -> dict:
        """Build a CustomerParty element."""
        result = {"cac:Party": self._build_party(cp.party)}
        if cp.buyer_contact:
            result["cac:BuyerContact"] = self._build_contact(cp.buyer_contact)
        if cp.delivery_contact:
            result["cac:DeliveryContact"] = self._build_contact(cp.delivery_contact)
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

        # Party identifications
        if party.party_identifications:
            result["cac:PartyIdentification"] = [
                {"cbc:ID": {"@schemeID": pi.id.scheme_id, "#text": pi.id.value}
                 if pi.id.scheme_id else pi.id.value}
                for pi in party.party_identifications
            ]

        # Party names
        if party.party_names:
            result["cac:PartyName"] = [
                {"cbc:Name": pn.name} for pn in party.party_names
            ]

        # Postal address
        if party.postal_address:
            result["cac:PostalAddress"] = self._build_address(party.postal_address)

        # Contact
        if party.contact:
            result["cac:Contact"] = self._build_contact(party.contact)

        return result

    def _build_address(self, addr: Address) -> dict:
        """Build an Address element."""
        result = {}
        if addr.street_name:
            result["cbc:StreetName"] = addr.street_name
        if addr.additional_street_name:
            result["cbc:AdditionalStreetName"] = addr.additional_street_name
        if addr.building_number:
            result["cbc:BuildingNumber"] = addr.building_number
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
        if contact.telefax:
            result["cbc:Telefax"] = contact.telefax
        return result

    def _build_delivery(self, delivery: Delivery) -> dict:
        """Build a Delivery element."""
        result = {}
        if delivery.quantity:
            result["cbc:Quantity"] = {
                "@unitCode": delivery.quantity.unit_code,
                "#text": str(delivery.quantity.value),
            }
        if delivery.actual_delivery_date:
            result["cbc:ActualDeliveryDate"] = format_date(delivery.actual_delivery_date)
        if delivery.latest_delivery_date:
            result["cbc:LatestDeliveryDate"] = format_date(delivery.latest_delivery_date)
        if delivery.tracking_id:
            result["cbc:TrackingID"] = delivery.tracking_id
        if delivery.delivery_location:
            result["cac:DeliveryLocation"] = {
                "cac:Address": self._build_address(delivery.delivery_location)
            }
        if delivery.delivery_party:
            result["cac:DeliveryParty"] = self._build_party(delivery.delivery_party)
        return result

    def _build_payment_terms(self, pt: PaymentTerms) -> dict:
        """Build a PaymentTerms element."""
        result = {}
        if pt.note:
            result["cbc:Note"] = pt.note
        if pt.payment_due_date:
            result["cbc:PaymentDueDate"] = format_date(pt.payment_due_date)
        if pt.settlement_discount_percent:
            result["cbc:SettlementDiscountPercent"] = str(pt.settlement_discount_percent)
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
        result["cac:TaxCategory"] = self._build_tax_category(st.tax_category)
        return result

    def _build_tax_category(self, tc: TaxCategory) -> dict:
        """Build a TaxCategory element."""
        result = {}
        if tc.id:
            result["cbc:ID"] = tc.id
        if tc.percent is not None:
            result["cbc:Percent"] = str(tc.percent)
        if tc.tax_scheme:
            result["cac:TaxScheme"] = {"cbc:ID": tc.tax_scheme}
        return result

    def _build_monetary_total(self, mt) -> dict:
        """Build a MonetaryTotal element."""
        result = {}

        def add_amount(key: str, amount: Amount | None):
            if amount:
                result[key] = {
                    "@currencyID": amount.currency,
                    "#text": str(amount.value),
                }

        add_amount("cbc:LineExtensionAmount", mt.line_extension_amount)
        add_amount("cbc:TaxExclusiveAmount", mt.tax_exclusive_amount)
        add_amount("cbc:TaxInclusiveAmount", mt.tax_inclusive_amount)
        add_amount("cbc:AllowanceTotalAmount", mt.allowance_total_amount)
        add_amount("cbc:ChargeTotalAmount", mt.charge_total_amount)
        add_amount("cbc:PayableRoundingAmount", mt.payable_rounding_amount)
        add_amount("cbc:PayableAmount", mt.payable_amount)
        return result

    def _build_order_line(self, line: OrderLine) -> dict:
        """Build an OrderLine element."""
        line_item = {
            "cbc:ID": line.id,
            "cbc:Quantity": {
                "@unitCode": line.quantity.unit_code,
                "#text": str(line.quantity.value),
            },
            "cac:Item": self._build_item(line.item),
        }

        if line.line_extension_amount:
            line_item["cbc:LineExtensionAmount"] = {
                "@currencyID": line.line_extension_amount.currency,
                "#text": str(line.line_extension_amount.value),
            }

        if line.price:
            line_item["cac:Price"] = self._build_price(line.price)

        if line.allowance_charges:
            line_item["cac:AllowanceCharge"] = [
                self._build_allowance_charge(ac) for ac in line.allowance_charges
            ]

        if line.tax_total:
            line_item["cac:TaxTotal"] = [
                self._build_tax_total(tt) for tt in line.tax_total
            ]

        return {"cac:LineItem": line_item}

    def _build_item(self, item: Item) -> dict:
        """Build an Item element."""
        result = {}
        if item.description:
            result["cbc:Description"] = item.description
        if item.name:
            result["cbc:Name"] = item.name
        if item.sellers_item_identification:
            result["cac:SellersItemIdentification"] = {
                "cbc:ID": item.sellers_item_identification.id.value
            }
        if item.standard_item_identification:
            si = item.standard_item_identification
            result["cac:StandardItemIdentification"] = {
                "cbc:ID": {"@schemeID": si.id.scheme_id, "#text": si.id.value}
                if si.id.scheme_id else si.id.value
            }
        return result

    def _build_price(self, price: Price) -> dict:
        """Build a Price element."""
        result = {
            "cbc:PriceAmount": {
                "@currencyID": price.price_amount.currency,
                "#text": str(price.price_amount.value),
            }
        }
        if price.base_quantity:
            result["cbc:BaseQuantity"] = {
                "@unitCode": price.base_quantity.unit_code,
                "#text": str(price.base_quantity.value),
            }
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
        if ac.allowance_charge_reason_code:
            result["cbc:AllowanceChargeReasonCode"] = ac.allowance_charge_reason_code
        return result
