"""
EDIFACT Abstract Syntax Tree (AST) Node Types.

This module defines the data structures for representing parsed EDIFACT documents.
All nodes support error recovery - errors are attached to nodes rather than
stopping parsing.

EDIFACT Structure:
    UNA (optional) - Service String Advice (delimiters)
    UNB/UNZ       - Interchange envelope
      UNG/UNE     - Functional Group (optional)
        UNH/UNT   - Message envelope
          ...     - Message content (segments and segment groups)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edi_schema.edifact.models import (
        Component,
        Composite,
        DataElement,
        Segment,
        SegmentElement,
        SegmentGroup,
    )


# =============================================================================
# Source Position Tracking
# =============================================================================


@dataclass(frozen=True)
class SourcePosition:
    """
    Location in source document for error reporting.

    All positions are designed to be human-readable (1-indexed for line/column).
    """

    offset: int  # Byte offset from start of document (0-indexed)
    line: int  # Line number (1-indexed)
    column: int  # Column number (1-indexed)
    length: int = 0  # Length of the token/segment

    def __str__(self) -> str:
        return f"line {self.line}, col {self.column}"

    def to_dict(self) -> dict:
        return {
            "offset": self.offset,
            "line": self.line,
            "column": self.column,
            "length": self.length,
        }


# =============================================================================
# Error Types
# =============================================================================


class ErrorSeverity(Enum):
    """Severity level for parse/validation errors."""

    FATAL = "fatal"  # Cannot continue parsing at all
    ERROR = "error"  # Serious issue, but parsing can continue
    WARNING = "warning"  # Minor issue, document may still be valid


class ErrorCategory(Enum):
    """Category of error for filtering and reporting."""

    STRUCTURAL = "structural"  # Delimiters, terminators, basic syntax
    ENVELOPE = "envelope"  # UNB/UNZ, UNG/UNE, UNH/UNT matching
    SCHEMA = "schema"  # Segment order, groups, required segments
    ELEMENT = "element"  # Data type, length validation
    CODE = "code"  # Invalid code values
    SEMANTIC = "semantic"  # Cross-field rules, conditional requirements


class RecoveryPoint(Enum):
    """Well-defined points where parser can resynchronize after error."""

    SEGMENT_BOUNDARY = "segment"  # After any segment terminator
    GROUP_START = "group_start"  # At first segment of a segment group
    MESSAGE_START = "unh"  # At UNH segment
    MESSAGE_END = "unt"  # At UNT segment
    FUNCTIONAL_GROUP_START = "ung"  # At UNG segment
    FUNCTIONAL_GROUP_END = "une"  # At UNE segment
    INTERCHANGE_END = "unz"  # At UNZ segment


@dataclass
class ParseError:
    """
    A parse or validation error with full context.

    Designed to support both human-readable error messages and
    CONTRL acknowledgment generation.
    """

    # Error identification
    code: str  # Error code (for CONTRL UCI/UCM/UCS/UCD)
    message: str  # Human-readable description
    category: ErrorCategory
    severity: ErrorSeverity = ErrorSeverity.ERROR

    # Location in source
    position: SourcePosition | None = None

    # Location in document structure (for CONTRL)
    segment_tag: str | None = None
    segment_position: int | None = None  # Position in message (for UCS)
    element_position: int | None = None  # 1-indexed element (for UCD)
    component_position: int | None = None  # Component within composite (for UCD)

    # Context
    group_number: int | None = None  # Segment group number
    message_reference: str | None = None
    group_reference: str | None = None  # Functional group reference
    interchange_reference: str | None = None

    # Recovery information
    recovery_point: RecoveryPoint | None = None
    skipped_content: str | None = None  # What was skipped during recovery

    # Helpful extras
    expected: str | None = None  # What was expected
    actual: str | None = None  # What was found
    suggested_fix: str | None = None

    def __str__(self) -> str:
        loc = f" at {self.position}" if self.position else ""
        seg = f" in {self.segment_tag}" if self.segment_tag else ""
        return f"[{self.code}] {self.message}{seg}{loc}"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "code": self.code,
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "position": self.position.to_dict() if self.position else None,
            "segment_tag": self.segment_tag,
            "segment_position": self.segment_position,
            "element_position": self.element_position,
            "component_position": self.component_position,
            "group_number": self.group_number,
            "expected": self.expected,
            "actual": self.actual,
        }


# =============================================================================
# Delimiters
# =============================================================================


@dataclass
class Delimiters:
    """
    EDIFACT delimiter characters.

    These can be extracted from the UNA segment (if present) or default
    to the UNOA/UNOB character set defaults.

    UNA format (exactly 9 bytes):
        UNA:+.? '
           │││││└─ segment terminator (position 8)
           ││││└── reserved/space (position 7)
           │││└─── release/escape (position 6)
           ││└──── decimal notation (position 5)
           │└───── element separator (position 4)
           └────── component separator (position 3)
    """

    component: str = ":"  # Component data element separator
    element: str = "+"  # Data element separator
    decimal: str = "."  # Decimal notation
    release: str = "?"  # Release (escape) character
    segment: str = "'"  # Segment terminator

    def __str__(self) -> str:
        return (
            f"component={self.component!r} element={self.element!r} "
            f"decimal={self.decimal!r} release={self.release!r} segment={self.segment!r}"
        )

    @classmethod
    def from_una(cls, una_data: str) -> "Delimiters":
        """
        Extract delimiters from UNA segment.

        Args:
            una_data: The first 9 bytes of the document starting with "UNA"

        Returns:
            Delimiters instance with extracted values
        """
        if len(una_data) < 9 or not una_data.startswith("UNA"):
            raise ValueError("Invalid UNA segment: must be 9 bytes starting with 'UNA'")

        return cls(
            component=una_data[3],
            element=una_data[4],
            decimal=una_data[5],
            release=una_data[6],
            # position 7 is reserved (usually space)
            segment=una_data[8],
        )

    @classmethod
    def defaults(cls) -> "Delimiters":
        """Return EDIFACT default delimiters (UNOA/UNOB charset)."""
        return cls()

    def to_una(self) -> str:
        """Generate UNA segment from delimiters."""
        return f"UNA{self.component}{self.element}{self.decimal}{self.release} {self.segment}"


# =============================================================================
# Raw (Pre-Schema) AST Nodes
# =============================================================================


@dataclass
class RawComponent:
    """
    A single component within a composite element.

    Components are the atomic values within composites, separated by
    the component separator (default ':').
    """

    value: str
    position: SourcePosition
    component_index: int  # 1-indexed position within composite

    def __str__(self) -> str:
        return self.value

    def is_empty(self) -> bool:
        return not self.value


@dataclass
class RawElement:
    """
    An element within a segment (before schema validation).

    In EDIFACT, elements can be either:
    - Simple: A single value
    - Composite: Multiple components separated by component separator

    This class handles both cases.
    """

    value: str | None  # Full value (for simple) or None (for composite)
    position: SourcePosition
    element_index: int  # 1-indexed position in segment

    # For composite elements
    components: list[RawComponent] | None = None

    def __str__(self) -> str:
        if self.components:
            return ":".join(c.value for c in self.components)
        return self.value or ""

    @property
    def is_composite(self) -> bool:
        """Check if this is a composite element."""
        return self.components is not None and len(self.components) > 0

    def is_empty(self) -> bool:
        """Check if element has no meaningful value."""
        if self.components:
            return all(c.is_empty() for c in self.components)
        return not self.value

    def get_component(self, index: int) -> str | None:
        """Get component value by 1-indexed position."""
        if self.components and 1 <= index <= len(self.components):
            return self.components[index - 1].value
        # For simple elements, index 1 returns the value
        if index == 1 and not self.components:
            return self.value
        return None

    def get_simple_value(self) -> str | None:
        """Get value as simple string (first component if composite)."""
        if self.components:
            return self.components[0].value if self.components else None
        return self.value


@dataclass
class RawSegment:
    """
    A parsed segment before schema validation.

    Contains the segment tag and all elements.
    """

    tag: str
    elements: list[RawElement]
    position: SourcePosition
    raw_text: str  # Original text for error messages

    def __str__(self) -> str:
        return f"{self.tag} ({len(self.elements)} elements)"

    def get_element(self, index: int) -> RawElement | None:
        """Get element by 1-indexed position."""
        if 1 <= index <= len(self.elements):
            return self.elements[index - 1]
        return None

    def get_element_value(self, index: int) -> str | None:
        """Get simple element value by 1-indexed position."""
        elem = self.get_element(index)
        if elem is None:
            return None
        return elem.get_simple_value()

    def get_component_value(self, element_index: int, component_index: int) -> str | None:
        """Get component value from composite element."""
        elem = self.get_element(element_index)
        if elem is None:
            return None
        return elem.get_component(component_index)


# =============================================================================
# Parsed (Schema-Aware) AST Nodes
# =============================================================================


@dataclass
class ParsedComponent:
    """A component with schema definition attached."""

    value: str
    raw: RawComponent
    definition: "Component | None" = None
    element_definition: "DataElement | None" = None  # Resolved element
    errors: list[ParseError] = field(default_factory=list)

    def is_valid(self) -> bool:
        return len(self.errors) == 0


@dataclass
class ParsedElement:
    """An element with schema definition attached."""

    raw: RawElement
    definition: "SegmentElement | None" = None
    errors: list[ParseError] = field(default_factory=list)

    # For composite elements
    components: list[ParsedComponent] | None = None

    # For simple elements - resolved element definition
    element_definition: "DataElement | None" = None

    # For composite elements - resolved composite definition
    composite_definition: "Composite | None" = None

    @property
    def value(self) -> str | None:
        """Get the simple value or first component."""
        return self.raw.get_simple_value()

    @property
    def is_composite(self) -> bool:
        return self.raw.is_composite

    def is_valid(self) -> bool:
        if self.errors:
            return False
        if self.components:
            return all(c.is_valid() for c in self.components)
        return True

    def get_component(self, index: int) -> ParsedComponent | None:
        """Get component by 1-indexed position."""
        if self.components and 1 <= index <= len(self.components):
            return self.components[index - 1]
        return None


@dataclass
class ParsedSegment:
    """A segment with schema information attached."""

    tag: str
    elements: list[ParsedElement]
    raw: RawSegment
    definition: "Segment | None" = None
    errors: list[ParseError] = field(default_factory=list)
    position_in_message: int = 0  # For UCS segment position

    def is_valid(self) -> bool:
        if self.errors:
            return False
        return all(e.is_valid() for e in self.elements)

    def get_element(self, index: int) -> ParsedElement | None:
        """Get element by 1-indexed position."""
        if 1 <= index <= len(self.elements):
            return self.elements[index - 1]
        return None

    def get_element_value(self, index: int) -> str | None:
        """Get element value by 1-indexed position."""
        elem = self.get_element(index)
        return elem.value if elem else None


# =============================================================================
# Segment Group Instance
# =============================================================================


@dataclass
class SegmentGroupInstance:
    """
    An instance of a segment group in the parsed document.

    Segment groups can contain segments and nested child groups.
    A group may iterate multiple times in a message.
    """

    group_number: int  # Group identifier (1, 2, 3, etc.)
    definition: "SegmentGroup | None" = None
    segments: list[ParsedSegment] = field(default_factory=list)
    children: list["SegmentGroupInstance"] = field(default_factory=list)
    iteration: int = 1  # Which iteration of this group (1-indexed)
    errors: list[ParseError] = field(default_factory=list)

    def __str__(self) -> str:
        return f"SG{self.group_number}[{self.iteration}] ({len(self.segments)} segs, {len(self.children)} children)"

    def is_valid(self) -> bool:
        if self.errors:
            return False
        if not all(s.is_valid() for s in self.segments):
            return False
        return all(c.is_valid() for c in self.children)

    def all_segments(self) -> list[ParsedSegment]:
        """Get all segments including those in nested groups."""
        result = list(self.segments)
        for child in self.children:
            result.extend(child.all_segments())
        return result

    def all_errors(self) -> list[ParseError]:
        """Collect all errors from this group and descendants."""
        result = list(self.errors)
        for seg in self.segments:
            result.extend(seg.errors)
            for elem in seg.elements:
                result.extend(elem.errors)
                if elem.components:
                    for comp in elem.components:
                        result.extend(comp.errors)
        for child in self.children:
            result.extend(child.all_errors())
        return result


# =============================================================================
# Message Instance (UNH/UNT)
# =============================================================================


@dataclass
class MessageInstance:
    """
    A parsed message (UNH...UNT).

    Contains all parsed content organized by segments and segment groups.
    """

    # From UNH segment
    reference_number: str  # UNH.0062 - Message reference number
    message_type: str  # S009.0065 - e.g., "INVOIC"
    version: str  # S009.0052 - e.g., "D"
    release: str  # S009.0054 - e.g., "23A"
    controlling_agency: str = "UN"  # S009.0051

    # Association assigned code (optional)
    association_code: str | None = None  # S009.0057

    # Content
    content: list[ParsedSegment | SegmentGroupInstance] = field(default_factory=list)

    # Raw envelope segments
    unh_segment: RawSegment | None = None
    unt_segment: RawSegment | None = None

    # Validation
    segment_count: int | None = None  # From UNT.0074
    actual_segment_count: int = 0  # Counted during parsing
    errors: list[ParseError] = field(default_factory=list)

    def __str__(self) -> str:
        return f"Message {self.message_type}-{self.reference_number}"

    @property
    def message_identifier(self) -> str:
        """Get full message identifier (type:version:release:agency)."""
        return f"{self.message_type}:{self.version}:{self.release}:{self.controlling_agency}"

    def is_valid(self) -> bool:
        if self.errors:
            return False
        for item in self.content:
            if isinstance(item, ParsedSegment) and not item.is_valid():
                return False
            if isinstance(item, SegmentGroupInstance) and not item.is_valid():
                return False
        return True

    def all_segments(self) -> list[ParsedSegment]:
        """Get all segments in order."""
        result = []
        for item in self.content:
            if isinstance(item, ParsedSegment):
                result.append(item)
            elif isinstance(item, SegmentGroupInstance):
                result.extend(item.all_segments())
        return result

    def all_errors(self) -> list[ParseError]:
        """Collect all errors from this message and its contents."""
        result = list(self.errors)
        for item in self.content:
            if isinstance(item, ParsedSegment):
                result.extend(item.errors)
                for elem in item.elements:
                    result.extend(elem.errors)
            elif isinstance(item, SegmentGroupInstance):
                result.extend(item.all_errors())
        return result


# =============================================================================
# Functional Group Instance (UNG/UNE) - Optional in EDIFACT
# =============================================================================


@dataclass
class FunctionalGroupInstance:
    """
    A parsed functional group (UNG...UNE).

    Note: Functional groups are OPTIONAL in EDIFACT. Many implementations
    skip UNG/UNE and go directly from UNB to UNH.
    """

    # From UNG segment
    message_type: str  # UNG.0038 - Message group identification
    sender_id: str  # S006 - Application sender
    recipient_id: str  # S007 - Application recipient
    reference_number: str  # UNG.0048 - Group reference number

    # Optional UNG fields
    date: str | None = None  # S004.0017
    time: str | None = None  # S004.0019
    controlling_agency: str = "UN"  # UNG.0051
    message_version: str | None = None  # S008.0052
    message_release: str | None = None  # S008.0054

    # Content
    messages: list[MessageInstance] = field(default_factory=list)

    # Raw envelope segments
    ung_segment: RawSegment | None = None
    une_segment: RawSegment | None = None

    # Validation
    message_count: int | None = None  # From UNE.0060
    errors: list[ParseError] = field(default_factory=list)

    def __str__(self) -> str:
        return f"Group {self.message_type}-{self.reference_number} ({len(self.messages)} messages)"

    def is_valid(self) -> bool:
        if self.errors:
            return False
        return all(m.is_valid() for m in self.messages)

    def all_errors(self) -> list[ParseError]:
        """Collect all errors from this group and its messages."""
        result = list(self.errors)
        for msg in self.messages:
            result.extend(msg.all_errors())
        return result


# =============================================================================
# Interchange Instance (UNB/UNZ)
# =============================================================================


@dataclass
class InterchangeInstance:
    """
    A complete parsed interchange (UNB...UNZ).

    This is the top-level AST node representing an entire EDIFACT document.
    """

    # From UNB.S001 - Syntax identifier
    syntax_identifier: str  # S001.0001 - UNOA, UNOB, UNOC, etc.
    syntax_version: str  # S001.0002 - 1, 2, 3, 4

    # From UNB.S002 - Interchange sender
    sender_id: str  # S002.0004

    # From UNB.S003 - Interchange recipient
    recipient_id: str  # S003.0010

    # --- Fields with defaults below ---

    # From UNB.S002/S003 - Qualifiers (optional)
    sender_qualifier: str | None = None  # S002.0007
    recipient_qualifier: str | None = None  # S003.0007

    # From UNB.S004 - Date/time of preparation
    date: str = ""  # S004.0017 - YYMMDD or CCYYMMDD
    time: str = ""  # S004.0019 - HHMM

    # From UNB - Other fields
    control_reference: str = ""  # UNB.0020 - Interchange control reference
    application_reference: str | None = None  # UNB.0026
    processing_priority: str | None = None  # UNB.0029
    ack_request: str | None = None  # UNB.0031 - "1" if ACK requested
    agreement_id: str | None = None  # UNB.0032
    test_indicator: str | None = None  # UNB.0035 - "1" for test

    # Delimiters used in this interchange
    delimiters: Delimiters = field(default_factory=Delimiters)

    # Content - can have groups OR direct messages (but not mixed in practice)
    groups: list[FunctionalGroupInstance] = field(default_factory=list)
    messages: list[MessageInstance] = field(default_factory=list)  # Direct messages without UNG

    # Raw envelope segments
    unb_segment: RawSegment | None = None
    unz_segment: RawSegment | None = None

    # From UNZ - Validation
    count: int | None = None  # UNZ.0036 - Number of messages/groups
    errors: list[ParseError] = field(default_factory=list)

    def __str__(self) -> str:
        content_count = len(self.groups) if self.groups else len(self.messages)
        content_type = "groups" if self.groups else "messages"
        return f"Interchange {self.control_reference} ({content_count} {content_type})"

    def is_valid(self) -> bool:
        if self.errors:
            return False
        if self.groups:
            return all(g.is_valid() for g in self.groups)
        return all(m.is_valid() for m in self.messages)

    def is_test(self) -> bool:
        """Check if this is a test interchange."""
        return self.test_indicator == "1"

    def is_production(self) -> bool:
        """Check if this is a production interchange."""
        return self.test_indicator != "1"

    def all_messages(self) -> list[MessageInstance]:
        """Get all messages from all groups or direct messages."""
        if self.groups:
            result = []
            for group in self.groups:
                result.extend(group.messages)
            return result
        return list(self.messages)

    def all_errors(self) -> list[ParseError]:
        """Collect all errors from the entire interchange."""
        result = list(self.errors)
        if self.groups:
            for group in self.groups:
                result.extend(group.all_errors())
        else:
            for msg in self.messages:
                result.extend(msg.all_errors())
        return result


# =============================================================================
# Parse Result
# =============================================================================


@dataclass
class ParseStatistics:
    """Statistics collected during parsing."""

    total_bytes: int = 0
    segment_count: int = 0
    message_count: int = 0
    group_count: int = 0
    interchange_count: int = 0
    una_present: bool = False


@dataclass
class ParseResult:
    """
    Complete result of parsing an EDIFACT document.

    Contains the parsed interchange(s) plus all errors.
    Even with errors, partial results may be available.
    """

    interchanges: list[InterchangeInstance] = field(default_factory=list)
    errors: list[ParseError] = field(default_factory=list)
    warnings: list[ParseError] = field(default_factory=list)

    # Parsing metadata
    delimiters: Delimiters = field(default_factory=Delimiters)
    statistics: ParseStatistics = field(default_factory=ParseStatistics)

    # Recovery statistics
    segments_parsed: int = 0
    segments_skipped: int = 0
    recovery_count: int = 0  # How many times we recovered from errors

    def is_valid(self) -> bool:
        """Check if document is completely valid (no errors)."""
        if self.errors:
            return False
        return all(i.is_valid() for i in self.interchanges)

    def has_fatal_errors(self) -> bool:
        """Check if there are fatal errors that prevented parsing."""
        return any(e.severity == ErrorSeverity.FATAL for e in self.errors)

    def all_errors(self) -> list[ParseError]:
        """Get all errors including those attached to nodes."""
        result = list(self.errors)
        for interchange in self.interchanges:
            result.extend(interchange.all_errors())
        return result

    def error_count(self) -> int:
        """Total number of errors."""
        return len(self.all_errors())

    def all_messages(self) -> list[MessageInstance]:
        """Get all messages from all interchanges."""
        result = []
        for interchange in self.interchanges:
            result.extend(interchange.all_messages())
        return result

    def __str__(self) -> str:
        if self.interchanges:
            status = "valid" if self.is_valid() else f"{self.error_count()} errors"
            return f"ParseResult: {len(self.interchanges)} interchange(s) - {status}"
        return f"ParseResult: Failed with {len(self.errors)} errors"
