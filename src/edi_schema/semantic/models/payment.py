"""
Semantic Payment Models.

Payment terms, means, and instructions.
"""

from datetime import date
from decimal import Decimal

from pydantic import Field

from .base import SemanticModel
from .party import Party
from .primitives import Amount, Identifier, Period


class PaymentTerms(SemanticModel):
    """
    Payment terms.

    Maps to:
    - UBL: cac:PaymentTerms
    - X12: ITD segment
    - EDIFACT: PAT segment
    """

    id: str | None = Field(
        default=None,
        description="Terms identifier",
    )
    note: str | None = Field(
        default=None,
        description="Terms description",
    )
    reference_event_code: str | None = Field(
        default=None,
        description="Reference event for calculation",
    )
    settlement_discount_percent: Decimal | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Early payment discount percentage",
    )
    penalty_surcharge_percent: Decimal | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Late payment penalty percentage",
    )
    payment_percent: Decimal | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Percentage of total due",
    )
    amount: Amount | None = Field(
        default=None,
        description="Fixed payment amount",
    )
    settlement_discount_amount: Amount | None = Field(
        default=None,
        description="Discount amount for early payment",
    )
    penalty_amount: Amount | None = Field(
        default=None,
        description="Penalty amount for late payment",
    )
    payment_due_date: date | None = Field(
        default=None,
        description="Payment due date",
    )
    installment_due_date: date | None = Field(
        default=None,
        description="Installment due date",
    )
    invoicing_party_reference: str | None = Field(
        default=None,
        description="Invoicing party reference",
    )
    settlement_period: Period | None = Field(
        default=None,
        description="Period for settlement discount",
    )
    settlement_period_days: int | None = Field(
        default=None,
        ge=0,
        description="Number of days for settlement discount",
    )
    penalty_period: Period | None = Field(
        default=None,
        description="Period for penalty calculation",
    )
    payment_means_id: str | None = Field(
        default=None,
        description="Associated payment means ID",
    )

    def __str__(self) -> str:
        if self.payment_due_date:
            return f"Due: {self.payment_due_date}"
        if self.note:
            return self.note
        return "payment terms"


class FinancialAccount(SemanticModel):
    """
    Financial account information.

    Maps to:
    - UBL: cac:PayerFinancialAccount, cac:PayeeFinancialAccount
    - X12: Payment-related segments
    - EDIFACT: FII segment
    """

    id: Identifier | None = Field(
        default=None,
        description="Account identifier (IBAN, account number)",
    )
    name: str | None = Field(
        default=None,
        description="Account name",
    )
    alias_name: str | None = Field(
        default=None,
        description="Account alias",
    )
    account_type_code: str | None = Field(
        default=None,
        description="Account type",
    )
    account_format_code: str | None = Field(
        default=None,
        description="Account format (IBAN, BBAN, etc.)",
    )
    currency_code: str | None = Field(
        default=None,
        description="Account currency",
    )
    payment_note: str | None = Field(
        default=None,
        description="Payment note for account",
    )
    financial_institution_branch: "FinancialInstitutionBranch | None" = Field(
        default=None,
        description="Branch holding the account",
    )
    country_code: str | None = Field(
        default=None,
        description="Country of account",
    )

    def __str__(self) -> str:
        if self.id:
            return str(self.id)
        return self.name or "account"


class FinancialInstitutionBranch(SemanticModel):
    """
    Financial institution branch.

    Maps to:
    - UBL: cac:FinancialInstitutionBranch
    - X12: Bank routing information
    - EDIFACT: FII institution details
    """

    id: Identifier | None = Field(
        default=None,
        description="Branch identifier (BIC, routing number)",
    )
    name: str | None = Field(
        default=None,
        description="Branch name",
    )
    financial_institution: "FinancialInstitution | None" = Field(
        default=None,
        description="Parent institution",
    )
    address: "Address | None" = Field(
        default=None,
        description="Branch address",
    )

    def __str__(self) -> str:
        if self.id:
            return str(self.id)
        return self.name or "branch"


class FinancialInstitution(SemanticModel):
    """
    Financial institution.

    Maps to:
    - UBL: cac:FinancialInstitution
    - X12: Bank information
    - EDIFACT: FII institution
    """

    id: Identifier | None = Field(
        default=None,
        description="Institution identifier (BIC)",
    )
    name: str | None = Field(
        default=None,
        description="Institution name",
    )
    address: "Address | None" = Field(
        default=None,
        description="Institution address",
    )

    def __str__(self) -> str:
        if self.id:
            return str(self.id)
        return self.name or "institution"


