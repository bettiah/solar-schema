"""
EDIFACT Data Element Parser (EDED).

Parses the EDED (Element Data Element Directory) file which contains
data element definitions. The file format is:

     1001  Document name code                                      [C]

     Desc: Code specifying the document name.

     Repr: an..3

----------------------------------------------------------------------

     1003  Message type code                                       [B]

     Desc: Code specifying a type of message.

     Repr: an..6
"""

import re
from pathlib import Path

from ..models import DataElement
from .base import (
    clean_text,
    is_section_separator,
    parse_repr,
    read_file_lines,
    strip_change_indicator,
)

# Pattern for element header line
# Example: "     1001  Document name code                [C]"
ELEMENT_HEADER_PATTERN = re.compile(r"^[*#|+X\-\s]\s+(\d{4})\s+(.+?)(?:\s+\[([BIC])\])?\s*$")

# Pattern for Desc: line
DESC_PATTERN = re.compile(r"^\s+Desc:\s*(.*)$")

# Pattern for Repr: line
REPR_PATTERN = re.compile(r"^\s+Repr:\s*(an?|n)(\.\.)?(\.)?(\d+)\s*$")


def parse_eded(
    path: Path,
    code_lists: dict[str, dict[str, str]] | None = None,
) -> dict[str, DataElement]:
    """
    Parse an EDED (data element directory) file.

    Args:
        path: Path to the EDED file (e.g., EDED.23A)
        code_lists: Optional dictionary of code lists from UNCL parser.
                   If provided, codes will be attached to relevant elements.

    Returns:
        Dictionary mapping element tags to DataElement objects.

        Example:
            {
                '1001': DataElement(
                    tag='1001',
                    name='Document name code',
                    description='Code specifying the document name.',
                    data_type='an',
                    max_length=3,
                    codes={'1': 'Certificate...', '2': '...'},
                    usage='C'
                ),
                ...
            }
    """
    lines = read_file_lines(path)
    result: dict[str, DataElement] = {}

    current_tag: str | None = None
    current_name: str | None = None
    current_usage: str | None = None
    current_desc_parts: list[str] = []
    current_repr: str | None = None
    in_header = True
    in_description = False

    i = 0
    while i < len(lines):
        line = lines[i]

        # Skip section separators
        if is_section_separator(line):
            in_header = False
            # Save previous element if complete
            if current_tag is not None and current_repr is not None:
                _save_element(
                    result,
                    current_tag,
                    current_name or "",
                    current_desc_parts,
                    current_repr,
                    current_usage,
                    code_lists,
                )
            # Reset for next element
            current_tag = None
            current_name = None
            current_usage = None
            current_desc_parts = []
            current_repr = None
            in_description = False
            i += 1
            continue

        if in_header:
            i += 1
            continue

        # Normalize change indicators
        normalized = strip_change_indicator(line)

        # Check for element header
        header_match = ELEMENT_HEADER_PATTERN.match(normalized)
        if header_match:
            # Save previous element if complete
            if current_tag is not None and current_repr is not None:
                _save_element(
                    result,
                    current_tag,
                    current_name or "",
                    current_desc_parts,
                    current_repr,
                    current_usage,
                    code_lists,
                )

            # Start new element
            current_tag = header_match.group(1)
            current_name = header_match.group(2).strip()
            current_usage = header_match.group(3)
            current_desc_parts = []
            current_repr = None
            in_description = False
            i += 1
            continue

        # Check for Desc: line
        desc_match = DESC_PATTERN.match(normalized)
        if desc_match:
            in_description = True
            desc_text = desc_match.group(1).strip()
            if desc_text:
                current_desc_parts.append(desc_text)
            i += 1
            continue

        # Check for Repr: line
        repr_match = REPR_PATTERN.match(normalized)
        if repr_match:
            in_description = False
            # Reconstruct the repr string
            data_type = repr_match.group(1)
            is_variable = repr_match.group(2) == ".."
            length = repr_match.group(4)
            if is_variable:
                current_repr = f"{data_type}..{length}"
            else:
                current_repr = f"{data_type}{length}"
            i += 1
            continue

        # Check for Note: line (skip it and end description)
        stripped = normalized.strip()
        if stripped.startswith("Note:"):
            in_description = False
            i += 1
            continue

        # Description continuation
        if in_description and stripped:
            current_desc_parts.append(stripped)

        i += 1

    # Save final element
    if current_tag is not None and current_repr is not None:
        _save_element(
            result,
            current_tag,
            current_name or "",
            current_desc_parts,
            current_repr,
            current_usage,
            code_lists,
        )

    return result


def _save_element(
    result: dict[str, DataElement],
    tag: str,
    name: str,
    desc_parts: list[str],
    repr_str: str,
    usage: str | None,
    code_lists: dict[str, dict[str, str]] | None,
) -> None:
    """
    Create and save a DataElement to the result dictionary.
    """
    try:
        repr_info = parse_repr(repr_str)
    except ValueError:
        # Skip elements with invalid repr
        return

    description = clean_text(" ".join(desc_parts)) if desc_parts else ""

    # Get codes if available
    codes = None
    if code_lists and tag in code_lists:
        codes = code_lists[tag]

    element = DataElement(
        tag=tag,
        name=name,
        description=description,
        data_type=repr_info.data_type,
        min_length=repr_info.min_length,
        max_length=repr_info.max_length,
        codes=codes,
        usage=usage,  # type: ignore
    )
    result[tag] = element
