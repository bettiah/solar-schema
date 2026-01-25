"""
X12 Mapping Utilities.

Helper functions for extracting and converting X12 data to semantic models.
"""

from datetime import date, time
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edi_schema.x12.ast import (
        LoopInstance,
        ParsedSegment,
        RawSegment,
    )


def get_element_value(segment: "ParsedSegment | RawSegment", index: int) -> str | None:
    """
    Get element value from a segment by 1-indexed position.

    Works with both ParsedSegment and RawSegment.
    """
    if hasattr(segment, "raw"):
        # ParsedSegment
        return segment.raw.get_element_value(index)
    else:
        # RawSegment
        return segment.get_element_value(index)


def get_composite_component(
    segment: "ParsedSegment | RawSegment", element_index: int, component_index: int
) -> str | None:
    """
    Get a component from a composite element.

    Args:
        segment: The segment containing the composite
        element_index: 1-indexed element position
        component_index: 1-indexed component position within the composite
    """
    if hasattr(segment, "raw"):
        elem = segment.raw.get_element(element_index)
    else:
        elem = segment.get_element(element_index)

    if elem is None:
        return None

    # Check if it's a composite
    if hasattr(elem, "components"):
        return elem.get_component(component_index)
    elif hasattr(elem, "value"):
        # Simple element, only component 1 makes sense
        return elem.value if component_index == 1 else None

    return None


def parse_x12_date(value: str | None) -> date | None:
    """
    Parse X12 date format to Python date.

    Handles formats:
    - CCYYMMDD (8 chars)
    - YYMMDD (6 chars)
    """
    if not value:
        return None

    try:
        if len(value) == 8:
            # CCYYMMDD
            return date(int(value[0:4]), int(value[4:6]), int(value[6:8]))
        elif len(value) == 6:
            # YYMMDD - assume 20xx for 00-50, 19xx for 51-99
            year = int(value[0:2])
            if year <= 50:
                year += 2000
            else:
                year += 1900
            return date(year, int(value[2:4]), int(value[4:6]))
    except (ValueError, IndexError):
        pass

    return None


def parse_x12_time(value: str | None) -> time | None:
    """
    Parse X12 time format to Python time.

    Handles formats:
    - HHMM (4 chars)
    - HHMMSS (6 chars)
    - HHMMSSD (7 chars)
    """
    if not value:
        return None

    try:
        hour = int(value[0:2])
        minute = int(value[2:4])
        second = 0
        microsecond = 0

        if len(value) >= 6:
            second = int(value[4:6])
        if len(value) >= 7:
            # Decisecond
            microsecond = int(value[6]) * 100000

        return time(hour, minute, second, microsecond)
    except (ValueError, IndexError):
        pass

    return None


def parse_x12_amount(value: str | None, implied_decimals: int = 2) -> Decimal | None:
    """
    Parse X12 amount which may have implied decimal places.

    X12 amounts are often in cents (implied 2 decimal places).

    Args:
        value: The amount string
        implied_decimals: Number of implied decimal places (default 2)

    Returns:
        Decimal amount or None if invalid
    """
    if not value:
        return None

    try:
        # Remove leading zeros but preserve the number
        amount = Decimal(value)
        if implied_decimals > 0:
            amount = amount / (10**implied_decimals)
        return amount
    except InvalidOperation:
        return None


def parse_decimal(value: str | None) -> Decimal | None:
    """Parse a decimal value."""
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def format_x12_date(d: date | None) -> str:
    """Format date as X12 CCYYMMDD."""
    if not d:
        return ""
    return d.strftime("%Y%m%d")


def format_x12_time(t: time | None) -> str:
    """Format time as X12 HHMM."""
    if not t:
        return ""
    return t.strftime("%H%M")


def format_x12_amount(amount: Decimal | None, implied_decimals: int = 2) -> str:
    """
    Format amount for X12 (convert to cents/implied decimals).

    Args:
        amount: The decimal amount
        implied_decimals: Number of implied decimal places

    Returns:
        String representation in implied decimal format
    """
    if amount is None:
        return ""

    if implied_decimals > 0:
        multiplied = amount * (10**implied_decimals)
        return str(int(multiplied))
    return str(amount)


