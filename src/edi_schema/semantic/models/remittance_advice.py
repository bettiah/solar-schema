"""
Semantic Remittance Advice Models.

Remittance advice representations for payment notifications.
"""

from datetime import date, time
from decimal import Decimal

from pydantic import Field

from .base import SemanticModel
from .party import CustomerParty, Party, SupplierParty
from .payment import FinancialAccount, PaymentMeans
from .primitives import Amount, Period
from .reference import BillingReference, DocumentReference


class RemittanceAdviceLine(SemanticModel):
    """
    Line item in a remittance advice.

    Each line represents a payment against a specific invoice/document.

    Maps to:
    - UBL: cac:RemittanceAdviceLine
    - X12: RMR segment in 820
    - EDIFACT: DOC/MOA segment group in REMADV
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

    # Reference to paid document
    invoicing_party_reference: str | None = Field(
        default=None,
        description="Reference from invoicing party",
    )
    payee_party_reference: str | None = Field(
        default=None,
        description="Reference from payee party",
    )
    buyer_reference: str | None = Field(
        default=None,
        description="Buyer's reference",
    )

    # Amounts
    debit_line_amount: Amount | None = Field(
        default=None,
        description="Debit amount (payment owed by payer)",
    )
    credit_line_amount: Amount | None = Field(
        default=None,
        description="Credit amount (payment owed to payee)",
    )
    balance_amount: Amount | None = Field(
        default=None,
        description="Balance after this payment",
    )
    payment_purpose_code: str | None = Field(
        default=None,
        description="Payment purpose code",
    )

    # Periods
    invoice_period: list[Period] = Field(
        default_factory=list,
        description="Invoice periods covered",
    )

    # References
    billing_references: list[BillingReference] = Field(
        default_factory=list,
        description="References to invoices being paid",
    )
    document_references: list[DocumentReference] = Field(
        default_factory=list,
        description="Additional document references",
    )

    # Parties
    payee_party: Party | None = Field(
        default=None,
        description="Payee for this line",
    )
    originator_party: Party | None = Field(
        default=None,
        description="Originator of this line",
    )

    # Exchange rate
    exchange_rate: Decimal | None = Field(
        default=None,
        description="Exchange rate used for conversion",
    )
    exchange_rate_currency: str | None = Field(
        default=None,
        description="Currency for exchange rate",
    )

    def __str__(self) -> str:
        amount = self.credit_line_amount or self.debit_line_amount
        return f"RemittanceLine {self.id}: {amount}"


class RemittanceAdvice(SemanticModel):
    """
    Semantic Remittance Advice model.

    Represents notification of payment or payment details sent by a payer to a payee.

    Maps to:
    - X12: 820 Payment Order/Remittance Advice
    - UBL: RemittanceAdvice
    - EDIFACT: REMADV

    Example:
        >>> remittance = RemittanceAdvice(
        ...     id="REM-001",
        ...     issue_date=date(2024, 1, 15),
        ...     document_currency_code="USD",
        ...     total_debit_amount=Amount(value=Decimal("1000.00"), currency="USD"),
        ...     accounting_customer_party=CustomerParty(party=Party(...)),
        ...     payee_party=Party(...),
        ... )
    """

    # Identification
    id: str = Field(description="Remittance advice number")
    uuid: str | None = Field(
        default=None,
        description="UUID for this remittance advice",
    )
    issue_date: date = Field(description="Issue date")
    issue_time: time | None = Field(
        default=None,
        description="Issue time",
    )

    # Type
    remittance_advice_type_code: str | None = Field(
        default=None,
        description="Type code (original, replacement, etc.)",
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

    # Amounts
    total_debit_amount: Amount | None = Field(
        default=None,
        description="Total debit amount",
    )
    total_credit_amount: Amount | None = Field(
        default=None,
        description="Total credit amount",
    )
    total_payment_amount: Amount | None = Field(
        default=None,
        description="Total payment amount",
    )

    # Line count
    line_count: int | None = Field(
        default=None,
        description="Number of line items",
    )

    # Periods
    invoice_period: list[Period] = Field(
        default_factory=list,
        description="Invoice periods covered",
    )

    # References
    additional_document_references: list[DocumentReference] = Field(
        default_factory=list,
        description="Additional document references",
    )

    # Parties
    accounting_customer_party: CustomerParty | None = Field(
        default=None,
        description="Payer party (accounting customer)",
    )
    accounting_supplier_party: SupplierParty | None = Field(
        default=None,
        description="Payee party (accounting supplier)",
    )
    payee_party: Party | None = Field(
        default=None,
        description="Payee party (if different from supplier)",
    )

    # Payment details
    payment_means: PaymentMeans | None = Field(
        default=None,
        description="Payment means used",
    )
    payee_financial_account: FinancialAccount | None = Field(
        default=None,
        description="Payee's financial account",
    )
    payer_financial_account: FinancialAccount | None = Field(
        default=None,
        description="Payer's financial account",
    )

    # Totals
    tax_total: Amount | None = Field(
        default=None,
        description="Total tax amount",
    )

    # Lines
    remittance_advice_lines: list[RemittanceAdviceLine] = Field(
        default_factory=list,
        description="Remittance line items",
    )

    # Source tracking
    _source_format: str | None = None
    _source_version: str | None = None

    @property
    def calculated_line_count(self) -> int:
        """Actual number of remittance lines."""
        return len(self.remittance_advice_lines)

    @property
    def net_payment_amount(self) -> Amount | None:
        """Calculate net payment from credits minus debits."""
        if self.total_credit_amount and self.total_debit_amount:
            if self.total_credit_amount.currency != self.total_debit_amount.currency:
                return None
            net_value = self.total_credit_amount.value - self.total_debit_amount.value
            return Amount(value=net_value, currency=self.total_credit_amount.currency)
        return self.total_credit_amount or self.total_debit_amount

    def __str__(self) -> str:
        amount = self.total_payment_amount or self.total_credit_amount or self.total_debit_amount
        return f"RemittanceAdvice {self.id}: {amount}"


# Forward references
RemittanceAdvice.model_rebuild()
RemittanceAdviceLine.model_rebuild()
