"""
EDIFACT Schema Models.

Dataclass definitions for UN/EDIFACT schema components including:
- Data elements
- Composites
- Segments
- Messages (transaction sets)
"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class DataElement:
    """
    An EDIFACT data element definition.

    Data elements are the atomic units of data in EDIFACT messages.
    They have a numeric tag (e.g., '1001'), a type (a/n/an), and length constraints.

    Attributes:
        tag: Element tag (e.g., '1001', '3039')
        name: Human-readable name (e.g., 'Document name code')
        description: Full description of the element
        data_type: Type code - 'a' (alphabetic), 'n' (numeric), 'an' (alphanumeric)
        max_length: Maximum allowed length
        min_length: Minimum required length (0 for variable length)
        codes: Dictionary of valid code values and their descriptions, if applicable
        usage: Usage indicator - 'B' (batch), 'I' (interactive), 'C' (common)
    """

    tag: str
    name: str
    description: str
    data_type: Literal["a", "n", "an"]
    max_length: int
    min_length: int = 0
    codes: dict[str, str] | None = None
    usage: Literal["B", "I", "C"] | None = None

    # Protocol compliance
    @property
    def id(self) -> str:
        """ElementLike protocol: unique identifier."""
        return self.tag


@dataclass
class Component:
    """
    A component within a composite element.

    Components link data elements to their position and requirements
    within a composite.

    Attributes:
        position: Position within composite (10, 20, 30, etc.)
        element_tag: Reference to DataElement tag
        mandatory: Whether this component is required
        element: Resolved DataElement reference (set during resolution)
    """

    position: int
    element_tag: str
    mandatory: bool
    element: DataElement | None = None


@dataclass
class Composite:
    """
    An EDIFACT composite data element.

    Composites group related data elements together under a single tag.
    Tags start with 'C' followed by a 3-digit number (e.g., 'C082').

    Attributes:
        tag: Composite tag (e.g., 'C082', 'C507')
        name: Human-readable name (e.g., 'PARTY IDENTIFICATION DETAILS')
        description: Full description of the composite
        components: List of component element references
    """

    tag: str
    name: str
    description: str
    components: list[Component] = field(default_factory=list)

    # Protocol compliance
    @property
    def id(self) -> str:
        """CompositeLike protocol: unique identifier."""
        return self.tag


@dataclass
class SegmentElement:
    """
    An element reference within a segment definition.

    Represents either a composite or a standalone data element
    at a specific position in a segment.

    Attributes:
        position: Position within segment (10, 20, 30, etc.)
        tag: Element tag (composite 'C###' or data element '####')
        name: Human-readable name
        mandatory: Whether this element is required
        max_repeat: Maximum repetitions allowed (usually 1)
        is_composite: True if this references a composite
        resolved: Resolved Composite or DataElement reference
    """

    position: int
    tag: str
    name: str
    mandatory: bool
    max_repeat: int = 1
    is_composite: bool = False
    resolved: "Composite | DataElement | None" = None


@dataclass
class Segment:
    """
    An EDIFACT segment definition.

    Segments are the primary structural units in EDIFACT messages,
    identified by 3-letter tags (e.g., 'NAD', 'DTM', 'MOA').

    Attributes:
        tag: Segment tag (e.g., 'NAD', 'DTM')
        name: Human-readable name (e.g., 'NAME AND ADDRESS')
        function: Description of segment's function
        elements: List of element references in the segment
    """

    tag: str
    name: str
    function: str
    elements: list[SegmentElement] = field(default_factory=list)

    # Protocol compliance
    @property
    def id(self) -> str:
        """SegmentLike protocol: unique identifier."""
        return self.tag


@dataclass
class SegmentRef:
    """
    A reference to a segment within a message structure.

    Used in message definitions to specify which segments appear
    and their requirements (mandatory/conditional, repetitions).

    Attributes:
        position: Position in message (00010, 00020, etc.)
        segment_tag: Reference to Segment tag
        mandatory: Whether this segment is required at this position
        max_repeat: Maximum repetitions allowed
        definition: Usage description from section 4.1 Segment clarification
        segment: Resolved Segment reference (set during resolution)
    """

    position: int
    segment_tag: str
    mandatory: bool
    max_repeat: int
    definition: str = ""
    segment: Segment | None = None


@dataclass
class SegmentGroup:
    """
    A group of related segments within a message.

    Segment groups can nest to form hierarchical structures.
    They are identified by number (1, 2, 3, etc.) and can contain
    both segment references and nested segment groups.

    Attributes:
        number: Group number (1, 2, 3, etc.)
        mandatory: Whether this group is required
        max_repeat: Maximum repetitions of the entire group
        definition: Usage description from section 4.1 Segment clarification
        children: List of SegmentRef or nested SegmentGroup items
    """

    number: int
    mandatory: bool
    max_repeat: int
    definition: str = ""
    children: list["SegmentRef | SegmentGroup"] = field(default_factory=list)


@dataclass
class MessageSpec:
    """
    An EDIFACT message specification.

    Represents a complete message type like INVOIC, ORDERS, or DESADV.
    Contains metadata and the hierarchical structure of segments and groups.

    Attributes:
        code: Message type code (e.g., 'INVOIC', 'ORDERS')
        version: Version identifier (e.g., 'D')
        release: Release identifier (e.g., '23A')
        name: Human-readable name (e.g., 'Invoice message')
        definition: Functional definition from section 1.1
        structure: Hierarchical list of SegmentRef and SegmentGroup items
        controlling_agency: Usually 'UN' for UN/EDIFACT
    """

    code: str
    version: str
    release: str
    name: str
    definition: str = ""
    structure: list[SegmentRef | SegmentGroup] = field(default_factory=list)
    controlling_agency: str = "UN"

    # Protocol compliance
    @property
    def format(self) -> str:
        """SchemaLike protocol: EDI format identifier."""
        return "edifact"

    @property
    def id(self) -> str:
        """SchemaLike protocol: message type code."""
        return self.code

    @property
    def full_version(self) -> str:
        """Combined version and release (e.g., 'D.23A')."""
        return f"{self.version}.{self.release}"


@dataclass
class ResolvedMessageSpec:
    """
    A fully resolved message specification with all references linked.

    This is the result of loading a message through the schema builder.
    It provides convenient lookup methods for segments, elements, and composites.

    Attributes:
        spec: The underlying MessageSpec
        segments: Dictionary of all segments used in this message
        composites: Dictionary of all composites used in this message
        elements: Dictionary of all data elements used in this message
    """

    spec: MessageSpec
    segments: dict[str, Segment] = field(default_factory=dict)
    composites: dict[str, Composite] = field(default_factory=dict)
    elements: dict[str, DataElement] = field(default_factory=dict)

    # Protocol compliance for SchemaLike
    @property
    def format(self) -> str:
        """EDI format identifier."""
        return "edifact"

    @property
    def id(self) -> str:
        """Message type code."""
        return self.spec.code

    @property
    def version(self) -> str:
        """Version string."""
        return self.spec.full_version

    @property
    def name(self) -> str:
        """Human-readable message name."""
        return self.spec.name

    def get_segment(self, segment_id: str) -> Segment | None:
        """Look up a segment definition by ID."""
        return self.segments.get(segment_id)

    def get_element(self, element_id: str) -> DataElement | None:
        """Look up an element definition by ID."""
        return self.elements.get(element_id)

    def get_composite(self, composite_id: str) -> Composite | None:
        """Look up a composite definition by ID."""
        return self.composites.get(composite_id)

    def get_structure(self) -> list[SegmentRef | SegmentGroup]:
        """Get the hierarchical structure of the message."""
        return self.spec.structure
