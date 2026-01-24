"""
X12 Abstract Syntax Tree (AST) Node Types.

This module defines the data structures for representing parsed X12 documents.
All nodes support error recovery - errors are attached to nodes rather than
stopping parsing.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edi_schema.x12.models.element import DataElement
    from edi_schema.x12.models.segment import Segment
    from edi_schema.x12.models.transaction import LoopDefinition, TransactionSet


# =============================================================================
# Source Position Tracking
# =============================================================================


@dataclass(frozen=True)
class SourcePosition:
    """
    Location in source document for error reporting.

    All positions are designed to be human-readable (1-indexed).
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
    ENVELOPE = "envelope"  # ISA/IEA, GS/GE, ST/SE matching
    SCHEMA = "schema"  # Segment order, loops, required segments
    ELEMENT = "element"  # Data type, length validation
    CODE = "code"  # Invalid code values
    SEMANTIC = "semantic"  # Cross-field rules, conditional requirements


class RecoveryPoint(Enum):
    """Well-defined points where parser can resynchronize after error."""

    SEGMENT_BOUNDARY = "segment"  # After any segment terminator
    LOOP_START = "loop_start"  # At segment that starts a loop
    TRANSACTION_START = "st"  # At ST segment
    TRANSACTION_END = "se"  # At SE segment
    GROUP_START = "gs"  # At GS segment
    GROUP_END = "ge"  # At GE segment
    INTERCHANGE_END = "iea"  # At IEA segment


@dataclass
class ParseError:
    """
    A parse or validation error with full context.

    Designed to support both human-readable error messages and
    997/999 Functional Acknowledgment generation.
    """

    # Error identification
    code: str  # X12 error code (for 997 AK3/AK4/AK5)
    message: str  # Human-readable description
    category: ErrorCategory
    severity: ErrorSeverity = ErrorSeverity.ERROR

    # Location in source
    position: SourcePosition | None = None

    # Location in document structure (for 997)
    segment_tag: str | None = None
    segment_position: int | None = None  # Position in transaction (for AK3)
    element_position: int | None = None  # 1-indexed element (for AK4)
    component_position: int | None = None  # Sub-element position

    # Context
    loop_id: str | None = None
    transaction_id: str | None = None
    group_control: str | None = None

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
            "loop_id": self.loop_id,
            "expected": self.expected,
            "actual": self.actual,
        }


# =============================================================================
# Delimiters
# =============================================================================


@dataclass
class Delimiters:
    """
    X12 delimiter characters extracted from ISA segment.

    These are extracted from fixed positions in the ISA segment:
    - Position 3: Element separator (after "ISA")
    - Position 82: Repetition separator (ISA11 in 5010+)
    - Position 104: Component separator (ISA16)
    - Position 105: Segment terminator
    """

    element: str = "*"  # Element separator (most common: *)
    component: str = ":"  # Component separator for composites (: or >)
    repetition: str = "^"  # Repetition separator (^ or ~)
    segment: str = "~"  # Segment terminator (most common: ~)

    def __str__(self) -> str:
        return f"element={self.element!r} component={self.component!r} segment={self.segment!r}"


# =============================================================================
# Raw (Pre-Schema) AST Nodes
# =============================================================================


@dataclass
class RawElement:
    """
    A single parsed element value before schema validation.

    This represents a simple (non-composite) element.
    """

    value: str
    position: SourcePosition
    element_index: int  # 1-indexed position in segment

    def __str__(self) -> str:
        return self.value

    def is_empty(self) -> bool:
        return not self.value


@dataclass
class RawComposite:
    """
    A composite element with sub-elements before schema validation.

    Composites contain multiple components separated by the component delimiter.
    Example: "HC:99213" where HC is component 1 and 99213 is component 2.
    """

    components: list[str]
    position: SourcePosition
    element_index: int  # 1-indexed position in segment

    def __str__(self) -> str:
        return ":".join(self.components)

    def get_component(self, index: int) -> str | None:
        """Get component by 1-indexed position."""
        if 1 <= index <= len(self.components):
            return self.components[index - 1]
        return None

    def is_empty(self) -> bool:
        return not self.components or all(not c for c in self.components)


@dataclass
class RawSegment:
    """
    A parsed segment before schema validation.

    Contains the segment tag and all elements (simple or composite).
    """

    tag: str
    elements: list[RawElement | RawComposite]
    position: SourcePosition
    raw_text: str  # Original text for error messages

    def __str__(self) -> str:
        return f"{self.tag} ({len(self.elements)} elements)"

    def get_element(self, index: int) -> RawElement | RawComposite | None:
        """Get element by 1-indexed position (XX01, XX02, etc.)."""
        if 1 <= index <= len(self.elements):
            return self.elements[index - 1]
        return None

    def get_element_value(self, index: int) -> str | None:
        """Get simple element value by 1-indexed position."""
        elem = self.get_element(index)
        if elem is None:
            return None
        if isinstance(elem, RawElement):
            return elem.value
        if isinstance(elem, RawComposite):
            return elem.components[0] if elem.components else None
        return None


