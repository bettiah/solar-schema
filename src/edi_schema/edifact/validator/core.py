"""
EDIFACT Validator Core.

Provides multi-level validation for EDIFACT documents by orchestrating
the specialized validators.

Validation Levels:
1. Structural - Basic syntax (delimiters, terminators) - done in tokenizer
2. Envelope - UNB/UNZ, UNG/UNE, UNH/UNT matching - done in envelope parser
3. Schema - Segment order, required segments, group cardinality
4. Element - Data types, lengths, required elements
5. Code - Coded values against code lists
6. Semantic - Cross-element rules, conditional requirements
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

from edi_schema.edifact.ast import (
    ErrorCategory,
    ErrorSeverity,
    FunctionalGroupInstance,
    InterchangeInstance,
    MessageInstance,
    ParsedElement,
    ParsedSegment,
    ParseError,
    SegmentGroupInstance,
)
from edi_schema.edifact.validator.code import (
    CodeValidationContext,
    CodeValidator,
)
from edi_schema.edifact.validator.element import (
    ElementValidationContext,
    ElementValidator,
)
from edi_schema.edifact.validator.schema import (
    SchemaValidationContext,
    SchemaValidator,
)

if TYPE_CHECKING:
    from edi_schema.edifact.models import ResolvedMessageSpec
    from edi_schema.edifact.schema import EdifactSchemaLoader
    from edi_schema.edifact.schemas import GeneratedEdifactSchemaLoader


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
        """Check if document should be accepted (for CONTRL response)."""
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


class EdifactValidator:
    """
    Multi-level EDIFACT document validator.

    Validates parsed EDIFACT documents against schemas with configurable
    validation levels and error reporting suitable for CONTRL generation.

    Usage:
        validator = EdifactValidator(schema_loader)
        result = validator.validate(interchange)
        if not result.is_valid():
            for error in result.errors:
                print(error)
    """

    def __init__(
        self,
        schema_loader: "EdifactSchemaLoader | GeneratedEdifactSchemaLoader | None" = None,
        levels: set[ValidationLevel] | None = None,
        strict_codes: bool = False,
    ):
        """
        Initialize the validator.

        Args:
            schema_loader: Loader for EDIFACT schemas
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

        # Validate each functional group
        for group in interchange.groups:
            group_result = self._validate_group(group)
            result.merge(group_result)

        # Validate standalone messages (not in functional groups)
        for message in interchange.messages:
            msg_result = self._validate_message(message)
            result.merge(msg_result)

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

        # Validate each message in the group
        for message in group.messages:
            msg_result = self._validate_message(message)
            result.merge(msg_result)

        return result

    def _validate_message(
        self,
        message: MessageInstance,
    ) -> ValidationResult:
        """Validate a message."""
        result = ValidationResult()

        # Add any message-level errors from parsing
        for error in message.errors:
            result.add_error(error)

        # Load schema if available
        schema = self._load_schema(message)

        # Level 3: Schema validation
        if schema and ValidationLevel.SCHEMA in self.levels:
            schema_result = self._validate_schema(message, schema)
            result.merge(schema_result)

        # Level 4-5: Element and code validation
        if ValidationLevel.ELEMENT in self.levels or ValidationLevel.CODE in self.levels:
            content_result = self._validate_content(message, schema)
            result.merge(content_result)

        # Level 6: Semantic validation
        if ValidationLevel.SEMANTIC in self.levels:
            semantic_result = self._validate_semantics(message, schema)
            result.merge(semantic_result)

        return result

    def _load_schema(
        self,
        message: MessageInstance,
    ) -> "ResolvedMessageSpec | None":
        """Load schema for a message."""
        if self.schema_loader is None:
            return None

        try:
            if self.schema_loader.exists(message.message_type):
                return self.schema_loader.load(message.message_type)
        except Exception:
            pass

        return None

    def _validate_schema(
        self,
        message: MessageInstance,
        schema: "ResolvedMessageSpec",
    ) -> ValidationResult:
        """Run schema validation (Level 3)."""
        result = ValidationResult()

        context = SchemaValidationContext(
            message_type=message.message_type,
            message_reference=message.reference_number,
        )

        validator = SchemaValidator(schema)
        errors = validator.validate(message.content, context)

        for error in errors:
            result.add_error(error)

        return result

    def _validate_content(
        self,
        message: MessageInstance,
        schema: "ResolvedMessageSpec | None",
    ) -> ValidationResult:
        """Run element and code validation (Level 4-5)."""
        result = ValidationResult()

        # Get all segments from content (including those in groups)
        all_segments = self._flatten_content(message.content)

        for i, segment in enumerate(all_segments):
            position = i + 1

            # Get segment definition from schema
            seg_def = None
            if schema:
                seg_def = schema.get_segment(segment.tag)

            # Validate each element
            for j, element in enumerate(segment.elements):
                elem_position = j + 1

                # Create validation context
                elem_context = ElementValidationContext(
                    segment_tag=segment.tag,
                    segment_position=position,
                    element_position=elem_position,
                )

                # Get element definition from segment definition
                elem_def = None
                seg_elem = None
                if seg_def and j < len(seg_def.elements):
                    seg_elem = seg_def.elements[j]
                    if seg_elem.resolved:
                        elem_def = seg_elem.resolved

                # Level 4: Element validation
                if ValidationLevel.ELEMENT in self.levels:
                    errors = self.element_validator.validate(
                        element,
                        elem_context,
                        definition=elem_def,
                        mandatory=seg_elem.mandatory if seg_elem else False,
                    )
                    for error in errors:
                        result.add_error(error)

                # Level 5: Code validation
                if ValidationLevel.CODE in self.levels and elem_def:
                    code_context = CodeValidationContext(
                        segment_tag=segment.tag,
                        segment_position=position,
                        element_position=elem_position,
                        element_id=elem_def.tag if elem_def else None,
                    )

                    errors = self.code_validator.validate(
                        element,
                        elem_def,
                        code_context,
                    )
                    for error in errors:
                        result.add_error(error)

                # Also validate components for composite elements
                if element.components:
                    comp_errors = self._validate_components(
                        element, elem_context, elem_def, position
                    )
                    result.merge(comp_errors)

        return result

    def _validate_components(
        self,
        element: ParsedElement,
        elem_context: ElementValidationContext,
        definition,
        segment_position: int,
    ) -> ValidationResult:
        """Validate components within a composite element."""
        result = ValidationResult()

        if not element.components:
            return result

        # Get composite definition for component validation
        composite_def = element.composite_definition

        for k, component in enumerate(element.components):
            comp_position = k + 1

            # Get component definition
            comp_def = None
            comp_elem_def = None
            if composite_def and k < len(composite_def.components):
                comp_def = composite_def.components[k]
                comp_elem_def = comp_def.element

            if not component.value:
                # Check if mandatory
                if comp_def and comp_def.mandatory:
                    result.add_error(
                        ParseError(
                            code="13",  # Missing
                            message=f"Required component {elem_context.segment_tag}"
                            f"{elem_context.element_position:02d}-{comp_position} is empty",
                            category=ErrorCategory.ELEMENT,
                            severity=ErrorSeverity.ERROR,
                            segment_tag=elem_context.segment_tag,
                            segment_position=segment_position,
                            element_position=elem_context.element_position,
                            component_position=comp_position,
                        )
                    )
                continue

            # Validate component value against element definition
            if comp_elem_def and ValidationLevel.ELEMENT in self.levels:
                comp_context = ElementValidationContext(
                    segment_tag=elem_context.segment_tag,
                    segment_position=segment_position,
                    element_position=elem_context.element_position,
                    component_position=comp_position,
                )

                errors = self.element_validator.validate_value(
                    component.value,
                    comp_context,
                    data_type=comp_elem_def.data_type,
                    min_length=comp_elem_def.min_length,
                    max_length=comp_elem_def.max_length,
                )
                for error in errors:
                    result.add_error(error)

            # Code validation for component
            if comp_elem_def and ValidationLevel.CODE in self.levels:
                if comp_elem_def.codes and component.value:
                    if component.value not in comp_elem_def.codes:
                        severity = (
                            ErrorSeverity.ERROR if self.strict_codes else ErrorSeverity.WARNING
                        )
                        result.add_error(
                            ParseError(
                                code="12",  # Invalid value
                                message=f"Component {elem_context.segment_tag}"
                                f"{elem_context.element_position:02d}-{comp_position} "
                                f"has invalid code: {component.value!r}",
                                category=ErrorCategory.CODE,
                                severity=severity,
                                segment_tag=elem_context.segment_tag,
                                segment_position=segment_position,
                                element_position=elem_context.element_position,
                                component_position=comp_position,
                                actual=component.value,
                            )
                        )

        return result

    def _validate_semantics(
        self,
        message: MessageInstance,
        schema: "ResolvedMessageSpec | None",
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
        # Placeholder for future implementation

        return result

    def _flatten_content(
        self,
        content: list[ParsedSegment | SegmentGroupInstance],
    ) -> list[ParsedSegment]:
        """Flatten nested content into a list of segments."""
        result: list[ParsedSegment] = []

        for item in content:
            if isinstance(item, ParsedSegment):
                result.append(item)
            elif isinstance(item, SegmentGroupInstance):
                result.extend(item.segments)
                result.extend(self._flatten_content(item.children))

        return result


# Convenience functions


def validate_interchange(
    interchange: InterchangeInstance,
    schema_loader: "EdifactSchemaLoader | GeneratedEdifactSchemaLoader | None" = None,
) -> ValidationResult:
    """
    Convenience function to validate an interchange.

    Args:
        interchange: The parsed interchange
        schema_loader: Optional schema loader

    Returns:
        ValidationResult
    """
    validator = EdifactValidator(schema_loader)
    return validator.validate(interchange)


def validate_message(
    message: MessageInstance,
    schema: "ResolvedMessageSpec | None" = None,
) -> ValidationResult:
    """
    Convenience function to validate a single message.

    Args:
        message: The message to validate
        schema: Optional schema

    Returns:
        ValidationResult
    """
    result = ValidationResult()

    # Add message-level errors
    for error in message.errors:
        result.add_error(error)

    # Schema validation if available
    if schema:
        context = SchemaValidationContext(
            message_type=message.message_type,
            message_reference=message.reference_number,
        )

        validator = SchemaValidator(schema)
        errors = validator.validate(message.content, context)

        for error in errors:
            result.add_error(error)

    return result
