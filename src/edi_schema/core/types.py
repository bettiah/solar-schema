"""
Core type definitions and protocols for EDI Schema Library.

This module defines the common interfaces that both X12 and EDIFACT
implementations must satisfy, enabling a unified API.
"""

from enum import Enum
from typing import Any, Protocol, runtime_checkable


class RequirementDesignator(str, Enum):
    """
    Requirement designators for segment and element usage.

    Common across both X12 and EDIFACT standards.
    """

    MANDATORY = "M"  # Must be present
    OPTIONAL = "O"  # May be present
    CONDITIONAL = "C"  # Dependent on other elements/segments

    @property
    def is_required(self) -> bool:
        """Check if this designator indicates a required element."""
        return self == RequirementDesignator.MANDATORY

    @property
    def is_conditional(self) -> bool:
        """Check if this designator indicates a conditional element."""
        return self == RequirementDesignator.CONDITIONAL


@runtime_checkable
class ElementLike(Protocol):
    """
    Protocol for data elements across EDI formats.

    Data elements are the atomic units of data in EDI messages.
    Both X12 and EDIFACT have similar concepts with different terminology.
    """

    @property
    def id(self) -> str:
        """Unique identifier for this element (e.g., '1' for X12, '1001' for EDIFACT)."""
        ...

    @property
    def name(self) -> str:
        """Human-readable name of the element."""
        ...

    @property
    def min_length(self) -> int:
        """Minimum length of the element value."""
        ...

    @property
    def max_length(self) -> int:
        """Maximum length of the element value."""
        ...

    @property
    def data_type(self) -> str:
        """Data type code (format-specific)."""
        ...


@runtime_checkable
class CompositeLike(Protocol):
    """
    Protocol for composite data elements.

    Composites are groups of related simple elements that appear together.
    More prevalent in EDIFACT but also used in X12.
    """

    @property
    def id(self) -> str:
        """Unique identifier (e.g., 'C001' for X12, 'C082' for EDIFACT)."""
        ...

    @property
    def name(self) -> str:
        """Human-readable name of the composite."""
        ...

    @property
    def components(self) -> list[Any]:
        """List of component elements within this composite."""
        ...


@runtime_checkable
class SegmentLike(Protocol):
    """
    Protocol for segments across EDI formats.

    Segments are named groups of related data elements.
    Examples: ISA, GS, ST (X12) or UNB, UNH, NAD (EDIFACT)
    """

    @property
    def id(self) -> str:
        """Segment identifier (e.g., 'ISA', 'NAD')."""
        ...

    @property
    def name(self) -> str:
        """Human-readable name of the segment."""
        ...

    @property
    def elements(self) -> list[Any]:
        """List of elements (simple or composite) in this segment."""
        ...


@runtime_checkable
class SchemaLike(Protocol):
    """
    Protocol for loaded EDI schemas.

    A schema represents a complete transaction set (X12) or message (EDIFACT)
    definition that can be used for parsing and validation.
    """

    @property
    def format(self) -> str:
        """EDI format ('x12' or 'edifact')."""
        ...

    @property
    def id(self) -> str:
        """Schema identifier (e.g., '850' for X12, 'INVOIC' for EDIFACT)."""
        ...

    @property
    def version(self) -> str:
        """Version identifier (e.g., '005010' for X12, 'D.23A' for EDIFACT)."""
        ...

    @property
    def name(self) -> str:
        """Human-readable name of the transaction/message."""
        ...

    def get_segment(self, segment_id: str) -> SegmentLike | None:
        """Look up a segment definition by ID."""
        ...

    def get_element(self, element_id: str) -> ElementLike | None:
        """Look up an element definition by ID."""
        ...

    def get_composite(self, composite_id: str) -> CompositeLike | None:
        """Look up a composite definition by ID."""
        ...

    def get_structure(self) -> list[Any]:
        """Get the hierarchical structure of the transaction/message."""
        ...
