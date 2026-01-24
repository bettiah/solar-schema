"""
X12 Validator Core.

Provides multi-level validation for X12 EDI documents by orchestrating
the specialized validators.

Validation Levels:
1. Structural - Basic syntax (delimiters, terminators) - done in tokenizer
2. Envelope - ISA/IEA, GS/GE, ST/SE matching - done in envelope parser
3. Schema - Segment order, required segments, loop cardinality
4. Element - Data types, lengths, required elements
5. Code - Coded values against code lists
6. Semantic - Cross-element rules, conditional requirements
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

from edi_schema.x12.ast import (
    ErrorCategory,
    ErrorSeverity,
    FunctionalGroupInstance,
    InterchangeInstance,
    LoopInstance,
    ParsedSegment,
    ParseError,
    TransactionSetInstance,
)
from edi_schema.x12.enums import RequirementDesignator
from edi_schema.x12.validator.code import (
    CodeValidationContext,
    CodeValidator,
)
from edi_schema.x12.validator.element import (
    ElementValidationContext,
    ElementValidator,
)
from edi_schema.x12.validator.schema import (
    SchemaValidationContext,
    SchemaValidator,
)

if TYPE_CHECKING:
    from edi_schema.x12.schema import X12Schema, X12SchemaLoader
    from edi_schema.x12.schemas import GeneratedX12SchemaLoader


class ValidationLevel(Enum):
    """Validation levels."""

    STRUCTURAL = auto()  # Level 1
    ENVELOPE = auto()  # Level 2
    SCHEMA = auto()  # Level 3
    ELEMENT = auto()  # Level 4
    CODE = auto()  # Level 5
    SEMANTIC = auto()  # Level 6


@dataclass
class ValidationResult:
    """Result of validation."""

    errors: list[ParseError] = field(default_factory=list)
    warnings: list[ParseError] = field(default_factory=list)

    # Counts by level
    structural_errors: int = 0
    envelope_errors: int = 0
    schema_errors: int = 0
    element_errors: int = 0
    code_errors: int = 0
    semantic_errors: int = 0

    def is_valid(self) -> bool:
        """Check if validation passed (no errors)."""
        return len(self.errors) == 0

    def is_accepted(self) -> bool:
        """Check if document should be accepted (for 997 response)."""
        # Accepted if no errors (warnings are OK)
        return len(self.errors) == 0

    def total_errors(self) -> int:
        """Total number of errors."""
        return len(self.errors)

    def total_warnings(self) -> int:
        """Total number of warnings."""
        return len(self.warnings)

    def add_error(self, error: ParseError) -> None:
        """Add an error or warning."""
        if error.severity == ErrorSeverity.WARNING:
            self.warnings.append(error)
        else:
            self.errors.append(error)

        # Track by category
        if error.category == ErrorCategory.STRUCTURAL:
            self.structural_errors += 1
        elif error.category == ErrorCategory.ENVELOPE:
            self.envelope_errors += 1
        elif error.category == ErrorCategory.SCHEMA:
            self.schema_errors += 1
        elif error.category == ErrorCategory.ELEMENT:
            self.element_errors += 1
        elif error.category == ErrorCategory.CODE:
            self.code_errors += 1
        elif error.category == ErrorCategory.SEMANTIC:
            self.semantic_errors += 1

    def merge(self, other: "ValidationResult") -> None:
        """Merge another result into this one."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.structural_errors += other.structural_errors
        self.envelope_errors += other.envelope_errors
        self.schema_errors += other.schema_errors
        self.element_errors += other.element_errors
        self.code_errors += other.code_errors
        self.semantic_errors += other.semantic_errors


