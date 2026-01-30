"""
Declarative Mapping System for EDI Semantic Translation.

This module provides a declarative approach to mapping between X12 transactions
and semantic business models, replacing procedural mapper code with data-driven
mapping definitions.

Example usage:
    from edi_schema.semantic.mapping import MappingEngine, MessageContext
    from edi_schema.semantic.mapping.x12 import ORDER_850_MAPPING

    # Create context with envelope and external metadata
    context = MessageContext.from_parse_result(
        parse_result,
        filename="850_order.x12",
        received_at=datetime.now(),
    )

    # Create mapper and convert
    engine = MappingEngine(ORDER_850_MAPPING)
    result = engine.to_semantic(transaction, context=context)

    if result.success:
        order = result.model
    else:
        for error in result.errors:
            print(f"Error: {error}")
"""

from .context import MessageContext
from .diagnostics import (
    AggregateMetrics,
    MappingLogger,
    MappingMetrics,
    MappingStep,
    MappingTrace,
)
from .builder_engine import BuilderMappingEngine
from .engine import MappingEngine
from .errors import (
    ErrorAccumulator,
    ErrorContext,
    ErrorHandlingMode,
    MappingError,
    MappingErrorCode,
    MappingErrorSeverity,
    MappingException,
)
from .result import BatchMappingResult, MappingResult
from .transforms import (
    IDENTITY,
    PARSE_AMOUNT_CENTS,
    PARSE_BOOLEAN,
    PARSE_DATE,
    PARSE_DATE_YYMMDD,
    PARSE_DECIMAL,
    PARSE_TIME,
    STRIP,
    TO_INT,
    Transform,
    TransformRegistry,
    create_code_map_transform,
    get_transform,
    register_transform,
)
from .types import (
    ContextPath,
    EnvelopePath,
    FieldMapping,
    LoopMapping,
    PartyLoopMapping,
    QualifiedMapping,
    SegmentPath,
    SemanticPath,
    SourcePath,
    TransactionMapping,
    ctx,
    env,
    seg,
    sem,
)
from .validation import (
    CompositeValidationRule,
    ConditionalValidationRule,
    CrossFieldValidationRule,
    FieldValidationRule,
    RequiredFieldRule,
    ValidationRule,
    get_nested_attr,
    has_length,
    is_in_list,
    is_in_range,
    is_non_negative,
    is_not_empty,
    is_positive,
    is_valid_country_code,
    is_valid_currency_code,
    is_valid_date,
    is_valid_unit_code,
    matches_pattern,
)
from .validators import (
    FieldCoverage,
    MappingCoverageReport,
    MappingValidator,
    SegmentCoverage,
    generate_coverage_report,
    print_coverage_report,
)

__all__ = [
    # Core Engine
    "MappingEngine",
    "BuilderMappingEngine",
    "MessageContext",
    # Results
    "MappingResult",
    "BatchMappingResult",
    # Types - Paths
    "SegmentPath",
    "EnvelopePath",
    "ContextPath",
    "SemanticPath",
    "SourcePath",
    # Types - Path helpers
    "seg",
    "env",
    "ctx",
    "sem",
    # Types - Mappings
    "FieldMapping",
    "QualifiedMapping",
    "LoopMapping",
    "PartyLoopMapping",
    "TransactionMapping",
    # Transforms
    "Transform",
    "TransformRegistry",
    "PARSE_DATE",
    "PARSE_DATE_YYMMDD",
    "PARSE_TIME",
    "PARSE_DECIMAL",
    "PARSE_AMOUNT_CENTS",
    "TO_INT",
    "IDENTITY",
    "STRIP",
    "PARSE_BOOLEAN",
    "create_code_map_transform",
    "get_transform",
    "register_transform",
    # Errors
    "MappingError",
    "MappingErrorCode",
    "MappingErrorSeverity",
    "MappingException",
    "ErrorAccumulator",
    "ErrorContext",
    "ErrorHandlingMode",
    # Validation
    "ValidationRule",
    "FieldValidationRule",
    "RequiredFieldRule",
    "CrossFieldValidationRule",
    "ConditionalValidationRule",
    "CompositeValidationRule",
    # Built-in validators
    "is_not_empty",
    "is_positive",
    "is_non_negative",
    "is_valid_date",
    "is_valid_currency_code",
    "is_valid_country_code",
    "is_valid_unit_code",
    "matches_pattern",
    "is_in_list",
    "has_length",
    "is_in_range",
    "get_nested_attr",
    # Coverage/Validation
    "MappingValidator",
    "MappingCoverageReport",
    "FieldCoverage",
    "SegmentCoverage",
    "generate_coverage_report",
    "print_coverage_report",
    # Diagnostics
    "MappingLogger",
    "MappingMetrics",
    "AggregateMetrics",
    "MappingTrace",
    "MappingStep",
]
