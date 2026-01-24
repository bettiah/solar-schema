"""
EDIFACT Validator.

Provides multi-level validation for EDIFACT documents.

Validation Levels:
1. Structural - Basic syntax (delimiters, terminators)
2. Envelope - UNB/UNZ, UNG/UNE, UNH/UNT matching
3. Schema - Segment order, required segments, group cardinality
4. Element - Data types, lengths, required elements
5. Code - Coded values against UNCL code lists
6. Semantic - Cross-element rules, conditional requirements
"""

from .code import (
    DATE_TIME_QUALIFIERS,
    # Well-known code lists
    DOCUMENT_NAME_CODES,
    PARTY_FUNCTION_CODES,
    RESPONSE_TYPE_CODES,
    CodeValidationContext,
    CodeValidator,
    validate_code_value,
)
from .core import (
    EdifactValidator,
    ValidationLevel,
    ValidationResult,
    validate_interchange,
    validate_message,
)
from .element import (
    ElementValidationContext,
    ElementValidator,
    validate_element,
    validate_element_length,
    validate_element_type,
)
from .schema import (
    SchemaValidationContext,
    SchemaValidator,
    SegmentTracker,
    validate_group_cardinality,
    validate_required_segments,
    validate_segment_order,
)
from .semantic import (
    SemanticValidationContext,
    SemanticValidator,
    validate_semantics,
)

__all__ = [
    # Core
    "EdifactValidator",
    "ValidationResult",
    "ValidationLevel",
    "validate_interchange",
    "validate_message",
    # Element validation
    "ElementValidator",
    "ElementValidationContext",
    "validate_element",
    "validate_element_type",
    "validate_element_length",
    # Schema validation
    "SchemaValidator",
    "SchemaValidationContext",
    "SegmentTracker",
    "validate_segment_order",
    "validate_required_segments",
    "validate_group_cardinality",
    # Code validation
    "CodeValidator",
    "CodeValidationContext",
    "validate_code_value",
    "DOCUMENT_NAME_CODES",
    "PARTY_FUNCTION_CODES",
    "RESPONSE_TYPE_CODES",
    "DATE_TIME_QUALIFIERS",
    # Semantic validation
    "SemanticValidator",
    "SemanticValidationContext",
    "validate_semantics",
]
