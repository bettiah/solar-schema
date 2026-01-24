"""
Freeform Text Parser for X12 Schema Files.

Parses the freeform.txt file used in X12 005010 schema definitions.
This file contains free-form text descriptions, definitions, and code values
organized by section markers.

Section Types:
- SETPUR: Transaction Set Purpose/Scope
- SETNTE: Transaction Set Notes/Comments
- SEGPUR: Segment Purpose
- SEGNTE: Segment Notes/Comments
- COMPUR: Composite Data Element Purpose
- COMNTE: Composite Data Element Notes/Comments
- ELEDEF: Simple Data Element Definitions
- ELECOD: Simple Data Element Code Definitions
- ELENTE: Simple Data Element Code Explanations
- CSSRCE: Source of Referenced Code List
- CSFROM: Available From Address for Code Source Maintainer
- CSINET: Internet Address of Code Source Maintainer
- CSABST: Abstract for Code List
- CSNOTE: Code Source Notes

Format Notes:
- Sections start with *SECTION_TYPE
- Next line after marker contains the identifier
- Following lines contain the text content
- Continuation lines: some multi-line entries
- File uses cp1252 encoding (Windows-1252)
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


@dataclass
class FreeformEntry:
    """
    Represents a single entry from freeform.txt.

    Attributes:
        section_type: Type of entry (SETPUR, SEGNTE, etc.)
        identifier: Entity identifier (set id, segment id, element id, etc.)
        text: The text content
        extra_fields: Additional fields for structured entries (like notes)
    """

    section_type: str
    identifier: str
    text: str
    extra_fields: dict[str, str] = field(default_factory=dict)


@dataclass
class FreeformData:
    """
    Holds all parsed freeform data organized by type.

    Attributes:
        set_purposes: Transaction set purposes (SETPUR) - id -> text
        set_notes: Transaction set notes (SETNTE) - id -> list of texts
        segment_purposes: Segment purposes (SEGPUR) - id -> text
        segment_notes: Segment notes (SEGNTE) - (seg_id, elem_pos, note_type, seq) -> text
        composite_purposes: Composite purposes (COMPUR) - id -> text
        composite_notes: Composite notes (COMNTE) - (comp_id, elem_pos, note_type, seq) -> text
        element_definitions: Element definitions (ELEDEF) - id -> text
        element_codes: Element codes (ELECOD) - (elem_id, code, partition) -> description
        element_code_notes: Element code notes (ELENTE) - (elem_id, code, partition) -> explanation
        code_source_sources: Code source info (CSSRCE) - id -> text
        code_source_from: Code source address (CSFROM) - id -> text
        code_source_inet: Code source internet (CSINET) - id -> text
        code_source_abstract: Code source abstract (CSABST) - id -> text
        code_source_notes: Code source notes (CSNOTE) - id -> text
    """

    set_purposes: dict[str, str] = field(default_factory=dict)
    set_notes: dict[str, list[str]] = field(default_factory=dict)
    segment_purposes: dict[str, str] = field(default_factory=dict)
    segment_notes: dict[tuple[str, str, str, str], str] = field(default_factory=dict)
    composite_purposes: dict[str, str] = field(default_factory=dict)
    composite_notes: dict[tuple[str, str, str, str], str] = field(default_factory=dict)
    element_definitions: dict[str, str] = field(default_factory=dict)
    element_codes: dict[tuple[str, str, str], str] = field(default_factory=dict)
    element_code_notes: dict[tuple[str, str, str], str] = field(default_factory=dict)
    code_source_sources: dict[str, str] = field(default_factory=dict)
    code_source_from: dict[str, str] = field(default_factory=dict)
    code_source_inet: dict[str, str] = field(default_factory=dict)
    code_source_abstract: dict[str, str] = field(default_factory=dict)
    code_source_notes: dict[str, str] = field(default_factory=dict)

    def get_element_code_values(self, element_id: str) -> dict[str, str]:
        """
        Get all code values for a specific element.

        Args:
            element_id: The element ID to look up

        Returns:
            Dictionary mapping code values to descriptions
        """
        result = {}
        for (elem_id, code, _partition), desc in self.element_codes.items():
            if elem_id == element_id:
                result[code] = desc
        return result


def parse_freeform_file(filepath: Path | str) -> FreeformData:
    """
    Parse the freeform.txt file and return structured data.

    Args:
        filepath: Path to freeform.txt

    Returns:
        FreeformData object with all parsed content
    """
    filepath = Path(filepath)
    data = FreeformData()

    for entry in iter_freeform_entries(filepath):
        _store_entry(data, entry)

    return data


def iter_freeform_entries(filepath: Path | str) -> Iterator[FreeformEntry]:
    """
    Iterate over entries in freeform.txt.

    Yields FreeformEntry objects one at a time.

    Args:
        filepath: Path to freeform.txt

    Yields:
        FreeformEntry for each entry in the file
    """
    filepath = Path(filepath)

    # Try cp1252 first, fall back to utf-8 with errors ignored
    try:
        with open(filepath, "r", encoding="cp1252") as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

    # Split into lines
    lines = content.split("\n")

    i = 0
    while i < len(lines):
        line = lines[i]

        # Check for section marker
        if line.startswith("*"):
            section_type = line[1:].strip()

            # Move to identifier line
            i += 1
            if i >= len(lines):
                break

            identifier_line = lines[i].strip()

            # Collect text lines until next section marker or EOF
            i += 1
            text_lines = []
            while i < len(lines) and not lines[i].startswith("*"):
                text_lines.append(lines[i])
                i += 1

            # Join text, handling continuation (trailing space means continuation)
            text = _join_text_lines(text_lines)

            # Parse identifier and extra fields based on section type
            entry = _parse_entry(section_type, identifier_line, text)
            if entry:
                yield entry
        else:
            i += 1


def _join_text_lines(lines: list[str]) -> str:
    """
    Join text lines, handling continuation.

    Lines ending with space continue on next line without newline.
    Otherwise, lines are joined with space.
    """
    if not lines:
        return ""

    result = []
    current = ""

    for line in lines:
        if not line:  # Empty line
            if current:
                result.append(current)
                current = ""
            continue

        if current.endswith(" "):
            # Continuation line
            current = current + line
        else:
            if current:
                result.append(current)
            current = line

    if current:
        result.append(current)

    return "\n".join(result).strip()


def _parse_entry(section_type: str, identifier: str, text: str) -> FreeformEntry | None:
    """
    Parse an entry based on its section type.

    Different section types have different identifier formats.
    """
    if section_type in ("SETPUR", "SETNTE"):
        # Identifier is just the transaction set ID
        return FreeformEntry(
            section_type=section_type,
            identifier=identifier,
            text=text,
        )

    elif section_type == "SEGPUR":
        # Identifier is just the segment ID
        return FreeformEntry(
            section_type=section_type,
            identifier=identifier,
            text=text,
        )

    elif section_type == "SEGNTE":
        # Identifier format: SEG_ID,ELEM_POS,NOTE_TYPE,SEQ
        # Example: AAA,01,S,1
        parts = [p.strip() for p in identifier.split(",")]
        if len(parts) >= 4:
            return FreeformEntry(
                section_type=section_type,
                identifier=parts[0],  # segment_id
                text=text,
                extra_fields={
                    "element_position": parts[1],
                    "note_type": parts[2],
                    "sequence": parts[3],
                },
            )

    elif section_type in ("COMPUR", "COMNTE"):
        if section_type == "COMPUR":
            # Identifier is just the composite ID
            return FreeformEntry(
                section_type=section_type,
                identifier=identifier,
                text=text,
            )
        else:
            # COMNTE format: COMP_ID,ELEM_POS,NOTE_TYPE,SEQ
            parts = [p.strip() for p in identifier.split(",")]
            if len(parts) >= 4:
                return FreeformEntry(
                    section_type=section_type,
                    identifier=parts[0],
                    text=text,
                    extra_fields={
                        "element_position": parts[1],
                        "note_type": parts[2],
                        "sequence": parts[3],
                    },
                )

    elif section_type == "ELEDEF":
        # Identifier is just the element ID
        return FreeformEntry(
            section_type=section_type,
            identifier=identifier,
            text=text,
        )

    elif section_type == "ELECOD":
        # Identifier format: ELEM_ID, ,CODE,PARTITION (space-padded)
        # Example: 8, ,E,1 or 9, ,C1,1
        parts = [p.strip() for p in identifier.split(",")]
        if len(parts) >= 4:
            return FreeformEntry(
                section_type=section_type,
                identifier=parts[0],  # element_id
                text=text,
                extra_fields={
                    "code": parts[2],
                    "partition": parts[3],
                },
            )
        elif len(parts) >= 3:
            return FreeformEntry(
                section_type=section_type,
                identifier=parts[0],
                text=text,
                extra_fields={
                    "code": parts[2] if len(parts) > 2 else "",
                    "partition": "1",
                },
            )

    elif section_type == "ELENTE":
        # Same format as ELECOD
        parts = [p.strip() for p in identifier.split(",")]
        if len(parts) >= 4:
            return FreeformEntry(
                section_type=section_type,
                identifier=parts[0],
                text=text,
                extra_fields={
                    "code": parts[2],
                    "partition": parts[3],
                },
            )

    elif section_type in ("CSSRCE", "CSFROM", "CSINET", "CSABST", "CSNOTE"):
        # Identifier is just the code source ID
        return FreeformEntry(
            section_type=section_type,
            identifier=identifier,
            text=text,
        )

    return None


def _store_entry(data: FreeformData, entry: FreeformEntry) -> None:
    """Store an entry in the appropriate data structure."""
    section = entry.section_type

    if section == "SETPUR":
        data.set_purposes[entry.identifier] = entry.text

    elif section == "SETNTE":
        if entry.identifier not in data.set_notes:
            data.set_notes[entry.identifier] = []
        data.set_notes[entry.identifier].append(entry.text)

    elif section == "SEGPUR":
        data.segment_purposes[entry.identifier] = entry.text

    elif section == "SEGNTE":
        key = (
            entry.identifier,
            entry.extra_fields.get("element_position", ""),
            entry.extra_fields.get("note_type", ""),
            entry.extra_fields.get("sequence", ""),
        )
        data.segment_notes[key] = entry.text

    elif section == "COMPUR":
        data.composite_purposes[entry.identifier] = entry.text

    elif section == "COMNTE":
        key = (
            entry.identifier,
            entry.extra_fields.get("element_position", ""),
            entry.extra_fields.get("note_type", ""),
            entry.extra_fields.get("sequence", ""),
        )
        data.composite_notes[key] = entry.text

    elif section == "ELEDEF":
        data.element_definitions[entry.identifier] = entry.text

    elif section == "ELECOD":
        key = (
            entry.identifier,
            entry.extra_fields.get("code", ""),
            entry.extra_fields.get("partition", "1"),
        )
        data.element_codes[key] = entry.text

    elif section == "ELENTE":
        key = (
            entry.identifier,
            entry.extra_fields.get("code", ""),
            entry.extra_fields.get("partition", "1"),
        )
        data.element_code_notes[key] = entry.text

    elif section == "CSSRCE":
        data.code_source_sources[entry.identifier] = entry.text

    elif section == "CSFROM":
        data.code_source_from[entry.identifier] = entry.text

    elif section == "CSINET":
        data.code_source_inet[entry.identifier] = entry.text

    elif section == "CSABST":
        data.code_source_abstract[entry.identifier] = entry.text

    elif section == "CSNOTE":
        data.code_source_notes[entry.identifier] = entry.text


def get_segment_notes(
    data: FreeformData,
    segment_id: str,
) -> list[tuple[str, str, str, str]]:
    """
    Get all notes for a specific segment.

    Args:
        data: FreeformData object
        segment_id: The segment ID to look up

    Returns:
        List of (element_position, note_type, sequence, text) tuples
    """
    result = []
    for (seg_id, elem_pos, note_type, seq), text in data.segment_notes.items():
        if seg_id == segment_id:
            result.append((elem_pos, note_type, seq, text))
    return result


def get_composite_notes(
    data: FreeformData,
    composite_id: str,
) -> list[tuple[str, str, str, str]]:
    """
    Get all notes for a specific composite.

    Args:
        data: FreeformData object
        composite_id: The composite ID to look up

    Returns:
        List of (element_position, note_type, sequence, text) tuples
    """
    result = []
    for (comp_id, elem_pos, note_type, seq), text in data.composite_notes.items():
        if comp_id == composite_id:
            result.append((elem_pos, note_type, seq, text))
    return result
