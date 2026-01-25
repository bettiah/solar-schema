"""
Tests for semantic Pydantic models.

These tests verify that the semantic models:
1. Can be instantiated with valid data
2. Properly validate required fields
3. Enforce type constraints (currency codes, country codes, etc.)
4. Support serialization/deserialization
5. Work with complex nested structures
"""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from edi_schema.semantic import (
    Address,
    # Allowance/Charge
    AllowanceCharge,
    # Primitives
    Amount,
    Code,
    Contact,
    CustomerParty,
    # Delivery
    Delivery,
    # Payment
    DespatchAdvice,
    DespatchLine,
    Identifier,
    Invoice,
    InvoiceLine,
    # Item
    Item,
    ItemIdentification,
    Measure,
    # Monetary
    MonetaryTotal,
    Order,
    OrderLine,
    # Reference
    OrderLineReference,
    OrderReference,
    Party,
    PartyIdentification,
    PartyName,
    Period,
    Price,
    Quantity,
    Shipment,
    SupplierParty,
    # Tax
    TaxCategory,
    TaxSubtotal,
    TaxTotal,
)


class TestPrimitives:
    """Test primitive type models."""

    def test_amount_valid(self):
        """Amount with valid currency code."""
        amount = Amount(value=Decimal("100.50"), currency="USD")
        assert amount.value == Decimal("100.50")
        assert amount.currency == "USD"
        assert str(amount) == "100.50 USD"

    def test_amount_invalid_currency(self):
        """Amount rejects invalid currency codes."""
        with pytest.raises(ValidationError) as exc_info:
            Amount(value=Decimal("100"), currency="US")  # Too short
        assert "currency" in str(exc_info.value)

        with pytest.raises(ValidationError):
            Amount(value=Decimal("100"), currency="usd")  # Lowercase

    def test_quantity_valid(self):
        """Quantity with unit code."""
        qty = Quantity(value=Decimal("25"), unit_code="EA")
        assert qty.value == Decimal("25")
        assert qty.unit_code == "EA"
        assert str(qty) == "25 EA"

    def test_identifier_with_scheme(self):
        """Identifier with scheme information."""
        id = Identifier(value="123456789", scheme_id="DUNS", scheme_agency_id="16")
        assert id.value == "123456789"
        assert id.scheme_id == "DUNS"
        assert str(id) == "123456789 (DUNS)"

    def test_identifier_without_scheme(self):
        """Identifier without scheme."""
        id = Identifier(value="ABC-123")
        assert str(id) == "ABC-123"

    def test_period(self):
        """Period with start and end dates."""
        period = Period(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        assert period.start_date == date(2024, 1, 1)
        assert "from 2024-01-01" in str(period)
        assert "to 2024-12-31" in str(period)

    def test_measure(self):
        """Measure with unit."""
        m = Measure(value=Decimal("150.5"), unit_code="KGM")
        assert m.value == Decimal("150.5")
        assert m.unit_code == "KGM"

    def test_code(self):
        """Code with list information."""
        code = Code(value="380", list_id="UNCL1001", name="Commercial Invoice")
        assert code.value == "380"
        assert str(code) == "380"


class TestPartyModels:
    """Test party-related models."""

    def test_address_valid(self):
        """Complete address."""
        addr = Address(
            street_name="123 Main Street",
            additional_street_name="Suite 400",
            city_name="New York",
            postal_zone="10001",
            country_subentity="NY",
            country_code="US",
        )
        assert addr.street_name == "123 Main Street"
        assert addr.country_code == "US"
        assert "123 Main Street" in str(addr)
        assert "New York" in str(addr)

    def test_address_invalid_country_code(self):
        """Address rejects invalid country code."""
        with pytest.raises(ValidationError):
            Address(country_code="USA")  # Too long

    def test_contact(self):
        """Contact information."""
        contact = Contact(
            name="John Doe",
            telephone="+1-555-123-4567",
            electronic_mail="john.doe@example.com",
        )
        assert contact.name == "John Doe"
        assert str(contact) == "John Doe"

    def test_party_with_identifications(self):
        """Party with multiple identifiers."""
        party = Party(
            party_identifications=[
                PartyIdentification(id=Identifier(value="123456789", scheme_id="DUNS")),
                PartyIdentification(id=Identifier(value="5012345678901", scheme_id="GLN")),
            ],
            party_names=[PartyName(name="Acme Corporation")],
            postal_address=Address(city_name="Chicago", country_code="US"),
        )
        assert party.primary_name == "Acme Corporation"
        assert party.primary_id.value == "123456789"
        assert len(party.party_identifications) == 2

    def test_customer_party(self):
        """Customer party wrapper."""
        customer = CustomerParty(
            party=Party(party_names=[PartyName(name="Buyer Inc")]),
            buyer_contact=Contact(name="Purchasing Dept"),
        )
        assert customer.party.primary_name == "Buyer Inc"
        assert customer.buyer_contact.name == "Purchasing Dept"

    def test_supplier_party(self):
        """Supplier party wrapper."""
        supplier = SupplierParty(
            party=Party(party_names=[PartyName(name="Seller Corp")]),
            seller_contact=Contact(name="Sales Team"),
        )
        assert supplier.party.primary_name == "Seller Corp"


class TestItemModels:
    """Test item-related models."""

    def test_item_identification(self):
        """Item identifier."""
        item_id = ItemIdentification(id=Identifier(value="012345678901", scheme_id="UPC"))
        assert item_id.id.value == "012345678901"
        assert item_id.id.scheme_id == "UPC"

    def test_item_with_identifiers(self):
        """Item with various identifiers."""
        item = Item(
            name="Standard Widget",
            description="A standard widget for general use",
            standard_item_identification=ItemIdentification(
                id=Identifier(value="012345678901", scheme_id="UPC")
            ),
            sellers_item_identification=ItemIdentification(id=Identifier(value="WIDGET-001")),
            buyers_item_identification=ItemIdentification(id=Identifier(value="PRT-12345")),
        )
        assert item.display_name == "Standard Widget"
        assert item.primary_id == "012345678901"

    def test_item_without_name(self):
        """Item uses description if name missing."""
        item = Item(description="Generic Item Description")
        assert item.display_name == "Generic Item Description"

    def test_price(self):
        """Unit price."""
        price = Price(
            price_amount=Amount(value=Decimal("25.99"), currency="USD"),
            base_quantity=Quantity(value=Decimal("1"), unit_code="EA"),
        )
        assert price.price_amount.value == Decimal("25.99")
        assert str(price) == "25.99 USD"


class TestTaxModels:
    """Test tax-related models."""

    def test_tax_category(self):
        """Tax category."""
        cat = TaxCategory(id="S", percent=Decimal("7.5"))
        assert cat.id == "S"
        assert cat.percent == Decimal("7.5")
        assert "7.5%" in str(cat)

    def test_tax_subtotal(self):
        """Tax subtotal."""
        subtotal = TaxSubtotal(
            taxable_amount=Amount(value=Decimal("100.00"), currency="USD"),
            tax_amount=Amount(value=Decimal("7.50"), currency="USD"),
            percent=Decimal("7.5"),
        )
        assert subtotal.tax_amount.value == Decimal("7.50")

    def test_tax_total(self):
        """Tax total with subtotals."""
        tax_total = TaxTotal(
            tax_amount=Amount(value=Decimal("15.00"), currency="USD"),
            tax_subtotals=[
                TaxSubtotal(
                    tax_amount=Amount(value=Decimal("10.00"), currency="USD"),
                    tax_category=TaxCategory(id="S", percent=Decimal("10")),
                ),
                TaxSubtotal(
                    tax_amount=Amount(value=Decimal("5.00"), currency="USD"),
                    tax_category=TaxCategory(id="S", percent=Decimal("5")),
                ),
            ],
        )
        assert tax_total.tax_amount.value == Decimal("15.00")
        assert len(tax_total.tax_subtotals) == 2


class TestAllowanceCharge:
    """Test allowance/charge model."""

    def test_allowance(self):
        """Allowance (discount)."""
        allowance = AllowanceCharge(
            charge_indicator=False,
            allowance_charge_reason="Volume discount",
            amount=Amount(value=Decimal("50.00"), currency="USD"),
            percent=Decimal("10"),
        )
        assert allowance.is_allowance is True
        assert allowance.is_charge is False
        assert "Allowance" in str(allowance)

    def test_charge(self):
        """Charge (surcharge)."""
        charge = AllowanceCharge(
            charge_indicator=True,
            allowance_charge_reason="Handling fee",
            amount=Amount(value=Decimal("25.00"), currency="USD"),
        )
        assert charge.is_charge is True
        assert "Charge" in str(charge)


class TestMonetaryTotal:
    """Test monetary total model."""

    def test_monetary_total(self):
        """Complete monetary total."""
        total = MonetaryTotal(
            line_extension_amount=Amount(value=Decimal("1000.00"), currency="USD"),
            tax_exclusive_amount=Amount(value=Decimal("950.00"), currency="USD"),
            tax_inclusive_amount=Amount(value=Decimal("1017.50"), currency="USD"),
            allowance_total_amount=Amount(value=Decimal("50.00"), currency="USD"),
            payable_amount=Amount(value=Decimal("1017.50"), currency="USD"),
        )
        assert total.payable_amount.value == Decimal("1017.50")
        assert "1017.50" in str(total)


class TestOrderModel:
    """Test Order document model."""

    def test_order_minimal(self):
        """Minimal valid order."""
        order = Order(
            id="PO-2024-001",
            issue_date=date(2024, 1, 15),
            document_currency_code="USD",
        )
        assert order.id == "PO-2024-001"
        assert order.issue_date == date(2024, 1, 15)
        assert order.calculated_line_count == 0

    def test_order_with_lines(self):
        """Order with line items."""
        order = Order(
            id="PO-2024-002",
            issue_date=date(2024, 1, 15),
            document_currency_code="USD",
            buyer_customer_party=CustomerParty(
                party=Party(party_names=[PartyName(name="Buyer Corp")])
            ),
            seller_supplier_party=SupplierParty(
                party=Party(party_names=[PartyName(name="Seller Inc")])
            ),
            order_lines=[
                OrderLine(
                    id="1",
                    quantity=Quantity(value=Decimal("10"), unit_code="EA"),
                    item=Item(name="Widget A"),
                    price=Price(price_amount=Amount(value=Decimal("25.00"), currency="USD")),
                ),
                OrderLine(
                    id="2",
                    quantity=Quantity(value=Decimal("5"), unit_code="EA"),
                    item=Item(name="Widget B"),
                    price=Price(price_amount=Amount(value=Decimal("50.00"), currency="USD")),
                ),
            ],
        )
        assert order.calculated_line_count == 2
        assert order.total_quantity == Decimal("15")
        assert "2 lines" in str(order)

    def test_order_invalid_currency(self):
        """Order rejects invalid currency code."""
        with pytest.raises(ValidationError):
            Order(
                id="PO-001",
                issue_date=date(2024, 1, 15),
                document_currency_code="INVALID",
            )

    def test_order_line_calculated_total(self):
        """Order line calculates total."""
        line = OrderLine(
            id="1",
            quantity=Quantity(value=Decimal("10"), unit_code="EA"),
            item=Item(name="Test Item"),
            price=Price(price_amount=Amount(value=Decimal("25.00"), currency="USD")),
        )
        assert line.calculated_line_total == Decimal("250.00")


class TestInvoiceModel:
    """Test Invoice document model."""

    def test_invoice_minimal(self):
        """Minimal valid invoice."""
        invoice = Invoice(
            id="INV-2024-001",
            issue_date=date(2024, 1, 15),
            document_currency_code="USD",
            accounting_supplier_party=SupplierParty(
                party=Party(party_names=[PartyName(name="Seller")])
            ),
            accounting_customer_party=CustomerParty(
                party=Party(party_names=[PartyName(name="Buyer")])
            ),
            legal_monetary_total=MonetaryTotal(
                payable_amount=Amount(value=Decimal("1000.00"), currency="USD")
            ),
        )
        assert invoice.id == "INV-2024-001"
        assert invoice.is_credit_note is False

    def test_invoice_with_lines(self):
        """Invoice with line items."""
        invoice = Invoice(
            id="INV-2024-002",
            issue_date=date(2024, 1, 15),
            document_currency_code="USD",
            accounting_supplier_party=SupplierParty(
                party=Party(party_names=[PartyName(name="Seller Corp")])
            ),
            accounting_customer_party=CustomerParty(
                party=Party(party_names=[PartyName(name="Buyer Inc")])
            ),
            order_reference=OrderReference(id="PO-2024-001"),
            invoice_lines=[
                InvoiceLine(
                    id="1",
                    invoiced_quantity=Quantity(value=Decimal("10"), unit_code="EA"),
                    line_extension_amount=Amount(value=Decimal("250.00"), currency="USD"),
                    item=Item(name="Widget A"),
                    price=Price(price_amount=Amount(value=Decimal("25.00"), currency="USD")),
                ),
            ],
            tax_total=[
                TaxTotal(
                    tax_amount=Amount(value=Decimal("18.75"), currency="USD"),
                )
            ],
            legal_monetary_total=MonetaryTotal(
                line_extension_amount=Amount(value=Decimal("250.00"), currency="USD"),
                tax_exclusive_amount=Amount(value=Decimal("250.00"), currency="USD"),
                tax_inclusive_amount=Amount(value=Decimal("268.75"), currency="USD"),
                payable_amount=Amount(value=Decimal("268.75"), currency="USD"),
            ),
        )
        assert invoice.calculated_line_count == 1
        assert invoice.order_reference.id == "PO-2024-001"

    def test_credit_note_detection(self):
        """Invoice type code 381 is a credit note."""
        invoice = Invoice(
            id="CN-001",
            issue_date=date(2024, 1, 15),
            document_currency_code="USD",
            invoice_type_code="381",
            accounting_supplier_party=SupplierParty(
                party=Party(party_names=[PartyName(name="Seller")])
            ),
            accounting_customer_party=CustomerParty(
                party=Party(party_names=[PartyName(name="Buyer")])
            ),
            legal_monetary_total=MonetaryTotal(
                payable_amount=Amount(value=Decimal("-100.00"), currency="USD")
            ),
        )
        assert invoice.is_credit_note is True


class TestDespatchAdviceModel:
    """Test DespatchAdvice (ASN) document model."""

    def test_despatch_advice_minimal(self):
        """Minimal valid despatch advice."""
        asn = DespatchAdvice(
            id="ASN-2024-001",
            issue_date=date(2024, 1, 15),
        )
        assert asn.id == "ASN-2024-001"
        assert asn.calculated_line_count == 0

    def test_despatch_advice_with_lines(self):
        """Despatch advice with line items."""
        asn = DespatchAdvice(
            id="ASN-2024-002",
            issue_date=date(2024, 1, 15),
            despatch_supplier_party=SupplierParty(
                party=Party(party_names=[PartyName(name="Shipper Corp")])
            ),
            delivery_customer_party=CustomerParty(
                party=Party(party_names=[PartyName(name="Receiver Inc")])
            ),
            order_references=[OrderReference(id="PO-2024-001")],
            shipment=Shipment(
                id="SHIP-001",
                gross_weight_measure=Measure(value=Decimal("150"), unit_code="KGM"),
                total_transport_handling_unit_quantity=5,
            ),
            despatch_lines=[
                DespatchLine(
                    id="1",
                    delivered_quantity=Quantity(value=Decimal("10"), unit_code="EA"),
                    item=Item(name="Widget A"),
                    order_line_reference=OrderLineReference(
                        line_id="1",
                        order_reference=OrderReference(id="PO-2024-001"),
                    ),
                ),
                DespatchLine(
                    id="2",
                    delivered_quantity=Quantity(value=Decimal("5"), unit_code="EA"),
                    item=Item(name="Widget B"),
                    backorder_quantity=Quantity(value=Decimal("5"), unit_code="EA"),
                    backorder_reason="Out of stock",
                ),
            ],
        )
        assert asn.calculated_line_count == 2
        assert asn.shipment.total_transport_handling_unit_quantity == 5
        assert asn.despatch_lines[1].backorder_quantity.value == Decimal("5")


class TestSerialization:
    """Test model serialization and deserialization."""

    def test_order_to_dict(self):
        """Order serializes to dict."""
        order = Order(
            id="PO-001",
            issue_date=date(2024, 1, 15),
            document_currency_code="USD",
            order_lines=[
                OrderLine(
                    id="1",
                    quantity=Quantity(value=Decimal("10"), unit_code="EA"),
                    item=Item(name="Widget"),
                ),
            ],
        )
        data = order.model_dump()
        assert data["id"] == "PO-001"
        assert data["document_currency_code"] == "USD"
        assert len(data["order_lines"]) == 1
        assert data["order_lines"][0]["quantity"]["value"] == Decimal("10")

    def test_order_from_dict(self):
        """Order deserializes from dict."""
        data = {
            "id": "PO-002",
            "issue_date": "2024-01-15",
            "document_currency_code": "EUR",
            "order_lines": [
                {
                    "id": "1",
                    "quantity": {"value": "20", "unit_code": "EA"},
                    "item": {"name": "Gadget"},
                }
            ],
        }
        order = Order.model_validate(data)
        assert order.id == "PO-002"
        assert order.document_currency_code == "EUR"
        assert order.order_lines[0].quantity.value == Decimal("20")

    def test_json_round_trip(self):
        """Order survives JSON round-trip."""
        order = Order(
            id="PO-003",
            issue_date=date(2024, 1, 15),
            document_currency_code="GBP",
            note=["Rush order", "Handle with care"],
            buyer_customer_party=CustomerParty(
                party=Party(
                    party_names=[PartyName(name="Test Buyer")],
                    postal_address=Address(city_name="London", country_code="GB"),
                )
            ),
            order_lines=[
                OrderLine(
                    id="1",
                    quantity=Quantity(value=Decimal("5"), unit_code="EA"),
                    item=Item(name="Test Item", description="A test item"),
                    price=Price(price_amount=Amount(value=Decimal("99.99"), currency="GBP")),
                ),
            ],
        )

        # Serialize to JSON
        json_str = order.model_dump_json()

        # Deserialize back
        restored = Order.model_validate_json(json_str)

        assert restored.id == order.id
        assert restored.document_currency_code == order.document_currency_code
        assert restored.note == order.note
        assert (
            restored.buyer_customer_party.party.primary_name
            == order.buyer_customer_party.party.primary_name
        )
        assert len(restored.order_lines) == len(order.order_lines)
        assert (
            restored.order_lines[0].price.price_amount.value
            == order.order_lines[0].price.price_amount.value
        )


class TestComplexScenarios:
    """Test complex real-world scenarios."""

    def test_multi_party_order(self):
        """Order with multiple party roles."""
        order = Order(
            id="PO-COMPLEX-001",
            issue_date=date(2024, 1, 15),
            document_currency_code="USD",
            buyer_customer_party=CustomerParty(
                party=Party(
                    party_identifications=[
                        PartyIdentification(id=Identifier(value="123456789", scheme_id="DUNS"))
                    ],
                    party_names=[PartyName(name="Purchasing Corp")],
                ),
                buyer_contact=Contact(name="Buyer Contact", telephone="555-1234"),
            ),
            seller_supplier_party=SupplierParty(
                party=Party(party_names=[PartyName(name="Vendor Inc")]),
            ),
            accounting_customer_party=CustomerParty(
                party=Party(party_names=[PartyName(name="Billing Dept")]),
            ),
            delivery=[
                Delivery(
                    delivery_party=Party(
                        party_names=[PartyName(name="Warehouse A")],
                        postal_address=Address(
                            street_name="100 Warehouse Blvd",
                            city_name="Chicago",
                            postal_zone="60601",
                            country_code="US",
                        ),
                    ),
                    requested_delivery_period=Period(
                        start_date=date(2024, 2, 1),
                        end_date=date(2024, 2, 15),
                    ),
                ),
            ],
            order_lines=[
                OrderLine(
                    id="1",
                    quantity=Quantity(value=Decimal("100"), unit_code="EA"),
                    item=Item(name="Product A"),
                ),
            ],
        )
        assert order.buyer_customer_party.buyer_contact.name == "Buyer Contact"
        assert order.accounting_customer_party.party.primary_name == "Billing Dept"
        assert order.delivery[0].delivery_party.primary_name == "Warehouse A"

    def test_invoice_with_taxes_and_charges(self):
        """Invoice with tax breakdown and allowances/charges."""
        invoice = Invoice(
            id="INV-TAX-001",
            issue_date=date(2024, 1, 15),
            document_currency_code="EUR",
            accounting_supplier_party=SupplierParty(
                party=Party(party_names=[PartyName(name="EU Seller")])
            ),
            accounting_customer_party=CustomerParty(
                party=Party(party_names=[PartyName(name="EU Buyer")])
            ),
            allowance_charges=[
                AllowanceCharge(
                    charge_indicator=False,
                    allowance_charge_reason="Early payment discount",
                    amount=Amount(value=Decimal("50.00"), currency="EUR"),
                    percent=Decimal("5"),
                ),
                AllowanceCharge(
                    charge_indicator=True,
                    allowance_charge_reason="Shipping",
                    amount=Amount(value=Decimal("25.00"), currency="EUR"),
                ),
            ],
            tax_total=[
                TaxTotal(
                    tax_amount=Amount(value=Decimal("180.00"), currency="EUR"),
                    tax_subtotals=[
                        TaxSubtotal(
                            taxable_amount=Amount(value=Decimal("800.00"), currency="EUR"),
                            tax_amount=Amount(value=Decimal("160.00"), currency="EUR"),
                            percent=Decimal("20"),
                            tax_category=TaxCategory(
                                id="S",
                                percent=Decimal("20"),
                            ),
                        ),
                        TaxSubtotal(
                            taxable_amount=Amount(value=Decimal("200.00"), currency="EUR"),
                            tax_amount=Amount(value=Decimal("20.00"), currency="EUR"),
                            percent=Decimal("10"),
                            tax_category=TaxCategory(
                                id="S",
                                percent=Decimal("10"),
                            ),
                        ),
                    ],
                )
            ],
            invoice_lines=[
                InvoiceLine(
                    id="1",
                    invoiced_quantity=Quantity(value=Decimal("10"), unit_code="EA"),
                    line_extension_amount=Amount(value=Decimal("1000.00"), currency="EUR"),
                    item=Item(name="Standard Rate Item"),
                ),
            ],
            legal_monetary_total=MonetaryTotal(
                line_extension_amount=Amount(value=Decimal("1000.00"), currency="EUR"),
                allowance_total_amount=Amount(value=Decimal("50.00"), currency="EUR"),
                charge_total_amount=Amount(value=Decimal("25.00"), currency="EUR"),
                tax_exclusive_amount=Amount(value=Decimal("975.00"), currency="EUR"),
                tax_inclusive_amount=Amount(value=Decimal("1155.00"), currency="EUR"),
                payable_amount=Amount(value=Decimal("1155.00"), currency="EUR"),
            ),
        )
        assert len(invoice.allowance_charges) == 2
        assert len(invoice.tax_total[0].tax_subtotals) == 2
        assert invoice.legal_monetary_total.payable_amount.value == Decimal("1155.00")
