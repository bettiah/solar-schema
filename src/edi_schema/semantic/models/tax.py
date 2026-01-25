"""
Semantic Tax Models.

Tax calculation and reporting structures.
"""

from decimal import Decimal

from pydantic import Field

from .base import SemanticModel
from .primitives import Amount


class TaxScheme(SemanticModel):
    """
    Tax scheme identification.

    Maps to:
    - UBL: cac:TaxScheme
    - X12: TXI segment tax type codes
    - EDIFACT: TAX segment
    """

    id: str | None = Field(
        default=None,
        description="Tax scheme identifier (e.g., VAT, GST, PST)",
    )
    name: str | None = Field(
        default=None,
        description="Tax scheme name",
    )
    tax_type_code: str | None = Field(
        default=None,
        description="Tax type classification code",
    )
    currency_code: str | None = Field(
        default=None,
        description="Currency for tax amounts",
    )

    def __str__(self) -> str:
        return self.id or self.name or "unspecified tax"


class TaxCategory(SemanticModel):
    """
    Tax category within a scheme.

    Maps to:
    - UBL: cac:TaxCategory
    - X12: TXI segment
    - EDIFACT: TAX segment duty/tax category
    """

    id: str | None = Field(
        default=None,
        description="Tax category code (e.g., S=Standard, Z=Zero, E=Exempt)",
    )
    name: str | None = Field(
        default=None,
        description="Tax category name",
    )
    percent: Decimal | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Tax rate as percentage",
    )
    base_unit_measure: str | None = Field(
        default=None,
        description="Unit for per-unit taxes",
    )
    per_unit_amount: Amount | None = Field(
        default=None,
        description="Tax amount per unit",
    )
    tax_exemption_reason_code: str | None = Field(
        default=None,
        description="Exemption reason code",
    )
    tax_exemption_reason: str | None = Field(
        default=None,
        description="Exemption reason text",
    )
    tier_range: str | None = Field(
        default=None,
        description="Tax tier range",
    )
    tier_rate_percent: Decimal | None = Field(
        default=None,
        description="Tier rate percentage",
    )
    tax_scheme: TaxScheme | None = Field(
        default=None,
        description="Associated tax scheme",
    )

    def __str__(self) -> str:
        if self.percent is not None:
            return f"{self.id or 'Tax'} @ {self.percent}%"
        return self.id or "unspecified category"


class TaxSubtotal(SemanticModel):
    """
    Tax subtotal for a specific category/rate.

    Maps to:
    - UBL: cac:TaxSubtotal
    - X12: TXI segment (one per tax type)
    - EDIFACT: TAX+MOA combination
    """

    taxable_amount: Amount | None = Field(
        default=None,
        description="Amount subject to tax",
    )
    tax_amount: Amount = Field(description="Calculated tax amount")
    calculation_sequence_numeric: int | None = Field(
        default=None,
        description="Calculation order",
    )
    transaction_currency_tax_amount: Amount | None = Field(
        default=None,
        description="Tax in transaction currency",
    )
    percent: Decimal | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Tax rate applied",
    )
    base_unit_measure: str | None = Field(
        default=None,
        description="Unit for per-unit taxes",
    )
    per_unit_amount: Amount | None = Field(
        default=None,
        description="Tax per unit amount",
    )
    tier_range: str | None = Field(
        default=None,
        description="Tax tier range",
    )
    tier_rate_percent: Decimal | None = Field(
        default=None,
        description="Tier rate",
    )
    tax_category: TaxCategory | None = Field(
        default=None,
        description="Tax category details",
    )

    def __str__(self) -> str:
        return f"{self.tax_amount}"


class TaxTotal(SemanticModel):
    """
    Total tax for document or line.

    Maps to:
    - UBL: cac:TaxTotal
    - X12: TXI segment total
    - EDIFACT: TAX segment group
    """

    tax_amount: Amount = Field(description="Total tax amount")
    rounding_amount: Amount | None = Field(
        default=None,
        description="Rounding adjustment",
    )
    tax_evidence_indicator: bool | None = Field(
        default=None,
        description="Whether evidence is included",
    )
    tax_included_indicator: bool | None = Field(
        default=None,
        description="Whether tax is included in prices",
    )
    tax_subtotals: list[TaxSubtotal] = Field(
        default_factory=list,
        description="Breakdown by category/rate",
    )

    def __str__(self) -> str:
        return f"Tax: {self.tax_amount}"


class WithholdingTaxTotal(SemanticModel):
    """
    Withholding tax total.

    Maps to:
    - UBL: cac:WithholdingTaxTotal
    - X12: Various tax segments
    - EDIFACT: TAX with withholding qualifier
    """

    tax_amount: Amount = Field(description="Withholding tax amount")
    tax_subtotals: list[TaxSubtotal] = Field(
        default_factory=list,
        description="Breakdown by category",
    )

    def __str__(self) -> str:
        return f"Withholding: {self.tax_amount}"
