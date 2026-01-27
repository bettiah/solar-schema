"""
Validation Rules for Semantic Models.

Defines validation rules that run after mapping to ensure the
mapped model is semantically valid.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Callable

from .context import MessageContext
from .errors import MappingError, MappingErrorCode, MappingErrorSeverity


# =============================================================================
# Utility Functions for Path Access
# =============================================================================


def get_nested_attr(obj: Any, path: str) -> Any:
    """
    Get a nested attribute value by dot-separated path.

    Supports:
    - Simple paths: "id", "name"
    - Nested paths: "buyer_customer_party.party.name"
    - List indexing: "order_lines[0].id"
    - List all items: "order_lines[].quantity.value"

    Args:
        obj: The object to get the attribute from
        path: Dot-separated path with optional [] for lists

    Returns:
        The value at the path, or None if not found
    """
    if not path or obj is None:
        return obj

    parts = path.replace("[", ".[").split(".")
    current = obj

    for part in parts:
        if current is None:
            return None

        if part == "[]":
            # Return all items in list
            if isinstance(current, list):
                return current
            return None

        if part.startswith("[") and part.endswith("]"):
            # List index
            try:
                index = int(part[1:-1])
                if isinstance(current, list) and 0 <= index < len(current):
                    current = current[index]
                else:
                    return None
            except ValueError:
                return None
        else:
            # Attribute access
            if hasattr(current, part):
                current = getattr(current, part)
            elif isinstance(current, dict):
                current = current.get(part)
            else:
                return None

    return current


# =============================================================================
# Base Validation Rule
# =============================================================================


class ValidationRule(ABC):
    """Base class for validation rules."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable rule name."""
        pass

    @property
    def severity(self) -> MappingErrorSeverity:
        """Default severity for violations."""
        return MappingErrorSeverity.ERROR

    @abstractmethod
    def validate(self, model: Any, context: MessageContext | None) -> list[MappingError]:
        """
        Validate the model, return list of errors.

        Args:
            model: The semantic model to validate
            context: Optional message context for context-aware validation

        Returns:
            List of validation errors (empty if valid)
        """
        pass


# =============================================================================
# Field Validation Rule
# =============================================================================


@dataclass
class FieldValidationRule(ValidationRule):
    """Validate a single field."""

    path: str
    validator: Callable[[Any], bool]
    message: str
    rule_name: str | None = None
    error_severity: MappingErrorSeverity = MappingErrorSeverity.ERROR

    @property
    def name(self) -> str:
        return self.rule_name or f"validate_{self.path}"

    @property
    def severity(self) -> MappingErrorSeverity:
        return self.error_severity

    def validate(self, model: Any, context: MessageContext | None) -> list[MappingError]:
        """Validate the field value."""
        # Handle list paths like "order_lines[].quantity.value"
        if "[]" in self.path:
            return self._validate_list_path(model)

        value = get_nested_attr(model, self.path)

        # Skip validation if value is None (use required validation separately)
        if value is None:
            return []

        if not self.validator(value):
            return [
                MappingError(
                    code=MappingErrorCode.CONSTRAINT_VIOLATED,
                    severity=self.severity,
                    message=self.message,
                    target_path=self.path,
                    value=value,
                )
            ]
        return []

    def _validate_list_path(self, model: Any) -> list[MappingError]:
        """Validate a path that contains []."""
        errors: list[MappingError] = []
        parts = self.path.split("[]")

        if len(parts) != 2:
            return errors

        list_path = parts[0].rstrip(".")
        item_path = parts[1].lstrip(".")

        items = get_nested_attr(model, list_path)
        if not isinstance(items, list):
            return errors

        for i, item in enumerate(items):
            if item_path:
                value = get_nested_attr(item, item_path)
            else:
                value = item

            if value is not None and not self.validator(value):
                errors.append(
                    MappingError(
                        code=MappingErrorCode.CONSTRAINT_VIOLATED,
                        severity=self.severity,
                        message=self.message,
                        target_path=f"{list_path}[{i}].{item_path}" if item_path else f"{list_path}[{i}]",
                        value=value,
                    )
                )

        return errors


