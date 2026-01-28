"""
Semantic Invoice Models.

Invoice and credit/debit note representations.
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
from .payment import PaymentMeans, PaymentTerms, PrepaidPayment
from .primitives import Amount, Period, Quantity
from .reference import (
    BillingReference,
    DespatchLineReference,
    DocumentReference,
    OrderLineReference,
    ReceiptLineReference,
)
from .tax import TaxTotal, WithholdingTaxTotal


class InvoiceLine(SemanticModel):
    """
    Line item in an invoice.

    Maps to:
    - UBL: cac:InvoiceLine
    - X12: IT1 loop (IT1, PID, SAC, TXI, etc.)
    - EDIFACT: LIN segment group in INVOIC
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

    # Quantity and amounts
    invoiced_quantity: Quantity | None = Field(
        default=None,
        description="Invoiced quantity",
    )
    line_extension_amount: Amount | None = Field(
        default=None,
        description="Line total (before tax)",
    )
    tax_point_date: date | None = Field(
        default=None,
        description="Tax point date",
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
    payment_purpose_code: str | None = Field(
        default=None,
        description="Payment purpose code",
    )
    free_of_charge_indicator: bool | None = Field(
        default=None,
        description="Whether line is free of charge",
    )

    # Periods
    invoice_period: list[Period] = Field(
        default_factory=list,
        description="Invoice periods for this line",
    )

    # References
    order_line_references: list[OrderLineReference] = Field(
        default_factory=list,
        description="Order line references",
    )
    despatch_line_references: list[DespatchLineReference] = Field(
        default_factory=list,
        description="Despatch line references",
    )
    receipt_line_references: list[ReceiptLineReference] = Field(
        default_factory=list,
        description="Receipt line references",
    )
    billing_references: list[BillingReference] = Field(
        default_factory=list,
        description="Billing references",
    )
    document_references: list[DocumentReference] = Field(
        default_factory=list,
        description="Document references",
    )

    # Origin
    originator_party: Party | None = Field(
        default=None,
        description="Line originator party",
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
    tax_total: list[TaxTotal] = Field(
        default_factory=list,
        description="Line tax totals",
    )
    withholding_tax_total: list[WithholdingTaxTotal] = Field(
        default_factory=list,
        description="Withholding tax totals",
    )

    # Item and price
    item: Item = Field(description="Item details")
    price: Price | None = Field(
        default=None,
        description="Unit price",
    )

    # Sub-lines
    sub_invoice_lines: list["InvoiceLine"] = Field(
        default_factory=list,
        description="Sub-invoice lines",
    )

    def __str__(self) -> str:
        return f"Line {self.id}: {self.invoiced_quantity} x {self.item}"


class Invoice(SemanticModel):
    """
    Semantic Invoice model.

    Central document representing an invoice in format-agnostic form.

    Maps to:
    - X12: 810 Invoice
    - UBL: Invoice
    - EDIFACT: INVOIC

    Example:
        >>> invoice = Invoice(
        ...     id="INV-001",
        ...     issue_date=date(2024, 1, 15),
        ...     document_currency_code="USD",
        ...     accounting_supplier_party=SupplierParty(party=Party(...)),
        ...     accounting_customer_party=CustomerParty(party=Party(...)),
        ...     legal_monetary_total=MonetaryTotal(payable_amount=Amount(...)),
        ...     invoice_lines=[InvoiceLine(...)]
        ... )
    """

    # Identification
    id: str = Field(description="Invoice number")
    uuid: str | None = Field(
        default=None,
        description="UUID for this invoice",
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
    issue_date: date = Field(description="Invoice issue date")
    issue_time: time | None = Field(
        default=None,
        description="Invoice issue time",
    )
    due_date: date | None = Field(
        default=None,
        description="Payment due date",
    )
    tax_point_date: date | None = Field(
        default=None,
        description="Tax point date",
    )

    # Type
    invoice_type_code: str | None = Field(
        default=None,
        description="Invoice type code (380=Commercial, 381=Credit, etc.)",
    )

    # Notes
    note: list[str] = Field(
        default_factory=list,
        description="Invoice notes",
    )

    # Currency
    document_currency_code: str = Field(
        pattern=r"^[A-Z]{3}$",
        description="ISO 4217 document currency code",
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
    payment_currency_code: str | None = Field(
        default=None,
        pattern=r"^[A-Z]{3}$",
        description="Payment currency",
    )
    payment_alternative_currency_code: str | None = Field(
        default=None,
        pattern=r"^[A-Z]{3}$",
        description="Alternative payment currency",
    )

    # Exchange rates
    pricing_exchange_rate: Decimal | None = Field(
        default=None,
        description="Pricing currency exchange rate",
    )
    payment_exchange_rate: Decimal | None = Field(
        default=None,
        description="Payment currency exchange rate",
    )
    payment_alternative_exchange_rate: Decimal | None = Field(
        default=None,
        description="Alternative payment exchange rate",
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
    buyer_reference: str | None = Field(
        default=None,
        description="Buyer reference",
    )

    # Periods
    invoice_period: list[Period] = Field(
        default_factory=list,
        description="Invoice periods",
    )

    # References
    order_reference: "OrderReference | None" = Field(
        default=None,
        description="Purchase order reference",
    )
    billing_references: list[BillingReference] = Field(
        default_factory=list,
        description="Billing references",
    )
    despatch_document_reference: DocumentReference | None = Field(
        default=None,
        description="Despatch/shipping document reference",
    )
    receipt_document_reference: DocumentReference | None = Field(
        default=None,
        description="Receipt document reference",
    )
    statement_document_reference: DocumentReference | None = Field(
        default=None,
        description="Statement document reference",
    )
    originator_document_reference: DocumentReference | None = Field(
        default=None,
        description="Originator document reference",
    )
    contract_document_reference: DocumentReference | None = Field(
        default=None,
        description="Contract reference",
    )
    additional_document_references: list[DocumentReference] = Field(
        default_factory=list,
        description="Additional document references",
    )

    # Parties
    accounting_supplier_party: SupplierParty | None = Field(
        default=None,
        description="Seller/supplier party",
    )
    accounting_customer_party: CustomerParty | None = Field(
        default=None,
        description="Buyer/customer party",
    )
    payee_party: Party | None = Field(
        default=None,
        description="Payee (if different from seller)",
    )
    buyer_customer_party: CustomerParty | None = Field(
        default=None,
        description="Buyer party (if different from accounting customer)",
    )
    seller_supplier_party: SupplierParty | None = Field(
        default=None,
        description="Seller party (if different from accounting supplier)",
    )
    tax_representative_party: Party | None = Field(
        default=None,
        description="Tax representative party",
    )

    # Delivery
    delivery: list[Delivery] = Field(
        default_factory=list,
        description="Delivery information",
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
    prepaid_payments: list[PrepaidPayment] = Field(
        default_factory=list,
        description="Prepaid payments",
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
    withholding_tax_total: list[WithholdingTaxTotal] = Field(
        default_factory=list,
        description="Withholding tax totals",
    )

    # Totals
    legal_monetary_total: MonetaryTotal | None = Field(
        default=None,
        description="Invoice monetary totals",
    )

    # Lines
    invoice_lines: list[InvoiceLine] = Field(
        default_factory=list,
        description="Invoice line items",
    )

    # Line count (for validation)
    line_count: int | None = Field(
        default=None,
        description="Number of line items",
    )

    # Source tracking
    _source_format: str | None = None
    _source_version: str | None = None

    @property
    def calculated_line_count(self) -> int:
        """Actual number of invoice lines."""
        return len(self.invoice_lines)

    @property
    def is_credit_note(self) -> bool:
        """Check if this is a credit note."""
        return self.invoice_type_code in ("381", "Credit")

    def __str__(self) -> str:
        return f"Invoice {self.id} ({len(self.invoice_lines)} lines)"


class CreditNote(SemanticModel):
    """
    Semantic Credit Note model.

    Represents a credit memo/credit note for reducing amounts owed.

    Maps to:
    - X12: 812 Credit/Debit Adjustment
    - UBL: CreditNote
    - EDIFACT: CREMUL
    """

    # Identification
    id: str = Field(description="Credit note number")
    uuid: str | None = Field(
        default=None,
        description="UUID for this credit note",
    )
    issue_date: date = Field(description="Issue date")
    issue_time: time | None = Field(
        default=None,
        description="Issue time",
    )
    tax_point_date: date | None = Field(
        default=None,
        description="Tax point date",
    )
    credit_note_type_code: str | None = Field(
        default=None,
        description="Credit note type code",
    )
    note: list[str] = Field(
        default_factory=list,
        description="Notes",
    )

    # Currency
    document_currency_code: str = Field(
        pattern=r"^[A-Z]{3}$",
        description="Document currency",
    )
    tax_currency_code: str | None = Field(
        default=None,
        description="Tax currency",
    )

    # Accounting
    accounting_cost: str | None = Field(
        default=None,
        description="Accounting cost",
    )
    buyer_reference: str | None = Field(
        default=None,
        description="Buyer reference",
    )

    # Periods
    invoice_period: list[Period] = Field(
        default_factory=list,
        description="Credit note periods",
    )

    # References
    discrepancy_response: list[DocumentReference] = Field(
        default_factory=list,
        description="Discrepancy responses",
    )
    order_reference: "OrderReference | None" = Field(
        default=None,
        description="Order reference",
    )
    billing_references: list[BillingReference] = Field(
        default_factory=list,
        description="Billing references",
    )
    despatch_document_reference: DocumentReference | None = Field(
        default=None,
        description="Despatch reference",
    )
    receipt_document_reference: DocumentReference | None = Field(
        default=None,
        description="Receipt reference",
    )
    contract_document_reference: DocumentReference | None = Field(
        default=None,
        description="Contract reference",
    )
    additional_document_references: list[DocumentReference] = Field(
        default_factory=list,
        description="Additional references",
    )

    # Parties
    accounting_supplier_party: SupplierParty = Field(
        description="Supplier party",
    )
    accounting_customer_party: CustomerParty = Field(
        description="Customer party",
    )
    payee_party: Party | None = Field(
        default=None,
        description="Payee party",
    )
    tax_representative_party: Party | None = Field(
        default=None,
        description="Tax representative",
    )

    # Delivery
    delivery: list[Delivery] = Field(
        default_factory=list,
        description="Delivery information",
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

    # Allowances and charges
    allowance_charges: list[AllowanceCharge] = Field(
        default_factory=list,
        description="Allowances/charges",
    )

    # Tax
    tax_total: list[TaxTotal] = Field(
        default_factory=list,
        description="Tax totals",
    )

    # Totals
    legal_monetary_total: MonetaryTotal = Field(
        description="Credit note totals",
    )

    # Lines
    credit_note_lines: list["CreditNoteLine"] = Field(
        default_factory=list,
        description="Credit note lines",
    )

    # Source tracking
    _source_format: str | None = None
    _source_version: str | None = None

    def __str__(self) -> str:
        return f"CreditNote {self.id}"


class CreditNoteLine(SemanticModel):
    """Credit note line item."""

    id: str = Field(description="Line number")
    uuid: str | None = Field(default=None)
    note: list[str] = Field(default_factory=list)
    credited_quantity: Quantity = Field(description="Credited quantity")
    line_extension_amount: Amount = Field(description="Line total")
    accounting_cost: str | None = Field(default=None)
    tax_point_date: date | None = Field(default=None)
    invoice_period: list[Period] = Field(default_factory=list)

    # References
    order_line_references: list[OrderLineReference] = Field(default_factory=list)
    despatch_line_references: list[DespatchLineReference] = Field(default_factory=list)
    receipt_line_references: list[ReceiptLineReference] = Field(default_factory=list)
    billing_references: list[BillingReference] = Field(default_factory=list)
    document_references: list[DocumentReference] = Field(default_factory=list)

    # Delivery
    delivery: list[Delivery] = Field(default_factory=list)

    # Allowances and charges
    allowance_charges: list[AllowanceCharge] = Field(default_factory=list)

    # Tax
    tax_total: list[TaxTotal] = Field(default_factory=list)

    # Item and price
    item: Item = Field(description="Item details")
    price: Price | None = Field(default=None)

    # Sub-lines
    sub_credit_note_lines: list["CreditNoteLine"] = Field(default_factory=list)

    def __str__(self) -> str:
        return f"CreditLine {self.id}: {self.credited_quantity} x {self.item}"


# Forward references
from .reference import OrderReference  # noqa: E402

Invoice.model_rebuild()
CreditNote.model_rebuild()
InvoiceLine.model_rebuild()
CreditNoteLine.model_rebuild()
