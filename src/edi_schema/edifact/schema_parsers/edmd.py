"""
EDIFACT Message Parser (EDMD).

Parses the EDMD (Element Message Data) files which contain message
definitions including the segment table with nested segment groups.

File format (segment table section):
4.3.1  Segment table

Pos     Tag Name                                     S   R

            HEADER SECTION

00010   UNH Message header                           M   1
00020   BGM Beginning of message                     M   1

00120       ---- Segment group 1  ------------------ C   99999------------+
00130   RFF Reference                                M   1                |
00140   DTM Date/time/period                         C   5----------------+

00220       ---- Segment group 2  ------------------ C   99---------------+
00230   NAD Name and address                         M   1                |
00240   LOC Place/location identification            C   25               |
                                                                          |
00270       ---- Segment group 3  ------------------ C   9999------------+|
00280   RFF Reference                                M   1               ||
00290   DTM Date/time/period                         C   5---------------++

The trailing markers indicate nesting:
- `+` opens a new group
- `|` continues at current level
- `-+` closes one, opens another at same parent level
- `++` closes two levels (current and parent)
"""

import re
from pathlib import Path

from ..models import MessageSpec, SegmentGroup, SegmentRef
from .base import (
    parse_mandatory_indicator,
    read_file_lines,
    strip_change_indicator,
)

# Pattern for message metadata from header
# Example: "                                           Message Type : INVOIC"
MESSAGE_TYPE_PATTERN = re.compile(r"Message Type\s*:\s*(\w+)")
VERSION_PATTERN = re.compile(r"Version\s*:\s*(\w+)")
RELEASE_PATTERN = re.compile(r"Release\s*:\s*(\w+)")

# Pattern for segment table header
SEGMENT_TABLE_PATTERN = re.compile(r"^4\.3\.1\s+Segment table")

# Pattern for section headers (HEADER SECTION, DETAIL SECTION, etc.)
SECTION_HEADER_PATTERN = re.compile(r"^\s+(HEADER|DETAIL|SUMMARY)\s+SECTION\s*$")

# Pattern for segment group header - D23A style
# Example: "00120       ---- Segment group 1  ------------------ C   99999------------+"
# Note: Some D96A files use box-drawing characters (─, Ä, or replacement char) instead of dashes
SEGMENT_GROUP_PATTERN_D23A = re.compile(
    r"^(\d{4,5})\s*[*]?\s+[-─Ä\uFFFD]{3,}\s*Segment group (\d+)\s+[-─Ä\uFFFD]+\s+([MC])\s+(\d+)"
)

# Pattern for segment group header - D96A style
# Example: "0080   Segment group 1:  RFF-DTM"
SEGMENT_GROUP_PATTERN_D96A = re.compile(r"^(\d{4,5})\s+Segment group (\d+):\s+(.+)$")

# Pattern for segment line - D23A style
# Example: "00010   UNH Message header                           M   1"
# Example: "0010   UNH Message header                            M   1"
# Example: "00130   RFF Reference                                M   1                |"
SEGMENT_LINE_PATTERN_D23A = re.compile(r"^(\d{4,5})\s{2,3}([A-Z]{2,3})\s+(.+?)\s{2,}([MC])\s+(\d+)")

# Pattern for segment line - D96A style
# Example: "0010 | UNH, Message header"
# Example: "0020   BGM, Beginning of message"
# Example: "0090      RFF, Reference"
SEGMENT_LINE_PATTERN_D96A = re.compile(r"^(\d{4,5})\s*([|]?)\s*([A-Z]{2,3}),\s*(.+)$")

# Pattern for Pos Tag Name header (marks start of segment table) - D23A style
POS_TAG_NAME_PATTERN = re.compile(r"^Pos\s+Tag\s+Name")

# Pattern for segment table start in D96A (4.1.1 Header section, etc.)
SECTION_START_D96A = re.compile(r"^4\.1\.\d\s+(Header|Detail|Summary)\s+section", re.IGNORECASE)


