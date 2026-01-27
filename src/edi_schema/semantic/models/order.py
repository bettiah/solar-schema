"""
Semantic Order Models.

Purchase order and order line representations.
"""

from datetime import date, time
from decimal import Decimal

from pydantic import Field

from .allowance_charge import AllowanceCharge
from .base import SemanticModel
from .delivery import Delivery
from .item import Item, Price
from .monetary import MonetaryTotal
from .party import CustomerParty, Party, SupplierParty
from .payment import PaymentMeans, PaymentTerms
from .primitives import Amount, Period, Quantity
from .reference import DocumentReference
from .tax import TaxTotal


class OrderLine(SemanticModel):
    """
    Line item in a purchase order.

    Maps to:
    - UBL: cac:OrderLine
    - X12: PO1 loop (PO1, PID, SAC, etc.)
    - EDIFACT: LIN segment group
    """

    # Identification
    id: str = Field(description="Line item number")
    uuid: str | None = Field(
        default=None,
        description="UUID for this line",
    )
    sales_order_line_id: str | None = Field(
        default=None,
        description="Seller's line identifier",
    )
    note: list[str] = Field(
        default_factory=list,
        description="Line notes",
    )

    # Status
    line_status_code: str | None = Field(
        default=None,
        description="Line status code",
    )
    partial_delivery_indicator: bool | None = Field(
        default=None,
        description="Allow partial delivery",
    )
    back_order_allowed_indicator: bool | None = Field(
        default=None,
        description="Allow backorders",
    )
    accounting_cost_code: str | None = Field(
        default=None,
        description="Accounting cost code",
    )
    accounting_cost: str | None = Field(
        default=None,
        description="Accounting cost string",
    )

    # Quantity and amount
    quantity: Quantity = Field(description="Ordered quantity")
    line_extension_amount: Amount | None = Field(
        default=None,
        description="Line total (qty * price)",
    )
    total_tax_amount: Amount | None = Field(
        default=None,
        description="Total tax for line",
    )

    # Pricing
    minimum_quantity: Quantity | None = Field(
        default=None,
        description="Minimum order quantity",
    )
    maximum_quantity: Quantity | None = Field(
        default=None,
        description="Maximum order quantity",
    )
    minimum_backorder_quantity: Quantity | None = Field(
        default=None,
        description="Minimum backorder quantity",
    )
    maximum_backorder_quantity: Quantity | None = Field(
        default=None,
        description="Maximum backorder quantity",
    )

    # References
    inspection_method_code: str | None = Field(
        default=None,
        description="Inspection method code",
    )
    originator_party: Party | None = Field(
        default=None,
        description="Line originator party",
    )
    document_references: list[DocumentReference] = Field(
        default_factory=list,
        description="Document references for this line",
    )

    # Delivery
    delivery: list[Delivery] = Field(
        default_factory=list,
        description="Line-level delivery information",
    )
    delivery_terms: str | None = Field(
        default=None,
        description="Delivery terms for this line",
    )

    # Allowances and charges
    allowance_charges: list[AllowanceCharge] = Field(
        default_factory=list,
        description="Line allowances/charges",
    )

    # Tax
    tax_total: TaxTotal | None = Field(
        default=None,
        description="Line tax total",
    )

    # Item and price
    item: Item = Field(description="Item details")
    price: Price | None = Field(
        default=None,
        description="Unit price",
    )

    # Linked lines
    sub_order_lines: list["OrderLine"] = Field(
        default_factory=list,
        description="Sub-lines (kits, assemblies)",
    )

    @property
    def calculated_line_total(self) -> Decimal | None:
        """Calculate line total from quantity and price."""
        if self.price and self.price.price_amount:
            return self.quantity.value * self.price.price_amount.value
        return None

    def __str__(self) -> str:
        return f"Line {self.id}: {self.quantity} x {self.item}"