# =============================================================================
# Required Field Rule
# =============================================================================


@dataclass
class RequiredFieldRule(ValidationRule):
    """Validate that a field is present and not empty."""

    path: str
    message: str | None = None
    rule_name: str | None = None
    error_severity: MappingErrorSeverity = MappingErrorSeverity.ERROR

    @property
    def name(self) -> str:
        return self.rule_name or f"required_{self.path}"

    @property
    def severity(self) -> MappingErrorSeverity:
        return self.error_severity

    def validate(self, model: Any, context: MessageContext | None) -> list[MappingError]:
        """Validate that the field is present."""
        value = get_nested_attr(model, self.path)

        if value is None:
            return [
                MappingError(
                    code=MappingErrorCode.REQUIRED_FIELD_MISSING,
                    severity=self.severity,
                    message=self.message or f"Required field '{self.path}' is missing",
                    target_path=self.path,
                )
            ]

        # Check for empty strings
        if isinstance(value, str) and not value.strip():
            return [
                MappingError(
                    code=MappingErrorCode.REQUIRED_FIELD_MISSING,
                    severity=self.severity,
                    message=self.message or f"Required field '{self.path}' is empty",
                    target_path=self.path,
                )
            ]

        return []


# =============================================================================
# Cross-Field Validation Rule
# =============================================================================


@dataclass
class CrossFieldValidationRule(ValidationRule):
    """Validate relationships between fields."""

    rule_name: str
    fields: list[str]
    validator: Callable[[dict[str, Any]], bool]
    message: str
    error_severity: MappingErrorSeverity = MappingErrorSeverity.ERROR

    @property
    def name(self) -> str:
        return self.rule_name

    @property
    def severity(self) -> MappingErrorSeverity:
        return self.error_severity

    def validate(self, model: Any, context: MessageContext | None) -> list[MappingError]:
        """Validate the cross-field constraint."""
        values = {f: get_nested_attr(model, f) for f in self.fields}

        if not self.validator(values):
            return [
                MappingError(
                    code=MappingErrorCode.CROSS_FIELD_VALIDATION_FAILED,
                    severity=self.severity,
                    message=self.message,
                    target_path=", ".join(self.fields),
                    value=values,
                )
            ]
        return []


# =============================================================================
# Conditional Validation Rule
# =============================================================================


@dataclass
class ConditionalValidationRule(ValidationRule):
    """Validate only when a condition is met."""

    condition: Callable[[Any, MessageContext | None], bool]
    inner_rule: ValidationRule

    @property
    def name(self) -> str:
        return f"conditional_{self.inner_rule.name}"

    @property
    def severity(self) -> MappingErrorSeverity:
        return self.inner_rule.severity

    def validate(self, model: Any, context: MessageContext | None) -> list[MappingError]:
        """Validate if condition is met."""
        if self.condition(model, context):
            return self.inner_rule.validate(model, context)
        return []


# =============================================================================
# Composite Validation Rule
# =============================================================================


class CompositeValidationRule(ValidationRule):
    """Combines multiple validation rules."""

    def __init__(
        self,
        rule_name: str,
        rules: list[ValidationRule],
        stop_on_first_error: bool = False,
    ) -> None:
        self._name = rule_name
        self._rules = rules
        self._stop_on_first_error = stop_on_first_error

    @property
    def name(self) -> str:
        return self._name

    def validate(self, model: Any, context: MessageContext | None) -> list[MappingError]:
        """Run all inner rules."""
        errors: list[MappingError] = []

        for rule in self._rules:
            rule_errors = rule.validate(model, context)
            errors.extend(rule_errors)

            if self._stop_on_first_error and rule_errors:
                break

        return errors


# =============================================================================
# Built-in Validators
# =============================================================================


def is_not_empty(value: str) -> bool:
    """Check that a string value is not empty."""
    return value is not None and len(value.strip()) > 0