def parse_edmd(path: Path) -> MessageSpec:
    """
    Parse an EDMD (message definition) file.

    Args:
        path: Path to the message file (e.g., INVOIC_D.23A)

    Returns:
        MessageSpec containing the message structure.

        Example:
            MessageSpec(
                code='INVOIC',
                version='D',
                release='23A',
                name='Invoice message',
                structure=[
                    SegmentRef(position=10, segment_tag='UNH', ...),
                    SegmentRef(position=20, segment_tag='BGM', ...),
                    SegmentGroup(number=1, children=[
                        SegmentRef(position=130, segment_tag='RFF', ...),
                        SegmentRef(position=140, segment_tag='DTM', ...),
                    ]),
                    ...
                ]
            )
    """
    lines = read_file_lines(path)

    # Extract message metadata
    code = _extract_pattern(lines, MESSAGE_TYPE_PATTERN)
    version = _extract_pattern(lines, VERSION_PATTERN)
    release = _extract_pattern(lines, RELEASE_PATTERN)
    name = _extract_message_name(lines)
    definition = _extract_definition(lines)

    # Extract segment/group definitions from section 4.1
    clarifications = _parse_segment_clarifications(lines)

    # Find segment table section
    table_start, format_type = _find_segment_table_start(lines)
    if table_start is None:
        return MessageSpec(
            code=code or "",
            version=version or "",
            release=release or "",
            name=name or "",
            definition=definition,
            structure=[],
        )

    # Parse segment table based on format
    if format_type == "d96a":
        structure = _parse_segment_table_d96a(lines[table_start:], clarifications)
    else:
        structure = _parse_segment_table(lines[table_start:], clarifications)

    return MessageSpec(
        code=code or "",
        version=version or "",
        release=release or "",
        name=name or "",
        definition=definition,
        structure=structure,
    )


def _extract_pattern(lines: list[str], pattern: re.Pattern) -> str | None:
    """Extract a value matching a pattern from the lines."""
    for line in lines[:100]:  # Only check first 100 lines for metadata
        match = pattern.search(line)
        if match:
            return match.group(1)
    return None


def _extract_message_name(lines: list[str]) -> str | None:
    """
    Extract the message name from below the CONTENTS section.

    The message name appears right after the CONTENTS header:
                                  CONTENTS

                              Invoice message
    """
    # Find the CONTENTS line
    for i, line in enumerate(lines[:100]):
        if line.strip() == "CONTENTS":
            # Look at the next non-empty line
            for j in range(i + 1, min(i + 5, len(lines))):
                stripped = lines[j].strip()
                if stripped:
                    return stripped
            break
    return None


def _extract_definition(lines: list[str]) -> str:
    """
    Extract the functional definition from section 1.1.

    The definition appears after "1.1    Functional definition" and
    continues until the next section (1.2, 2., etc.).

    Example:
        1.1    Functional definition

               A message specifying details for goods or services ordered under
               conditions agreed between the seller and the buyer.

        1.2    Field of application
    """
    # Find "1.1" followed by "Functional definition" (case-insensitive)
    # Skip CONTENTS entries which are indented (start with spaces)
    start_idx = None
    for i, line in enumerate(lines[:200]):
        stripped = line.strip()
        # Check that line starts at column 0 (not indented CONTENTS entry)
        if (
            stripped.startswith("1.1")
            and "functional definition" in stripped.lower()
            and not line.startswith(" " * 5)
        ):  # Skip heavily indented lines
            start_idx = i + 1
            break

    if start_idx is None:
        return ""

    # Collect lines until next section header (1.2, 2., etc.)
    definition_lines = []
    for i in range(start_idx, min(start_idx + 20, len(lines))):
        stripped = lines[i].strip()

        # Stop at next section header (not indented)
        if re.match(r"^(1\.[2-9]|[2-9]\.)\s+", stripped) and not lines[i].startswith(" " * 5):
            break

        if stripped:
            definition_lines.append(stripped)

    return " ".join(definition_lines)


# Pattern for segment clarification entries
# D23A: "00010   UNH, Message header" or "00090   Segment group 1:  RFF-DTM"
# D96A: "0010 | UNH, Message header" or "0020   BGM, Beginning of message"
CLARIFICATION_ENTRY_PATTERN = re.compile(
    r"^(\d{4,5})\s+[|]?\s*([A-Z]{2,3},\s*.+|Segment group \d+.*)$"
)