class CardAccount(SemanticModel):
    """
    Payment card account.

    Maps to:
    - UBL: cac:CardAccount
    - X12: Card payment segments
    - EDIFACT: Card payment details
    """

    primary_account_number_id: str | None = Field(
        default=None,
        description="Card number (usually masked)",
    )
    network_id: str | None = Field(
        default=None,
        description="Card network (Visa, Mastercard, etc.)",
    )
    card_type_code: str | None = Field(
        default=None,
        description="Card type (credit, debit)",
    )
    validity_start_date: date | None = Field(
        default=None,
        description="Card validity start",
    )
    expiry_date: date | None = Field(
        default=None,
        description="Card expiry date",
    )
    issuer_id: str | None = Field(
        default=None,
        description="Card issuer identifier",
    )
    holder_name: str | None = Field(
        default=None,
        description="Cardholder name",
    )

    def __str__(self) -> str:
        if self.primary_account_number_id:
            return f"Card ending in {self.primary_account_number_id[-4:]}"
        return "card account"


class PaymentMandate(SemanticModel):
    """
    Payment mandate (direct debit authorization).

    Maps to:
    - UBL: cac:PaymentMandate
    - X12: Direct debit authorization
    - EDIFACT: Direct debit details
    """

    id: Identifier | None = Field(
        default=None,
        description="Mandate identifier",
    )
    mandate_type_code: str | None = Field(
        default=None,
        description="Mandate type",
    )
    maximum_payment_instructions_numeric: int | None = Field(
        default=None,
        description="Maximum payment instructions",
    )
    maximum_paid_amount: Amount | None = Field(
        default=None,
        description="Maximum amount per instruction",
    )
    signature_id: str | None = Field(
        default=None,
        description="Signature identifier",
    )
    payer_party: Party | None = Field(
        default=None,
        description="Payer party",
    )
    payer_financial_account: FinancialAccount | None = Field(
        default=None,
        description="Payer's account",
    )
    validity_period: Period | None = Field(
        default=None,
        description="Mandate validity period",
    )

    def __str__(self) -> str:
        if self.id:
            return f"Mandate {self.id}"
        return "payment mandate"


class PaymentMeans(SemanticModel):
    """
    Payment method/means.

    Maps to:
    - UBL: cac:PaymentMeans
    - X12: Various payment segments
    - EDIFACT: PAI segment
    """

    id: str | None = Field(
        default=None,
        description="Payment means identifier",
    )
    payment_means_code: str = Field(
        description="Payment means code (UNTDID 4461)",
    )
    payment_due_date: date | None = Field(
        default=None,
        description="Payment due date",
    )
    payment_channel_code: str | None = Field(
        default=None,
        description="Payment channel code",
    )
    instruction_id: str | None = Field(
        default=None,
        description="Payment instruction identifier",
    )
    instruction_note: str | None = Field(
        default=None,
        description="Payment instruction note",
    )
    payment_id: list[str] = Field(
        default_factory=list,
        description="Payment reference IDs",
    )

    # Accounts
    card_account: CardAccount | None = Field(
        default=None,
        description="Card account details",
    )
    payer_financial_account: FinancialAccount | None = Field(
        default=None,
        description="Payer's account",
    )
    payee_financial_account: FinancialAccount | None = Field(
        default=None,
        description="Payee's account",
    )
    credit_account: FinancialAccount | None = Field(
        default=None,
        description="Credit account",
    )
    payment_mandate: PaymentMandate | None = Field(
        default=None,
        description="Direct debit mandate",
    )

    def __str__(self) -> str:
        return f"Payment means: {self.payment_means_code}"


class PrepaidPayment(SemanticModel):
    """
    Prepaid payment information.

    Maps to:
    - UBL: cac:PrepaidPayment
    - X12: Prepayment references
    - EDIFACT: Prepayment details
    """

    id: str | None = Field(
        default=None,
        description="Prepayment identifier",
    )
    paid_amount: Amount | None = Field(
        default=None,
        description="Amount already paid",
    )
    received_date: date | None = Field(
        default=None,
        description="Date payment received",
    )
    paid_date: date | None = Field(
        default=None,
        description="Date of payment",
    )
    paid_time: str | None = Field(
        default=None,
        description="Time of payment",
    )
    instruction_id: str | None = Field(
        default=None,
        description="Payment instruction ID",
    )

    def __str__(self) -> str:
        if self.paid_amount:
            return f"Prepaid: {self.paid_amount}"
        return "prepaid payment"


# Forward references
from .party import Address  # noqa: E402

FinancialInstitution.model_rebuild()
FinancialInstitutionBranch.model_rebuild()
FinancialAccount.model_rebuild()
