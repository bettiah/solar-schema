"""
Semantic Quotation Models.

Price quote and quotation line representations.
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
from .reference import DocumentReference, OrderReference
from .tax import TaxTotal


class QuotationLine(SemanticModel):
    """
    Line item in a quotation.

    Maps to:
    - UBL: cac:QuotationLine
    - X12: PO1 loop in 843
    - EDIFACT: LIN segment group in QUOTES
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

    # Status
    line_status_code: str | None = Field(
        default=None,
        description="Line status code",
    )

    # Quantity and amount
    quantity: Quantity = Field(description="Quoted quantity")
    line_extension_amount: Amount | None = Field(
        default=None,
        description="Line total (qty * price)",
    )
    total_tax_amount: Amount | None = Field(
        default=None,
        description="Total tax for line",
    )

    # References
    request_for_quotation_line_id: str | None = Field(
        default=None,
        description="Reference to RFQ line",
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

    @property
    def calculated_line_total(self) -> Decimal | None:
        """Calculate line total from quantity and price."""
        if self.price and self.price.price_amount:
            return self.quantity.value * self.price.price_amount.value
        return None

    def __str__(self) -> str:
        return f"QuotationLine {self.id}: {self.quantity} x {self.item}"


class Quotation(SemanticModel):
    """
    Semantic Quotation (Price Quote) model.

    Central document representing a price quotation in format-agnostic form.

    Maps to:
    - X12: 843 Response to Request for Quotation
    - UBL: Quotation
    - EDIFACT: QUOTES

    Example:
        >>> quotation = Quotation(
        ...     id="QT-001",
        ...     issue_date=date(2024, 1, 15),
        ...     document_currency_code="USD",
        ...     seller_supplier_party=SupplierParty(party=Party(...)),
        ...     buyer_customer_party=CustomerParty(party=Party(...)),
        ...     quotation_lines=[QuotationLine(...)]
        ... )
    """

    # Identification
    id: str = Field(description="Quotation number")
    uuid: str | None = Field(
        default=None,
        description="UUID for this quotation",
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
    issue_date: date = Field(description="Quotation issue date")
    issue_time: time | None = Field(
        default=None,
        description="Quotation issue time",
    )

    # Type and purpose
    quotation_type_code: str | None = Field(
        default=None,
        description="Quotation type code",
    )

    # Notes
    note: list[str] = Field(
        default_factory=list,
        description="Quotation notes",
    )

    # Currency
    document_currency_code: str = Field(
        pattern=r"^[A-Z]{3}$",
        description="ISO 4217 currency code",
    )
    pricing_currency_code: str | None = Field(
        default=None,
        pattern=r"^[A-Z]{3}$",
        description="Pricing currency",
    )
    tax_currency_code: str | None = Field(
        default=None,
        pattern=r"^[A-Z]{3}$",
        description="Tax reporting currency",
    )

    # Validity
    validity_period: Period | None = Field(
        default=None,
        description="Quotation validity period",
    )

    # References
    request_for_quotation_document_reference: DocumentReference | None = Field(
        default=None,
        description="Referenced request for quotation",
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
        description="Seller/quoting party",
    )
    buyer_customer_party: CustomerParty | None = Field(
        default=None,
        description="Buyer party",
    )
    originator_customer_party: CustomerParty | None = Field(
        default=None,
        description="Quotation originator",
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
    payment_means: PaymentMeans | None = Field(
        default=None,
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
    quoted_monetary_total: MonetaryTotal | None = Field(
        default=None,
        description="Quoted monetary totals",
    )

    # Lines
    quotation_lines: list[QuotationLine] = Field(
        default_factory=list,
        description="Quotation line items",
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
        return sum(line.quantity.value for line in self.quotation_lines)

    @property
    def calculated_line_count(self) -> int:
        """Actual number of quotation lines."""
        return len(self.quotation_lines)

    def __str__(self) -> str:
        return f"Quotation {self.id} ({len(self.quotation_lines)} lines)"


# Forward reference for sub-lines
QuotationLine.model_rebuild()
