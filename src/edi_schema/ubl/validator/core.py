"""
Core Validation Infrastructure.

Provides the main validator, validation results, and orchestration.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable

from ..ast import (
    ErrorCategory,
    ErrorSeverity,
    ParsedDocument,
    ParsedElement,
    ParseError,
    ParseResult,
    SourcePosition,
)
from ..models import UBLSchema


class ValidationLevel(Enum):
    """Validation levels that can be enabled/disabled."""

    STRUCTURAL = auto()  # Well-formed XML (handled by parser)
    SCHEMA = auto()  # Element presence, order, cardinality
    ELEMENT = auto()  # Data types, lengths, formats
    CODE = auto()  # Code list membership
    BUSINESS = auto()  # Cross-element rules (future)


@dataclass
class ValidationContext:
    """Context passed through validation."""

    schema: UBLSchema
    current_path: list[str] = field(default_factory=list)
    errors: list[ParseError] = field(default_factory=list)
    warnings: list[ParseError] = field(default_factory=list)

    def push_path(self, segment: str) -> None:
        """Add a path segment."""
        self.current_path.append(segment)

    def pop_path(self) -> None:
        """Remove the last path segment."""
        if self.current_path:
            self.current_path.pop()

    @property
    def xpath(self) -> str:
        """Get current XPath."""
        return "/" + "/".join(self.current_path)

    def add_error(
        self,
        code: str,
        message: str,
        category: ErrorCategory,
        position: SourcePosition | None = None,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        expected: str | None = None,
        actual: str | None = None,
        **context_data,
    ) -> None:
        """Add a validation error."""
        error = ParseError(
            code=code,
            message=message,
            severity=severity,
            category=category,
            position=position,
            xpath=self.xpath,
            expected=expected,
            actual=actual,
            context=context_data if context_data else {},
        )
        if severity == ErrorSeverity.WARNING:
            self.warnings.append(error)
        else:
            self.errors.append(error)


@dataclass
class ValidationResult:
    """Result of validating a UBL document."""

    document: ParsedDocument | None = None
    errors: list[ParseError] = field(default_factory=list)
    warnings: list[ParseError] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Check if validation passed (no errors)."""
        return len(self.errors) == 0

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return len(self.warnings) > 0

    def add_error(self, error: ParseError) -> None:
        """Add an error to the result."""
        if error.severity == ErrorSeverity.WARNING:
            self.warnings.append(error)
        else:
            self.errors.append(error)

    def merge(self, other: "ValidationResult") -> None:
        """Merge another result into this one."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "valid": self.is_valid,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
        }


# Type for validator functions
ValidatorFunc = Callable[[ParsedElement, ValidationContext], None]


class UBLValidator:
    """
    Main validator that orchestrates validation at multiple levels.

    Usage:
        validator = UBLValidator(
            schema_loader=loader,
            levels={ValidationLevel.SCHEMA, ValidationLevel.ELEMENT, ValidationLevel.CODE},
        )
        result = validator.validate(parsed_document)
    """

    def __init__(
        self,
        schema: UBLSchema | None = None,
        levels: set[ValidationLevel] | None = None,
    ):
        """
        Initialize the validator.

        Args:
            schema: UBL schema to validate against
            levels: Set of validation levels to apply (default: all)
        """
        self.schema = schema
        self.levels = levels or {
            ValidationLevel.SCHEMA,
            ValidationLevel.ELEMENT,
            ValidationLevel.CODE,
        }

        # Registered validators for each level
        self._validators: dict[ValidationLevel, list[ValidatorFunc]] = {
            level: [] for level in ValidationLevel
        }

    def register_validator(
        self,
        level: ValidationLevel,
        validator: ValidatorFunc,
    ) -> None:
        """Register a validator function for a specific level."""
        self._validators[level].append(validator)

    def validate(
        self,
        document: ParsedDocument,
        schema: UBLSchema | None = None,
    ) -> ValidationResult:
        """
        Validate a parsed UBL document.

        Args:
            document: The parsed document to validate
            schema: Optional schema override

        Returns:
            ValidationResult with all errors and warnings
        """
        schema = schema or self.schema
        if schema is None:
            raise ValueError("No schema provided for validation")

        result = ValidationResult(document=document)

        # Verify document type matches schema
        if document.document_type != schema.name:
            result.add_error(
                ParseError(
                    code="DOCUMENT_TYPE_MISMATCH",
                    message=f"Expected {schema.name}, got {document.document_type}",
                    severity=ErrorSeverity.ERROR,
                    category=ErrorCategory.SCHEMA,
                    expected=schema.name,
                    actual=document.document_type,
                )
            )
            return result

        # Create validation context
        context = ValidationContext(schema=schema)

        # Run validators at each enabled level
        for level in self.levels:
            if level == ValidationLevel.STRUCTURAL:
                # Already handled by parser
                continue

            for validator in self._validators[level]:
                self._validate_element(document.root, validator, context)

        # Collect results
        result.errors.extend(context.errors)
        result.warnings.extend(context.warnings)

        return result

    def _validate_element(
        self,
        element: ParsedElement,
        validator: ValidatorFunc,
        context: ValidationContext,
    ) -> None:
        """Recursively validate an element and its children."""
        context.push_path(element.tag)

        try:
            validator(element, context)
        except Exception as e:
            context.add_error(
                code="VALIDATOR_ERROR",
                message=f"Validator raised exception: {e}",
                category=ErrorCategory.STRUCTURAL,
                position=element.position,
            )

        for child in element.children:
            self._validate_element(child, validator, context)

        context.pop_path()

    def validate_result(
        self,
        parse_result: ParseResult,
        schema: UBLSchema | None = None,
    ) -> ValidationResult:
        """
        Validate a ParseResult, preserving parse errors.

        Args:
            parse_result: Result from parsing
            schema: Optional schema override

        Returns:
            ValidationResult including parse errors
        """
        result = ValidationResult()

        # Include parse errors
        result.errors.extend(parse_result.errors)

        # Skip validation if no document
        if parse_result.document is None:
            return result

        # Run validation
        validation_result = self.validate(parse_result.document, schema)
        result.merge(validation_result)

        return result


def create_validator(
    schema: UBLSchema,
    levels: set[ValidationLevel] | None = None,
) -> UBLValidator:
    """
    Create a fully configured validator with all standard validators.

    Args:
        schema: UBL schema to validate against
        levels: Validation levels to enable

    Returns:
        Configured UBLValidator instance
    """
    # Import here to avoid circular imports
    from .code import validate_codes
    from .element import validate_element_types
    from .schema import validate_cardinality, validate_structure

    validator = UBLValidator(schema=schema, levels=levels)

    # Register standard validators
    validator.register_validator(ValidationLevel.SCHEMA, validate_structure)
    validator.register_validator(ValidationLevel.SCHEMA, validate_cardinality)
    validator.register_validator(ValidationLevel.ELEMENT, validate_element_types)
    validator.register_validator(ValidationLevel.CODE, validate_codes)

    return validator
