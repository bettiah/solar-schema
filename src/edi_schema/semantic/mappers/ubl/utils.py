"""
UBL Mapping Utilities.

Helper functions for extracting and converting UBL data to semantic models.
"""

from datetime import date, time
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edi_schema.ubl.ast import ParsedElement


def get_child_value(element: "ParsedElement | None", tag: str) -> str | None:
    """Get the text value of a child element."""
    if element is None:
        return None
    child = element.find_child(tag)
    return child.value if child else None


def get_child_attr(
    element: "ParsedElement | None", tag: str, attr: str
) -> str | None:
    """Get an attribute value from a child element."""
    if element is None:
        return None
    child = element.find_child(tag)
    if child is None:
        return None
    return child.get_attribute(attr)


def parse_date(value: str | None) -> date | None:
    """Parse ISO date format to Python date."""
    if not value:
        return None
    try:
        # UBL uses ISO 8601: YYYY-MM-DD
        parts = value.split("-")
        if len(parts) == 3:
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, IndexError):
        pass
    return None


def parse_time(value: str | None) -> time | None:
    """Parse ISO time format to Python time."""
    if not value:
        return None
    try:
        # UBL uses ISO 8601: HH:MM:SS or HH:MM:SS.ffffff
        # May include timezone
        time_part = value.split("+")[0].split("-")[0].split("Z")[0]
        parts = time_part.split(":")
        if len(parts) >= 2:
            hour = int(parts[0])
            minute = int(parts[1])
            second = 0
            microsecond = 0
            if len(parts) >= 3:
                sec_parts = parts[2].split(".")
                second = int(sec_parts[0])
                if len(sec_parts) > 1:
                    # Microseconds
                    micro_str = sec_parts[1][:6].ljust(6, "0")
                    microsecond = int(micro_str)
            return time(hour, minute, second, microsecond)
    except (ValueError, IndexError):
        pass
    return None


def parse_decimal(value: str | None) -> Decimal | None:
    """Parse a decimal value."""
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def format_date(d: date | None) -> str:
    """Format date as ISO 8601."""
    if not d:
        return ""
    return d.isoformat()


def format_time(t: time | None) -> str:
    """Format time as ISO 8601."""
    if not t:
        return ""
    return t.isoformat()


def get_amount_with_currency(
    element: "ParsedElement | None", tag: str
) -> tuple[Decimal | None, str | None]:
    """
    Get an amount value and its currency from a UBL amount element.

    UBL amounts have the value as text and currency as @currencyID attribute.
    """
    if element is None:
        return None, None
    child = element.find_child(tag)
    if child is None:
        return None, None
    value = parse_decimal(child.value)
    currency = child.get_attribute("currencyID")
    return value, currency


def get_quantity_with_unit(
    element: "ParsedElement | None", tag: str
) -> tuple[Decimal | None, str | None]:
    """
    Get a quantity value and its unit from a UBL quantity element.

    UBL quantities have the value as text and unit as @unitCode attribute.
    """
    if element is None:
        return None, None
    child = element.find_child(tag)
    if child is None:
        return None, None
    value = parse_decimal(child.value)
    unit = child.get_attribute("unitCode")
    return value, unit


def get_identifier_with_scheme(
    element: "ParsedElement | None", tag: str
) -> tuple[str | None, str | None, str | None]:
    """
    Get an identifier value and its scheme from a UBL ID element.

    Returns (value, schemeID, schemeAgencyID).
    """
    if element is None:
        return None, None, None
    child = element.find_child(tag)
    if child is None:
        return None, None, None
    value = child.value
    scheme_id = child.get_attribute("schemeID")
    scheme_agency_id = child.get_attribute("schemeAgencyID")
    return value, scheme_id, scheme_agency_id


def find_party_by_type(
    root: "ParsedElement", party_type: str
) -> "ParsedElement | None":
    """
    Find a party element by its type tag.

    E.g., "BuyerCustomerParty", "SellerSupplierParty", "AccountingSupplierParty"
    """
    return root.find_child(party_type)
