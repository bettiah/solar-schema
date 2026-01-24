"""
X12 Validator.

Provides multi-level validation for X12 EDI documents.

Validation Levels:
1. Structural - Basic syntax (delimiters, terminators)
2. Envelope - ISA/IEA, GS/GE, ST/SE matching
3. Schema - Segment order, required segments, loop cardinality
4. Element - Data types, lengths, required elements
5. Code - Coded values against code lists
6. Semantic - Cross-element rules, conditional requirements
"""

from .code import (
    CodeValidator,
    validate_code_value,
)
from .core import (
    ValidationLevel,
    ValidationResult,
    X12Validator,
    validate_interchange,
    validate_transaction,
)
from .element import (
    ElementValidator,
    validate_element,
    validate_element_length,
    validate_element_type,
)
from .schema import (
    SchemaValidator,
    validate_loop_cardinality,
    validate_required_segments,
    validate_segment_order,
)

__all__ = [
    # Core
    "X12Validator",
    "ValidationResult",
    "ValidationLevel",
    "validate_interchange",
    "validate_transaction",
    # Element validation
    "ElementValidator",
    "validate_element",
    "validate_element_type",
    "validate_element_length",
    # Schema validation
    "SchemaValidator",
    "validate_segment_order",
    "validate_required_segments",
    "validate_loop_cardinality",
    # Code validation
    "CodeValidator",
    "validate_code_value",
]