# =============================================================================
# Parsed (Schema-Aware) AST Nodes
# =============================================================================


@dataclass
class ParsedElement:
    """An element with schema information attached."""

    value: str
    raw: RawElement | RawComposite
    definition: "DataElement | None" = None
    errors: list[ParseError] = field(default_factory=list)

    # For composite elements
    is_composite: bool = False
    components: list[str] = field(default_factory=list)

    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def get_component(self, index: int) -> str | None:
        """Get component by 1-indexed position (for composites)."""
        if self.is_composite and self.components and 1 <= index <= len(self.components):
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
    position_in_transaction: int = 0  # For AK3 segment position

    def is_valid(self) -> bool:
        if self.errors:
            return False
        return all(e.is_valid() for e in self.elements)

    def get_element(self, index: int) -> ParsedElement | None:
        """Get element by 1-indexed position."""
        if 1 <= index <= len(self.elements):
            return self.elements[index - 1]
        return None


@dataclass
class LoopInstance:
    """
    An instance of a loop in the parsed document.

    Loops can contain segments and nested child loops.
    A loop may iterate multiple times in a document.
    """

    loop_id: str
    definition: "LoopDefinition | None" = None
    segments: list[ParsedSegment] = field(default_factory=list)
    children: list["LoopInstance"] = field(default_factory=list)
    iteration: int = 1  # Which iteration of this loop (1-indexed)
    errors: list[ParseError] = field(default_factory=list)

    # For HL-based loops
    hl_level_code: str | None = None

    def is_valid(self) -> bool:
        if self.errors:
            return False
        if not all(s.is_valid() for s in self.segments):
            return False
        return all(c.is_valid() for c in self.children)

    def all_segments(self) -> list[ParsedSegment]:
        """Get all segments including those in nested loops."""
        result = list(self.segments)
        for child in self.children:
            result.extend(child.all_segments())
        return result


# =============================================================================
# HL Hierarchy Nodes (for 856, 837, etc.)
# =============================================================================


@dataclass
class HLNode:
    """
    A node in an HL (Hierarchical Level) structure.

    Used for documents like 856 (ASN) and 837 (Claims) where the
    hierarchy is defined at runtime via HL segments.

    HL segment structure:
    - HL01: Hierarchical ID (unique within transaction)
    - HL02: Hierarchical Parent ID (empty for root)
    - HL03: Hierarchical Level Code (S=Shipment, O=Order, P=Pack, I=Item, etc.)
    - HL04: Hierarchical Child Code (0=no children, 1=has children)
    """

    hl_id: str  # HL01 - unique ID
    parent_id: str | None  # HL02 - parent's HL01
    level_code: str  # HL03 - type of level
    has_children: bool  # HL04 - whether children expected

    segments: list[ParsedSegment] = field(default_factory=list)
    children: list["HLNode"] = field(default_factory=list)
    parent: "HLNode | None" = None
    errors: list[ParseError] = field(default_factory=list)

    def __str__(self) -> str:
        return f"HL {self.hl_id} (level={self.level_code}, children={len(self.children)})"


# =============================================================================
# Transaction Set Instance
# =============================================================================


@dataclass
class TransactionSetInstance:
    """
    A parsed transaction set (ST...SE).

    Contains all parsed content organized by loops/segments,
    plus any errors encountered during parsing.
    """

    transaction_id: str  # ST01 - e.g., "850", "837"
    control_number: str  # ST02 - control number
    implementation_reference: str | None = None  # ST03 - e.g., "005010X222A1"

    schema: "TransactionSet | None" = None
    content: list[ParsedSegment | LoopInstance] = field(default_factory=list)

    # For HL-based documents (856, 837, 270, 271, etc.)
    hl_root: HLNode | None = None

    # Validation
    segment_count: int = 0  # From SE01
    actual_segment_count: int = 0  # Counted during parsing
    errors: list[ParseError] = field(default_factory=list)

    def __str__(self) -> str:
        return f"Transaction {self.transaction_id}-{self.control_number}"

    def is_valid(self) -> bool:
        if self.errors:
            return False
        for item in self.content:
            if isinstance(item, ParsedSegment) and not item.is_valid():
                return False
            if isinstance(item, LoopInstance) and not item.is_valid():
                return False
        return True

    def all_segments(self) -> list[ParsedSegment]:
        """Get all segments in order."""
        result = []
        for item in self.content:
            if isinstance(item, ParsedSegment):
                result.append(item)
            elif isinstance(item, LoopInstance):
                result.extend(item.all_segments())
        return result

    def all_errors(self) -> list[ParseError]:
        """Collect all errors from this transaction and its contents."""
        result = list(self.errors)
        for item in self.content:
            if isinstance(item, ParsedSegment):
                result.extend(item.errors)
                for elem in item.elements:
                    result.extend(elem.errors)
            elif isinstance(item, LoopInstance):
                result.extend(self._collect_loop_errors(item))
        return result

    def _collect_loop_errors(self, loop: LoopInstance) -> list[ParseError]:
        """Recursively collect errors from a loop."""
        result = list(loop.errors)
        for seg in loop.segments:
            result.extend(seg.errors)
            for elem in seg.elements:
                result.extend(elem.errors)
        for child in loop.children:
            result.extend(self._collect_loop_errors(child))
        return result


