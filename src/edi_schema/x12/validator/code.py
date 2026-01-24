"""
Code Validator (Level 5).

Validates coded element values against code lists.

X12 has multiple sources for code values:
- Element definitions contain inline code values (from freeform.txt ELECOD sections)
- External code sources referenced by code_source field
- Implementation guide specific code subsets

Error Codes (for 997 AK4):
- 7: Invalid code value
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from edi_schema.x12.ast import (
    ErrorCategory,
    ErrorSeverity,
    ParsedElement,
    ParseError,
)
from edi_schema.x12.enums import DataElementType

# Alias for cleaner code
DataType = DataElementType

if TYPE_CHECKING:
    from edi_schema.x12.models.element import DataElement


@dataclass
class CodeValidationContext:
    """Context for code validation."""

    segment_tag: str
    segment_position: int
    element_position: int
    element_id: str | None = None
    loop_id: str | None = None


class CodeValidator:
    """
    Validates coded element values against their code lists.

    Code sources in X12:
    1. Inline codes in element definition (code_values dict)
    2. External code sources (cs_de.txt, cs_cv.txt)
    3. Industry-specific codes (HIPAA, etc.)

    By default, unknown codes generate warnings rather than errors
    because code lists may be incomplete.
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
            external_codes: Optional dict of external code sources
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
        value = element.value

        # Skip empty values (handled by element validator)
        if not value:
            return errors

        # Only validate ID type elements
        if definition.data_type != DataType.ID:
            return errors

        # Get valid codes
        valid_codes = self._get_valid_codes(definition)

        # If no code list, skip validation
        if not valid_codes:
            return errors

        # Check if value is valid
        if value not in valid_codes:
            severity = ErrorSeverity.ERROR if self.strict else ErrorSeverity.WARNING

            errors.append(
                ParseError(
                    code="7",  # Invalid code value
                    message=f"Element {context.segment_tag}{context.element_position:02d} "
                    f"has invalid code value: {value!r}",
                    category=ErrorCategory.CODE,
                    severity=severity,
                    position=element.raw.position if hasattr(element.raw, "position") else None,
                    segment_tag=context.segment_tag,
                    segment_position=context.segment_position,
                    element_position=context.element_position,
                    loop_id=context.loop_id,
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
        if definition.code_values:
            valid_codes.update(definition.code_values.keys())

        # External codes if element has a code source
        if definition.code_source and definition.code_source in self.external_codes:
            valid_codes.update(self.external_codes[definition.code_source])

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

            errors.append(
                ParseError(
                    code="7",
                    message=f"Element {context.segment_tag}{context.element_position:02d} "
                    f"has invalid code value: {value!r}",
                    category=ErrorCategory.CODE,
                    severity=severity,
                    segment_tag=context.segment_tag,
                    segment_position=context.segment_position,
                    element_position=context.element_position,
                    loop_id=context.loop_id,
                    actual=value,
                )
            )

        return errors


# Well-known code lists for common elements

# ISA05/ISA07 - ID Qualifier
ID_QUALIFIERS = {
    "01": "Duns (Dun & Bradstreet)",
    "02": "SCAC (Standard Carrier Alpha Code)",
    "03": "Federal Maritime Commission",
    "04": "IATA (International Air Transport Association)",
    "07": "Global Location Number",
    "08": "UCC EDI Communications ID",
    "09": "X.121 (CCITT)",
    "10": "Department of Defense Communication ID",
    "11": "DEA (Drug Enforcement Administration)",
    "12": "Phone",
    "13": "UCS Code",
    "14": "Duns Plus Suffix",
    "15": "Petroleum Accountants Society of Canada Company Code",
    "16": "Duns Number With 4-Character Suffix",
    "17": "American Bankers Association Transit Routing Number",
    "18": "AIAG (Automotive Industry Action Group)",
    "19": "EDI Council of Australia",
    "20": "HIN (Health Industry Number)",
    "27": "Carrier Identification Number (Transportation)",
    "28": "Fiscal Intermediary Identification Number",
    "29": "Medicare Provider and Supplier Identification Number",
    "30": "Federal Tax ID",
    "31": "NAICS Code",
    "32": "Carrier Commercial Number",
    "33": "Postal Service Processing Code",
    "34": "Social Security Number",
    "35": "Standard Industrial Classification (SIC) Code",
    "36": "Statistics Canada List of Financial Institutions",
    "37": "Store Number",
    "38": "Swiss Clearing Identification Code",
    "AM": "Association Mexicana del Codigo de Producto",
    "NR": "National Retail Merchants Association",
    "SA": "Society of Actuaries",
    "SN": "Standard Address Number",
    "ZZ": "Mutually Defined",
}

# GS01 - Functional ID Codes
FUNCTIONAL_ID_CODES = {
    "AA": "Account Analysis (822)",
    "AG": "Application Advice (824)",
    "BE": "Benefit Enrollment (834)",
    "CA": "Purchase Order Change Acknowledgment (865)",
    "CO": "Cooperative Advertising Agreements (290)",
    "FA": "Functional Acknowledgment (997)",
    "GF": "Response to a Load Tender (990)",
    "HB": "Eligibility, Coverage, or Benefit Information (271)",
    "HC": "Health Care Claim (837)",
    "HI": "Health Care Services Review Information (278)",
    "HN": "Health Care Claim Status Notification (277)",
    "HP": "Health Care Claim Payment/Advice (835)",
    "HR": "Health Care Claim Status Request (276)",
    "HS": "Eligibility, Coverage, or Benefit Inquiry (270)",
    "IA": "Inventory Inquiry/Advice (846)",
    "IN": "Invoice (810)",
    "ME": "Mortgage Application Information (1028)",
    "MF": "Motor Carrier Pickup Manifest (215)",
    "NL": "Name and Address Lists (101)",
    "OW": "Warehouse Shipping Order (940)",
    "PO": "Purchase Order (850)",
    "PR": "Purchase Order Acknowledgment (855)",
    "PS": "Planning Schedule (830)",
    "PT": "Product Transfer (867)",
    "RA": "Remittance Advice (820)",
    "RC": "Receiving Advice (861)",
    "RD": "Royalty Regulatory Report (185)",
    "RF": "Response to Request for Quotation (843)",
    "RO": "Order Status Inquiry (869)",
    "RS": "Order Status Report (870)",
    "SH": "Ship Notice/Manifest (856)",
    "SM": "Motor Carrier Load Tender (204)",
    "SP": "Specifications (841)",
    "ST": "Price/Sales Catalog (832)",
    "SW": "Warehouse Shipping Advice (945)",
    "TX": "Text Message (864)",
    "WA": "Product Service Transaction Sets (140)",
}

# Usage indicator (ISA15)
USAGE_INDICATORS = {
    "I": "Information",
    "P": "Production",
    "T": "Test",
}


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
