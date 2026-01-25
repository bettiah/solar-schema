"""
X12 Transaction Set Parser.

Parses transaction set content (the segments between ST and SE) using the
loop hierarchy schema. Produces a structured tree of ParsedSegment and
LoopInstance nodes.

Features:
- Schema-driven parsing using LoopMatcher
- HL (Hierarchical Level) segment support for 837/856 documents
- Error recovery with detailed error reporting
- Loop iteration tracking
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from edi_schema.x12.ast import (
    ErrorCategory,
    ErrorSeverity,
    LoopInstance,
    ParsedElement,
    ParsedSegment,
    ParseError,
    RawSegment,
    RecoveryPoint,
)
from edi_schema.x12.parser.loop_hierarchy import (
    LoopMatcher,
    LoopNode,
    MatchAction,
    build_loop_hierarchy,
)

if TYPE_CHECKING:
    from edi_schema.x12.schema import X12Schema


@dataclass
class HLNode:
    """
    Represents a node in an HL hierarchy.

    HL segments create dynamic parent-child relationships at runtime,
    used in 837 (healthcare claims), 856 (ASN), 270/271 (eligibility).
    """

    id: str  # HL01 - Hierarchical ID
    parent_id: str | None  # HL02 - Parent ID (None for root)
    level_code: str  # HL03 - Level code (20=provider, 22=subscriber, etc.)
    child_code: str  # HL04 - 1=has children, 0=no children

    # Parsed content
    hl_segment: RawSegment
    content_segments: list[RawSegment] = field(default_factory=list)
    children: list["HLNode"] = field(default_factory=list)

    # For tree building
    parent: "HLNode | None" = None

    def add_child(self, child: "HLNode") -> None:
        """Add a child HL node."""
        child.parent = self
        self.children.append(child)


class HLParser:
    """
    Parses HL (Hierarchical Level) segment hierarchies.

    HL segments define parent-child relationships at runtime:
    - HL*1**20*1 → ID=1, no parent, level=20 (billing provider), has children
    - HL*2*1*22*0 → ID=2, parent=1, level=22 (subscriber), no children

    Used in:
    - 837 Healthcare Claims (20=billing, 22=subscriber, 23=patient)
    - 856 Advance Ship Notice (S=shipment, O=order, P=pack, I=item)
    - 270/271 Eligibility (20=info source, 21=info receiver, 22=subscriber)
    """

    def __init__(self):
        self.nodes: dict[str, HLNode] = {}  # ID → Node
        self.roots: list[HLNode] = []
        self.errors: list[ParseError] = []

    def reset(self) -> None:
        """Reset parser state."""
        self.nodes = {}
        self.roots = []
        self.errors = []

    def process_hl(
        self,
        segment: RawSegment,
        position: int,
    ) -> tuple[HLNode | None, ParseError | None]:
        """
        Process an HL segment and add it to the hierarchy.

        Args:
            segment: The HL segment
            position: Position in transaction (for error reporting)

        Returns:
            Tuple of (HLNode, error) - error is None if successful
        """
        # Extract HL elements
        elements = segment.elements

        hl_id = elements[0].value if len(elements) > 0 else ""
        parent_id = elements[1].value if len(elements) > 1 and elements[1].value else None
        level_code = elements[2].value if len(elements) > 2 else ""
        child_code = elements[3].value if len(elements) > 3 else "0"

        error = None

        # Validate HL ID
        if not hl_id:
            error = ParseError(
                code="HL01",
                message="HL segment missing hierarchical ID (HL01)",
                category=ErrorCategory.SCHEMA,
                severity=ErrorSeverity.ERROR,
                position=segment.position,
                segment_tag="HL",
                segment_position=position,
                element_position=1,
            )
            return None, error

        # Check for duplicate ID
        if hl_id in self.nodes:
            error = ParseError(
                code="HL02",
                message=f"Duplicate HL ID: {hl_id}",
                category=ErrorCategory.SCHEMA,
                severity=ErrorSeverity.ERROR,
                position=segment.position,
                segment_tag="HL",
                segment_position=position,
                element_position=1,
            )
            # Continue anyway, use the new one

        # Validate parent reference
        parent_node = None
        if parent_id:
            parent_node = self.nodes.get(parent_id)
            if parent_node is None:
                error = ParseError(
                    code="HL03",
                    message=f"HL segment references non-existent parent: {parent_id}",
                    category=ErrorCategory.SCHEMA,
                    severity=ErrorSeverity.ERROR,
                    position=segment.position,
                    segment_tag="HL",
                    segment_position=position,
                    element_position=2,
                    recovery_point=RecoveryPoint.SEGMENT_BOUNDARY,
                )
                # Recovery: make it a root node
                parent_node = None

        # Create node
        node = HLNode(
            id=hl_id,
            parent_id=parent_id,
            level_code=level_code,
            child_code=child_code,
            hl_segment=segment,
            content_segments=[],
            children=[],
            parent=parent_node,
        )

        self.nodes[hl_id] = node

        if parent_node:
            parent_node.add_child(node)
        else:
            self.roots.append(node)

        return node, error

    def add_content_to_current(
        self,
        segment: RawSegment,
        current_node: HLNode | None,
    ) -> None:
        """Add a content segment to the current HL node."""
        if current_node:
            current_node.content_segments.append(segment)

    def get_hierarchy(self) -> list[HLNode]:
        """Get the root nodes of the HL hierarchy."""
        return self.roots

    def to_loop_instances(
        self,
        node: HLNode,
        loop_id_prefix: str = "HL",
    ) -> LoopInstance:
        """
        Convert an HLNode tree to LoopInstance tree.

        Args:
            node: The HLNode to convert
            loop_id_prefix: Prefix for loop IDs

        Returns:
            LoopInstance representing this HL subtree
        """
        # Create parsed segments from content
        parsed_segments = []

        # Add HL segment itself
        parsed_segments.append(self._to_parsed_segment(node.hl_segment))

        # Add content segments
        for seg in node.content_segments:
            parsed_segments.append(self._to_parsed_segment(seg))

        # Create loop instance
        loop = LoopInstance(
            loop_id=f"{loop_id_prefix}_{node.level_code}",
            definition=None,  # HL loops are dynamic
            segments=parsed_segments,
            children=[],
            iteration=1,
            hl_level_code=node.level_code,
            errors=[],
        )

        # Convert children
        for child in node.children:
            loop.children.append(self.to_loop_instances(child, loop_id_prefix))

        return loop

    def _to_parsed_segment(self, raw: RawSegment) -> ParsedSegment:
        """Convert a RawSegment to ParsedSegment."""
        parsed_elements = []
        for elem in raw.elements:
            if hasattr(elem, "value"):
                parsed_elements.append(
                    ParsedElement(
                        value=elem.value,
                        raw=elem,
                        definition=None,
                        errors=[],
                    )
                )
            elif hasattr(elem, "components"):
                # Composite - join for now
                parsed_elements.append(
                    ParsedElement(
                        value=elem.components[0] if elem.components else "",
                        raw=elem,
                        definition=None,
                        errors=[],
                        is_composite=True,
                        components=elem.components,
                    )
                )
            else:
                parsed_elements.append(
                    ParsedElement(
                        value=str(elem),
                        raw=elem,
                        definition=None,
                        errors=[],
                    )
                )

        return ParsedSegment(
            tag=raw.tag,
            elements=parsed_elements,
            raw=raw,
            definition=None,
            errors=[],
        )


@dataclass
class TransactionParserState:
    """Tracks parser state during transaction parsing."""

    in_hl_loop: bool = False
    current_hl_node: HLNode | None = None
    loop_iterations: dict[str, int] = field(default_factory=dict)


class TransactionParser:
    """
    Parses transaction set content using schema-driven loop matching.

    This parser takes the raw segments from a transaction set (between ST
    and SE) and organizes them into a proper loop hierarchy using the schema.

    Features:
    - Schema-driven parsing with LoopMatcher
    - HL segment hierarchy support
    - Error recovery for out-of-order segments
    - Detailed error reporting for schema violations
    """

    def __init__(self, schema: "X12Schema | None" = None):
        """
        Initialize the parser.

        Args:
            schema: Optional X12Schema for loop matching. If not provided,
                   parsing will be done without schema validation.
        """
        self.schema = schema
        self.loop_hierarchy: LoopNode | None = None
        self.matcher: LoopMatcher | None = None
        self.hl_parser: HLParser = HLParser()
        self.errors: list[ParseError] = []
        self.state: TransactionParserState = TransactionParserState()

        if schema:
            # Use pre-built loop_hierarchy from schema if available
            if schema.loop_hierarchy is not None:
                self.loop_hierarchy = schema.loop_hierarchy
            else:
                self.loop_hierarchy = build_loop_hierarchy(schema)
            self.matcher = LoopMatcher(self.loop_hierarchy)

    def parse(
        self,
        segments: list[RawSegment],
        transaction_id: str,
    ) -> list[ParsedSegment | LoopInstance]:
        """
        Parse transaction content into structured loop instances.

        Args:
            segments: Raw segments from the transaction (excluding ST/SE)
            transaction_id: Transaction set ID (e.g., "850", "837")

        Returns:
            List of ParsedSegment and LoopInstance representing the structure
        """
        self.errors = []
        self.state = TransactionParserState()
        self.hl_parser.reset()

        # Check if this transaction uses HL hierarchies
        uses_hl = self._uses_hl_hierarchy(transaction_id)

        if uses_hl:
            return self._parse_with_hl(segments)
        elif self.matcher:
            return self._parse_with_schema(segments)
        else:
            return self._parse_without_schema(segments)

    def _uses_hl_hierarchy(self, transaction_id: str) -> bool:
        """
        Check if this transaction type uses HL hierarchies.

        HL-based transactions:
        - 837 (Healthcare Claim)
        - 856 (Advance Ship Notice)
        - 270 (Eligibility Inquiry)
        - 271 (Eligibility Response)
        - 278 (Authorization Request/Response)
        - 835 (with HL in some versions)
        """
        # Check if any segments are HL
        return transaction_id in ("837", "856", "270", "271", "278")

    def _parse_with_hl(
        self,
        segments: list[RawSegment],
    ) -> list[ParsedSegment | LoopInstance]:
        """
        Parse a transaction that uses HL hierarchies.

        HL transactions have a different structure:
        - Header segments (before first HL)
        - HL hierarchy (HL segments with content)
        - Trailer segments (after last HL content)
        """
        result: list[ParsedSegment | LoopInstance] = []
        current_hl: HLNode | None = None
        position = 0

        for i, segment in enumerate(segments):
            position = i + 1  # 1-indexed

            if segment.tag == "HL":
                # Process HL segment
                node, error = self.hl_parser.process_hl(segment, position)
                if error:
                    self.errors.append(error)
                current_hl = node
                self.state.current_hl_node = node
                self.state.in_hl_loop = True

            elif self.state.in_hl_loop and current_hl:
                # Add segment to current HL node
                self.hl_parser.add_content_to_current(segment, current_hl)

            else:
                # Header or trailer segment (outside HL)
                result.append(self._to_parsed_segment(segment))

        # Convert HL hierarchy to LoopInstances
        for root in self.hl_parser.get_hierarchy():
            result.append(self.hl_parser.to_loop_instances(root))

        # Add HL parser errors
        self.errors.extend(self.hl_parser.errors)

        return result

    def _parse_with_schema(
        self,
        segments: list[RawSegment],
    ) -> list[ParsedSegment | LoopInstance]:
        """
        Parse using schema-driven loop matching.
        """
        if not self.matcher or not self.loop_hierarchy:
            return self._parse_without_schema(segments)

        self.matcher.reset()
        result: list[ParsedSegment | LoopInstance] = []

        # Track current loop for building LoopInstances
        loop_stack: list[tuple[LoopNode, LoopInstance]] = []
        root_content: list[ParsedSegment | LoopInstance] = []

        for i, segment in enumerate(segments):
            position = i + 1  # 1-indexed

            # Match segment against schema
            match_result = self.matcher.match_segment(segment.tag)

            # Handle match result
            if match_result.action == MatchAction.ACCEPT:
                # Normal case - segment matches expected position
                parsed = self._to_parsed_segment(segment)
                self._add_to_current_loop(parsed, loop_stack, root_content)
                self.matcher.advance_to(match_result)

            elif match_result.action == MatchAction.ACCEPT_OUT_OF_ORDER:
                # Segment is valid but out of order
                self.errors.append(
                    ParseError(
                        code="SCH01",
                        message=match_result.message or f"Segment {segment.tag} out of order",
                        category=ErrorCategory.SCHEMA,
                        severity=ErrorSeverity.WARNING,
                        position=segment.position,
                        segment_tag=segment.tag,
                        segment_position=position,
                        recovery_point=RecoveryPoint.SEGMENT_BOUNDARY,
                    )
                )
                parsed = self._to_parsed_segment(segment)
                self._add_to_current_loop(parsed, loop_stack, root_content)

            elif match_result.action == MatchAction.ENTER_CHILD_LOOP:
                # Start a new child loop
                loop_node = match_result.loop
                iteration = self._get_next_iteration(loop_node.loop_id)

                loop_instance = LoopInstance(
                    loop_id=loop_node.loop_id,
                    definition=None,  # TODO: Link to definition
                    segments=[],
                    children=[],
                    iteration=iteration,
                    errors=[],
                )

                # Add loop to parent
                if loop_stack:
                    loop_stack[-1][1].children.append(loop_instance)
                else:
                    root_content.append(loop_instance)

                loop_stack.append((loop_node, loop_instance))

                # Add the segment that started the loop
                parsed = self._to_parsed_segment(segment)
                loop_instance.segments.append(parsed)

                self.matcher.advance_to(match_result)

            elif match_result.action == MatchAction.ENTER_SIBLING_LOOP:
                # Pop current loop and start sibling
                if loop_stack:
                    loop_stack.pop()

                loop_node = match_result.loop
                iteration = self._get_next_iteration(loop_node.loop_id)

                loop_instance = LoopInstance(
                    loop_id=loop_node.loop_id,
                    definition=None,
                    segments=[],
                    children=[],
                    iteration=iteration,
                    errors=[],
                )

                if loop_stack:
                    loop_stack[-1][1].children.append(loop_instance)
                else:
                    root_content.append(loop_instance)

                loop_stack.append((loop_node, loop_instance))

                parsed = self._to_parsed_segment(segment)
                loop_instance.segments.append(parsed)

                self.matcher.advance_to(match_result)

            elif match_result.action == MatchAction.NEW_ITERATION:
                # Start new iteration of current loop
                if loop_stack:
                    loop_node = loop_stack[-1][0]
                    loop_stack.pop()

                    iteration = self._get_next_iteration(loop_node.loop_id)

                    # Check cardinality
                    max_rep = loop_node.max_repeat
                    if max_rep not in (-1, ">1"):
                        try:
                            if iteration > int(max_rep):
                                self.errors.append(
                                    ParseError(
                                        code="SCH02",
                                        message=f"Loop {loop_node.loop_id} exceeds maximum iterations ({max_rep})",
                                        category=ErrorCategory.SCHEMA,
                                        severity=ErrorSeverity.WARNING,
                                        position=segment.position,
                                        segment_tag=segment.tag,
                                        segment_position=position,
                                        loop_id=loop_node.loop_id,
                                    )
                                )
                        except (ValueError, TypeError):
                            pass

                    loop_instance = LoopInstance(
                        loop_id=loop_node.loop_id,
                        definition=None,
                        segments=[],
                        children=[],
                        iteration=iteration,
                        errors=[],
                    )

                    # Add to parent of previous iteration
                    if loop_stack:
                        loop_stack[-1][1].children.append(loop_instance)
                    else:
                        root_content.append(loop_instance)

                    loop_stack.append((loop_node, loop_instance))

                    parsed = self._to_parsed_segment(segment)
                    loop_instance.segments.append(parsed)

                self.matcher.advance_to(match_result)

            elif match_result.action == MatchAction.POP_TO_PARENT:
                # Pop back up to parent loop
                for _ in range(match_result.levels_popped):
                    if loop_stack:
                        loop_stack.pop()

                parsed = self._to_parsed_segment(segment)
                self._add_to_current_loop(parsed, loop_stack, root_content)

                self.matcher.advance_to(match_result)

            elif match_result.action == MatchAction.UNKNOWN_SEGMENT:
                # Segment doesn't match schema
                self.errors.append(
                    ParseError(
                        code="SCH03",
                        message=f"Unexpected segment {segment.tag}",
                        category=ErrorCategory.SCHEMA,
                        severity=ErrorSeverity.ERROR,
                        position=segment.position,
                        segment_tag=segment.tag,
                        segment_position=position,
                        expected=", ".join(match_result.expected or []),
                        recovery_point=RecoveryPoint.SEGMENT_BOUNDARY,
                    )
                )

                # Still add the segment to current position (recovery)
                parsed = self._to_parsed_segment(segment)
                parsed.errors.append(self.errors[-1])
                self._add_to_current_loop(parsed, loop_stack, root_content)

            else:
                # Fallback - just add segment
                parsed = self._to_parsed_segment(segment)
                self._add_to_current_loop(parsed, loop_stack, root_content)

        return root_content

    def _parse_without_schema(
        self,
        segments: list[RawSegment],
    ) -> list[ParsedSegment | LoopInstance]:
        """
        Parse without schema - just convert segments.

        This is used when no schema is available or for simple parsing.
        """
        result: list[ParsedSegment | LoopInstance] = []

        for segment in segments:
            result.append(self._to_parsed_segment(segment))

        return result

    def _add_to_current_loop(
        self,
        segment: ParsedSegment,
        loop_stack: list[tuple[LoopNode, LoopInstance]],
        root_content: list[ParsedSegment | LoopInstance],
    ) -> None:
        """Add a segment to the current loop or root."""
        if loop_stack:
            loop_stack[-1][1].segments.append(segment)
        else:
            root_content.append(segment)

    def _get_next_iteration(self, loop_id: str) -> int:
        """Get the next iteration number for a loop."""
        current = self.state.loop_iterations.get(loop_id, 0)
        next_iter = current + 1
        self.state.loop_iterations[loop_id] = next_iter
        return next_iter

    def _to_parsed_segment(self, raw: RawSegment) -> ParsedSegment:
        """Convert a RawSegment to ParsedSegment."""
        parsed_elements = []
        for elem in raw.elements:
            if hasattr(elem, "value"):
                parsed_elements.append(
                    ParsedElement(
                        value=elem.value,
                        raw=elem,
                        definition=None,
                        errors=[],
                    )
                )
            elif hasattr(elem, "components"):
                # Composite
                parsed_elements.append(
                    ParsedElement(
                        value=elem.components[0] if elem.components else "",
                        raw=elem,
                        definition=None,
                        errors=[],
                        is_composite=True,
                        components=elem.components,
                    )
                )
            else:
                parsed_elements.append(
                    ParsedElement(
                        value=str(elem),
                        raw=elem,
                        definition=None,
                        errors=[],
                    )
                )

        return ParsedSegment(
            tag=raw.tag,
            elements=parsed_elements,
            raw=raw,
            definition=None,
            errors=[],
        )


def parse_transaction(
    segments: list[RawSegment],
    transaction_id: str,
    schema: "X12Schema | None" = None,
) -> tuple[list[ParsedSegment | LoopInstance], list[ParseError]]:
    """
    Convenience function to parse a transaction set.

    Args:
        segments: Raw segments from the transaction (excluding ST/SE)
        transaction_id: Transaction set ID (e.g., "850", "837")
        schema: Optional schema for loop matching

    Returns:
        Tuple of (parsed content, errors)
    """
    parser = TransactionParser(schema)
    content = parser.parse(segments, transaction_id)
    return content, parser.errors
