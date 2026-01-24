"""
X12 Transaction Set Models.

This module defines dataclasses for representing X12 transaction sets
and their hierarchical structure.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edi_schema.x12.enums import RequirementDesignator, TransactionSetArea


@dataclass
class TransactionSetSegment:
    """
    Represents a segment reference within a transaction set structure.

    This defines how a segment is used within a specific transaction set,
    including its position, requirements, loop membership, and repetition limits.

    Attributes:
        area: Transaction set area (1=Heading, 2=Detail, 3=Summary)
        sequence: Position within the area (e.g., "0100", "0200")
        segment_id: Reference to Segment id
        requirement: M=Mandatory, O=Optional, C=Conditional
        max_use: Maximum times segment can appear (int or ">1" for unlimited)
        loop_level: Nesting level of the loop (0 = not in a loop)
        loop_repeat: How many times the loop can repeat (int or ">1" for unlimited)
        loop_id: Loop identifier if this segment starts or is part of a loop
    """

    area: "TransactionSetArea"
    sequence: str
    segment_id: str
    requirement: "RequirementDesignator"
    max_use: int | str = 1
    loop_level: int = 0
    loop_repeat: int | str = 0
    loop_id: str | None = None

    def __str__(self) -> str:
        loop_info = f" Loop:{self.loop_id}" if self.loop_id else ""
        return f"{self.area.value}/{self.sequence}: {self.segment_id} ({self.requirement.value}){loop_info}"

    def is_loop_start(self) -> bool:
        """Check if this segment starts a new loop."""
        return bool(self.loop_id)

    def is_unlimited(self) -> bool:
        """Check if max_use is unlimited."""
        return self.max_use == ">1"

    def get_max_use_int(self) -> int:
        """Get max_use as an integer, returning -1 for unlimited."""
        if self.max_use == ">1":
            return -1
        return int(self.max_use)

    def get_loop_repeat_int(self) -> int:
        """Get loop_repeat as an integer, returning -1 for unlimited."""
        if self.loop_repeat == ">1":
            return -1
        return int(self.loop_repeat) if self.loop_repeat else 0


@dataclass
class LoopDefinition:
    """
    Represents a loop within a transaction set structure.

    Loops are repeating groups of segments that appear together.
    They can be nested to form hierarchical structures.

    Attributes:
        loop_id: Loop identifier (often matches first segment ID)
        level: Nesting level (1 = top level loop)
        repeat: Maximum repetitions (int or ">1" for unlimited)
        parent_loop_id: ID of containing loop, if nested
        segments: List of segments within this loop
    """

    loop_id: str
    level: int
    repeat: int | str
    parent_loop_id: str | None = None
    segments: list[TransactionSetSegment] = field(default_factory=list)

    def __str__(self) -> str:
        return f"Loop {self.loop_id} (level {self.level}, {len(self.segments)} segments)"


@dataclass
class TransactionSet:
    """
    Represents an X12 transaction set definition.

    A transaction set is a complete message type in X12, such as a
    Purchase Order (850), Invoice (810), or Functional Acknowledgment (997).

    Attributes:
        id: Transaction set identifier (e.g., "810", "850", "997")
        name: Human-readable name (e.g., "Invoice", "Purchase Order")
        functional_group: Functional group code (e.g., "IN", "PO")
        purpose: Purpose description from SETPUR in freeform.txt
        structure: List of segment references defining the structure
        notes: Notes from SETNTE in freeform.txt
    """

    id: str
    name: str
    functional_group: str
    purpose: str | None = None
    structure: list[TransactionSetSegment] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return f"Transaction Set {self.id}: {self.name} (FG: {self.functional_group})"

    def get_heading_segments(self) -> list[TransactionSetSegment]:
        """Get segments in the heading area (area 1)."""
        return [s for s in self.structure if s.area.value == "1"]

    def get_detail_segments(self) -> list[TransactionSetSegment]:
        """Get segments in the detail area (area 2)."""
        return [s for s in self.structure if s.area.value == "2"]

    def get_summary_segments(self) -> list[TransactionSetSegment]:
        """Get segments in the summary area (area 3)."""
        return [s for s in self.structure if s.area.value == "3"]

    def get_loops(self) -> dict[str, LoopDefinition]:
        """
        Build a dictionary of loop definitions from the structure.

        Returns a dict mapping loop_id to LoopDefinition objects.
        """
        loops: dict[str, LoopDefinition] = {}

        for seg in self.structure:
            if seg.loop_id:
                if seg.loop_id not in loops:
                    loops[seg.loop_id] = LoopDefinition(
                        loop_id=seg.loop_id,
                        level=seg.loop_level,
                        repeat=seg.loop_repeat,
                    )
                loops[seg.loop_id].segments.append(seg)

        return loops

    def mandatory_segments(self) -> list[TransactionSetSegment]:
        """Get list of mandatory segments in this transaction set."""
        return [s for s in self.structure if s.requirement.value == "M"]
