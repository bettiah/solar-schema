"""
Code Validator.

Validates coded element values against code lists.
"""

from ..ast import ErrorCategory, ErrorSeverity, ParsedElement
from ..models import BBIE, CodeList
from .core import ValidationContext


# Map of element names to code list identifiers
ELEMENT_CODE_LISTS: dict[str, str] = {
    # Currency-related elements
    "CurrencyCode": "CurrencyCode",
    "SourceCurrencyCode": "CurrencyCode",
    "TargetCurrencyCode": "CurrencyCode",
    "DocumentCurrencyCode": "CurrencyCode",
    "TaxCurrencyCode": "CurrencyCode",
    "PricingCurrencyCode": "CurrencyCode",
    "PaymentCurrencyCode": "CurrencyCode",
    "PaymentAlternativeCurrencyCode": "CurrencyCode",

    # Country-related elements
    "CountrySubentityCode": "CountryIdentificationCode",
    "IdentificationCode": "CountryIdentificationCode",

    # Language elements
    "LanguageID": "LanguageCode",
    "LocaleCode": "LanguageCode",

    # Unit-related elements
    "PackSizeNumeric": "UnitOfMeasureCode",

    # Payment elements
    "PaymentMeansCode": "PaymentMeansCode",
    "PaymentChannelCode": "ChannelCode",

    # Transport elements
    "TransportModeCode": "TransportModeCode",
    "TransportEquipmentTypeCode": "TransportEquipmentTypeCode",
    "HandlingCode": "HandlingCode",
    "PackagingTypeCode": "PackagingTypeCode",
    "LocationTypeCode": "LocationTypeCode",

    # Allowance/charge
    "AllowanceChargeReasonCode": "AllowanceChargeReasonCode",
}


# Attribute-to-code-list mappings
ATTRIBUTE_CODE_LISTS: dict[str, str] = {
    "currencyID": "CurrencyCode",
    "unitCode": "UnitOfMeasureCode",
    "mimeCode": "BinaryObjectMimeCode",
    "languageID": "LanguageCode",
}


def validate_codes(element: ParsedElement, context: ValidationContext) -> None:
    """
    Validate coded element values against code lists.

    Args:
        element: The element to validate
        context: Validation context
    """
    component = element.schema_component

    # Skip non-BBIE elements (ABIEs don't have direct values)
    if not isinstance(component, BBIE):
        return

    # Check element value if it's a Code type
    if component.representation_term == "Code" and element.value:
        _validate_element_code(element, component, context)

    # Check attribute codes
    _validate_attribute_codes(element, context)


def _validate_element_code(
    element: ParsedElement,
    bbie: BBIE,
    context: ValidationContext,
) -> None:
    """
    Validate the element's text value against its code list.

    Args:
        element: The element with a coded value
        bbie: The BBIE schema
        context: Validation context
    """
    value = element.value
    if not value:
        return

    # Determine which code list to use
    code_list_id = ELEMENT_CODE_LISTS.get(element.tag)

    if code_list_id:
        code_list = context.schema.code_lists.get(code_list_id)
        if code_list:
            if not code_list.validate(value):
                context.add_error(
                    code="INVALID_CODE",
                    message=f"Invalid code '{value}' in '{element.tag}', not in {code_list_id}",
                    category=ErrorCategory.CODE,
                    position=element.position,
                    value=value,
                    code_list=code_list_id,
                )
        else:
            # Code list not loaded - add warning
            context.add_error(
                code="CODE_LIST_NOT_LOADED",
                message=f"Code list '{code_list_id}' not loaded, cannot validate '{element.tag}'",
                category=ErrorCategory.CODE,
                position=element.position,
                severity=ErrorSeverity.WARNING,
                code_list=code_list_id,
            )

    # Check listID attribute if present
    list_id_attr = element.get_attribute("listID")
    if list_id_attr:
        _validate_with_list_id(element, value, list_id_attr, context)


def _validate_attribute_codes(
    element: ParsedElement,
    context: ValidationContext,
) -> None:
    """
    Validate coded attributes (currencyID, unitCode, etc.).

    Args:
        element: The element to check
        context: Validation context
    """
    for attr in element.attributes:
        code_list_id = ATTRIBUTE_CODE_LISTS.get(attr.name)
        if code_list_id:
            code_list = context.schema.code_lists.get(code_list_id)
            if code_list:
                if not code_list.validate(attr.value):
                    context.add_error(
                        code="INVALID_ATTRIBUTE_CODE",
                        message=f"Invalid {attr.name} '{attr.value}' in '{element.tag}', not in {code_list_id}",
                        category=ErrorCategory.CODE,
                        position=element.position,
                        attribute=attr.name,
                        value=attr.value,
                        code_list=code_list_id,
                    )


def _validate_with_list_id(
    element: ParsedElement,
    value: str,
    list_id: str,
    context: ValidationContext,
) -> None:
    """
    Validate a code against a specific list identified by listID attribute.

    Args:
        element: The element with coded value
        value: The code value
        list_id: The listID attribute value
        context: Validation context
    """
    # Try to find the code list by listID
    code_list = None

    # Search in available code lists
    for cl_id, cl in context.schema.code_lists.items():
        if cl.short_name == list_id or cl.id == list_id:
            code_list = cl
            break

    if code_list:
        if not code_list.validate(value):
            context.add_error(
                code="INVALID_CODE_FOR_LIST",
                message=f"Invalid code '{value}' in '{element.tag}' for list '{list_id}'",
                category=ErrorCategory.CODE,
                position=element.position,
                value=value,
                list_id=list_id,
            )


def validate_currency_code(
    value: str,
    context: ValidationContext,
    element: ParsedElement,
) -> bool:
    """
    Validate a currency code against ISO 4217.

    Args:
        value: Currency code to validate
        context: Validation context
        element: Element for error reporting

    Returns:
        True if valid, False otherwise
    """
    code_list = context.schema.code_lists.get("CurrencyCode")
    if code_list:
        return code_list.validate(value)
    # If code list not loaded, return True (can't validate)
    return True


def validate_country_code(
    value: str,
    context: ValidationContext,
    element: ParsedElement,
) -> bool:
    """
    Validate a country code against ISO 3166-1.

    Args:
        value: Country code to validate
        context: Validation context
        element: Element for error reporting

    Returns:
        True if valid, False otherwise
    """
    code_list = context.schema.code_lists.get("CountryIdentificationCode")
    if code_list:
        return code_list.validate(value)
    return True


def validate_unit_code(
    value: str,
    context: ValidationContext,
    element: ParsedElement,
) -> bool:
    """
    Validate a unit of measure code against UNECE Rec 20.

    Args:
        value: Unit code to validate
        context: Validation context
        element: Element for error reporting

    Returns:
        True if valid, False otherwise
    """
    code_list = context.schema.code_lists.get("UnitOfMeasureCode")
    if code_list:
        return code_list.validate(value)
    return True
