"""
EDIFACT Mapping Utilities.

Helper functions for extracting and converting EDIFACT data to semantic models.
"""

from datetime import date, time
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edi_schema.edifact.ast import (
        ParsedSegment,
        SegmentGroupInstance,
    )


def get_element_value(segment: "ParsedSegment", index: int) -> str | None:
    """
    Get element value from a segment by 1-indexed position.

    Works with both RawSegment and ParsedSegment.
    """
    elem = segment.get_element(index)
    if elem is None:
        return None
    return elem.value if hasattr(elem, "value") else None


def get_component_value(
    segment: "ParsedSegment", element_index: int, component_index: int
) -> str | None:
    """
    Get a component from a composite element.

    Args:
        segment: The segment containing the composite
        element_index: 1-indexed element position
        component_index: 1-indexed component position within the composite

    Returns:
        Component value or None
    """
    elem = segment.get_element(element_index)
    if elem is None:
        return None

    if hasattr(elem, "is_composite") and elem.is_composite:
        comp = elem.get_component(component_index)
        return comp.value if comp else None
    elif hasattr(elem, "value"):
        # Simple element, only component 1 makes sense
        return elem.value if component_index == 1 else None

    return None


def parse_edifact_date(value: str | None) -> date | None:
    """
    Parse EDIFACT date format to Python date.

    Handles formats:
    - CCYYMMDD (8 chars) - Format 102
    - YYMMDD (6 chars) - Format 101
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


def parse_edifact_time(value: str | None) -> time | None:
    """
    Parse EDIFACT time format to Python time.

    Handles formats:
    - HHMM (4 chars) - Format 401
    - HHMMSS (6 chars) - Format 402
    """
    if not value:
        return None

    try:
        hour = int(value[0:2])
        minute = int(value[2:4])
        second = 0

        if len(value) >= 6:
            second = int(value[4:6])

        return time(hour, minute, second)
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


def format_edifact_date(d: date | None) -> str:
    """Format date as EDIFACT CCYYMMDD (format 102)."""
    if not d:
        return ""
    return d.strftime("%Y%m%d")


def format_edifact_time(t: time | None) -> str:
    """Format time as EDIFACT HHMM (format 401)."""
    if not t:
        return ""
    return t.strftime("%H%M")


def find_segment(
    content: "list[ParsedSegment | SegmentGroupInstance]", tag: str
) -> "ParsedSegment | None":
    """
    Find the first segment with the given tag in content.

    Searches through top-level segments only, not inside groups.
    """
    from edi_schema.edifact.ast import ParsedSegment

    for item in content:
        if isinstance(item, ParsedSegment) and item.tag == tag:
            return item
    return None


def find_all_segments(
    content: "list[ParsedSegment | SegmentGroupInstance]", tag: str
) -> "list[ParsedSegment]":
    """
    Find all segments with the given tag in content.

    Searches through top-level segments only.
    """
    from edi_schema.edifact.ast import ParsedSegment

    return [item for item in content if isinstance(item, ParsedSegment) and item.tag == tag]


def find_segment_group(
    content: "list[ParsedSegment | SegmentGroupInstance]", group_number: int
) -> "SegmentGroupInstance | None":
    """
    Find the first segment group with the given group number.
    """
    from edi_schema.edifact.ast import SegmentGroupInstance

    for item in content:
        if isinstance(item, SegmentGroupInstance) and item.group_number == group_number:
            return item
    return None


def find_all_segment_groups(
    content: "list[ParsedSegment | SegmentGroupInstance]", group_number: int
) -> "list[SegmentGroupInstance]":
    """
    Find all segment groups with the given group number.
    """
    from edi_schema.edifact.ast import SegmentGroupInstance

    return [
        item
        for item in content
        if isinstance(item, SegmentGroupInstance) and item.group_number == group_number
    ]


def find_segment_in_group(group: "SegmentGroupInstance", tag: str) -> "ParsedSegment | None":
    """Find a segment within a group."""
    for seg in group.segments:
        if seg.tag == tag:
            return seg
    return None


def find_all_segments_in_group(group: "SegmentGroupInstance", tag: str) -> "list[ParsedSegment]":
    """Find all segments with given tag within a group."""
    return [seg for seg in group.segments if seg.tag == tag]


def find_child_group(
    group: "SegmentGroupInstance", group_number: int
) -> "SegmentGroupInstance | None":
    """Find a child group within a parent group."""
    for child in group.children:
        if child.group_number == group_number:
            return child
    return None


def find_all_child_groups(
    group: "SegmentGroupInstance", group_number: int
) -> "list[SegmentGroupInstance]":
    """Find all child groups with given group number."""
    return [child for child in group.children if child.group_number == group_number]


# EDIFACT party qualifier to semantic role mapping
NAD_PARTY_QUALIFIER_MAP = {
    "BY": "buyer",
    "SU": "supplier",
    "SE": "seller",
    "DP": "delivery_party",
    "UC": "consignee",
    "SF": "ship_from",
    "ST": "ship_to",
    "IV": "invoicee",
    "PE": "payee",
    "PR": "payer",
    "CA": "carrier",
}


# EDIFACT product ID qualifier to semantic mapping
PRODUCT_ID_QUALIFIER_MAP = {
    "SRV": ("standard", "EAN"),
    "EN": ("standard", "EAN"),
    "UP": ("standard", "UPC"),
    "BP": ("buyers", None),
    "VP": ("sellers", None),
    "MF": ("manufacturers", None),
    "SA": ("sellers", None),
}


# EDIFACT reference qualifier mapping
REFERENCE_QUALIFIER_MAP = {
    "ON": "purchase_order",
    "VN": "vendor_order",
    "IV": "invoice",
    "AAK": "despatch_advice",
    "AAM": "receipt_advice",
    "CT": "contract",
    "DQ": "delivery_note",
}


def map_nad_party_qualifier(qualifier: str) -> str:
    """Map EDIFACT NAD party qualifier to semantic role."""
    return NAD_PARTY_QUALIFIER_MAP.get(qualifier, qualifier)


def map_product_id_qualifier(qualifier: str) -> tuple[str, str | None]:
    """
    Map EDIFACT product ID qualifier to (field_type, scheme).

    field_type: 'standard', 'sellers', 'buyers', 'manufacturers', 'additional'
    scheme: The schemeID to use (e.g., 'EAN') or None
    """
    return PRODUCT_ID_QUALIFIER_MAP.get(qualifier, ("additional", None))


def map_reference_qualifier(qualifier: str) -> str:
    """Map EDIFACT reference qualifier to semantic type."""
    return REFERENCE_QUALIFIER_MAP.get(qualifier, qualifier)


def get_dtm_date(
    content: "list[ParsedSegment | SegmentGroupInstance]", qualifier: str
) -> date | None:
    """
    Find DTM segment with specified qualifier and return parsed date.

    DTM structure: DTM+qualifier:date:format'
    Common qualifiers:
    - 137: Document date
    - 171: Reference date
    - 35: Delivery date requested
    - 17: Delivery date estimated
    """
    for seg in find_all_segments(content, "DTM"):
        qual = get_component_value(seg, 1, 1)
        if qual == qualifier:
            date_val = get_component_value(seg, 1, 2)
            return parse_edifact_date(date_val)
    return None
