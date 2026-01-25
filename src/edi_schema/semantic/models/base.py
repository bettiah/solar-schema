"""
Semantic Model Base Classes.

Provides the foundation for all semantic business models used in
cross-format translation between X12, UBL, and EDIFACT.
"""

from pydantic import BaseModel, ConfigDict


class SemanticModel(BaseModel):
    """
    Base class for all semantic models.

    Provides common configuration for Pydantic models used in
    EDI format translation.
    """

    model_config = ConfigDict(
        # Allow extra fields for format-specific metadata
        extra="allow",
        # Use enum values in serialization
        use_enum_values=True,
        # Validate on assignment
        validate_assignment=True,
        # Allow population by field name
        populate_by_name=True,
        # Strict mode for better type checking
        strict=False,
    )