def is_positive(value: Decimal | int | float) -> bool:
    """Check that a numeric value is positive."""
    return value is not None and value > 0


def is_non_negative(value: Decimal | int | float) -> bool:
    """Check that a numeric value is non-negative."""
    return value is not None and value >= 0


def is_valid_date(value: date) -> bool:
    """Check that a date is valid (reasonable range)."""
    return value is not None and 1900 <= value.year <= 2100


def is_valid_currency_code(value: str) -> bool:
    """Check that a value is a valid ISO 4217 currency code."""
    # Common currency codes - not exhaustive
    valid_codes = {
        "USD",
        "EUR",
        "GBP",
        "CAD",
        "AUD",
        "JPY",
        "CHF",
        "CNY",
        "INR",
        "MXN",
        "BRL",
        "KRW",
        "SGD",
        "HKD",
        "NZD",
        "SEK",
        "NOK",
        "DKK",
        "ZAR",
        "RUB",
    }
    return value in valid_codes


def is_valid_country_code(value: str) -> bool:
    """Check that a value is a valid ISO 3166-1 alpha-2 country code."""
    # Common country codes - not exhaustive
    valid_codes = {
        "US",
        "CA",
        "MX",
        "GB",
        "DE",
        "FR",
        "IT",
        "ES",
        "NL",
        "BE",
        "AT",
        "CH",
        "AU",
        "NZ",
        "JP",
        "CN",
        "KR",
        "IN",
        "BR",
        "AR",
        "ZA",
        "SE",
        "NO",
        "DK",
        "FI",
        "PL",
        "CZ",
        "HU",
        "RO",
        "BG",
        "GR",
        "PT",
        "IE",
        "SG",
        "HK",
        "TW",
        "TH",
        "MY",
        "ID",
        "PH",
        "VN",
    }
    return value in valid_codes


def is_valid_unit_code(value: str) -> bool:
    """Check that a value is a valid UN/ECE Rec 20 unit code."""
    # Common unit codes
    valid_codes = {
        "EA",  # Each
        "PC",  # Piece
        "BX",  # Box
        "CS",  # Case
        "CT",  # Carton
        "PK",  # Package
        "KG",  # Kilogram
        "LB",  # Pound
        "OZ",  # Ounce
        "GRM",  # Gram
        "MTR",  # Meter
        "FT",  # Foot
        "IN",  # Inch
        "CM",  # Centimeter
        "LTR",  # Liter
        "GAL",  # Gallon
        "QT",  # Quart
        "UN",  # Unit
        "SET",  # Set
        "PR",  # Pair
        "DZ",  # Dozen
        "RL",  # Roll
        "SH",  # Sheet
        "CA",  # Can
        "BT",  # Bottle
        "PL",  # Pallet
        "CY",  # Cylinder
    }
    return value in valid_codes


def matches_pattern(pattern: str) -> Callable[[str], bool]:
    """Create a validator that checks if value matches a regex pattern."""
    import re

    compiled = re.compile(pattern)

    def validator(value: str) -> bool:
        return bool(compiled.match(value))

    return validator


def is_in_list(valid_values: list[Any]) -> Callable[[Any], bool]:
    """Create a validator that checks if value is in a list."""
    valid_set = set(valid_values)

    def validator(value: Any) -> bool:
        return value in valid_set

    return validator


def has_length(min_length: int = 0, max_length: int | None = None) -> Callable[[str], bool]:
    """Create a validator that checks string length."""

    def validator(value: str) -> bool:
        if value is None:
            return min_length == 0
        length = len(value)
        if length < min_length:
            return False
        if max_length is not None and length > max_length:
            return False
        return True

    return validator


def is_in_range(
    min_value: Decimal | int | float | None = None,
    max_value: Decimal | int | float | None = None,
) -> Callable[[Decimal | int | float], bool]:
    """Create a validator that checks if value is in a numeric range."""

    def validator(value: Decimal | int | float) -> bool:
        if value is None:
            return False
        if min_value is not None and value < min_value:
            return False
        if max_value is not None and value > max_value:
            return False
        return True

    return validator
