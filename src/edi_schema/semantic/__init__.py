"""
Semantic Business Models for EDI Translation.

This module provides format-agnostic Pydantic models that serve as the canonical
representation for translating between X12, UBL, and EDIFACT formats.

The semantic layer is based on UN/CEFACT CCTS (Core Components Technical
Specification) and uses UBL naming conventions as the standard.

Usage:
    from edi_schema.semantic import Order, Invoice, DespatchAdvice
    from edi_schema.semantic import Party, Address, Item, Amount

    # Create a semantic order
    order = Order(
        id="PO-001",
        issue_date=date(2024, 1, 15),
        document_currency_code="USD",
        buyer_customer_party=CustomerParty(
            party=Party(
                party_names=[PartyName(name="Acme Corp")],
                postal_address=Address(
                    street_name="123 Main St",
                    city_name="New York",
                    country_code="US",
                ),
            )
        ),
        order_lines=[
            OrderLine(
                id="1",
                quantity=Quantity(value=Decimal("10"), unit_code="EA"),
                item=Item(name="Widget"),
                price=Price(
                    price_amount=Amount(value=Decimal("25.00"), currency="USD")
                ),
            )
        ],
    )
"""

# Import all models for convenient access
from .models import (
    # Item
    AdditionalItemProperty,
    # Party
    Address,
    # Allowance/Charge
    AllowanceCharge,
    # Primitives
    Amount,
    # Reference
    Attachment,
    BillingReference,
    BillingReferenceLine,
    # Payment
    CardAccount,
    Code,
    CommodityClassification,
    Contact,
    CreditNote,
    CreditNoteLine,
    CustomerParty,
    # Delivery
    Delivery,
    DeliveryTerms,
    Despatch,
    DespatchAdvice,
    DespatchLine,
    DespatchLineReference,
    DocumentReference,
    FinancialAccount,
    FinancialInstitution,
    FinancialInstitutionBranch,
    HazardousItem,
    Identifier,
    Invoice,
    InvoiceLine,
    Item,
    ItemIdentification,
    ItemInstance,
    LineReference,
    Measure,
    # Monetary
    MonetaryTotal,
    # Documents
    Order,
    OrderLine,
    OrderLineReference,
    OrderReference,
    Party,
    PartyIdentification,
    PartyLegalEntity,
    PartyName,
    PartyTaxScheme,
    PaymentMandate,
    PaymentMeans,
    PaymentTerms,
    Period,
    PrepaidPayment,
    Price,
    Quantity,
    ReceiptAdvice,
    ReceiptLine,
    ReceiptLineReference,
    # Base
    SemanticModel,
    Shipment,
    ShipmentStage,
    SupplierParty,
    # Tax
    TaxCategory,
    TaxScheme,
    TaxSubtotal,
    TaxTotal,
    Text,
    TransportEquipment,
    TransportHandlingUnit,
    TransportMeans,
    WithholdingTaxTotal,
)

__all__ = [
    # Base
    "SemanticModel",
    # Primitives
    "Amount",
    "Code",
    "Identifier",
    "Measure",
    "Period",
    "Quantity",
    "Text",
    # Party
    "Address",
    "Contact",
    "CustomerParty",
    "Party",
    "PartyIdentification",
    "PartyLegalEntity",
    "PartyName",
    "PartyTaxScheme",
    "SupplierParty",
    # Item
    "AdditionalItemProperty",
    "CommodityClassification",
    "HazardousItem",
    "Item",
    "ItemIdentification",
    "ItemInstance",
    "Price",
    # Tax
    "TaxCategory",
    "TaxScheme",
    "TaxSubtotal",
    "TaxTotal",
    "WithholdingTaxTotal",
    # Allowance/Charge
    "AllowanceCharge",
    # Delivery
    "Delivery",
    "DeliveryTerms",
    "Despatch",
    "Shipment",
    "ShipmentStage",
    "TransportEquipment",
    "TransportHandlingUnit",
    "TransportMeans",
    # Reference
    "Attachment",
    "BillingReference",
    "BillingReferenceLine",
    "DespatchLineReference",
    "DocumentReference",
    "LineReference",
    "OrderLineReference",
    "OrderReference",
    "ReceiptLineReference",
    # Monetary
    "MonetaryTotal",
    # Payment
    "CardAccount",
    "FinancialAccount",
    "FinancialInstitution",
    "FinancialInstitutionBranch",
    "PaymentMandate",
    "PaymentMeans",
    "PaymentTerms",
    "PrepaidPayment",
    # Documents
    "Order",
    "OrderLine",
    "Invoice",
    "InvoiceLine",
    "CreditNote",
    "CreditNoteLine",
    "DespatchAdvice",
    "DespatchLine",
    "ReceiptAdvice",
    "ReceiptLine",
]
