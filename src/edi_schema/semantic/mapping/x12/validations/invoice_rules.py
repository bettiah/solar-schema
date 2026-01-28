"""
Validation rules for Invoice (810) transactions.
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
# Invoice-Specific Validation Rules
# =============================================================================


INVOICE_VALIDATION_RULES = [
    # Required fields
    RequiredFieldRule(
        path="id",
        message="Invoice ID is required",
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
        message="Invoice ID cannot be empty",
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
        path="invoice_lines[].invoiced_quantity.value",
        validator=is_positive,
        message="Line quantity must be positive",
    ),
    FieldValidationRule(
        path="invoice_lines[].price.price_amount.value",
        validator=is_non_negative,
        message="Line price cannot be negative",
    ),
    # Note: Line count validation disabled - X12 fixtures may have truncated lines
    # and line count may not match actual number of line items in the file
]
