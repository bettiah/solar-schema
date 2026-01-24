"""
Element Validator.

Validates element values against CCTS data type rules.
"""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Callable

from ..ast import ErrorCategory, ErrorSeverity, ParsedElement
from ..enums import RepresentationTerm
from ..models import BBIE
from .core import ValidationContext


# Type alias for type validators
TypeValidator = Callable[[str, ParsedElement, ValidationContext], bool]


def validate_element_types(element: ParsedElement, context: ValidationContext) -> None:
    """
    Validate element value against its BBIE data type.

    Args:
        element: The element to validate
        context: Validation context
    """
    component = element.schema_component

    if not isinstance(component, BBIE):
        return

    # Get representation term
    rep_term = component.representation_term

    # Get validator for this type
    validator = TYPE_VALIDATORS.get(rep_term)
    if validator:
        validator(element.value, element, component, context)

    # Validate required attributes
    _validate_required_attributes(element, component, context)


def _validate_required_attributes(
    element: ParsedElement,
    bbie: BBIE,
    context: ValidationContext,
) -> None:
    """
    Validate required attributes for specific types.

    Args:
        element: The element to check
        bbie: The BBIE schema
        context: Validation context
    """
    rep_term = bbie.representation_term

    # Amount requires currencyID
    if rep_term == "Amount":
        if element.get_attribute("currencyID") is None:
            context.add_error(
                code="MISSING_CURRENCY_ID",
                message=f"Amount element '{element.tag}' requires currencyID attribute",
                category=ErrorCategory.ELEMENT,
                position=element.position,
            )

    # Measure requires unitCode
    elif rep_term == "Measure":
        if element.get_attribute("unitCode") is None:
            context.add_error(
                code="MISSING_UNIT_CODE",
                message=f"Measure element '{element.tag}' requires unitCode attribute",
                category=ErrorCategory.ELEMENT,
                position=element.position,
            )

    # Quantity requires unitCode
    elif rep_term == "Quantity":
        if element.get_attribute("unitCode") is None:
            context.add_error(
                code="MISSING_UNIT_CODE",
                message=f"Quantity element '{element.tag}' requires unitCode attribute",
                category=ErrorCategory.ELEMENT,
                position=element.position,
            )

    # BinaryObject requires mimeCode
    elif rep_term == "Binary Object":
        if element.get_attribute("mimeCode") is None:
            context.add_error(
                code="MISSING_MIME_CODE",
                message=f"BinaryObject element '{element.tag}' requires mimeCode attribute",
                category=ErrorCategory.ELEMENT,
                position=element.position,
                severity=ErrorSeverity.WARNING,
            )


def validate_amount(
    value: str | None,
    element: ParsedElement,
    bbie: BBIE,
    context: ValidationContext,
) -> bool:
    """Validate Amount type (decimal with currency)."""
    if value is None:
        return True

    try:
        Decimal(value)
        return True
    except InvalidOperation:
        context.add_error(
            code="INVALID_AMOUNT",
            message=f"Invalid amount value '{value}' in '{element.tag}'",
            category=ErrorCategory.ELEMENT,
            position=element.position,
            value=value,
        )
        return False


def validate_code(
    value: str | None,
    element: ParsedElement,
    bbie: BBIE,
    context: ValidationContext,
) -> bool:
    """Validate Code type (string from controlled vocabulary)."""
    if value is None:
        return True

    # Code validation is handled by code.py
    return True


def validate_date(
    value: str | None,
    element: ParsedElement,
    bbie: BBIE,
    context: ValidationContext,
) -> bool:
    """Validate Date type (ISO 8601 date: YYYY-MM-DD)."""
    if value is None:
        return True

    # ISO 8601 date format
    date_pattern = r"^\d{4}-\d{2}-\d{2}$"
    if not re.match(date_pattern, value):
        context.add_error(
            code="INVALID_DATE_FORMAT",
            message=f"Invalid date format '{value}' in '{element.tag}', expected YYYY-MM-DD",
            category=ErrorCategory.ELEMENT,
            position=element.position,
            value=value,
        )
        return False

    # Validate as actual date
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        context.add_error(
            code="INVALID_DATE",
            message=f"Invalid date value '{value}' in '{element.tag}'",
            category=ErrorCategory.ELEMENT,
            position=element.position,
            value=value,
        )
        return False


def validate_datetime(
    value: str | None,
    element: ParsedElement,
    bbie: BBIE,
    context: ValidationContext,
) -> bool:
    """Validate DateTime type (ISO 8601 datetime)."""
    if value is None:
        return True

    # ISO 8601 datetime formats
    datetime_patterns = [
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$",  # Without timezone
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",  # UTC
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$",  # With offset
    ]

    if not any(re.match(p, value) for p in datetime_patterns):
        context.add_error(
            code="INVALID_DATETIME_FORMAT",
            message=f"Invalid datetime format '{value}' in '{element.tag}'",
            category=ErrorCategory.ELEMENT,
            position=element.position,
            value=value,
        )
        return False

    return True


def validate_identifier(
    value: str | None,
    element: ParsedElement,
    bbie: BBIE,
    context: ValidationContext,
) -> bool:
    """Validate Identifier type (string)."""
    if value is None:
        return True

    # Identifiers should not be empty when present
    if not value.strip():
        context.add_error(
            code="EMPTY_IDENTIFIER",
            message=f"Identifier element '{element.tag}' has empty value",
            category=ErrorCategory.ELEMENT,
            position=element.position,
            severity=ErrorSeverity.WARNING,
        )

    return True


