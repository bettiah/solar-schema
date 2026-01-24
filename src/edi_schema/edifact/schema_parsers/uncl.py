"""
EDIFACT Code List Parser (UNCL).

Parses the UNCL (UN Code List) file which contains valid code values
for coded data elements. The file format is:

    *    1001  Document name code                                      [C]

         Desc: Code specifying the document name.

         Repr: an..3

         1     Certificate of analysis
                  Certificate providing the values of an analysis.

         2     Certificate of conformity
                  Certificate certifying the conformity to predefined
                  definitions.
"""

import re
from pathlib import Path
from typing import Iterator

from .base import (
    clean_text,
    is_section_separator,
    read_file_lines,
    strip_change_indicator,
)

# Pattern for element header line: tag followed by name
# Example: "*    1001  Document name code                [C]"
# Must have: change indicator (or space) + exactly 4 spaces + 4-digit tag + 2 spaces + name
# This distinguishes from text containing years like "1999 Kyoto Convention"
ELEMENT_HEADER_PATTERN = re.compile(r"^[*#|+X\s]\s{4}(\d{4})\s{2}(.+?)(?:\s+\[([BIC])\])?\s*$")

# Pattern for code value line
# Example: "     1     Certificate of analysis"
CODE_VALUE_PATTERN = re.compile(r"^\s+(\d+|[A-Z]{1,3}|[A-Z0-9]{2,4})\s{2,}(.+)$")


def parse_uncl(path: Path) -> dict[str, dict[str, str]]:
    """
    Parse a UNCL (code list) file.

    Args:
        path: Path to the UNCL file (e.g., UNCL.23A)

    Returns:
        Dictionary mapping element tags to code dictionaries.
        Each code dictionary maps code values to descriptions.

        Example:
            {
                '1001': {
                    '1': 'Certificate of analysis',
                    '2': 'Certificate of conformity',
                    ...
                },
                '1049': {...},
                ...
            }
    """
    lines = read_file_lines(path)
    result: dict[str, dict[str, str]] = {}

    current_element: str | None = None
    current_codes: dict[str, str] = {}
    current_code: str | None = None
    current_desc_parts: list[str] = []
    in_header = True  # Skip file header

    for line in lines:
        # Section separators mark element boundaries
        if is_section_separator(line):
            in_header = False
            # Save current element before starting next
            if current_element is not None:
                if current_code is not None and current_desc_parts:
                    current_codes[current_code] = clean_text(" ".join(current_desc_parts))
                if current_codes:
                    result[current_element] = current_codes
                # Reset for next element
                current_element = None
                current_codes = {}
                current_code = None
                current_desc_parts = []
            continue

        if in_header:
            continue

        # Normalize change indicators
        normalized = strip_change_indicator(line)

        # Check for element header
        header_match = ELEMENT_HEADER_PATTERN.match(normalized)
        if header_match:
            # Save previous element's codes
            if current_element is not None:
                # Save any pending code description
                if current_code is not None and current_desc_parts:
                    current_codes[current_code] = clean_text(" ".join(current_desc_parts))
                if current_codes:
                    result[current_element] = current_codes

            # Start new element
            current_element = header_match.group(1)
            current_codes = {}
            current_code = None
            current_desc_parts = []
            continue

        # Skip if we're not in an element
        if current_element is None:
            continue

        # Skip Desc: and Repr: lines
        stripped = normalized.strip()
        if stripped.startswith(("Desc:", "Repr:", "Note:")):
            continue

        # Check for code value line
        code_match = CODE_VALUE_PATTERN.match(normalized)
        if code_match:
            # Save previous code description
            if current_code is not None and current_desc_parts:
                current_codes[current_code] = clean_text(" ".join(current_desc_parts))

            # Start new code
            current_code = code_match.group(1)
            current_desc_parts = [code_match.group(2).strip()]
            continue

        # Check for description continuation
        if current_code is not None and stripped:
            # This is a continuation of the previous code's description
            # Must be indented (description lines are heavily indented)
            if normalized.startswith(" " * 14):
                current_desc_parts.append(stripped)

    # Save final element
    if current_element is not None:
        if current_code is not None and current_desc_parts:
            current_codes[current_code] = clean_text(" ".join(current_desc_parts))
        if current_codes:
            result[current_element] = current_codes

    return result


def iter_elements_with_codes(
    path: Path,
) -> Iterator[tuple[str, str, dict[str, str]]]:
    """
    Iterate over elements that have code values.

    Yields tuples of (element_tag, element_name, codes_dict).
    This is useful for building code lists while also capturing element names.

    Args:
        path: Path to the UNCL file

    Yields:
        Tuples of (tag, name, codes)
    """
    lines = read_file_lines(path)

    current_element: str | None = None
    current_name: str | None = None
    current_codes: dict[str, str] = {}
    current_code: str | None = None
    current_desc_parts: list[str] = []
    in_header = True

    for line in lines:
        if is_section_separator(line):
            in_header = False
            # Yield previous element if it has codes
            if current_element is not None and current_name is not None:
                if current_code is not None and current_desc_parts:
                    current_codes[current_code] = clean_text(" ".join(current_desc_parts))
                if current_codes:
                    yield (current_element, current_name, current_codes)
                # Reset for next element
                current_element = None
                current_name = None
                current_codes = {}
                current_code = None
                current_desc_parts = []
            continue

        if in_header:
            continue

        normalized = strip_change_indicator(line)
        header_match = ELEMENT_HEADER_PATTERN.match(normalized)

        if header_match:
            # Start new element
            current_element = header_match.group(1)
            current_name = header_match.group(2).strip()
            current_codes = {}
            current_code = None
            current_desc_parts = []
            continue

        if current_element is None:
            continue

        stripped = normalized.strip()
        if stripped.startswith(("Desc:", "Repr:", "Note:")):
            continue

        code_match = CODE_VALUE_PATTERN.match(normalized)
        if code_match:
            if current_code is not None and current_desc_parts:
                current_codes[current_code] = clean_text(" ".join(current_desc_parts))
            current_code = code_match.group(1)
            current_desc_parts = [code_match.group(2).strip()]
            continue

        if current_code is not None and stripped:
            if normalized.startswith(" " * 14):
                current_desc_parts.append(stripped)

    # Yield final element
    if current_element is not None and current_name is not None:
        if current_code is not None and current_desc_parts:
            current_codes[current_code] = clean_text(" ".join(current_desc_parts))
        if current_codes:
            yield (current_element, current_name, current_codes)
