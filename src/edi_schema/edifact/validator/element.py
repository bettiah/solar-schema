"""
Element Validator (Level 4).

Validates individual data elements against their schema definitions:
- Data type (a, n, an)
- Length constraints (min/max)
- Required vs optional

EDIFACT Error Codes (for CONTRL UCD):
- 12: Invalid value
- 13: Missing
- 14: Value not supported
- 37: Invalid character
- 38: Numeric when alphabetic expected
- 39: Alphabetic when numeric expected
"""

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from edi_schema.edifact.ast import (
    ErrorCategory,
    ErrorSeverity,
    ParsedElement,
    ParseError,
    SourcePosition,
)

if TYPE_CHECKING:
    from edi_schema.edifact.models import Composite, DataElement


@dataclass
class ElementValidationContext:
    """Context for element validation."""

    segment_tag: str
    segment_position: int
    element_position: int
    component_position: int | None = None


class ElementValidator:
    """
    Validates data elements against schema definitions.

    Supports EDIFACT data types:
    - a: Alphabetic (A-Z, a-z, space)
    - n: Numeric (0-9, with optional sign and decimal)
    - an: Alphanumeric (any printable characters)
    """

    # Regex patterns for validation
    PATTERNS = {
        "alphabetic": re.compile(r"^[A-Za-z ]*$"),
        "numeric": re.compile(r"^-?\d*\.?\d*$"),
        "alphanumeric": re.compile(r"^[\x20-\x7E]*$"),  # Printable ASCII
    }

    def __init__(self):
        self.errors: list[ParseError] = []

    def validate(
        self,
        element: ParsedElement,
        context: ElementValidationContext,
        definition: "DataElement | Composite | None" = None,
        mandatory: bool = False,
    ) -> list[ParseError]:
        """
        Validate a single element.

        Args:
            element: The parsed element to validate
            context: Validation context (segment, position)
            definition: Element or composite definition from schema
            mandatory: Whether this element is required

        Returns:
            List of validation errors
        """
        errors: list[ParseError] = []

        # Get value - for simple elements use value, for composites check first component
        value = element.raw.value if element.raw else None

        # For composite elements, we validate components separately
        if element.components:
            # Composite validation is handled by the core validator
            return errors

        # Get position for error reporting
        position = element.raw.position if element.raw else None

        # Check required
        if not value:
            if mandatory:
                errors.append(
                    ParseError(
                        code="13",  # Missing
                        message=f"Required element {context.segment_tag}"
                        f"{context.element_position:02d} is empty",
                        category=ErrorCategory.ELEMENT,
                        severity=ErrorSeverity.ERROR,
                        position=position,
                        segment_tag=context.segment_tag,
                        segment_position=context.segment_position,
                        element_position=context.element_position,
                    )
                )
            return errors  # Empty optional element is OK

        # Get type and length constraints from definition
        if definition and hasattr(definition, "data_type"):
            data_type = definition.data_type
            min_length = getattr(definition, "min_length", 0)
            max_length = getattr(definition, "max_length", 99999)

            # Length validation
            errors.extend(self._validate_length(value, min_length, max_length, context, position))

            # Type validation
            errors.extend(self._validate_type(value, data_type, context, position))

        return errors

    def validate_value(
        self,
        value: str,
        context: ElementValidationContext,
        data_type: str | None = None,
        min_length: int = 0,
        max_length: int = 99999,
    ) -> list[ParseError]:
        """
        Validate a raw value without ParsedElement wrapper.

        Args:
            value: The value to validate
            context: Validation context
            data_type: Expected data type (a, n, an)
            min_length: Minimum length
            max_length: Maximum length

        Returns:
            List of validation errors
        """
        errors: list[ParseError] = []

        if not value:
            return errors

        # Length validation
        errors.extend(self._validate_length(value, min_length, max_length, context, None))

        # Type validation
        if data_type:
            errors.extend(self._validate_type(value, data_type, context, None))

        return errors

    def _validate_length(
        self,
        value: str,
        min_length: int,
        max_length: int,
        context: ElementValidationContext,
        position: SourcePosition | None,
    ) -> list[ParseError]:
        """Validate element length."""
        errors: list[ParseError] = []

        if len(value) < min_length:
            elem_id = f"{context.segment_tag}{context.element_position:02d}"
            if context.component_position:
                elem_id += f"-{context.component_position}"

            errors.append(
                ParseError(
                    code="12",  # Invalid value
                    message=f"Element {elem_id} too short: {len(value)} < {min_length}",
                    category=ErrorCategory.ELEMENT,
                    severity=ErrorSeverity.ERROR,
                    position=position,
                    segment_tag=context.segment_tag,
                    segment_position=context.segment_position,
                    element_position=context.element_position,
                    component_position=context.component_position,
                    actual=str(len(value)),
                    expected=f">= {min_length}",
                )
            )

        if len(value) > max_length:
            elem_id = f"{context.segment_tag}{context.element_position:02d}"
            if context.component_position:
                elem_id += f"-{context.component_position}"

            errors.append(
                ParseError(
                    code="12",  # Invalid value
                    message=f"Element {elem_id} too long: {len(value)} > {max_length}",
                    category=ErrorCategory.ELEMENT,
                    severity=ErrorSeverity.ERROR,
                    position=position,
                    segment_tag=context.segment_tag,
                    segment_position=context.segment_position,
                    element_position=context.element_position,
                    component_position=context.component_position,
                    actual=str(len(value)),
                    expected=f"<= {max_length}",
                )
            )

        return errors

    def _validate_type(
        self,
        value: str,
        data_type: str,
        context: ElementValidationContext,
        position: SourcePosition | None,
    ) -> list[ParseError]:
        """Validate element data type."""
        errors: list[ParseError] = []

        # Normalize data type
        dtype = data_type.lower()

        if dtype == "a":
            errors.extend(self._validate_alphabetic(value, context, position))
        elif dtype == "n":
            errors.extend(self._validate_numeric(value, context, position))
        elif dtype == "an":
            errors.extend(self._validate_alphanumeric(value, context, position))
        # Unknown types are not validated

        return errors

    def _validate_alphabetic(
        self,
        value: str,
        context: ElementValidationContext,
        position: SourcePosition | None,
    ) -> list[ParseError]:
        """Validate alphabetic (a) data type - letters and space only."""
        errors: list[ParseError] = []

        if not self.PATTERNS["alphabetic"].match(value):
            elem_id = f"{context.segment_tag}{context.element_position:02d}"
            if context.component_position:
                elem_id += f"-{context.component_position}"

            # Find invalid characters
            invalid_chars = [c for c in value if not c.isalpha() and c != " "]

            errors.append(
                ParseError(
                    code="38",  # Numeric when alphabetic expected
                    message=f"Element {elem_id} must be alphabetic: {value!r}",
                    category=ErrorCategory.ELEMENT,
                    severity=ErrorSeverity.ERROR,
                    position=position,
                    segment_tag=context.segment_tag,
                    segment_position=context.segment_position,
                    element_position=context.element_position,
                    component_position=context.component_position,
                    expected="alphabetic",
                    actual=value,
                )
            )

        return errors

    def _validate_numeric(
        self,
        value: str,
        context: ElementValidationContext,
        position: SourcePosition | None,
    ) -> list[ParseError]:
        """Validate numeric (n) data type - digits with optional sign and decimal."""
        errors: list[ParseError] = []

        if not self.PATTERNS["numeric"].match(value):
            elem_id = f"{context.segment_tag}{context.element_position:02d}"
            if context.component_position:
                elem_id += f"-{context.component_position}"

            errors.append(
                ParseError(
                    code="39",  # Alphabetic when numeric expected
                    message=f"Element {elem_id} must be numeric: {value!r}",
                    category=ErrorCategory.ELEMENT,
                    severity=ErrorSeverity.ERROR,
                    position=position,
                    segment_tag=context.segment_tag,
                    segment_position=context.segment_position,
                    element_position=context.element_position,
                    component_position=context.component_position,
                    expected="numeric",
                    actual=value,
                )
            )

        return errors

    def _validate_alphanumeric(
        self,
        value: str,
        context: ElementValidationContext,
        position: SourcePosition | None,
    ) -> list[ParseError]:
        """Validate alphanumeric (an) data type - any printable ASCII."""
        errors: list[ParseError] = []

        if not self.PATTERNS["alphanumeric"].match(value):
            elem_id = f"{context.segment_tag}{context.element_position:02d}"
            if context.component_position:
                elem_id += f"-{context.component_position}"

            # Find invalid characters
            invalid_chars = [c for c in value if ord(c) < 0x20 or ord(c) > 0x7E]

            errors.append(
                ParseError(
                    code="37",  # Invalid character
                    message=f"Element {elem_id} contains invalid characters: {invalid_chars!r}",
                    category=ErrorCategory.ELEMENT,
                    severity=ErrorSeverity.ERROR,
                    position=position,
                    segment_tag=context.segment_tag,
                    segment_position=context.segment_position,
                    element_position=context.element_position,
                    component_position=context.component_position,
                )
            )

        return errors


# Convenience functions


def validate_element(
    element: ParsedElement,
    context: ElementValidationContext,
    definition: "DataElement | Composite | None" = None,
    mandatory: bool = False,
) -> list[ParseError]:
    """
    Convenience function to validate a single element.
    """
    validator = ElementValidator()
    return validator.validate(element, context, definition, mandatory)


def validate_element_type(
    value: str,
    data_type: str,
    context: ElementValidationContext,
) -> list[ParseError]:
    """
    Validate just the data type of a value.
    """
    validator = ElementValidator()
    return validator._validate_type(value, data_type, context, None)


def validate_element_length(
    value: str,
    min_length: int,
    max_length: int,
    context: ElementValidationContext,
) -> list[ParseError]:
    """
    Validate just the length of a value.
    """
    validator = ElementValidator()
    return validator._validate_length(value, min_length, max_length, context, None)
