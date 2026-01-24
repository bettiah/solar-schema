"""
Base parsing utilities for EDIFACT schema files.

Provides common functionality used across all EDIFACT parsers including:
- Representation (Repr) field parsing
- Section detection
- Line parsing utilities
"""

import re
from pathlib import Path
from typing import Literal, NamedTuple


class ReprInfo(NamedTuple):
    """
    Parsed representation field information.

    The Repr field in EDIFACT specs defines the data type and length constraints.
    Format examples: 'an..35', 'n3', 'a..17'

    Attributes:
        data_type: 'a' (alphabetic), 'n' (numeric), or 'an' (alphanumeric)
        min_length: Minimum length (0 for variable, same as max for fixed)
        max_length: Maximum length
    """

    data_type: Literal["a", "n", "an"]
    min_length: int
    max_length: int


# Regex pattern for parsing Repr field
# Examples: an..35, n3, a..17, an3
REPR_PATTERN = re.compile(r"^(an?|n)(\.\.)?(\d+)$")


def parse_repr(repr_str: str) -> ReprInfo:
    """
    Parse an EDIFACT representation string.

    Args:
        repr_str: Representation string like 'an..35', 'n3', 'a..17'

    Returns:
        ReprInfo with data_type, min_length, max_length

    Raises:
        ValueError: If the representation format is invalid

    Examples:
        >>> parse_repr('an..35')
        ReprInfo(data_type='an', min_length=0, max_length=35)
        >>> parse_repr('n3')
        ReprInfo(data_type='n', min_length=3, max_length=3)
        >>> parse_repr('a..17')
        ReprInfo(data_type='a', min_length=0, max_length=17)
    """
    repr_str = repr_str.strip()
    match = REPR_PATTERN.match(repr_str)

    if not match:
        raise ValueError(f"Invalid representation format: '{repr_str}'")

    data_type = match.group(1)
    is_variable = match.group(2) == ".."
    length = int(match.group(3))

    if is_variable:
        return ReprInfo(data_type=data_type, min_length=0, max_length=length)  # type: ignore
    else:
        return ReprInfo(data_type=data_type, min_length=length, max_length=length)  # type: ignore


def is_section_separator(line: str) -> bool:
    """
    Check if a line is a section separator.

    Handles different EDIFACT directory formats:
    - D23A style: dashes "----------------------------------------------------------------------"
    - D96A style: box drawing "ÄÄÄÄÄÄÄÄÄ..." (0xC4 in CP437/Latin-1, read as UTF-8)

    Args:
        line: Line of text to check

    Returns:
        True if the line is a separator
    """
    stripped = line.strip()
    if len(stripped) < 50:
        return False

    # Check for ASCII dash separator (D23A style)
    if stripped.startswith("-" * 10):
        return True

    # Check for box drawing separator (D96A style)
    # 0xC4 byte in CP437/Latin-1 becomes various chars in UTF-8 with errors='replace'
    # Most common: 'Ä' (U+00C4) or replacement character
    first_char = stripped[0] if stripped else ""
    if first_char in ("Ä", "─", "\ufffd", "═"):
        # Check if line is mostly this character
        return all(c == first_char for c in stripped)

    return False


def is_change_indicator(line: str) -> bool:
    """
    Check if a line starts with a change indicator.

    Change indicators are: +, *, #, |, -, X
    These appear at the start of lines to indicate modifications.

    Args:
        line: Line of text to check

    Returns:
        True if line starts with a change indicator
    """
    if not line or len(line) < 1:
        return False
    first_char = line[0]
    return first_char in ("+", "*", "#", "|", "-", "X")


def strip_change_indicator(line: str) -> str:
    """
    Remove change indicator from start of line if present.

    Args:
        line: Line that may have a change indicator

    Returns:
        Line with change indicator replaced by space
    """
    if is_change_indicator(line):
        return " " + line[1:]
    return line


def parse_usage_indicator(text: str) -> Literal["B", "I", "C"] | None:
    """
    Extract usage indicator from text.

    Usage indicators appear in brackets: [B], [I], [C]
    - B = batch messages only
    - I = interactive messages only
    - C = common usage in both

    Args:
        text: Text that may contain a usage indicator

    Returns:
        Usage indicator letter or None if not found
    """
    match = re.search(r"\[([BIC])\]", text)
    if match:
        return match.group(1)  # type: ignore
    return None


def parse_mandatory_indicator(char: str) -> bool:
    """
    Parse mandatory/conditional indicator.

    Args:
        char: Single character 'M' or 'C'

    Returns:
        True if mandatory ('M'), False if conditional ('C')
    """
    return char.upper() == "M"


def read_file_lines(path: Path) -> list[str]:
    """
    Read all lines from a file.

    Args:
        path: Path to the file

    Returns:
        List of lines with trailing newlines stripped

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return [line.rstrip("\n\r") for line in f]


def clean_text(text: str) -> str:
    """
    Clean up text by normalizing whitespace.

    Args:
        text: Input text

    Returns:
        Text with multiple spaces collapsed and trimmed
    """
    return " ".join(text.split())


def extract_description(lines: list[str], start_idx: int) -> tuple[str, int]:
    """
    Extract a multi-line description starting from 'Desc:'.

    Descriptions can span multiple lines with indentation.

    Args:
        lines: List of all lines
        start_idx: Index of the 'Desc:' line

    Returns:
        Tuple of (description text, next line index after description)
    """
    desc_parts = []
    i = start_idx

    # First line has 'Desc:' prefix
    first_line = lines[i]
    desc_match = re.search(r"Desc:\s*(.*)", first_line)
    if desc_match:
        desc_parts.append(desc_match.group(1).strip())

    i += 1

    # Continue while lines are indented (part of description)
    while i < len(lines):
        line = lines[i]
        # Check if this is a continuation of description
        # Descriptions are indented and don't start new fields
        if line.startswith("     ") and not line.strip().startswith(("Repr:", "Note:")):
            # Check if it looks like continuation text
            stripped = line.strip()
            if stripped and not re.match(r"^\d{3,4}\s+\d{4}", stripped):
                # Not a component/element line
                if not re.match(r"^[A-Z]{1,4}\d{0,4}\s+[A-Z]", stripped):
                    desc_parts.append(stripped)
                    i += 1
                    continue
        break

    return clean_text(" ".join(desc_parts)), i


class ParseError(Exception):
    """
    Exception raised when parsing fails.

    Attributes:
        message: Error description
        line_number: Line number where error occurred (if known)
        line_content: Content of the problematic line (if available)
    """

    def __init__(
        self,
        message: str,
        line_number: int | None = None,
        line_content: str | None = None,
    ):
        self.message = message
        self.line_number = line_number
        self.line_content = line_content
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        parts = [self.message]
        if self.line_number is not None:
            parts.append(f"at line {self.line_number}")
        if self.line_content is not None:
            parts.append(f": {self.line_content!r}")
        return " ".join(parts)
