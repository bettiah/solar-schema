"""
Code Validator (Level 5).

Validates coded element values against code lists from UNCL (UN Code Lists).

EDIFACT code lists are defined in UNCL.xxA files and contain valid values
for coded data elements like:
- Element 1001: Document name code
- Element 3035: Party function code qualifier
- Element 4343: Response type code

EDIFACT Error Codes (for CONTRL UCD):
- 12: Invalid value
- 14: Value not supported
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from edi_schema.edifact.ast import (
    ErrorCategory,
    ErrorSeverity,
    ParsedElement,
    ParseError,
)

if TYPE_CHECKING:
    from edi_schema.edifact.models import DataElement


@dataclass
class CodeValidationContext:
    """Context for code validation."""

    segment_tag: str
    segment_position: int
    element_position: int
    element_id: str | None = None
    component_position: int | None = None


class CodeValidator:
    """
    Validates coded element values against their code lists.

    Code sources in EDIFACT:
    1. Inline codes in DataElement.codes (from UNCL parser)
    2. External code sources (user-provided)

    By default, unknown codes generate warnings rather than errors
    because code lists may be incomplete or implementation-specific.
    """

    def __init__(
        self,
        strict: bool = False,
        external_codes: dict[str, set[str]] | None = None,
    ):
        """
        Initialize the code validator.

        Args:
            strict: If True, unknown codes are errors; if False, warnings
            external_codes: Optional dict of external code sources {element_tag: {codes}}
        """
        self.strict = strict
        self.external_codes = external_codes or {}
        self.errors: list[ParseError] = []

    def validate(
        self,
        element: ParsedElement,
        definition: "DataElement",
        context: CodeValidationContext,
    ) -> list[ParseError]:
        """
        Validate an element value against its code list.

        Args:
            element: The parsed element
            definition: The element definition with code values
            context: Validation context

        Returns:
            List of validation errors/warnings
        """
        errors: list[ParseError] = []

        # Get value from element
        value = element.raw.value if element.raw else None

        # Skip empty values (handled by element validator)
        if not value:
            return errors

        # Only validate DataElement types (Composite doesn't have codes)
        # Check if definition has a 'codes' attribute (DataElement has it, Composite doesn't)
        if not hasattr(definition, "codes") or not definition.codes:
            return errors

        # Get valid codes
        valid_codes = self._get_valid_codes(definition)

        # If no code list, skip validation
        if not valid_codes:
            return errors

        # Check if value is valid
        if value not in valid_codes:
            severity = ErrorSeverity.ERROR if self.strict else ErrorSeverity.WARNING

            elem_id = f"{context.segment_tag}{context.element_position:02d}"
            if context.component_position:
                elem_id += f"-{context.component_position}"

            errors.append(
                ParseError(
                    code="12",  # Invalid value
                    message=f"Element {elem_id} has invalid code value: {value!r}",
                    category=ErrorCategory.CODE,
                    severity=severity,
                    position=element.raw.position if element.raw else None,
                    segment_tag=context.segment_tag,
                    segment_position=context.segment_position,
                    element_position=context.element_position,
                    component_position=context.component_position,
                    actual=value,
                    expected=f"one of {len(valid_codes)} valid codes",
                )
            )

        return errors

    def _get_valid_codes(self, definition: "DataElement") -> set[str]:
        """
        Get the set of valid codes for an element.

        Combines inline codes with external codes if available.
        """
        valid_codes: set[str] = set()

        # Inline codes from element definition
        if definition.codes:
            valid_codes.update(definition.codes.keys())

        # External codes if element has them
        if definition.tag in self.external_codes:
            valid_codes.update(self.external_codes[definition.tag])

        return valid_codes

    def validate_against_list(
        self,
        value: str,
        valid_codes: set[str],
        context: CodeValidationContext,
    ) -> list[ParseError]:
        """
        Validate a value against a specific code list.

        Args:
            value: The value to validate
            valid_codes: Set of valid code values
            context: Validation context

        Returns:
            List of validation errors
        """
        errors: list[ParseError] = []

        if not value or not valid_codes:
            return errors

        if value not in valid_codes:
            severity = ErrorSeverity.ERROR if self.strict else ErrorSeverity.WARNING

            elem_id = f"{context.segment_tag}{context.element_position:02d}"
            if context.component_position:
                elem_id += f"-{context.component_position}"

            errors.append(
                ParseError(
                    code="12",  # Invalid value
                    message=f"Element {elem_id} has invalid code value: {value!r}",
                    category=ErrorCategory.CODE,
                    severity=severity,
                    segment_tag=context.segment_tag,
                    segment_position=context.segment_position,
                    element_position=context.element_position,
                    component_position=context.component_position,
                    actual=value,
                )
            )

        return errors


# Well-known EDIFACT code lists for common elements

# Element 1001 - Document name code
DOCUMENT_NAME_CODES = {
    "380": "Commercial invoice",
    "381": "Credit note",
    "382": "Debit note",
    "383": "Corrected invoice",
    "384": "Consolidated invoice",
    "385": "Proforma invoice",
    "386": "Factored invoice",
    "389": "Self-billed invoice",
    "393": "Factored credit note",
    "220": "Order",
    "221": "Blanket order",
    "224": "Rush order",
    "225": "Repair order",
    "226": "Call off order",
    "227": "Consignment order",
    "228": "Sample order",
    "229": "Spot order",
    "351": "Despatch advice",
    "352": "Cross-docking despatch advice",
}

# Element 3035 - Party function code qualifier
PARTY_FUNCTION_CODES = {
    "BY": "Buyer",
    "SE": "Seller",
    "SU": "Supplier",
    "CN": "Consignee",
    "DP": "Delivery party",
    "PE": "Payee",
    "PR": "Payer",
    "IV": "Invoicee",
    "CA": "Carrier",
    "MF": "Manufacturer",
    "OB": "Ordered by",
    "UC": "Ultimate consignee",
    "WH": "Warehouse keeper",
}

# Element 4343 - Response type code
RESPONSE_TYPE_CODES = {
    "AA": "Accept with amendment",
    "AB": "Accepted with detail",
    "AC": "Acknowledged",
    "AD": "Accepted with detail and exception",
    "AE": "Accepted with exception",
    "AF": "Accept with amendment/exception",
    "AI": "Accept with amendment with detail",
    "AK": "Accepted",
    "AP": "Accepted with percentage",
    "AR": "Accepted without reservation",
    "RE": "Rejected",
    "RJ": "Rejected with detail",
}

# Element 2379 - Date/time period qualifier
DATE_TIME_QUALIFIERS = {
    "137": "Document/message date/time",
    "171": "Reference date/time",
    "2": "Delivery date/time, requested",
    "10": "Shipment date/time, requested",
    "11": "Despatch date and/or time",
    "35": "Delivery date/time, actual",
    "36": "Expiry date",
    "50": "Goods receipt date/time",
    "63": "Delivery date/time, latest",
    "64": "Delivery date/time, earliest",
    "69": "Delivery date/time, earliest/latest",
}


# Convenience function


def validate_code_value(
    value: str,
    valid_codes: set[str] | dict[str, str],
    context: CodeValidationContext,
    strict: bool = False,
) -> list[ParseError]:
    """
    Convenience function to validate a code value.

    Args:
        value: The value to validate
        valid_codes: Set or dict of valid codes
        context: Validation context
        strict: If True, invalid codes are errors; if False, warnings

    Returns:
        List of validation errors
    """
    if isinstance(valid_codes, dict):
        valid_codes = set(valid_codes.keys())

    validator = CodeValidator(strict=strict)
    return validator.validate_against_list(value, valid_codes, context)
