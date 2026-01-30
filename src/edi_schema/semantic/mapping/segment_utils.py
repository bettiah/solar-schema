"""
Utility functions for working with parsed EDI segments.

These functions extract element values from ParsedSegment/RawSegment objects
and find loops within transaction content.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from edi_schema.x12.ast import LoopInstance, ParsedSegment


def find_all_loops(
    content: list["ParsedSegment | LoopInstance"],
    loop_id: str,
) -> list["LoopInstance"]:
    """
    Find all loops with the given ID, including implicit loops.

    Handles both proper LoopInstance objects and "implicit loops"
    where consecutive segments form a logical loop.
    """
    from edi_schema.x12.ast import LoopInstance, ParsedSegment, RawSegment

    # Known child segments for common loop types
    LOOP_CHILD_SEGMENTS = {
        "N1": {"N1", "N2", "N3", "N4", "PER", "REF"},
        "PO1": {"PO1", "PID", "SAC", "DTM", "MEA", "CTP", "PAM", "PO3", "PO4", "REF", "MSG"},
        "IT1": {"IT1", "PID", "SAC", "DTM", "MEA", "CTP", "REF", "SLN"},
        "ITD": {"ITD"},
    }

    results: list["LoopInstance"] = []
    child_segments = LOOP_CHILD_SEGMENTS.get(loop_id, {loop_id})

    i = 0
    while i < len(content):
        item = content[i]

        if isinstance(item, LoopInstance) and item.loop_id == loop_id:
            results.append(item)
            i += 1
        elif isinstance(item, (ParsedSegment, RawSegment)) and item.tag == loop_id:
            # Found a standalone segment that should start a loop
            # Collect consecutive segments that belong to this implicit loop
            segments = [item]
            j = i + 1
            while j < len(content):
                next_item = content[j]
                if isinstance(next_item, (ParsedSegment, RawSegment)) and next_item.tag in child_segments:
                    if next_item.tag == loop_id:
                        # New loop trigger - stop here
                        break
                    segments.append(next_item)
                    j += 1
                elif isinstance(next_item, LoopInstance):
                    break
                else:
                    break

            # Create synthetic LoopInstance
            implicit_loop = LoopInstance(
                loop_id=loop_id,
                segments=segments,
                children=[],
            )
            results.append(implicit_loop)
            i = j
        else:
            i += 1

    return results


def get_element_value(segment: "ParsedSegment", index: int) -> str | None:
    """Get element value from segment by 1-indexed position.

    Returns None for both missing elements AND empty strings.
    """
    value = None
    # RawSegment has get_element_value directly
    if hasattr(segment, "get_element_value"):
        value = segment.get_element_value(index)
    # ParsedSegment may have raw attribute
    elif hasattr(segment, "raw") and hasattr(segment.raw, "get_element_value"):
        value = segment.raw.get_element_value(index)

    # Treat empty strings as None (no value)
    if value is not None and value.strip() == "":
        return None
    return value


def get_composite_component(
    segment: "ParsedSegment",
    element_index: int,
    component_index: int,
) -> str | None:
    """Get component from composite element."""
    # RawSegment has get_element directly
    if hasattr(segment, "get_element"):
        elem = segment.get_element(element_index)
    elif hasattr(segment, "raw") and hasattr(segment.raw, "get_element"):
        elem = segment.raw.get_element(element_index)
    else:
        return None

    if elem is None:
        return None
    if hasattr(elem, "components"):
        return elem.get_component(component_index)
    elif hasattr(elem, "value"):
        return elem.value if component_index == 1 else None
    return None
