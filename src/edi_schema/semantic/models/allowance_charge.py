"""
Semantic Allowance/Charge Models.

Discounts, surcharges, and other adjustments.
"""

from decimal import Decimal

from pydantic import Field

from .base import SemanticModel
from .primitives import Amount


class AllowanceCharge(SemanticModel):
    """
    Allowance (discount) or charge (surcharge).

    Maps to:
    - UBL: cac:AllowanceCharge
    - X12: SAC segment
    - EDIFACT: ALC segment group
    """

    # Type indicator
    charge_indicator: bool = Field(
        description="True = charge (surcharge), False = allowance (discount)"
    )

    # Reason
    allowance_charge_reason_code: str | None = Field(
        default=None,
        description="Reason code (UNTDID 5189 for charges, 4465 for allowances)",
    )
    allowance_charge_reason: str | None = Field(
        default=None,
        description="Reason description",
    )

    # Sequence
    sequence_numeric: int | None = Field(
        default=None,
        description="Sequence for calculation order",
    )
    prepaid_indicator: bool | None = Field(
        default=None,
        description="Whether already paid",
    )

    # Amounts
    multiplier_factor_numeric: Decimal | None = Field(
        default=None,
        description="Multiplier for percentage-based calculations",
    )
    amount: Amount = Field(description="Allowance or charge amount")
    base_amount: Amount | None = Field(
        default=None,
        description="Base amount for percentage calculation",
    )
    per_unit_amount: Amount | None = Field(
        default=None,
        description="Per-unit amount for quantity-based calculations",
    )

    # Calculation
    percent: Decimal | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Percentage rate",
    )

    # Tax
    tax_categories: list["TaxCategory"] = Field(
        default_factory=list,
        description="Associated tax categories",
    )
    tax_total: "TaxTotal | None" = Field(
        default=None,
        description="Tax total for this allowance/charge",
    )

    @property
    def is_allowance(self) -> bool:
        """Check if this is an allowance (discount)."""
        return not self.charge_indicator

    @property
    def is_charge(self) -> bool:
        """Check if this is a charge (surcharge)."""
        return self.charge_indicator

    def __str__(self) -> str:
        type_str = "Charge" if self.charge_indicator else "Allowance"
        return f"{type_str}: {self.amount}"


# Forward references for circular imports
from .tax import TaxCategory, TaxTotal  # noqa: E402

AllowanceCharge.model_rebuild()
