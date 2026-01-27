"""
Loop Hierarchy Builder.

Builds a proper nested loop tree from the flat transaction set structure
defined in setdetl.txt.

The setdetl.txt uses these columns to define loop structure:
- Column 7 (loop_level): Nesting level (0 = not in loop, 1 = first level, 2 = nested, etc.)
- Column 8 (loop_repeat): How many times this loop can repeat (>1 = unlimited)
- Column 9 (loop_id): Non-empty = this segment starts a new loop with this ID

Algorithm:
1. Process segments in area/sequence order
2. When loop_id is non-empty, start a new loop at that level
3. Segments at same level without loop_id belong to current loop
4. Higher level = nested child loop
5. Lower level = pop back up to parent
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from edi_schema.x12.models.transaction import TransactionSet, TransactionSetSegment


@runtime_checkable
class HasStructure(Protocol):
    """Protocol for objects that provide transaction set structure."""

    def get_structure(self) -> list["TransactionSetSegment"]:
        """Get the list of segments in the transaction set."""
        ...


@dataclass
class LoopNode:
    """
    A node in the loop hierarchy tree.

    This represents either:
    - The ROOT node (contains top-level segments and child loops)
    - A LOOP node (has loop_id, contains segments that belong to the loop)

    Loops can be nested arbitrarily deep.
    """

    loop_id: str  # Loop identifier (e.g., "N1", "PO1", "ROOT")
    level: int  # Nesting level (0 = root, 1 = first level loop, etc.)
    max_repeat: int | str  # Maximum iterations (-1 or ">1" = unlimited)

    # Schema segments that belong directly to this loop
    segments: list["TransactionSetSegment"] = field(default_factory=list)

    # Child loops (nested within this loop)
    children: list["LoopNode"] = field(default_factory=list)

    # Parent loop (None for root)
    parent: "LoopNode | None" = None

    # For runtime tracking during parsing
    _segment_set: set[str] = field(default_factory=set, repr=False)
    _segment_index_map: dict[str, int] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        """Build segment set and index map for quick lookup."""
        self._segment_set = {s.segment_id for s in self.segments}
        self._segment_index_map = {s.segment_id: i for i, s in enumerate(self.segments)}

    def __str__(self) -> str:
        repeat_str = "unlimited" if self.max_repeat in (-1, ">1") else str(self.max_repeat)
        return f"Loop {self.loop_id} (level={self.level}, repeat={repeat_str}, {len(self.segments)} segs, {len(self.children)} children)"

    def __repr__(self) -> str:
        return self.__str__()

    def add_segment(self, segment: "TransactionSetSegment") -> None:
        """Add a segment to this loop."""
        self.segments.append(segment)
        self._segment_set.add(segment.segment_id)

    def add_child(self, child: "LoopNode") -> None:
        """Add a child loop."""
        child.parent = self
        self.children.append(child)

    def contains_segment(self, segment_id: str) -> bool:
        """Check if this loop (not children) contains the segment."""
        return segment_id in self._segment_set

    def get_segment_index(self, segment_id: str) -> int | None:
        """Get the index of a segment in this loop, or None if not found."""
        return self._segment_index_map.get(segment_id)

    def get_first_segment_id(self) -> str | None:
        """Get the ID of the first segment (loop trigger)."""
        if self.segments:
            return self.segments[0].segment_id
        return None

    def find_child_by_first_segment(self, segment_id: str) -> "LoopNode | None":
        """Find a child loop that starts with the given segment."""
        for child in self.children:
            if child.get_first_segment_id() == segment_id:
                return child
        return None

    def find_child_by_id(self, loop_id: str) -> "LoopNode | None":
        """Find a child loop by its loop ID."""
        for child in self.children:
            if child.loop_id == loop_id:
                return child
        return None

    def get_all_segment_ids(self) -> set[str]:
        """Get all segment IDs in this loop and all descendants."""
        result = set(self._segment_set)
        for child in self.children:
            result.update(child.get_all_segment_ids())
        return result

    def get_expected_segments(self) -> list[str]:
        """
        Get list of expected segment IDs at this level.

        Returns segments from this loop plus first segments of child loops.
        """
        result = [s.segment_id for s in self.segments]
        for child in self.children:
            first = child.get_first_segment_id()
            if first:
                result.append(first)
        return result

    def get_depth(self) -> int:
        """Get the maximum depth of this subtree."""
        if not self.children:
            return 1
        return 1 + max(child.get_depth() for child in self.children)

    def to_dict(self) -> dict:
        """Convert to dictionary for debugging/serialization."""
        return {
            "loop_id": self.loop_id,
            "level": self.level,
            "max_repeat": self.max_repeat,
            "segments": [s.segment_id for s in self.segments],
            "children": [c.to_dict() for c in self.children],
        }

    def print_tree(self, indent: int = 0) -> str:
        """Pretty print the loop tree."""
        lines = []
        prefix = "  " * indent
        repeat_str = "∞" if self.max_repeat in (-1, ">1") else str(self.max_repeat)

        lines.append(f"{prefix}[{self.loop_id}] (×{repeat_str})")

        for seg in self.segments:
            req = (
                seg.requirement.value if hasattr(seg.requirement, "value") else str(seg.requirement)
            )
            lines.append(f"{prefix}  - {seg.segment_id} ({req})")

        for child in self.children:
            lines.append(child.print_tree(indent + 1))

        return "\n".join(lines)


class LoopHierarchyBuilder:
    """
    Builds a proper nested loop tree from a TransactionSet's flat structure.

    The setdetl.txt structure uses loop_level to indicate nesting:
    - level 0: Not in any loop (top-level segments)
    - level 1: First level loop
    - level 2: Nested within a level 1 loop
    - etc.

    When a segment has a loop_id, it starts a new loop at that level.
    Subsequent segments at the same level belong to that loop until
    a new loop starts or the level decreases.

    Accepts either:
    - TransactionSet (has .structure attribute)
    - X12Schema (has .get_structure() method)
    """

    def __init__(self, schema: "TransactionSet | HasStructure"):
        self.schema = schema

    def _get_structure(self) -> list["TransactionSetSegment"]:
        """Get the structure from either TransactionSet or X12Schema."""
        # Try get_structure() method first (X12Schema)
        if hasattr(self.schema, "get_structure"):
            return self.schema.get_structure()
        # Fall back to .structure attribute (TransactionSet)
        if hasattr(self.schema, "structure"):
            return self.schema.structure
        raise TypeError("Schema must have 'structure' attribute or 'get_structure()' method")

    def build(self) -> LoopNode:
        """
        Build the complete loop hierarchy.

        Returns the ROOT node containing the entire structure.
        """
        # Create root node
        root = LoopNode(
            loop_id="ROOT",
            level=0,
            max_repeat=1,
            segments=[],
            children=[],
            parent=None,
        )

        # Stack of active loops at each level
        # Index = level, value = active loop at that level
        loop_stack: dict[int, LoopNode] = {0: root}

        # Process segments in order
        for seg in self._get_structure():
            level = seg.loop_level

            if level == 0:
                # Top-level segment (not in any loop)
                if seg.loop_id:
                    # This starts a level-0 "loop" (unusual but possible)
                    new_loop = LoopNode(
                        loop_id=seg.loop_id,
                        level=0,
                        max_repeat=seg.loop_repeat if seg.loop_repeat else 1,
                        segments=[seg],
                        children=[],
                    )
                    root.add_child(new_loop)
                    loop_stack[0] = new_loop
                else:
                    # Just a regular top-level segment
                    root.add_segment(seg)
            else:
                # Segment is in a loop
                if seg.loop_id:
                    # This segment starts a new loop
                    new_loop = LoopNode(
                        loop_id=seg.loop_id,
                        level=level,
                        max_repeat=seg.loop_repeat if seg.loop_repeat else 1,
                        segments=[seg],
                        children=[],
                    )

                    # Find parent loop (one level up)
                    parent_level = level - 1
                    parent_loop = loop_stack.get(parent_level, root)

                    # Add as child of parent
                    parent_loop.add_child(new_loop)

                    # Update stack - this is now the active loop at this level
                    loop_stack[level] = new_loop

                    # Clear any deeper levels (they're closed now)
                    for l in list(loop_stack.keys()):
                        if l > level:
                            del loop_stack[l]
                else:
                    # Segment belongs to current loop at this level
                    current_loop = loop_stack.get(level)
                    if current_loop:
                        current_loop.add_segment(seg)
                    else:
                        # No loop at this level yet - unusual, add to root
                        root.add_segment(seg)

        # Rebuild segment sets for all nodes
        self._rebuild_segment_sets(root)

        return root

    def _rebuild_segment_sets(self, node: LoopNode) -> None:
        """Recursively rebuild segment sets and index maps after tree construction."""
        node._segment_set = {s.segment_id for s in node.segments}
        node._segment_index_map = {s.segment_id: i for i, s in enumerate(node.segments)}
        for child in node.children:
            self._rebuild_segment_sets(child)


def build_loop_hierarchy(schema: "TransactionSet | HasStructure") -> LoopNode:
    """
    Convenience function to build loop hierarchy for a transaction set.

    Args:
        schema: The transaction set or X12Schema to build hierarchy for.
                Must have either a 'structure' attribute or 'get_structure()' method.

    Returns:
        Root LoopNode containing the complete hierarchy
    """
    builder = LoopHierarchyBuilder(schema)
    return builder.build()


# =============================================================================
# Loop Matching for Parsing
# =============================================================================


@dataclass
class LoopPosition:
    """
    Tracks current position within the loop hierarchy during parsing.

    This is used by the parser to know where it is in the expected
    document structure and to determine valid next segments.
    """

    current_loop: LoopNode
    segment_index: int = 0  # Index within current loop's segments
    iteration: int = 1  # Which iteration of the loop we're in
    parent_position: "LoopPosition | None" = None

    def get_expected_segments(self) -> list[str]:
        """Get list of segment IDs that are valid at current position."""
        expected = []

        # Remaining segments in current loop
        for i in range(self.segment_index, len(self.current_loop.segments)):
            expected.append(self.current_loop.segments[i].segment_id)

        # First segments of child loops
        for child in self.current_loop.children:
            first = child.get_first_segment_id()
            if first:
                expected.append(first)

        # First segment of current loop (for new iteration)
        first = self.current_loop.get_first_segment_id()
        if first and self._can_iterate():
            expected.append(first)

        return expected

    def _can_iterate(self) -> bool:
        """Check if another iteration of current loop is allowed."""
        max_rep = self.current_loop.max_repeat
        if max_rep in (-1, ">1"):
            return True
        try:
            return self.iteration < int(max_rep)
        except (ValueError, TypeError):
            return True

    def get_path(self) -> list[str]:
        """Get the path from root to current position."""
        path = []
        pos: LoopPosition | None = self
        while pos:
            path.append(f"{pos.current_loop.loop_id}[{pos.iteration}]")
            pos = pos.parent_position
        return list(reversed(path))


class LoopMatcher:
    """
    Matches parsed segments against the loop hierarchy schema.

    Supports error recovery by:
    1. Detecting out-of-order segments within a loop
    2. Finding valid child loops that match a segment
    3. Finding parent loops that match a segment (current loop ended)
    4. Detecting new loop iterations
    """

    def __init__(self, root: LoopNode):
        self.root = root
        self.position = LoopPosition(current_loop=root)

    def reset(self) -> None:
        """Reset matcher to start of document."""
        self.position = LoopPosition(current_loop=self.root)

    def skip_envelope_segments(self) -> None:
        """
        Skip past ST segment in the ROOT loop.

        Transaction content is parsed without ST/SE envelope segments
        (they're already handled by the document parser), but the schema
        includes them in ROOT. This method advances past ST so the first
        content segment (typically BEG, BGN, etc.) is expected.
        """
        if self.position.current_loop.loop_id == "ROOT":
            # Check if first segment is ST and skip it
            segs = self.position.current_loop.segments
            if segs and segs[0].segment_id == "ST":
                self.position.segment_index = 1

    def match_segment(self, segment_id: str) -> "MatchResult":
        """
        Attempt to match a segment ID against expected structure.

        Returns a MatchResult indicating what action to take.
        """
        current = self.position.current_loop

        # Strategy 1: Exact match at current position
        if self._is_expected_next(segment_id):
            return MatchResult(
                action=MatchAction.ACCEPT,
                loop=current,
                advance_segment=True,
            )

        # Strategy 2: New iteration of current loop (check BEFORE out-of-order)
        # This must be checked before out-of-order because the first segment
        # of a loop is also in the loop's segment list
        first_seg = current.get_first_segment_id()
        if segment_id == first_seg and self.position._can_iterate():
            return MatchResult(
                action=MatchAction.NEW_ITERATION,
                loop=current,
            )

        # Strategy 3: Segment in current loop but not at expected position
        seg_index = current.get_segment_index(segment_id)
        if seg_index is not None:
            current_index = self.position.segment_index
            if seg_index >= current_index:
                # Segment is ahead - just skipping optional segments, this is fine
                return MatchResult(
                    action=MatchAction.ACCEPT_SKIP,
                    loop=current,
                    advance_segment=True,
                    segment_schema_index=seg_index,
                )
            else:
                # Segment is behind current position - check if it can repeat
                seg_def = current.segments[seg_index]
                max_use = getattr(seg_def, "get_max_use_int", lambda: 1)()
                if max_use > 1 or max_use == -1:
                    # Segment can repeat - this is a valid repetition, not out of order
                    # Stay at current position (don't advance segment_index)
                    return MatchResult(
                        action=MatchAction.ACCEPT,
                        loop=current,
                        advance_segment=False,  # Don't move forward
                    )
                else:
                    # Segment cannot repeat - true out of order (backtracking)
                    return MatchResult(
                        action=MatchAction.ACCEPT_OUT_OF_ORDER,
                        loop=current,
                        message=f"Segment {segment_id} out of order in loop {current.loop_id}",
                    )

        # Strategy 4: Start of a child loop
        child_loop = current.find_child_by_first_segment(segment_id)
        if child_loop:
            return MatchResult(
                action=MatchAction.ENTER_CHILD_LOOP,
                loop=child_loop,
            )

        # Strategy 5: Segment belongs to a parent loop (current ended early)
        parent_loop, levels, child_loop, is_new_iteration = self._find_parent_containing(segment_id)
        if parent_loop:
            if child_loop:
                # Segment starts a child loop of a parent - enter that loop
                return MatchResult(
                    action=MatchAction.ENTER_SIBLING_LOOP,
                    loop=child_loop,
                    levels_popped=levels,
                    message=f"Loop {current.loop_id} ended, entering sibling {child_loop.loop_id}",
                )
            if is_new_iteration:
                # Segment starts a new iteration of a parent loop
                return MatchResult(
                    action=MatchAction.NEW_ITERATION_PARENT,
                    loop=parent_loop,
                    levels_popped=levels,
                    message=f"Loop {current.loop_id} ended, starting new iteration of {parent_loop.loop_id}",
                )
            return MatchResult(
                action=MatchAction.POP_TO_PARENT,
                loop=parent_loop,
                levels_popped=levels,
                message=f"Loop {current.loop_id} ended, returning to {parent_loop.loop_id}",
            )

        # Strategy 6: Segment starts a sibling loop at parent level
        if self.position.parent_position:
            parent = self.position.parent_position.current_loop
            sibling = parent.find_child_by_first_segment(segment_id)
            if sibling:
                return MatchResult(
                    action=MatchAction.ENTER_SIBLING_LOOP,
                    loop=sibling,
                    levels_popped=1,
                )

        # Strategy 7: Unknown segment - will be recorded as error
        return MatchResult(
            action=MatchAction.UNKNOWN_SEGMENT,
            loop=current,
            message=f"Unexpected segment {segment_id}",
            expected=self.position.get_expected_segments(),
        )

    def _is_expected_next(self, segment_id: str) -> bool:
        """Check if segment is the expected next segment."""
        segs = self.position.current_loop.segments
        idx = self.position.segment_index
        if idx < len(segs):
            return segs[idx].segment_id == segment_id
        return False

    def _find_parent_containing(
        self, segment_id: str
    ) -> tuple[LoopNode | None, int, LoopNode | None, bool]:
        """
        Find a parent loop that contains this segment.

        Returns (parent_loop, levels_popped, child_loop, is_new_iteration) or (None, 0, None, False) if not found.

        If child_loop is not None, the segment starts a child loop of parent_loop.
        If is_new_iteration is True, the segment starts a new iteration of parent_loop.
        """
        levels = 0
        pos = self.position.parent_position

        while pos:
            levels += 1
            loop = pos.current_loop

            # Check first segment for new iteration FIRST
            # (must come before contains_segment because the first segment is also in the loop)
            if loop.get_first_segment_id() == segment_id:
                return loop, levels, None, True

            # Check if segment is in this loop (but not at start position)
            if loop.contains_segment(segment_id):
                return loop, levels, None, False

            # Check if segment starts a child of this loop
            child = loop.find_child_by_first_segment(segment_id)
            if child:
                return loop, levels, child, False

            pos = pos.parent_position

        return None, 0, None, False

    def advance_to(self, result: "MatchResult") -> None:
        """Update position based on match result."""
        if result.action == MatchAction.ACCEPT:
            if result.advance_segment:
                self.position.segment_index += 1

        elif result.action == MatchAction.ACCEPT_SKIP:
            # Advance to position after the matched segment
            if result.segment_schema_index is not None:
                self.position.segment_index = result.segment_schema_index + 1
            else:
                self.position.segment_index += 1

        elif result.action == MatchAction.ACCEPT_OUT_OF_ORDER:
            # Don't advance index, segment was out of order
            pass

        elif result.action == MatchAction.ENTER_CHILD_LOOP:
            # Push current position and enter child
            new_pos = LoopPosition(
                current_loop=result.loop,
                segment_index=1,  # Already matched first segment
                iteration=1,
                parent_position=self.position,
            )
            self.position = new_pos

        elif result.action == MatchAction.NEW_ITERATION:
            # Increment iteration, reset segment index
            self.position.iteration += 1
            self.position.segment_index = 1  # Already matched first segment

        elif result.action in (MatchAction.POP_TO_PARENT, MatchAction.ENTER_SIBLING_LOOP, MatchAction.NEW_ITERATION_PARENT):
            # Pop back up to parent
            for _ in range(result.levels_popped):
                if self.position.parent_position:
                    self.position = self.position.parent_position

            if result.action == MatchAction.ENTER_SIBLING_LOOP:
                # Then enter the sibling
                new_pos = LoopPosition(
                    current_loop=result.loop,
                    segment_index=1,
                    iteration=1,
                    parent_position=self.position,
                )
                self.position = new_pos
            elif result.action == MatchAction.NEW_ITERATION_PARENT:
                # Start new iteration of the parent loop
                self.position.iteration += 1
                self.position.segment_index = 1  # Already matched first segment


class MatchAction:
    """Actions the parser can take based on segment matching."""

    ACCEPT = "accept"  # Segment matches expected position
    ACCEPT_SKIP = "accept_skip"  # Segment matches but skips optional segments
    ACCEPT_OUT_OF_ORDER = "accept_out_of_order"  # In current loop but wrong order
    ENTER_CHILD_LOOP = "enter_child_loop"  # Start a nested child loop
    ENTER_SIBLING_LOOP = "enter_sibling_loop"  # Pop and start sibling loop
    NEW_ITERATION = "new_iteration"  # Start another iteration of current loop
    NEW_ITERATION_PARENT = "new_iteration_parent"  # Pop and start new iteration of parent
    POP_TO_PARENT = "pop_to_parent"  # Return to parent loop
    UNKNOWN_SEGMENT = "unknown_segment"  # Doesn't match anything


@dataclass
class MatchResult:
    """Result of attempting to match a segment."""

    action: str  # One of MatchAction values
    loop: LoopNode  # The loop this segment belongs to (or current if unknown)
    advance_segment: bool = False
    levels_popped: int = 0
    message: str | None = None
    expected: list[str] | None = None
    segment_schema_index: int | None = None  # For ACCEPT_SKIP: index to advance to