def find_segment(
    content: list["ParsedSegment | LoopInstance"], tag: str
) -> "ParsedSegment | None":
    """
    Find the first segment with the given tag in content.

    Searches through top-level segments only, not inside loops.
    """
    from edi_schema.x12.ast import ParsedSegment

    for item in content:
        if isinstance(item, ParsedSegment) and item.tag == tag:
            return item
    return None


def find_all_segments(
    content: list["ParsedSegment | LoopInstance"], tag: str
) -> list["ParsedSegment"]:
    """
    Find all segments with the given tag in content.

    Searches through top-level segments only.
    """
    from edi_schema.x12.ast import ParsedSegment

    return [item for item in content if isinstance(item, ParsedSegment) and item.tag == tag]


def find_loop(
    content: list["ParsedSegment | LoopInstance"], loop_id: str
) -> "LoopInstance | None":
    """
    Find the first loop with the given ID in content.
    """
    from edi_schema.x12.ast import LoopInstance

    for item in content:
        if isinstance(item, LoopInstance) and item.loop_id == loop_id:
            return item
    return None


def find_all_loops(
    content: list["ParsedSegment | LoopInstance"], loop_id: str
) -> list["LoopInstance"]:
    """
    Find all loops with the given ID in content.
    """
    from edi_schema.x12.ast import LoopInstance

    return [item for item in content if isinstance(item, LoopInstance) and item.loop_id == loop_id]


def find_segment_in_loop(loop: "LoopInstance", tag: str) -> "ParsedSegment | None":
    """Find a segment within a loop."""
    for seg in loop.segments:
        if seg.tag == tag:
            return seg
    return None


def find_all_segments_in_loop(loop: "LoopInstance", tag: str) -> list["ParsedSegment"]:
    """Find all segments with given tag within a loop."""
    return [seg for seg in loop.segments if seg.tag == tag]


def find_child_loop(loop: "LoopInstance", loop_id: str) -> "LoopInstance | None":
    """Find a child loop within a parent loop."""
    for child in loop.children:
        if child.loop_id == loop_id:
            return child
    return None


def find_all_child_loops(loop: "LoopInstance", loop_id: str) -> list["LoopInstance"]:
    """Find all child loops with given ID."""
    return [child for child in loop.children if child.loop_id == loop_id]


# X12 N1 party code to semantic role mapping
N1_PARTY_CODE_MAP = {
    "BY": "buyer",
    "SE": "seller",
    "ST": "ship_to",
    "SF": "ship_from",
    "BT": "bill_to",
    "RI": "remit_to",
    "CA": "carrier",
    "VN": "vendor",
    "SU": "supplier",
    "II": "issuer",
    "PR": "payer",
    "PE": "payee",
}


# X12 product ID qualifier to semantic mapping
PRODUCT_ID_QUALIFIER_MAP = {
    "UP": ("standard", "UPC"),  # UPC
    "EN": ("standard", "EAN"),  # EAN
    "UK": ("standard", "UCC/EAN-128"),  # UCC/EAN-128
    "VP": ("sellers", None),  # Vendor Part Number
    "BP": ("buyers", None),  # Buyer Part Number
    "MG": ("manufacturers", None),  # Manufacturer Part Number
    "SK": ("sellers", None),  # SKU
    "IN": ("buyers", None),  # Buyer Item Number
    "MN": ("manufacturers", None),  # Model Number
    "SN": ("additional", "Serial"),  # Serial Number
}


# X12 N1*03 ID qualifier to scheme mapping
ID_QUALIFIER_MAP = {
    "1": "DUNS",
    "9": "DUNS+4",
    "12": "Phone",
    "91": "SellerAssigned",
    "92": "BuyerAssigned",
    "ZZ": "MutuallyDefined",
}


def map_n1_party_code(code: str) -> str:
    """Map X12 N1*01 party code to semantic role."""
    return N1_PARTY_CODE_MAP.get(code, code)


def map_product_id_qualifier(qualifier: str) -> tuple[str, str | None]:
    """
    Map X12 product ID qualifier to (field_type, scheme).

    field_type: 'standard', 'sellers', 'buyers', 'manufacturers', 'additional'
    scheme: The schemeID to use (e.g., 'UPC', 'EAN') or None
    """
    return PRODUCT_ID_QUALIFIER_MAP.get(qualifier, ("additional", None))


def map_id_qualifier(qualifier: str) -> str:
    """Map X12 N1*03 ID qualifier to scheme name."""
    return ID_QUALIFIER_MAP.get(qualifier, qualifier)