# =============================================================================
# Functional Group Instance
# =============================================================================


@dataclass
class FunctionalGroupInstance:
    """
    A parsed functional group (GS...GE).

    Contains one or more transaction sets of the same type.
    """

    functional_id: str  # GS01 - e.g., "PO", "IN", "HC"
    sender_id: str  # GS02
    receiver_id: str  # GS03
    date: str  # GS04 - CCYYMMDD
    time: str  # GS05 - HHMM
    control_number: str  # GS06
    responsible_agency: str  # GS07 - usually "X"
    version: str  # GS08 - e.g., "005010X222A1"

    transactions: list[TransactionSetInstance] = field(default_factory=list)

    # Validation
    transaction_count: int = 0  # From GE01
    errors: list[ParseError] = field(default_factory=list)

    def __str__(self) -> str:
        return f"Group {self.functional_id}-{self.control_number} ({len(self.transactions)} transactions)"

    def is_valid(self) -> bool:
        if self.errors:
            return False
        return all(t.is_valid() for t in self.transactions)

    def is_accepted(self) -> bool:
        """Check if group should be accepted (for 997)."""
        return self.is_valid()

    def all_errors(self) -> list[ParseError]:
        """Collect all errors from this group and its transactions."""
        result = list(self.errors)
        for txn in self.transactions:
            result.extend(txn.all_errors())
        return result


# =============================================================================
# Interchange Instance (Top Level)
# =============================================================================


@dataclass
class InterchangeInstance:
    """
    A complete parsed interchange (ISA...IEA).

    This is the top-level AST node representing an entire X12 document.
    """

    # ISA fields
    auth_qualifier: str  # ISA01
    auth_info: str  # ISA02
    security_qualifier: str  # ISA03
    security_info: str  # ISA04
    sender_qualifier: str  # ISA05
    sender_id: str  # ISA06
    receiver_qualifier: str  # ISA07
    receiver_id: str  # ISA08
    date: str  # ISA09 - YYMMDD
    time: str  # ISA10 - HHMM
    repetition_separator: str  # ISA11
    version: str  # ISA12 - e.g., "00501"
    control_number: str  # ISA13
    ack_requested: str  # ISA14 - "0" or "1"
    usage_indicator: str  # ISA15 - "P", "T", or "I"
    component_separator: str  # ISA16

    delimiters: Delimiters = field(default_factory=Delimiters)
    groups: list[FunctionalGroupInstance] = field(default_factory=list)

    # Validation
    group_count: int = 0  # From IEA01
    errors: list[ParseError] = field(default_factory=list)

    def __str__(self) -> str:
        return f"Interchange {self.control_number} ({len(self.groups)} groups)"

    def is_valid(self) -> bool:
        if self.errors:
            return False
        return all(g.is_valid() for g in self.groups)

    def is_test(self) -> bool:
        """Check if this is a test interchange."""
        return self.usage_indicator == "T"

    def is_production(self) -> bool:
        """Check if this is a production interchange."""
        return self.usage_indicator == "P"

    def all_errors(self) -> list[ParseError]:
        """Collect all errors from the entire interchange."""
        result = list(self.errors)
        for group in self.groups:
            result.extend(group.all_errors())
        return result

    def all_transactions(self) -> list[TransactionSetInstance]:
        """Get all transactions from all groups."""
        result = []
        for group in self.groups:
            result.extend(group.transactions)
        return result


# =============================================================================
# Parse Result
# =============================================================================


@dataclass
class ParseResult:
    """
    Complete result of parsing an X12 document.

    Contains the parsed interchange (if successful) plus all errors.
    Even with errors, partial results may be available.
    """

    interchange: InterchangeInstance | None = None
    errors: list[ParseError] = field(default_factory=list)
    warnings: list[ParseError] = field(default_factory=list)

    # Recovery statistics
    segments_parsed: int = 0
    segments_skipped: int = 0
    recovery_count: int = 0  # How many times we recovered from errors

    def is_valid(self) -> bool:
        """Check if document is completely valid (no errors)."""
        return len(self.errors) == 0 and (self.interchange is None or self.interchange.is_valid())

    def has_fatal_errors(self) -> bool:
        """Check if there are fatal errors that prevented parsing."""
        return any(e.severity == ErrorSeverity.FATAL for e in self.errors)

    def all_errors(self) -> list[ParseError]:
        """Get all errors including those attached to nodes."""
        result = list(self.errors)
        if self.interchange:
            result.extend(self.interchange.all_errors())
        return result

    def error_count(self) -> int:
        """Total number of errors."""
        return len(self.all_errors())

    def __str__(self) -> str:
        if self.interchange:
            status = "valid" if self.is_valid() else f"{self.error_count()} errors"
            return f"ParseResult: {self.interchange} - {status}"
        return f"ParseResult: Failed with {len(self.errors)} errors"
