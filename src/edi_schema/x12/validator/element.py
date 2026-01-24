"""
Element Validator (Level 4).

Validates individual data elements against their schema definitions:
- Data type (AN, ID, N, R, DT, TM)
- Length constraints (min/max)
- Required vs optional

Error Codes (for 997 AK4):
- 1: Mandatory data element missing
- 4: Data element too short
- 5: Data element too long
- 6: Invalid character in data element
- 7: Invalid code value (delegated to code validator)
- 8: Invalid date
- 9: Invalid time
- 10: Exclusion condition violated
"""

import re
from dataclasses import dataclass

from edi_schema.x12.ast import (
    ErrorCategory,
    ErrorSeverity,
    ParsedElement,
    ParseError,
    SourcePosition,
)
from edi_schema.x12.enums import DataElementType, RequirementDesignator

# Aliases for cleaner code
DataType = DataElementType
Requirement = RequirementDesignator


@dataclass
class ElementValidationContext:
    """Context for element validation."""

    segment_tag: str
    segment_position: int
    element_position: int
    loop_id: str | None = None


class ElementValidator:
    """
    Validates data elements against schema definitions.

    Supports X12 data types:
    - AN: Alphanumeric (any printable ASCII)
    - ID: Identifier (alphanumeric, often has code list)
    - N: Numeric (integer)
    - Nn: Numeric with implied decimal (N0-N9)
    - R: Decimal number
    - DT: Date (CCYYMMDD or YYMMDD)
    - TM: Time (HHMM, HHMMSS, or HHMMSSD)
    - B: Binary (not validated)
    """

    # Regex patterns for validation
    PATTERNS = {
        "alphanumeric": re.compile(r"^[\x20-\x7E]*$"),  # Printable ASCII
        "numeric": re.compile(r"^-?\d*$"),
        "decimal": re.compile(r"^-?\d*\.?\d*$"),
        "date_ccyymmdd": re.compile(r"^\d{8}$"),
        "date_yymmdd": re.compile(r"^\d{6}$"),
        "time_hhmm": re.compile(r"^\d{4}$"),
        "time_hhmmss": re.compile(r"^\d{6}$"),
        "time_hhmmssd": re.compile(r"^\d{7,8}$"),
    }

    def __init__(self):
        self.errors: list[ParseError] = []

    def validate(
        self,
        element: ParsedElement,
        context: ElementValidationContext,
        data_type: DataType | None = None,
        min_length: int = 1,
        max_length: int = 99999,
        requirement: Requirement = Requirement.O,
    ) -> list[ParseError]:
        """
        Validate a single element.

        Args:
            element: The parsed element to validate
            context: Validation context (segment, position)
            data_type: Expected data type
            min_length: Minimum length
            max_length: Maximum length
            requirement: M=mandatory, O=optional, C=conditional

        Returns:
            List of validation errors
        """
        errors: list[ParseError] = []
        value = element.value

        # Get position for error reporting
        position = element.raw.position if hasattr(element.raw, "position") else None

        # Check required
        if not value:
            if requirement == Requirement.M:
                errors.append(
                    ParseError(
                        code="1",  # Mandatory data element missing
                        message=f"Required element {context.segment_tag}{context.element_position:02d} is empty",
                        category=ErrorCategory.ELEMENT,
                        severity=ErrorSeverity.ERROR,
                        position=position,
                        segment_tag=context.segment_tag,
                        segment_position=context.segment_position,
                        element_position=context.element_position,
                        loop_id=context.loop_id,
                    )
                )
            return errors  # Empty optional element is OK

        # Length validation
        errors.extend(self._validate_length(value, min_length, max_length, context, position))

        # Type validation
        if data_type:
            errors.extend(self._validate_type(value, data_type, context, position))

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
            errors.append(
                ParseError(
                    code="4",  # Data element too short
                    message=f"Element {context.segment_tag}{context.element_position:02d} "
                    f"too short: {len(value)} < {min_length}",
                    category=ErrorCategory.ELEMENT,
                    severity=ErrorSeverity.ERROR,
                    position=position,
                    segment_tag=context.segment_tag,
                    segment_position=context.segment_position,
                    element_position=context.element_position,
                    loop_id=context.loop_id,
                    actual=str(len(value)),
                    expected=f">= {min_length}",
                )
            )

        if len(value) > max_length:
            errors.append(
                ParseError(
                    code="5",  # Data element too long
                    message=f"Element {context.segment_tag}{context.element_position:02d} "
                    f"too long: {len(value)} > {max_length}",
                    category=ErrorCategory.ELEMENT,
                    severity=ErrorSeverity.ERROR,
                    position=position,
                    segment_tag=context.segment_tag,
                    segment_position=context.segment_position,
                    element_position=context.element_position,
                    loop_id=context.loop_id,
                    actual=str(len(value)),
                    expected=f"<= {max_length}",
                )
            )

        return errors

    def _validate_type(
        self,
        value: str,
        data_type: DataType,
        context: ElementValidationContext,
        position: SourcePosition | None,
    ) -> list[ParseError]:
        """Validate element data type."""
        errors: list[ParseError] = []

        # Dispatch to type-specific validator
        validator_method = getattr(
            self, f"_validate_{data_type.value.lower()}", self._validate_alphanumeric
        )

        type_errors = validator_method(value, context, position)
        errors.extend(type_errors)

        return errors

    def _validate_an(
        self,
        value: str,
        context: ElementValidationContext,
        position: SourcePosition | None,
    ) -> list[ParseError]:
        """Validate alphanumeric (AN) data type."""
        return self._validate_alphanumeric(value, context, position)

    def _validate_alphanumeric(
        self,
        value: str,
        context: ElementValidationContext,
        position: SourcePosition | None,
    ) -> list[ParseError]:
        """Validate alphanumeric (AN) data type - any printable ASCII."""
        errors: list[ParseError] = []

        if not self.PATTERNS["alphanumeric"].match(value):
            # Find invalid characters
            invalid_chars = [c for c in value if ord(c) < 0x20 or ord(c) > 0x7E]
            errors.append(
                ParseError(
                    code="6",  # Invalid character in data element
                    message=f"Element {context.segment_tag}{context.element_position:02d} "
                    f"contains invalid characters: {invalid_chars!r}",
                    category=ErrorCategory.ELEMENT,
                    severity=ErrorSeverity.ERROR,
                    position=position,
                    segment_tag=context.segment_tag,
                    segment_position=context.segment_position,
                    element_position=context.element_position,
                    loop_id=context.loop_id,
                )
            )

        return errors

    def _validate_id(
        self,
        value: str,
        context: ElementValidationContext,
        position: SourcePosition | None,
    ) -> list[ParseError]:
        """
        Validate identifier (ID) data type.

        ID is essentially alphanumeric but often has an associated code list.
        Code list validation is handled separately by CodeValidator.
        """
        return self._validate_alphanumeric(value, context, position)

    def _validate_n(
        self,
        value: str,
        context: ElementValidationContext,
        position: SourcePosition | None,
    ) -> list[ParseError]:
        """Validate numeric (N) data type - integer."""
        return self._validate_numeric(value, context, position)

    def _validate_n0(
        self,
        value: str,
        context: ElementValidationContext,
        position: SourcePosition | None,
    ) -> list[ParseError]:
        """Validate N0 - integer (no implied decimal)."""
        return self._validate_numeric(value, context, position)

    def _validate_n1(
        self,
        value: str,
        context: ElementValidationContext,
        position: SourcePosition | None,
    ) -> list[ParseError]:
        """Validate N1 - numeric with 1 implied decimal place."""
        return self._validate_numeric(value, context, position)

    def _validate_n2(
        self,
        value: str,
        context: ElementValidationContext,
        position: SourcePosition | None,
    ) -> list[ParseError]:
        """Validate N2 - numeric with 2 implied decimal places."""
        return self._validate_numeric(value, context, position)

    def _validate_numeric(
        self,
        value: str,
        context: ElementValidationContext,
        position: SourcePosition | None,
    ) -> list[ParseError]:
        """Validate numeric data - integers only (may have leading minus)."""
        errors: list[ParseError] = []

        if not self.PATTERNS["numeric"].match(value):
            errors.append(
                ParseError(
                    code="6",  # Invalid character in data element
                    message=f"Element {context.segment_tag}{context.element_position:02d} "
                    f"must be numeric: {value!r}",
                    category=ErrorCategory.ELEMENT,
                    severity=ErrorSeverity.ERROR,
                    position=position,
                    segment_tag=context.segment_tag,
                    segment_position=context.segment_position,
                    element_position=context.element_position,
                    loop_id=context.loop_id,
                    expected="numeric",
                    actual=value,
                )
            )

        return errors

    def _validate_r(
        self,
        value: str,
        context: ElementValidationContext,
        position: SourcePosition | None,
    ) -> list[ParseError]:
        """Validate real/decimal (R) data type."""
        errors: list[ParseError] = []

        if not self.PATTERNS["decimal"].match(value):
            errors.append(
                ParseError(
                    code="6",  # Invalid character in data element
                    message=f"Element {context.segment_tag}{context.element_position:02d} "
                    f"must be decimal: {value!r}",
                    category=ErrorCategory.ELEMENT,
                    severity=ErrorSeverity.ERROR,
                    position=position,
                    segment_tag=context.segment_tag,
                    segment_position=context.segment_position,
                    element_position=context.element_position,
                    loop_id=context.loop_id,
                    expected="decimal",
                    actual=value,
                )
            )

        return errors

    def _validate_dt(
        self,
        value: str,
        context: ElementValidationContext,
        position: SourcePosition | None,
    ) -> list[ParseError]:
        """Validate date (DT) data type - CCYYMMDD or YYMMDD."""
        errors: list[ParseError] = []

        # Check format
        if len(value) == 8:
            if not self.PATTERNS["date_ccyymmdd"].match(value):
                errors.append(
                    ParseError(
                        code="8",  # Invalid date
                        message=f"Element {context.segment_tag}{context.element_position:02d} "
                        f"invalid date format: {value!r}",
                        category=ErrorCategory.ELEMENT,
                        severity=ErrorSeverity.ERROR,
                        position=position,
                        segment_tag=context.segment_tag,
                        segment_position=context.segment_position,
                        element_position=context.element_position,
                        loop_id=context.loop_id,
                        expected="CCYYMMDD",
                        actual=value,
                    )
                )
                return errors

            # Parse and validate components
            year = int(value[0:4])
            month = int(value[4:6])
            day = int(value[6:8])

        elif len(value) == 6:
            if not self.PATTERNS["date_yymmdd"].match(value):
                errors.append(
                    ParseError(
                        code="8",  # Invalid date
                        message=f"Element {context.segment_tag}{context.element_position:02d} "
                        f"invalid date format: {value!r}",
                        category=ErrorCategory.ELEMENT,
                        severity=ErrorSeverity.ERROR,
                        position=position,
                        segment_tag=context.segment_tag,
                        segment_position=context.segment_position,
                        element_position=context.element_position,
                        loop_id=context.loop_id,
                        expected="YYMMDD",
                        actual=value,
                    )
                )
                return errors

            # Parse components (YY is ambiguous, assume 20xx for 00-49, 19xx for 50-99)
            yy = int(value[0:2])
            year = 2000 + yy if yy < 50 else 1900 + yy
            month = int(value[2:4])
            day = int(value[4:6])

        else:
            errors.append(
                ParseError(
                    code="8",  # Invalid date
                    message=f"Element {context.segment_tag}{context.element_position:02d} "
                    f"invalid date length: {len(value)}",
                    category=ErrorCategory.ELEMENT,
                    severity=ErrorSeverity.ERROR,
                    position=position,
                    segment_tag=context.segment_tag,
                    segment_position=context.segment_position,
                    element_position=context.element_position,
                    loop_id=context.loop_id,
                    expected="6 or 8 digits",
                    actual=str(len(value)),
                )
            )
            return errors

        # Validate month
        if month < 1 or month > 12:
            errors.append(
                ParseError(
                    code="8",
                    message=f"Element {context.segment_tag}{context.element_position:02d} "
                    f"invalid month: {month}",
                    category=ErrorCategory.ELEMENT,
                    severity=ErrorSeverity.ERROR,
                    position=position,
                    segment_tag=context.segment_tag,
                    segment_position=context.segment_position,
                    element_position=context.element_position,
                    loop_id=context.loop_id,
                )
            )

        # Validate day (basic check)
        if day < 1 or day > 31:
            errors.append(
                ParseError(
                    code="8",
                    message=f"Element {context.segment_tag}{context.element_position:02d} "
                    f"invalid day: {day}",
                    category=ErrorCategory.ELEMENT,
                    severity=ErrorSeverity.ERROR,
                    position=position,
                    segment_tag=context.segment_tag,
                    segment_position=context.segment_position,
                    element_position=context.element_position,
                    loop_id=context.loop_id,
                )
            )

        return errors

    def _validate_tm(
        self,
        value: str,
        context: ElementValidationContext,
        position: SourcePosition | None,
    ) -> list[ParseError]:
        """Validate time (TM) data type - HHMM, HHMMSS, or HHMMSSD."""
        errors: list[ParseError] = []

        # Check format
        if len(value) == 4:
            if not self.PATTERNS["time_hhmm"].match(value):
                errors.append(
                    ParseError(
                        code="9",  # Invalid time
                        message=f"Element {context.segment_tag}{context.element_position:02d} "
                        f"invalid time format: {value!r}",
                        category=ErrorCategory.ELEMENT,
                        severity=ErrorSeverity.ERROR,
                        position=position,
                        segment_tag=context.segment_tag,
                        segment_position=context.segment_position,
                        element_position=context.element_position,
                        loop_id=context.loop_id,
                        expected="HHMM",
                        actual=value,
                    )
                )
                return errors
            hour = int(value[0:2])
            minute = int(value[2:4])

        elif len(value) == 6:
            if not self.PATTERNS["time_hhmmss"].match(value):
                errors.append(
                    ParseError(
                        code="9",
                        message=f"Element {context.segment_tag}{context.element_position:02d} "
                        f"invalid time format: {value!r}",
                        category=ErrorCategory.ELEMENT,
                        severity=ErrorSeverity.ERROR,
                        position=position,
                        segment_tag=context.segment_tag,
                        segment_position=context.segment_position,
                        element_position=context.element_position,
                        loop_id=context.loop_id,
                        expected="HHMMSS",
                        actual=value,
                    )
                )
                return errors
            hour = int(value[0:2])
            minute = int(value[2:4])
            second = int(value[4:6])
            if second > 59:
                errors.append(
                    ParseError(
                        code="9",
                        message=f"Element {context.segment_tag}{context.element_position:02d} "
                        f"invalid seconds: {second}",
                        category=ErrorCategory.ELEMENT,
                        severity=ErrorSeverity.ERROR,
                        position=position,
                        segment_tag=context.segment_tag,
                        segment_position=context.segment_position,
                        element_position=context.element_position,
                        loop_id=context.loop_id,
                    )
                )

        elif 7 <= len(value) <= 8:
            if not self.PATTERNS["time_hhmmssd"].match(value):
                errors.append(
                    ParseError(
                        code="9",
                        message=f"Element {context.segment_tag}{context.element_position:02d} "
                        f"invalid time format: {value!r}",
                        category=ErrorCategory.ELEMENT,
                        severity=ErrorSeverity.ERROR,
                        position=position,
                        segment_tag=context.segment_tag,
                        segment_position=context.segment_position,
                        element_position=context.element_position,
                        loop_id=context.loop_id,
                        expected="HHMMSSD or HHMMSSDD",
                        actual=value,
                    )
                )
                return errors
            hour = int(value[0:2])
            minute = int(value[2:4])

        else:
            errors.append(
                ParseError(
                    code="9",
                    message=f"Element {context.segment_tag}{context.element_position:02d} "
                    f"invalid time length: {len(value)}",
                    category=ErrorCategory.ELEMENT,
                    severity=ErrorSeverity.ERROR,
                    position=position,
                    segment_tag=context.segment_tag,
                    segment_position=context.segment_position,
                    element_position=context.element_position,
                    loop_id=context.loop_id,
                    expected="4, 6, 7, or 8 digits",
                    actual=str(len(value)),
                )
            )
            return errors

        # Validate hour and minute
        if hour > 23:
            errors.append(
                ParseError(
                    code="9",
                    message=f"Element {context.segment_tag}{context.element_position:02d} "
                    f"invalid hour: {hour}",
                    category=ErrorCategory.ELEMENT,
                    severity=ErrorSeverity.ERROR,
                    position=position,
                    segment_tag=context.segment_tag,
                    segment_position=context.segment_position,
                    element_position=context.element_position,
                    loop_id=context.loop_id,
                )
            )

        if minute > 59:
            errors.append(
                ParseError(
                    code="9",
                    message=f"Element {context.segment_tag}{context.element_position:02d} "
                    f"invalid minute: {minute}",
                    category=ErrorCategory.ELEMENT,
                    severity=ErrorSeverity.ERROR,
                    position=position,
                    segment_tag=context.segment_tag,
                    segment_position=context.segment_position,
                    element_position=context.element_position,
                    loop_id=context.loop_id,
                )
            )

        return errors

    def _validate_b(
        self,
        value: str,
        context: ElementValidationContext,
        position: SourcePosition | None,
    ) -> list[ParseError]:
        """Validate binary (B) data type - no validation."""
        return []


# Convenience functions


def validate_element(
    element: ParsedElement,
    context: ElementValidationContext,
    data_type: DataType | None = None,
    min_length: int = 1,
    max_length: int = 99999,
    requirement: Requirement = Requirement.O,
) -> list[ParseError]:
    """
    Convenience function to validate a single element.
    """
    validator = ElementValidator()
    return validator.validate(element, context, data_type, min_length, max_length, requirement)


def validate_element_type(
    value: str,
    data_type: DataType,
    context: ElementValidationContext,
) -> list[ParseError]:
    """
    Validate just the data type of a value.
    """
    validator = ElementValidator()
    position = None
    return validator._validate_type(value, data_type, context, position)


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
    position = None
    return validator._validate_length(value, min_length, max_length, context, position)
