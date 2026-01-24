"""
X12 Segment Models.

This module defines dataclasses for representing X12 segments and their elements.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edi_schema.x12.enums import NoteType, RequirementDesignator


@dataclass
class SegmentElement:
    """
    Represents an element reference within a segment.

    This defines the position and requirements for an element
    (simple or composite) when used within a segment.

    Attributes:
        sequence: Position in segment (e.g., "01", "02")
        element_id: Reference to DataElement or Composite id
        requirement: M=Mandatory, O=Optional, C=Conditional
        repetition_count: Number of times element can repeat (1 = no repeat)
    """

    sequence: str
    element_id: str
    requirement: "RequirementDesignator"
    repetition_count: int = 1

    def __str__(self) -> str:
        rep = f" x{self.repetition_count}" if self.repetition_count > 1 else ""
        return f"{self.sequence}: Element {self.element_id} ({self.requirement.value}){rep}"

    def is_composite(self) -> bool:
        """Check if this references a composite element (starts with 'C')."""
        return self.element_id.startswith("C")


@dataclass
class SegmentNote:
    """
    Represents a note associated with a segment.

    Notes provide additional context about segment usage, syntax rules,
    or semantic meaning.

    Attributes:
        segment_id: ID of the segment this note belongs to
        element_position: Element position this note refers to (e.g., "01", "02")
        note_type: N=Syntax, S=Semantic, C=Comment
        sequence: Note sequence number within the segment/element
        text: The note text content
    """

    segment_id: str
    element_position: str
    note_type: "NoteType"
    sequence: str
    text: str

    def __str__(self) -> str:
        return f"Note {self.segment_id}/{self.element_position} ({self.note_type.value}): {self.text[:50]}..."


@dataclass
class Segment:
    """
    Represents an X12 segment.

    Segments are named groups of related data elements that form the
    building blocks of X12 transaction sets. Examples include ISA, GS,
    ST, and functional segments like N1, PO1, etc.

    Attributes:
        id: Segment identifier (e.g., "ISA", "N1", "PO1")
        name: Human-readable name (e.g., "Interchange Control Header")
        purpose: Purpose description from SEGPUR in freeform.txt
        elements: List of element references in this segment
        notes: List of notes from SEGNTE in freeform.txt
    """

    id: str
    name: str
    purpose: str | None = None
    elements: list[SegmentElement] = field(default_factory=list)
    notes: list[SegmentNote] = field(default_factory=list)

    def __str__(self) -> str:
        return f"Segment {self.id}: {self.name} ({len(self.elements)} elements)"

    def get_element(self, sequence: str) -> SegmentElement | None:
        """Get an element by its sequence position."""
        for elem in self.elements:
            if elem.sequence == sequence:
                return elem
        return None

    def get_notes_for_element(self, sequence: str) -> list[SegmentNote]:
        """Get all notes for a specific element position."""
        return [n for n in self.notes if n.element_position == sequence]

    def mandatory_elements(self) -> list[SegmentElement]:
        """Get list of mandatory elements in this segment."""
        return [e for e in self.elements if e.requirement.value == "M"]