class X12Validator:
    """
    Multi-level X12 document validator.

    Validates parsed X12 documents against schemas with configurable
    validation levels and error reporting suitable for 997/999 generation.

    Usage:
        validator = X12Validator(schema_loader)
        result = validator.validate(interchange)
        if not result.is_valid():
            for error in result.errors:
                print(error)
    """

    def __init__(
        self,
        schema_loader: "X12SchemaLoader | GeneratedX12SchemaLoader | None" = None,
        levels: set[ValidationLevel] | None = None,
        strict_codes: bool = False,
    ):
        """
        Initialize the validator.

        Args:
            schema_loader: Loader for X12 schemas
            levels: Which validation levels to run (default: all)
            strict_codes: If True, invalid codes are errors; if False, warnings
        """
        self.schema_loader = schema_loader
        self.levels = levels or {
            ValidationLevel.STRUCTURAL,
            ValidationLevel.ENVELOPE,
            ValidationLevel.SCHEMA,
            ValidationLevel.ELEMENT,
            ValidationLevel.CODE,
            ValidationLevel.SEMANTIC,
        }
        self.strict_codes = strict_codes

        # Specialized validators
        self.element_validator = ElementValidator()
        self.code_validator = CodeValidator(strict=strict_codes)

    def validate(
        self,
        interchange: InterchangeInstance,
    ) -> ValidationResult:
        """
        Validate a complete interchange.

        Args:
            interchange: The parsed interchange

        Returns:
            ValidationResult with all errors and warnings
        """
        result = ValidationResult()

        # Level 1-2: Structural and envelope errors are already captured
        # during parsing - add them to result
        for error in interchange.errors:
            result.add_error(error)

        # Validate each group
        for group in interchange.groups:
            group_result = self._validate_group(group)
            result.merge(group_result)

        return result

    def _validate_group(
        self,
        group: FunctionalGroupInstance,
    ) -> ValidationResult:
        """Validate a functional group."""
        result = ValidationResult()

        # Add any group-level errors from parsing
        for error in group.errors:
            result.add_error(error)

        # Validate each transaction
        for txn in group.transactions:
            txn_result = self._validate_transaction(txn, group)
            result.merge(txn_result)

        return result

    def _validate_transaction(
        self,
        txn: TransactionSetInstance,
        group: FunctionalGroupInstance,
    ) -> ValidationResult:
        """Validate a transaction set."""
        result = ValidationResult()

        # Add any transaction-level errors from parsing
        for error in txn.errors:
            result.add_error(error)

        # Load schema if available
        schema = None
        if self.schema_loader:
            try:
                schema = self.schema_loader.load(txn.transaction_id)
            except Exception:
                # Schema not found - continue without schema validation
                pass

        # Level 3: Schema validation
        if schema and ValidationLevel.SCHEMA in self.levels:
            schema_result = self._validate_schema(txn, schema, group)
            result.merge(schema_result)

        # Level 4-5: Element and code validation
        if ValidationLevel.ELEMENT in self.levels or ValidationLevel.CODE in self.levels:
            content_result = self._validate_content(txn, schema, group)
            result.merge(content_result)

        # Level 6: Semantic validation
        if ValidationLevel.SEMANTIC in self.levels:
            semantic_result = self._validate_semantics(txn, schema)
            result.merge(semantic_result)

        return result

    def _validate_schema(
        self,
        txn: TransactionSetInstance,
        schema: "X12Schema",
        group: FunctionalGroupInstance,
    ) -> ValidationResult:
        """Run schema validation (Level 3)."""
        result = ValidationResult()

        context = SchemaValidationContext(
            transaction_id=txn.transaction_id,
            group_control=group.control_number,
        )

        validator = SchemaValidator(schema)
        errors = validator.validate(txn.content, context)

        for error in errors:
            result.add_error(error)

        return result

    def _validate_content(
        self,
        txn: TransactionSetInstance,
        schema: "X12Schema | None",
        group: FunctionalGroupInstance,
    ) -> ValidationResult:
        """Run element and code validation (Level 4-5)."""
        result = ValidationResult()

        # Get all segments
        all_segments = self._flatten_content(txn.content)

        for i, segment in enumerate(all_segments):
            position = i + 1

            # Find segment definition in schema
            seg_def = None
            if schema:
                for s in schema.get_structure():
                    if s.segment_id == segment.tag:
                        seg_def = s
                        break

            # Validate each element
            for j, element in enumerate(segment.elements):
                elem_position = j + 1

                # Create validation context
                elem_context = ElementValidationContext(
                    segment_tag=segment.tag,
                    segment_position=position,
                    element_position=elem_position,
                )

                # Find element definition from schema using helper method
                elem_def = None
                seg_elem_ref = None
                if schema:
                    definition, seg_elem_ref = schema.get_segment_element_definition(
                        segment.tag, elem_position
                    )
                    # Only use simple elements for now
                    # Composite elements would need nested validation
                    if definition is not None and not seg_elem_ref.element_id.startswith("C"):
                        elem_def = definition

                # Level 4: Element validation (if we have definition)
                if ValidationLevel.ELEMENT in self.levels and elem_def:
                    # Requirement comes from SegmentElement, not DataElement
                    requirement = (
                        seg_elem_ref.requirement if seg_elem_ref else RequirementDesignator.O
                    )
                    errors = self.element_validator.validate(
                        element,
                        elem_context,
                        data_type=elem_def.data_type,
                        min_length=elem_def.min_length,
                        max_length=elem_def.max_length,
                        requirement=requirement,
                    )
                    for error in errors:
                        result.add_error(error)

                # Level 5: Code validation
                if ValidationLevel.CODE in self.levels and elem_def:
                    code_context = CodeValidationContext(
                        segment_tag=segment.tag,
                        segment_position=position,
                        element_position=elem_position,
                        element_id=elem_def.id if elem_def else None,
                    )

                    errors = self.code_validator.validate(
                        element,
                        elem_def,
                        code_context,
                    )
                    for error in errors:
                        result.add_error(error)

        return result

    def _validate_semantics(
        self,
        txn: TransactionSetInstance,
        schema: "X12Schema | None",
    ) -> ValidationResult:
        """
        Run semantic validation (Level 6).

        Semantic rules include:
        - Conditional requirements (if A then B required)
        - Mutual exclusion (A or B but not both)
        - Cross-element dependencies
        - Syntax notes from schema

        TODO: Implement syntax note parsing and evaluation.
        """
        result = ValidationResult()

        # Semantic validation is complex and schema-specific
        # For now, this is a placeholder for future implementation

        return result

    def _flatten_content(
        self,
        content: list[ParsedSegment | LoopInstance],
    ) -> list[ParsedSegment]:
        """Flatten nested content into a list of segments."""
        result: list[ParsedSegment] = []

        for item in content:
            if isinstance(item, ParsedSegment):
                result.append(item)
            elif isinstance(item, LoopInstance):
                result.extend(item.segments)
                result.extend(self._flatten_content(item.children))

        return result


# Convenience functions


def validate_interchange(
    interchange: InterchangeInstance,
    schema_loader: "X12SchemaLoader | GeneratedX12SchemaLoader | None" = None,
) -> ValidationResult:
    """
    Convenience function to validate an interchange.

    Args:
        interchange: The parsed interchange
        schema_loader: Optional schema loader

    Returns:
        ValidationResult
    """
    validator = X12Validator(schema_loader)
    return validator.validate(interchange)


def validate_transaction(
    txn: TransactionSetInstance,
    schema: "X12Schema | None" = None,
    group_control: str | None = None,
) -> ValidationResult:
    """
    Convenience function to validate a single transaction.

    Args:
        txn: The transaction to validate
        schema: Optional schema
        group_control: Optional group control number

    Returns:
        ValidationResult
    """
    result = ValidationResult()

    # Add transaction-level errors
    for error in txn.errors:
        result.add_error(error)

    # Schema validation if available
    if schema:
        context = SchemaValidationContext(
            transaction_id=txn.transaction_id,
            group_control=group_control,
        )

        validator = SchemaValidator(schema)
        errors = validator.validate(txn.content, context)

        for error in errors:
            result.add_error(error)

    return result