def _parse_segment_clarifications(lines: list[str]) -> dict[int, str]:
    """
    Parse section 4.1 (Segment clarification) to extract definitions.

    Returns a dictionary mapping position numbers to their definitions.

    Format in section 4.1:
        00010   UNH, Message header
                A service segment starting and uniquely identifying a message.
                The message type code for the Purchase order message is ORDERS.

        00020   BGM, Beginning of message
                A segment by which the sender must uniquely identify...
    """
    definitions: dict[int, str] = {}

    # Find section 4.1 start (look for "4.1" followed by "Segment clarification")
    # D23A uses "Segment clarification", D96A uses "Data Segment Clarification"
    # Skip CONTENTS entries which are indented (start with spaces)
    start_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        stripped_lower = stripped.lower()
        if (
            stripped.startswith("4.1")
            and "segment clarification" in stripped_lower
            and not line.startswith(" " * 5)
        ):  # Skip heavily indented lines
            start_idx = i + 1
            break

    if start_idx is None:
        return definitions

    # Find section 4.2 or 4.3 (end of clarification section)
    # Skip CONTENTS entries which are indented
    end_idx = len(lines)
    for i in range(start_idx, len(lines)):
        stripped = lines[i].strip()
        if (stripped.startswith("4.2") or stripped.startswith("4.3")) and not lines[i].startswith(
            " " * 5
        ):
            end_idx = i
            break

    # Parse entries within section 4.1
    current_position: int | None = None
    current_lines: list[str] = []

    def save_current():
        nonlocal current_position, current_lines
        if current_position is not None and current_lines:
            # Join lines and clean up
            text = " ".join(current_lines)
            definitions[current_position] = text
        current_position = None
        current_lines = []

    for i in range(start_idx, end_idx):
        line = lines[i]
        stripped = line.strip()

        # Skip section headers like "4.1.1  Header section"
        if re.match(r"^4\.1\.\d", stripped):
            save_current()
            continue

        # Skip "Information to be provided..." preamble lines
        if stripped.startswith("Information to be provided"):
            save_current()
            continue

        # Check for new entry (position number at start)
        entry_match = CLARIFICATION_ENTRY_PATTERN.match(stripped)
        if entry_match:
            # Save previous entry
            save_current()
            current_position = int(entry_match.group(1))
            continue

        # Skip empty lines between entries
        if not stripped:
            continue

        # Accumulate definition text (indented lines)
        if current_position is not None:
            current_lines.append(stripped)

    # Save last entry
    save_current()

    return definitions


def _find_segment_table_start(lines: list[str]) -> tuple[int | None, str]:
    """
    Find the start of the segment table section.

    Returns:
        Tuple of (start_line_index, format_type) where format_type is 'd23a' or 'd96a'
    """
    # Find all occurrences of "4.3.1  Segment table" or "4.3.1 Segment table"
    # The actual table is the one followed by "Pos Tag Name" header
    segment_table_starts = []
    for i, line in enumerate(lines):
        if SEGMENT_TABLE_PATTERN.match(line.strip()):
            segment_table_starts.append(i)

    # For each potential start, check if it's the real table (has Pos Tag Name header)
    for start in segment_table_starts:
        for j in range(start, min(start + 15, len(lines))):
            if POS_TAG_NAME_PATTERN.match(lines[j].strip()):
                # Verify this has actual segment data after it
                for k in range(j + 1, min(j + 30, len(lines))):
                    stripped = lines[k].strip()
                    if SEGMENT_LINE_PATTERN_D23A.match(stripped):
                        return j + 1, "d23a"
                    if SEGMENT_GROUP_PATTERN_D23A.match(stripped):
                        return j + 1, "d23a"

    # Try D96A style (4.1.1 Header section)
    for i, line in enumerate(lines):
        if SECTION_START_D96A.match(line.strip()):
            # Find the first segment line after this
            for j in range(i + 1, min(i + 20, len(lines))):
                if SEGMENT_LINE_PATTERN_D96A.match(lines[j].strip()):
                    return j, "d96a"

    return None, ""


