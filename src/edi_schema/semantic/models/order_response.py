"""
Semantic Order Response Models.

Order response (acknowledgment) representations.
"""

from datetime import date, time

from pydantic import Field

from .allowance_charge import AllowanceCharge
from .base import SemanticModel
from .delivery import Delivery
from .item import Item, Price
from .monetary import MonetaryTotal
from .party import CustomerParty, Party, SupplierParty
from .payment import PaymentMeans, PaymentTerms
from .primitives import Amount, Period, Quantity
from .reference import DocumentReference, OrderLineReference, OrderReference
from .tax import TaxTotal


class OrderResponseLine(SemanticModel):
    """
    Line item in an order response.

    Maps to:
    - UBL: cac:OrderLine in OrderResponse
    - X12: PO1 loop in 855
    - EDIFACT: LIN segment group in ORDRSP
    """

    # Identification
    id: str = Field(description="Line item number")
    uuid: str | None = Field(
        default=None,
        description="UUID for this line",
    )
    note: list[str] = Field(
        default_factory=list,
        description="Line notes",
    )

    # Line response
    line_status_code: str | None = Field(
        default=None,
        description="Line status code (e.g., accepted, rejected, changed)",
    )
    substitution_status_code: str | None = Field(
        default=None,
        description="Substitution status code",
    )

    # Quantities
    quantity: Quantity | None = Field(
        default=None,
        description="Ordered/confirmed quantity",
    )
    outstanding_quantity: Quantity | None = Field(
        default=None,
        description="Outstanding quantity",
    )

    # Reason
    outstanding_reason: list[str] = Field(
        default_factory=list,
        description="Reason for outstanding quantity",
    )

    # Amounts
    line_extension_amount: Amount | None = Field(
        default=None,
        description="Line total",
    )

    # References
    order_line_reference: OrderLineReference | None = Field(
        default=None,
        description="Reference to original order line",
    )
    document_references: list[DocumentReference] = Field(
        default_factory=list,
        description="Additional document references",
    )

    # Delivery
    delivery: list[Delivery] = Field(
        default_factory=list,
        description="Delivery details",
    )
    promised_delivery_period: Period | None = Field(
        default=None,
        description="Promised delivery period",
    )

    # Allowances and charges
    allowance_charges: list[AllowanceCharge] = Field(
        default_factory=list,
        description="Allowances/charges for this line",
    )

    # Tax
    tax_total: list[TaxTotal] = Field(
        default_factory=list,
        description="Line tax totals",
    )

    # Item and price
    item: Item = Field(description="Item details")
    price: Price | None = Field(
        default=None,
        description="Unit price",
    )

    def __str__(self) -> str:
        status = self.line_status_code or "unknown"
        return f"OrderResponseLine {self.id} ({status}): {self.item}"


class OrderResponse(SemanticModel):
    """
    Semantic Order Response (Acknowledgment) model.

    Represents a seller's response to a purchase order.

    Maps to:
    - X12: 855 Purchase Order Acknowledgment
    - UBL: OrderResponse
    - EDIFACT: ORDRSP

    Example:
        >>> response = OrderResponse(
        ...     id="ACK-001",
        ...     issue_date=date(2024, 1, 15),
        ...     document_currency_code="USD",
        ...     order_response_code="AC",  # Accepted with changes
        ...     order_reference=OrderReference(id="PO-001"),
        ...     seller_supplier_party=SupplierParty(party=Party(...)),
        ...     buyer_customer_party=CustomerParty(party=Party(...)),
        ... )
    """

    # Identification
    id: str = Field(description="Order response number")
    uuid: str | None = Field(
        default=None,
        description="UUID for this order response",
    )
    issue_date: date = Field(description="Issue date")
    issue_time: time | None = Field(
        default=None,
        description="Issue time",
    )

    # Response codes
    order_response_code: str | None = Field(
        default=None,
        description="Overall response code (accepted/rejected/modified)",
    )
    order_type_code: str | None = Field(
        default=None,
        description="Order type code",
    )

    # Notes
    note: list[str] = Field(
        default_factory=list,
        description="Notes",
    )

    # Currency
    document_currency_code: str = Field(
        pattern=r"^[A-Z]{3}$",
        description="Document currency",
    )
    pricing_currency_code: str | None = Field(
        default=None,
        description="Pricing currency",
    )
    tax_currency_code: str | None = Field(
        default=None,
        description="Tax currency",
    )

    # Line count
    line_count: int | None = Field(
        default=None,
        description="Number of line items",
    )

    # Validity
    validity_period: Period | None = Field(
        default=None,
        description="Response validity period",
    )

    # References
    order_reference: OrderReference | None = Field(
        default=None,
        description="Reference to original purchase order",
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
    seller_supplier_party: SupplierParty | None = Field(
        default=None,
        description="Seller/vendor",
    )
    buyer_customer_party: CustomerParty | None = Field(
        default=None,
        description="Buyer/customer",
    )
    originator_customer_party: CustomerParty | None = Field(
        default=None,
        description="Originator",
    )
    freight_forwarder_party: Party | None = Field(
        default=None,
        description="Freight forwarder",
    )
    accounting_supplier_party: SupplierParty | None = Field(
        default=None,
        description="Accounting supplier party",
    )
    accounting_customer_party: CustomerParty | None = Field(
        default=None,
        description="Accounting customer party",
    )

    # Delivery
    delivery: list[Delivery] = Field(
        default_factory=list,
        description="Delivery details",
    )
    delivery_terms: str | None = Field(
        default=None,
        description="Delivery terms (Incoterms)",
    )

    # Payment
    payment_terms: list[PaymentTerms] = Field(
        default_factory=list,
        description="Payment terms",
    )
    payment_means: list[PaymentMeans] = Field(
        default_factory=list,
        description="Payment means",
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
        description="Anticipated monetary total",
    )

    # Lines
    order_lines: list[OrderResponseLine] = Field(
        default_factory=list,
        description="Order response line items",
    )

    # Source tracking
    _source_format: str | None = None
    _source_version: str | None = None

    @property
    def calculated_line_count(self) -> int:
        """Actual number of order response lines."""
        return len(self.order_lines)

    @property
    def is_accepted(self) -> bool:
        """Check if order was fully accepted."""
        return self.order_response_code in ("AC", "AP", "accepted")

    @property
    def is_rejected(self) -> bool:
        """Check if order was rejected."""
        return self.order_response_code in ("RJ", "rejected")

    def __str__(self) -> str:
        code = self.order_response_code or "unknown"
        return f"OrderResponse {self.id} ({code}) for {self.order_reference}"


# Forward references
OrderResponse.model_rebuild()
OrderResponseLine.model_rebuild()
