"""
Semantic Business Models.

Pydantic models for format-agnostic representation of EDI business documents.
These models serve as the canonical form for translation between X12, UBL,
and EDIFACT formats.

The model hierarchy is based on UN/CEFACT CCTS (Core Components Technical
Specification) and aligned with UBL naming conventions.
"""

# Base
# Allowance/Charge models
from .allowance_charge import AllowanceCharge
from .base import SemanticModel

# Delivery models
from .delivery import (
    Delivery,
    DeliveryTerms,
    Despatch,
    Shipment,
    ShipmentStage,
    TransportEquipment,
    TransportHandlingUnit,
    TransportMeans,
)
from .despatch_advice import (
    DespatchAdvice,
    DespatchLine,
    ReceiptAdvice,
    ReceiptLine,
)
from .invoice import CreditNote, CreditNoteLine, Invoice, InvoiceLine

# Item models
from .item import (
    AdditionalItemProperty,
    CommodityClassification,
    HazardousItem,
    Item,
    ItemIdentification,
    ItemInstance,
    Price,
)

# Monetary models
from .monetary import MonetaryTotal

# Document models
from .order import Order, OrderLine
from .order_response import OrderResponse, OrderResponseLine

# Party models
from .party import (
    Address,
    Contact,
    CustomerParty,
    Party,
    PartyIdentification,
    PartyLegalEntity,
    PartyName,
    PartyTaxScheme,
    SupplierParty,
)

# Payment models
from .payment import (
    CardAccount,
    FinancialAccount,
    FinancialInstitution,
    FinancialInstitutionBranch,
    PaymentMandate,
    PaymentMeans,
    PaymentTerms,
    PrepaidPayment,
)

# Primitives
from .primitives import (
    Amount,
    Code,
    Identifier,
    Measure,
    Period,
    Quantity,
    Text,
)
from .quotation import Quotation, QuotationLine

# Reference models
from .reference import (
    Attachment,
    BillingReference,
    BillingReferenceLine,
    DespatchLineReference,
    DocumentReference,
    LineReference,
    OrderLineReference,
    OrderReference,
    ReceiptLineReference,
)
from .remittance_advice import RemittanceAdvice, RemittanceAdviceLine

# Tax models
from .tax import (
    TaxCategory,
    TaxScheme,
    TaxSubtotal,
    TaxTotal,
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
    "OrderResponse",
    "OrderResponseLine",
    "Quotation",
    "QuotationLine",
    "Invoice",
    "InvoiceLine",
    "CreditNote",
    "CreditNoteLine",
    "RemittanceAdvice",
    "RemittanceAdviceLine",
    "DespatchAdvice",
    "DespatchLine",
    "ReceiptAdvice",
    "ReceiptLine",
]
