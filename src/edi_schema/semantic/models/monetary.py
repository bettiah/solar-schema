"""
Semantic Monetary Total Models.

Document-level monetary summaries.
"""

from pydantic import Field

from .base import SemanticModel
from .primitives import Amount


class MonetaryTotal(SemanticModel):
    """
    Document monetary totals.

    Maps to:
    - UBL: cac:LegalMonetaryTotal, cac:AnticipatedMonetaryTotal, cac:RequestedMonetaryTotal
    - X12: TDS segment (amounts in cents)
    - EDIFACT: MOA segment group
    """

    line_extension_amount: Amount | None = Field(
        default=None,
        description="Sum of line extension amounts (before allowances/charges/tax)",
    )
    tax_exclusive_amount: Amount | None = Field(
        default=None,
        description="Total excluding tax",
    )
    tax_inclusive_amount: Amount | None = Field(
        default=None,
        description="Total including tax",
    )
    allowance_total_amount: Amount | None = Field(
        default=None,
        description="Total allowances (discounts)",
    )
    charge_total_amount: Amount | None = Field(
        default=None,
        description="Total charges (surcharges)",
    )
    prepaid_amount: Amount | None = Field(
        default=None,
        description="Amount already paid",
    )
    payable_rounding_amount: Amount | None = Field(
        default=None,
        description="Rounding adjustment",
    )
    payable_amount: Amount | None = Field(
        default=None,
        description="Amount payable (final total)",
    )
    payable_alternative_amount: Amount | None = Field(
        default=None,
        description="Alternative payable amount",
    )

    def __str__(self) -> str:
        if self.payable_amount:
            return f"Total: {self.payable_amount}"
        if self.tax_inclusive_amount:
            return f"Total: {self.tax_inclusive_amount}"
        return "monetary total"
