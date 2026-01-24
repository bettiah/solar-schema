"""
EDIFACT Segment Parser (EDSD).

Parses the EDSD (Element Segment Data) file which contains segment
definitions. Each segment has a tag, name, function, and list of elements.

File format:
       NAD  NAME AND ADDRESS

       Function: To specify the name and address of a party.

010    C082 PARTY IDENTIFICATION DETAILS      C    1
       3039  Party identifier                 M      an..35
       1131  Code list identification code    C      an..17
       3055  Code list responsible agency code C     an..3

020    C058 NAME AND ADDRESS                  C    1
       3124  Name and address description     M      an..35
       ...

030    3164 CITY NAME                         C    1 an..35

----------------------------------------------------------------------
"""

import re
from pathlib import Path

from ..models import Segment, SegmentElement
from .base import (
    clean_text,
    is_section_separator,
    parse_mandatory_indicator,
    read_file_lines,
    strip_change_indicator,
)

# Pattern for segment header line
# Example: "       NAD  NAME AND ADDRESS"
# Also handles: "       ADR  ADDRESS" and "*      UNH  MESSAGE HEADER"
SEGMENT_HEADER_PATTERN = re.compile(r"^[*#|+X\s]\s{5,6}([A-Z]{2,3})\s{1,2}(.+)$")

# Pattern for Function: line
FUNCTION_PATTERN = re.compile(r"^\s+Function:\s*(.*)$")

# Pattern for element line - composite or standalone
# D23A format includes max_repeat, D96A does not:
# D23A Composite: "010    C082 PARTY IDENTIFICATION DETAILS      C    1"
# D96A Composite: "010   C817  ADDRESS USAGE                                  C  "
# D23A Standalone: "030    3164 CITY NAME                         C    1 an..35"
# D96A Standalone: "030   3164  CITY NAME                                      C  an..35"
ELEMENT_COMPOSITE_PATTERN = re.compile(r"^(\d{3})\s+(C\d{3})\s+(.+?)\s+([MC])(?:\s+(\d+))?\s*$")

ELEMENT_STANDALONE_PATTERN = re.compile(
    r"^(\d{3})\s+(\d{4})\s+(.+?)\s+([MC])\s+(?:(\d+)\s+)?(an?|n)(\.\.)?\d+\s*$"
)

# Pattern for component sub-line (indented under composite)
# Example: "       3039  Party identifier                 M      an..35"
COMPONENT_SUBLINE_PATTERN = re.compile(r"^\s{7}(\d{4})\s+(.+?)\s+([MC])\s+(an?|n)(\.\.)?\d+\s*$")

# Pattern for Note: line
NOTE_PATTERN = re.compile(r"^\s+Note:\s*")


def parse_edsd(path: Path) -> dict[str, Segment]:
    """
    Parse an EDSD (segment directory) file.

    Args:
        path: Path to the EDSD file (e.g., EDSD.23A)

    Returns:
        Dictionary mapping segment tags to Segment objects.

        Example:
            {
                'NAD': Segment(
                    tag='NAD',
                    name='NAME AND ADDRESS',
                    function='To specify the name and address of a party.',
                    elements=[
                        SegmentElement(position=10, tag='C082', name='PARTY...', ...),
                        SegmentElement(position=20, tag='C058', name='NAME...', ...),
                        SegmentElement(position=30, tag='3164', name='CITY NAME', ...),
                        ...
                    ]
                ),
                ...
            }
    """
    lines = read_file_lines(path)
    result: dict[str, Segment] = {}

    current_tag: str | None = None
    current_name: str | None = None
    current_function_parts: list[str] = []
    current_elements: list[SegmentElement] = []
    in_header = True
    in_function = False
    in_note = False

    for line in lines:
        # Skip section separators and save previous segment
        if is_section_separator(line):
            in_header = False
            # Save previous segment
            if current_tag is not None:
                _save_segment(
                    result,
                    current_tag,
                    current_name or "",
                    current_function_parts,
                    current_elements,
                )
            # Reset for next segment
            current_tag = None
            current_name = None
            current_function_parts = []
            current_elements = []
            in_function = False
            in_note = False
            continue

        if in_header:
            continue

        # Normalize change indicators
        normalized = strip_change_indicator(line)

        # Check for segment header
        header_match = SEGMENT_HEADER_PATTERN.match(normalized)
        if header_match:
            current_tag = header_match.group(1)
            current_name = header_match.group(2).strip()
            in_function = False
            in_note = False
            continue

        # Check for Function: line
        func_match = FUNCTION_PATTERN.match(normalized)
        if func_match:
            in_function = True
            in_note = False
            func_text = func_match.group(1).strip()
            if func_text:
                current_function_parts.append(func_text)
            continue

        # Check for Note: line
        if NOTE_PATTERN.match(normalized):
            in_function = False
            in_note = True
            continue

        # Check for composite element line
        composite_match = ELEMENT_COMPOSITE_PATTERN.match(normalized)
        if composite_match:
            in_function = False
            in_note = False
            position = int(composite_match.group(1))
            tag = composite_match.group(2)
            name = composite_match.group(3).strip()
            mandatory = parse_mandatory_indicator(composite_match.group(4))
            # max_repeat is optional (D96A doesn't have it), default to 1
            max_repeat_str = composite_match.group(5)
            max_repeat = int(max_repeat_str) if max_repeat_str else 1

            current_elements.append(
                SegmentElement(
                    position=position,
                    tag=tag,
                    name=name,
                    mandatory=mandatory,
                    max_repeat=max_repeat,
                    is_composite=True,
                )
            )
            continue

        # Check for standalone element line
        standalone_match = ELEMENT_STANDALONE_PATTERN.match(normalized)
        if standalone_match:
            in_function = False
            in_note = False
            position = int(standalone_match.group(1))
            tag = standalone_match.group(2)
            name = standalone_match.group(3).strip()
            mandatory = parse_mandatory_indicator(standalone_match.group(4))
            # max_repeat is optional (D96A doesn't have it), default to 1
            max_repeat_str = standalone_match.group(5)
            max_repeat = int(max_repeat_str) if max_repeat_str else 1

            current_elements.append(
                SegmentElement(
                    position=position,
                    tag=tag,
                    name=name,
                    mandatory=mandatory,
                    max_repeat=max_repeat,
                    is_composite=False,
                )
            )
            continue

        # Check for component sub-line (just skip these, they're part of composite)
        if COMPONENT_SUBLINE_PATTERN.match(normalized):
            continue

        # Function continuation
        stripped = normalized.strip()
        if in_function and stripped:
            current_function_parts.append(stripped)

    # Save final segment
    if current_tag is not None:
        _save_segment(
            result,
            current_tag,
            current_name or "",
            current_function_parts,
            current_elements,
        )

    return result


def _save_segment(
    result: dict[str, Segment],
    tag: str,
    name: str,
    function_parts: list[str],
    elements: list[SegmentElement],
) -> None:
    """Create and save a Segment to the result dictionary."""
    function = clean_text(" ".join(function_parts)) if function_parts else ""
    segment = Segment(
        tag=tag,
        name=name,
        function=function,
        elements=sorted(elements, key=lambda e: e.position),
    )
    result[tag] = segment
