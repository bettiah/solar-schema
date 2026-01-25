"""
Semantic Primitive Types.

Core data types used throughout the semantic model hierarchy,
aligned with UN/CEFACT CCTS representation terms.
"""

from datetime import date, time
from decimal import Decimal
from typing import Annotated

from pydantic import Field

from .base import SemanticModel


class Amount(SemanticModel):
    """
    Monetary amount with currency.

    Maps to:
    - UBL: cbc:*Amount (AmountType)
    - X12: Monetary amounts with implied decimals
    - EDIFACT: MOA segment amounts
    """

    value: Decimal = Field(description="The monetary value")
    currency: str = Field(
        pattern=r"^[A-Z]{3}$",
        description="ISO 4217 currency code (e.g., USD, EUR, GBP)",
    )

    def __str__(self) -> str:
        return f"{self.value} {self.currency}"


class Quantity(SemanticModel):
    """
    Numeric quantity with unit of measure.

    Maps to:
    - UBL: cbc:*Quantity (QuantityType)
    - X12: Quantity fields with UOM element
    - EDIFACT: QTY segment
    """

    value: Decimal = Field(description="The numeric quantity value")
    unit_code: str = Field(description="UNECE Rec 20 unit of measure code (e.g., EA, KG, LB)")

    def __str__(self) -> str:
        return f"{self.value} {self.unit_code}"


class Measure(SemanticModel):
    """
    Physical measurement with unit.

    Maps to:
    - UBL: cbc:*Measure (MeasureType)
    - X12: Weight, dimension fields
    - EDIFACT: MEA segment
    """

    value: Decimal = Field(description="The measurement value")
    unit_code: str = Field(description="UNECE Rec 20 unit code")

    def __str__(self) -> str:
        return f"{self.value} {self.unit_code}"


class Identifier(SemanticModel):
    """
    Identifier with optional scheme information.

    Maps to:
    - UBL: cbc:ID with schemeID/schemeAgencyID attributes
    - X12: Various ID fields with qualifiers
    - EDIFACT: Identifiers with code list qualifiers
    """

    value: str = Field(description="The identifier value")
    scheme_id: str | None = Field(
        default=None,
        description="Identifier scheme (e.g., DUNS, GLN, UPC, EAN)",
    )
    scheme_agency_id: str | None = Field(
        default=None,
        description="Agency maintaining the scheme (e.g., 6=UN, 9=EAN)",
    )
    scheme_name: str | None = Field(
        default=None,
        description="Human-readable name of the scheme",
    )

    def __str__(self) -> str:
        if self.scheme_id:
            return f"{self.value} ({self.scheme_id})"
        return self.value


class Code(SemanticModel):
    """
    Coded value from a controlled vocabulary.

    Maps to:
    - UBL: cbc:*Code (CodeType)
    - X12: Coded element values
    - EDIFACT: Coded data elements
    """

    value: str = Field(description="The code value")
    list_id: str | None = Field(
        default=None,
        description="Code list identifier",
    )
    list_agency_id: str | None = Field(
        default=None,
        description="Agency maintaining the code list",
    )
    list_version_id: str | None = Field(
        default=None,
        description="Version of the code list",
    )
    name: str | None = Field(
        default=None,
        description="Human-readable name for the code",
    )

    def __str__(self) -> str:
        return self.value


class Period(SemanticModel):
    """
    Date/time period with optional start and end bounds.

    Maps to:
    - UBL: cac:Period
    - X12: DTM segments with date ranges
    - EDIFACT: DTM segments
    """

    start_date: date | None = Field(
        default=None,
        description="Period start date",
    )
    end_date: date | None = Field(
        default=None,
        description="Period end date",
    )
    start_time: time | None = Field(
        default=None,
        description="Period start time",
    )
    end_time: time | None = Field(
        default=None,
        description="Period end time",
    )
    description: str | None = Field(
        default=None,
        description="Description of the period",
    )

    def __str__(self) -> str:
        parts = []
        if self.start_date:
            parts.append(f"from {self.start_date}")
        if self.end_date:
            parts.append(f"to {self.end_date}")
        return " ".join(parts) if parts else "unspecified period"


class Text(SemanticModel):
    """
    Text content with optional language identifier.

    Maps to:
    - UBL: cbc:*Text, cbc:Note, cbc:Description
    - X12: MSG, NTE segments
    - EDIFACT: FTX segment
    """

    value: str = Field(description="The text content")
    language_id: str | None = Field(
        default=None,
        description="ISO 639-1 language code (e.g., en, de, fr)",
    )

    def __str__(self) -> str:
        return self.value


# Type aliases for common patterns
AmountType = Annotated[Amount, Field(description="Monetary amount")]
QuantityType = Annotated[Quantity, Field(description="Quantity with unit")]
IdentifierType = Annotated[Identifier, Field(description="Identifier with scheme")]