def _parse_segment_table(
    lines: list[str],
    clarifications: dict[int, str] | None = None,
) -> list[SegmentRef | SegmentGroup]:
    """
    Parse the segment table into a hierarchical structure.

    Uses a stack-based approach to handle nested segment groups.
    The nesting depth is tracked by counting trailing `|` and `+` markers.

    Args:
        lines: Lines from the segment table section
        clarifications: Optional dict mapping position -> definition text
    """
    if clarifications is None:
        clarifications = {}

    result: list[SegmentRef | SegmentGroup] = []

    # Stack to track nested groups: each entry is (group, parent_list)
    # parent_list is where to add the group when it closes
    group_stack: list[tuple[SegmentGroup, list[SegmentRef | SegmentGroup]]] = []

    def get_current_list() -> list[SegmentRef | SegmentGroup]:
        """Get the list to add items to (either result or current group's children)."""
        if group_stack:
            return group_stack[-1][0].children
        return result

    for line in lines:
        normalized = strip_change_indicator(line)
        stripped = normalized.strip()

        # Skip empty lines and section headers
        if not stripped or SECTION_HEADER_PATTERN.match(normalized):
            continue

        # Check for segment group header
        group_match = SEGMENT_GROUP_PATTERN_D23A.match(stripped)
        if group_match:
            position = int(group_match.group(1))
            group_num = int(group_match.group(2))
            mandatory = parse_mandatory_indicator(group_match.group(3))
            max_repeat = int(group_match.group(4))

            # Count closing markers (how many groups end here)
            close_count = _count_closures(line)

            # Close groups as needed
            for _ in range(close_count):
                if group_stack:
                    closed_group, parent_list = group_stack.pop()
                    parent_list.append(closed_group)

            # Create new group
            new_group = SegmentGroup(
                number=group_num,
                mandatory=mandatory,
                max_repeat=max_repeat,
                definition=clarifications.get(position, ""),
                children=[],
            )

            # Push new group onto stack
            group_stack.append((new_group, get_current_list()))
            continue

        # Check for segment line
        seg_match = SEGMENT_LINE_PATTERN_D23A.match(stripped)
        if seg_match:
            position = int(seg_match.group(1))
            tag = seg_match.group(2)
            mandatory = parse_mandatory_indicator(seg_match.group(4))
            max_repeat = int(seg_match.group(5))

            segment_ref = SegmentRef(
                position=position,
                segment_tag=tag,
                mandatory=mandatory,
                definition=clarifications.get(position, ""),
                max_repeat=max_repeat,
            )

            # Add to current group or result
            get_current_list().append(segment_ref)

            # Count closing markers
            close_count = _count_closures(line)

            # Close groups as needed
            for _ in range(close_count):
                if group_stack:
                    closed_group, parent_list = group_stack.pop()
                    parent_list.append(closed_group)
            continue

    # Close any remaining open groups
    while group_stack:
        closed_group, parent_list = group_stack.pop()
        parent_list.append(closed_group)

    return result