class Order(SemanticModel):
    """
    Semantic Order (Purchase Order) model.

    Central document representing a purchase order in format-agnostic form.

    Maps to:
    - X12: 850 Purchase Order
    - UBL: Order
    - EDIFACT: ORDERS

    Example:
        >>> order = Order(
        ...     id="PO-001",
        ...     issue_date=date(2024, 1, 15),
        ...     document_currency_code="USD",
        ...     buyer_customer_party=CustomerParty(party=Party(...)),
        ...     seller_supplier_party=SupplierParty(party=Party(...)),
        ...     order_lines=[OrderLine(...)]
        ... )
    """

    # Identification
    id: str = Field(description="Purchase order number")
    uuid: str | None = Field(
        default=None,
        description="UUID for this order",
    )
    sales_order_id: str | None = Field(
        default=None,
        description="Seller's sales order ID",
    )
    copy_indicator: bool | None = Field(
        default=None,
        description="Whether this is a copy",
    )
    customization_id: str | None = Field(
        default=None,
        description="Customization identifier",
    )
    profile_id: str | None = Field(
        default=None,
        description="Profile identifier",
    )
    profile_execution_id: str | None = Field(
        default=None,
        description="Profile execution identifier",
    )

    # Dates and times
    issue_date: date = Field(description="Order issue date")
    issue_time: time | None = Field(
        default=None,
        description="Order issue time",
    )

    # Type and purpose
    order_type_code: str | None = Field(
        default=None,
        description="Order type code",
    )
    document_purpose_code: str | None = Field(
        default=None,
        description="Document purpose (00=Original, 05=Replace, etc.)",
    )

    # Notes
    note: list[str] = Field(
        default_factory=list,
        description="Order notes",
    )

    # Currency
    document_currency_code: str = Field(
        pattern=r"^[A-Z]{3}$",
        description="ISO 4217 currency code",
    )
    tax_currency_code: str | None = Field(
        default=None,
        pattern=r"^[A-Z]{3}$",
        description="Tax reporting currency",
    )
    pricing_currency_code: str | None = Field(
        default=None,
        pattern=r"^[A-Z]{3}$",
        description="Pricing currency",
    )

    # Pricing
    requested_invoice_currency_code: str | None = Field(
        default=None,
        description="Requested invoice currency",
    )
    pricing_exchange_rate: Decimal | None = Field(
        default=None,
        description="Pricing currency exchange rate",
    )
    tax_exchange_rate: Decimal | None = Field(
        default=None,
        description="Tax currency exchange rate",
    )

    # Accounting
    accounting_cost_code: str | None = Field(
        default=None,
        description="Accounting cost code",
    )
    accounting_cost: str | None = Field(
        default=None,
        description="Accounting cost string",
    )

    # Validity
    validity_period: Period | None = Field(
        default=None,
        description="Order validity period",
    )

    # References
    quotation_document_reference: DocumentReference | None = Field(
        default=None,
        description="Referenced quotation",
    )
    order_document_references: list[DocumentReference] = Field(
        default_factory=list,
        description="Referenced orders (blanket PO, etc.)",
    )
    originator_document_reference: DocumentReference | None = Field(
        default=None,
        description="Originator document reference",
    )
    catalogue_reference: DocumentReference | None = Field(
        default=None,
        description="Catalogue reference",
    )
    additional_document_references: list[DocumentReference] = Field(
        default_factory=list,
        description="Additional document references",
    )
    contract_document_reference: DocumentReference | None = Field(
        default=None,
        description="Contract reference",
    )

    # Parties
    buyer_customer_party: CustomerParty | None = Field(
        default=None,
        description="Buyer party",
    )
    seller_supplier_party: SupplierParty | None = Field(
        default=None,
        description="Seller party",
    )
    originator_customer_party: CustomerParty | None = Field(
        default=None,
        description="Order originator",
    )
    freight_forwarder_party: Party | None = Field(
        default=None,
        description="Freight forwarder",
    )
    accounting_customer_party: CustomerParty | None = Field(
        default=None,
        description="Accounting customer (bill-to)",
    )
    payee_party: Party | None = Field(
        default=None,
        description="Payee party (remit-to)",
    )

    # Delivery
    delivery: list[Delivery] = Field(
        default_factory=list,
        description="Delivery information",
    )
    delivery_terms: str | None = Field(
        default=None,
        description="Delivery terms (Incoterms)",
    )

    # Payment
    payment_means: list[PaymentMeans] = Field(
        default_factory=list,
        description="Payment means",
    )
    payment_terms: list[PaymentTerms] = Field(
        default_factory=list,
        description="Payment terms",
    )
    transaction_conditions: str | None = Field(
        default=None,
        description="Transaction conditions",
    )

    # Allowances and charges
    allowance_charges: list[AllowanceCharge] = Field(
        default_factory=list,
        description="Document-level allowances/charges",
    )

    # Tax
    tax_total: list[TaxTotal] = Field(
        default_factory=list,
        description="Tax totals",
    )

    # Totals
    anticipated_monetary_total: MonetaryTotal | None = Field(
        default=None,
        description="Anticipated monetary totals",
    )

    # Lines
    order_lines: list[OrderLine] = Field(
        default_factory=list,
        description="Order line items",
    )

    # Line count (for validation)
    line_count: int | None = Field(
        default=None,
        description="Number of line items (for validation)",
    )

    # Source tracking (not part of business data)
    _source_format: str | None = None
    _source_version: str | None = None

    @property
    def total_quantity(self) -> Decimal:
        """Sum of all line quantities."""
        return sum(line.quantity.value for line in self.order_lines)

    @property
    def calculated_line_count(self) -> int:
        """Actual number of order lines."""
        return len(self.order_lines)

    def __str__(self) -> str:
        return f"Order {self.id} ({len(self.order_lines)} lines)"


# Forward reference for sub-lines
OrderLine.model_rebuild()
