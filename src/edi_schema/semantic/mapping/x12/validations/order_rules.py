"""
Validation rules for Order (850) transactions.
"""

from ...validation import (
    CrossFieldValidationRule,
    FieldValidationRule,
    RequiredFieldRule,
    is_non_negative,
    is_not_empty,
    is_positive,
    is_valid_currency_code,
    is_valid_date,
)


# =============================================================================
# Order-Specific Validation Rules
# =============================================================================


ORDER_VALIDATION_RULES = [
    # Required fields
    RequiredFieldRule(
        path="id",
        message="Order ID is required",
    ),
    RequiredFieldRule(
        path="issue_date",
        message="Issue date is required",
    ),
    RequiredFieldRule(
        path="document_currency_code",
        message="Document currency code is required",
    ),
    # Field constraints
    FieldValidationRule(
        path="id",
        validator=is_not_empty,
        message="Order ID cannot be empty",
    ),
    FieldValidationRule(
        path="issue_date",
        validator=is_valid_date,
        message="Issue date must be a valid date",
    ),
    FieldValidationRule(
        path="document_currency_code",
        validator=is_valid_currency_code,
        message="Document currency must be a valid ISO 4217 code",
    ),
    # Line item validations
    FieldValidationRule(
        path="order_lines[].quantity.value",
        validator=is_positive,
        message="Line quantity must be positive",
    ),
    FieldValidationRule(
        path="order_lines[].price.price_amount.value",
        validator=is_non_negative,
        message="Line price cannot be negative",
    ),
    # Cross-field validations
    CrossFieldValidationRule(
        rule_name="line_count_matches",
        fields=["line_count", "order_lines"],
        validator=lambda v: (
            v["line_count"] is None or len(v["order_lines"] or []) == v["line_count"]
        ),
        message="Line count does not match actual number of order lines",
    ),
    CrossFieldValidationRule(
        rule_name="has_at_least_one_line",
        fields=["order_lines"],
        validator=lambda v: v["order_lines"] is not None and len(v["order_lines"]) > 0,
        message="Order must have at least one line item",
    ),
]
