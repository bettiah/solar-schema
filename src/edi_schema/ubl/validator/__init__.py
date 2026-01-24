"""
UBL Document Validator.

This package provides validation for UBL XML documents:
- Schema validation (structure, cardinality)
- Element validation (data types, formats)
- Code validation (code list membership)
"""

from .core import (
    create_validator,
    UBLValidator,
    ValidationContext,
    ValidationLevel,
    ValidationResult,
)
from .code import validate_codes
from .element import validate_element_types
from .schema import (
    get_missing_required_elements,
    get_unexpected_elements,
    validate_cardinality,
    validate_structure,
)

__all__ = [
    # Core
    "create_validator",
    "UBLValidator",
    "ValidationContext",
    "ValidationLevel",
    "ValidationResult",
    # Validators
    "validate_cardinality",
    "validate_codes",
    "validate_element_types",
    "validate_structure",
    # Utilities
    "get_missing_required_elements",
    "get_unexpected_elements",
]