def validate_indicator(
    value: str | None,
    element: ParsedElement,
    bbie: BBIE,
    context: ValidationContext,
) -> bool:
    """Validate Indicator type (boolean: true/false)."""
    if value is None:
        return True

    if value.lower() not in ("true", "false", "1", "0"):
        context.add_error(
            code="INVALID_INDICATOR",
            message=f"Invalid indicator value '{value}' in '{element.tag}', expected true/false",
            category=ErrorCategory.ELEMENT,
            position=element.position,
            value=value,
        )
        return False

    return True


def validate_measure(
    value: str | None,
    element: ParsedElement,
    bbie: BBIE,
    context: ValidationContext,
) -> bool:
    """Validate Measure type (decimal with unit)."""
    if value is None:
        return True

    try:
        Decimal(value)
        return True
    except InvalidOperation:
        context.add_error(
            code="INVALID_MEASURE",
            message=f"Invalid measure value '{value}' in '{element.tag}'",
            category=ErrorCategory.ELEMENT,
            position=element.position,
            value=value,
        )
        return False


def validate_numeric(
    value: str | None,
    element: ParsedElement,
    bbie: BBIE,
    context: ValidationContext,
) -> bool:
    """Validate Numeric type (decimal)."""
    if value is None:
        return True

    try:
        Decimal(value)
        return True
    except InvalidOperation:
        context.add_error(
            code="INVALID_NUMERIC",
            message=f"Invalid numeric value '{value}' in '{element.tag}'",
            category=ErrorCategory.ELEMENT,
            position=element.position,
            value=value,
        )
        return False


def validate_percent(
    value: str | None,
    element: ParsedElement,
    bbie: BBIE,
    context: ValidationContext,
) -> bool:
    """Validate Percent type (decimal, typically 0-100)."""
    if value is None:
        return True

    try:
        num = Decimal(value)
        # Warning for unusual percentage values
        if num < 0 or num > 100:
            context.add_error(
                code="UNUSUAL_PERCENT",
                message=f"Unusual percent value '{value}' in '{element.tag}'",
                category=ErrorCategory.ELEMENT,
                position=element.position,
                severity=ErrorSeverity.WARNING,
                value=value,
            )
        return True
    except InvalidOperation:
        context.add_error(
            code="INVALID_PERCENT",
            message=f"Invalid percent value '{value}' in '{element.tag}'",
            category=ErrorCategory.ELEMENT,
            position=element.position,
            value=value,
        )
        return False


def validate_quantity(
    value: str | None,
    element: ParsedElement,
    bbie: BBIE,
    context: ValidationContext,
) -> bool:
    """Validate Quantity type (decimal with unit)."""
    if value is None:
        return True

    try:
        Decimal(value)
        return True
    except InvalidOperation:
        context.add_error(
            code="INVALID_QUANTITY",
            message=f"Invalid quantity value '{value}' in '{element.tag}'",
            category=ErrorCategory.ELEMENT,
            position=element.position,
            value=value,
        )
        return False


def validate_rate(
    value: str | None,
    element: ParsedElement,
    bbie: BBIE,
    context: ValidationContext,
) -> bool:
    """Validate Rate type (decimal)."""
    if value is None:
        return True

    try:
        Decimal(value)
        return True
    except InvalidOperation:
        context.add_error(
            code="INVALID_RATE",
            message=f"Invalid rate value '{value}' in '{element.tag}'",
            category=ErrorCategory.ELEMENT,
            position=element.position,
            value=value,
        )
        return False


def validate_text(
    value: str | None,
    element: ParsedElement,
    bbie: BBIE,
    context: ValidationContext,
) -> bool:
    """Validate Text type (string)."""
    # Text has no specific format requirements
    return True


def validate_time(
    value: str | None,
    element: ParsedElement,
    bbie: BBIE,
    context: ValidationContext,
) -> bool:
    """Validate Time type (ISO 8601 time: HH:MM:SS)."""
    if value is None:
        return True

    # ISO 8601 time patterns
    time_patterns = [
        r"^\d{2}:\d{2}:\d{2}$",  # HH:MM:SS
        r"^\d{2}:\d{2}:\d{2}Z$",  # With UTC indicator
        r"^\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$",  # With timezone offset
    ]

    if not any(re.match(p, value) for p in time_patterns):
        context.add_error(
            code="INVALID_TIME_FORMAT",
            message=f"Invalid time format '{value}' in '{element.tag}', expected HH:MM:SS",
            category=ErrorCategory.ELEMENT,
            position=element.position,
            value=value,
        )
        return False

    return True


def validate_binary_object(
    value: str | None,
    element: ParsedElement,
    bbie: BBIE,
    context: ValidationContext,
) -> bool:
    """Validate BinaryObject type (base64 encoded)."""
    if value is None:
        return True

    # Basic base64 validation
    base64_pattern = r"^[A-Za-z0-9+/]*={0,2}$"
    if not re.match(base64_pattern, value.replace("\n", "").replace("\r", "")):
        context.add_error(
            code="INVALID_BASE64",
            message=f"Invalid base64 encoding in '{element.tag}'",
            category=ErrorCategory.ELEMENT,
            position=element.position,
        )
        return False

    return True


# Map representation terms to validators
TYPE_VALIDATORS: dict[str, Callable] = {
    "Amount": validate_amount,
    "Binary Object": validate_binary_object,
    "Code": validate_code,
    "Date": validate_date,
    "Date Time": validate_datetime,
    "Graphic": validate_binary_object,
    "Identifier": validate_identifier,
    "Indicator": validate_indicator,
    "Measure": validate_measure,
    "Name": validate_text,
    "Numeric": validate_numeric,
    "Percent": validate_percent,
    "Picture": validate_binary_object,
    "Quantity": validate_quantity,
    "Rate": validate_rate,
    "Sound": validate_binary_object,
    "Text": validate_text,
    "Time": validate_time,
    "Value": validate_numeric,
    "Video": validate_binary_object,
}