def _parse_segment_table_d96a(
    lines: list[str],
    clarifications: dict[int, str] | None = None,
) -> list[SegmentRef | SegmentGroup]:
    """
    Parse D96A format segment table.

    D96A format is simpler:
    - Segments: "0010 | UNH, Message header" (| = mandatory, space = conditional)
    - Groups: "0080   Segment group 1:  RFF-DTM"
    - Nesting is indicated by indentation of segment lines

    Groups contain the segments that follow them until the next same-level group.

    Args:
        lines: Lines from the segment table section
        clarifications: Optional dict mapping position -> definition text
    """
    if clarifications is None:
        clarifications = {}

    result: list[SegmentRef | SegmentGroup] = []

    # Stack to track nested groups
    # Each entry is (group, parent_list, indent_level)
    group_stack: list[tuple[SegmentGroup, list[SegmentRef | SegmentGroup], int]] = []

    def get_current_list() -> list[SegmentRef | SegmentGroup]:
        """Get the list to add items to."""
        if group_stack:
            return group_stack[-1][0].children
        return result

    def get_indent(line: str) -> int:
        """Get indentation level (number of leading spaces before position)."""
        match = re.match(r"^(\d{4,5})", line)
        if match:
            # Count spaces before the position number
            return len(line) - len(line.lstrip())
        return 0

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            i += 1
            continue

        # Skip section headers and description text
        if SECTION_HEADER_PATTERN.match(line) or SECTION_START_D96A.match(stripped):
            i += 1
            continue

        # Skip lines that look like descriptions (don't start with position number)
        if not re.match(r"^\d{4,5}", stripped):
            i += 1
            continue

        # Check for segment group header
        group_match = SEGMENT_GROUP_PATTERN_D96A.match(stripped)
        if group_match:
            position = int(group_match.group(1))
            group_num = int(group_match.group(2))
            # D96A doesn't specify M/C for groups explicitly, default to conditional
            # Group repeat count defaults to 99999 (many)
            mandatory = False
            max_repeat = 99999

            # Determine group nesting level from indentation
            indent = get_indent(line)

            # Close groups that are at same or higher indentation level
            while group_stack and group_stack[-1][2] >= indent:
                closed_group, parent_list, _ = group_stack.pop()
                parent_list.append(closed_group)

            # Create new group
            new_group = SegmentGroup(
                number=group_num,
                mandatory=mandatory,
                max_repeat=max_repeat,
                definition=clarifications.get(position, ""),
                children=[],
            )

            # Push onto stack
            group_stack.append((new_group, get_current_list(), indent))
            i += 1
            continue

        # Check for segment line
        seg_match = SEGMENT_LINE_PATTERN_D96A.match(stripped)
        if seg_match:
            position = int(seg_match.group(1))
            mandatory_marker = seg_match.group(2)
            tag = seg_match.group(3)
            # D96A: | = mandatory, space = conditional
            mandatory = mandatory_marker == "|"
            max_repeat = 1  # D96A doesn't show repeat count, default to 1

            segment_ref = SegmentRef(
                position=position,
                segment_tag=tag,
                mandatory=mandatory,
                max_repeat=max_repeat,
                definition=clarifications.get(position, ""),
            )

            # Add to current group or result
            get_current_list().append(segment_ref)
            i += 1
            continue

        i += 1

    # Close any remaining open groups
    while group_stack:
        closed_group, parent_list, _ = group_stack.pop()
        parent_list.append(closed_group)

    return result


def _count_closures(line: str) -> int:
    """
    Count how many groups close at the end of this line.

    In D23A style files, closing is indicated by trailing markers:
    - `-----+` or similar with a final `+` closes and opens
    - `-----++` closes two levels
    - Trailing `|` means continue at current level

    In D96A files, box-drawing characters are used:
    - `Ŀ` (U+013F) or similar = opening marker (like +)
    - `Ù` (U+0179) = closing marker
    - Box-drawing chars and replacement chars (U+FFFD) = fillers

    The counting logic:
    - For segments: count closing markers at the end
    - For groups: the opening marker is handled by group detection
    """
    stripped = line.rstrip()
    if not stripped:
        return 0

    # Characters that indicate closures
    CLOSE_CHARS = {"+", "Ù", "ٳ", "\u0179"}  # Plus various box-drawing close chars

    # Characters that indicate continuation (don't close)
    CONTINUE_CHARS = {"|", "�", "\ufffd", "Ŀ", "\u013f"}

    # Filler characters (separators)
    FILLER_CHARS = {"-", "─", "Ä", "\ufffd", "�"}

    # Look at trailing characters
    close_count = 0
    for char in reversed(stripped):
        if char in CLOSE_CHARS:
            close_count += 1
        elif char in CONTINUE_CHARS:
            # Continue marker, stop counting but don't add
            break
        elif char in FILLER_CHARS:
            # Filler, stop counting
            break
        elif char.isspace() or char.isalnum():
            # Regular content, stop
            break

    return close_count


def list_messages(directory: Path) -> list[str]:
    """
    List all message codes available in an edmd directory.

    Args:
        directory: Path to edmd/ directory

    Returns:
        List of message codes (e.g., ['INVOIC', 'ORDERS', 'DESADV'])
    """
    messages = []
    if not directory.exists():
        return messages

    for file in directory.iterdir():
        if file.name.endswith("_D.23A") or file.name.endswith("_D.22B"):
            # Extract message code from filename
            code = file.name.split("_")[0]
            messages.append(code)

    return sorted(messages)
