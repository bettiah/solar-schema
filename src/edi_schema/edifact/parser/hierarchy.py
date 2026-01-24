"""
Segment Group Hierarchy Builder.

Builds a proper nested group tree from the EDIFACT message structure
defined in the schema. Unlike X12 loops (which use level numbers),
EDIFACT segment groups are explicitly nested in the MessageSpec structure.

EDIFACT message structure example:
    00010   UNH Message header                    M   1
    00020   BGM Beginning of message              M   1
    ...
    00120       ---- Segment group 1  ----------- C   99999----+
    00130   RFF Reference                         M   1        |
    00140   DTM Date/time/period                  C   5--------+
    00150       ---- Segment group 2  ----------- C   99999----+||
    00160   NAD Name and address                  M   1        |||
    00170       ---- Segment group 3  ----------- C   99999---+|||
    00180   RFF Reference                         M   1       ||||
    00190   DTM Date/time/period                  C   5-------+|||

The nesting is tracked by the trailing +, |, ++ markers.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edi_schema.edifact.models import (
        MessageSpec,
        ResolvedMessageSpec,
        SegmentRef,
    )


@dataclass
class GroupNode:
    """
    A node in the segment group hierarchy tree.

    This represents either:
    - The ROOT node (contains top-level segments and child groups)
    - A GROUP node (has group_number, contains segments that belong to the group)

    Groups can be nested arbitrarily deep.
    """

    group_number: int | None  # None for root, 1, 2, 3... for groups
    max_repeat: int  # Maximum iterations (-1 or large number = unlimited)
    mandatory: bool  # Whether this group is required

    # Schema segment references that belong directly to this group
    segment_refs: list["SegmentRef"] = field(default_factory=list)

    # Child groups (nested within this group)
    children: list["GroupNode"] = field(default_factory=list)

    # Parent group (None for root)
    parent: "GroupNode | None" = None

    # For runtime tracking during parsing
    _segment_set: set[str] = field(default_factory=set, repr=False)
    _trigger_tag: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Build segment set and determine trigger tag."""
        self._rebuild_segment_set()

    def _rebuild_segment_set(self) -> None:
        """Rebuild the set of segment tags in this group."""
        self._segment_set = {ref.segment_tag for ref in self.segment_refs}
        # Trigger is the first segment (usually mandatory)
        if self.segment_refs:
            self._trigger_tag = self.segment_refs[0].segment_tag

    def __str__(self) -> str:
        name = f"SG{self.group_number}" if self.group_number else "ROOT"
        repeat_str = "unlimited" if self.max_repeat >= 99999 else str(self.max_repeat)
        req = "M" if self.mandatory else "C"
        return f"{name} ({req}, ×{repeat_str}, {len(self.segment_refs)} segs, {len(self.children)} children)"

    def __repr__(self) -> str:
        return self.__str__()

    @property
    def trigger_tag(self) -> str | None:
        """Get the trigger segment tag (first segment that starts this group)."""
        return self._trigger_tag

    def add_segment_ref(self, ref: "SegmentRef") -> None:
        """Add a segment reference to this group."""
        self.segment_refs.append(ref)
        self._segment_set.add(ref.segment_tag)
        if self._trigger_tag is None:
            self._trigger_tag = ref.segment_tag

    def add_child(self, child: "GroupNode") -> None:
        """Add a child group."""
        child.parent = self
        self.children.append(child)

    def contains_segment(self, segment_tag: str) -> bool:
        """Check if this group (not children) contains the segment."""
        return segment_tag in self._segment_set

    def find_child_by_trigger(self, segment_tag: str) -> "GroupNode | None":
        """Find a child group that is triggered by the given segment."""
        for child in self.children:
            if child.trigger_tag == segment_tag:
                return child
        return None

    def find_child_by_number(self, group_number: int) -> "GroupNode | None":
        """Find a child group by its group number."""
        for child in self.children:
            if child.group_number == group_number:
                return child
        return None

    def get_all_segment_tags(self) -> set[str]:
        """Get all segment tags in this group and all descendants."""
        result = set(self._segment_set)
        for child in self.children:
            result.update(child.get_all_segment_tags())
        return result

    def get_expected_segments(self) -> list[str]:
        """
        Get list of expected segment tags at this level.

        Returns segments from this group plus trigger segments of child groups.
        """
        result = [ref.segment_tag for ref in self.segment_refs]
        for child in self.children:
            if child.trigger_tag:
                result.append(child.trigger_tag)
        return result

    def get_depth(self) -> int:
        """Get the maximum depth of this subtree."""
        if not self.children:
            return 1
        return 1 + max(child.get_depth() for child in self.children)

    def get_path(self) -> list[int | None]:
        """Get the path from root to this node (list of group numbers)."""
        path: list[int | None] = []
        node: GroupNode | None = self
        while node:
            path.append(node.group_number)
            node = node.parent
        return list(reversed(path))

    def to_dict(self) -> dict:
        """Convert to dictionary for debugging/serialization."""
        return {
            "group_number": self.group_number,
            "max_repeat": self.max_repeat,
            "mandatory": self.mandatory,
            "trigger_tag": self._trigger_tag,
            "segments": [ref.segment_tag for ref in self.segment_refs],
            "children": [c.to_dict() for c in self.children],
        }

    def print_tree(self, indent: int = 0) -> str:
        """Pretty print the group tree."""
        lines = []
        prefix = "  " * indent
        name = f"SG{self.group_number}" if self.group_number else "ROOT"
        repeat_str = "∞" if self.max_repeat >= 99999 else str(self.max_repeat)
        req = "M" if self.mandatory else "C"

        lines.append(f"{prefix}[{name}] ({req} ×{repeat_str})")

        for ref in self.segment_refs:
            req_char = "M" if ref.mandatory else "C"
            lines.append(f"{prefix}  - {ref.segment_tag} ({req_char})")

        for child in self.children:
            lines.append(child.print_tree(indent + 1))

        return "\n".join(lines)


class GroupHierarchyBuilder:
    """
    Builds a proper nested group tree from an EDIFACT MessageSpec or ResolvedMessageSpec.

    The EDIFACT message structure already contains nested SegmentGroup objects,
    so this builder primarily converts that into a more parser-friendly tree
    structure with quick lookup capabilities.
    """

    def __init__(self, spec: "MessageSpec | ResolvedMessageSpec"):
        """
        Initialize the builder.

        Args:
            spec: MessageSpec or ResolvedMessageSpec to build hierarchy from
        """
        self.spec = spec

    def _get_structure(self) -> list:
        """Get the structure list from the spec."""
        if hasattr(self.spec, "spec"):
            # ResolvedMessageSpec
            return self.spec.spec.structure
        if hasattr(self.spec, "structure"):
            # MessageSpec
            return self.spec.structure
        raise TypeError("Spec must have 'structure' attribute")

    def build(self) -> GroupNode:
        """
        Build the complete group hierarchy.

        Returns:
            Root GroupNode containing the entire structure
        """
        root = GroupNode(
            group_number=None,
            max_repeat=1,
            mandatory=True,
            segment_refs=[],
            children=[],
            parent=None,
        )

        structure = self._get_structure()
        self._process_items(structure, root)

        return root

    def _process_items(
        self,
        items: list,
        parent: GroupNode,
    ) -> None:
        """
        Process a list of SegmentRef and SegmentGroup items.

        Args:
            items: List of SegmentRef or SegmentGroup from schema
            parent: Parent GroupNode to add items to
        """
        from edi_schema.edifact.models import SegmentGroup, SegmentRef

        for item in items:
            if isinstance(item, SegmentRef):
                # Add segment reference to parent group
                parent.add_segment_ref(item)
            elif isinstance(item, SegmentGroup):
                # Create child group node
                child = GroupNode(
                    group_number=item.number,
                    max_repeat=item.max_repeat,
                    mandatory=item.mandatory,
                    segment_refs=[],
                    children=[],
                )
                parent.add_child(child)

                # Recursively process children
                self._process_items(item.children, child)


def build_group_hierarchy(spec: "MessageSpec | ResolvedMessageSpec") -> GroupNode:
    """
    Convenience function to build group hierarchy for a message spec.

    Args:
        spec: The MessageSpec or ResolvedMessageSpec to build hierarchy for

    Returns:
        Root GroupNode containing the complete hierarchy
    """
    builder = GroupHierarchyBuilder(spec)
    return builder.build()


# =============================================================================
# Group Matching for Parsing
# =============================================================================


@dataclass
class GroupPosition:
    """
    Tracks current position within the group hierarchy during parsing.

    This is used by the parser to know where it is in the expected
    document structure and to determine valid next segments.
    """

    current_group: GroupNode
    segment_index: int = 0  # Index within current group's segment_refs
    iteration: int = 1  # Which iteration of the group we're in
    parent_position: "GroupPosition | None" = None

    def get_expected_segments(self) -> list[str]:
        """Get list of segment tags that are valid at current position."""
        expected = []

        # Remaining segments in current group
        for i in range(self.segment_index, len(self.current_group.segment_refs)):
            expected.append(self.current_group.segment_refs[i].segment_tag)

        # Trigger segments of child groups
        for child in self.current_group.children:
            if child.trigger_tag:
                expected.append(child.trigger_tag)

        # Trigger segment of current group (for new iteration)
        trigger = self.current_group.trigger_tag
        if trigger and self._can_iterate():
            expected.append(trigger)

        return expected

    def _can_iterate(self) -> bool:
        """Check if another iteration of current group is allowed."""
        max_rep = self.current_group.max_repeat
        if max_rep >= 99999:
            return True
        return self.iteration < max_rep

    def get_path(self) -> list[str]:
        """Get the path from root to current position."""
        path = []
        pos: GroupPosition | None = self
        while pos:
            name = (
                f"SG{pos.current_group.group_number}" if pos.current_group.group_number else "ROOT"
            )
            path.append(f"{name}[{pos.iteration}]")
            pos = pos.parent_position
        return list(reversed(path))


class MatchAction:
    """Actions the parser can take based on segment matching."""

    ACCEPT = "accept"  # Segment matches expected position
    ACCEPT_OUT_OF_ORDER = "accept_out_of_order"  # In current group but wrong order
    ENTER_CHILD_GROUP = "enter_child_group"  # Start a nested child group
    ENTER_SIBLING_GROUP = "enter_sibling_group"  # Pop and start sibling group
    NEW_ITERATION = "new_iteration"  # Start another iteration of current group
    POP_TO_PARENT = "pop_to_parent"  # Return to parent group
    UNKNOWN_SEGMENT = "unknown_segment"  # Doesn't match anything


@dataclass
class MatchResult:
    """Result of attempting to match a segment."""

    action: str  # One of MatchAction values
    group: GroupNode  # The group this segment belongs to (or current if unknown)
    advance_segment: bool = False
    levels_popped: int = 0
    message: str | None = None
    expected: list[str] | None = None


class GroupMatcher:
    """
    Matches parsed segments against the group hierarchy schema.

    Supports error recovery by:
    1. Detecting out-of-order segments within a group
    2. Finding valid child groups that match a segment
    3. Finding parent groups that match a segment (current group ended)
    4. Detecting new group iterations
    """

    def __init__(self, root: GroupNode):
        self.root = root
        self.position = GroupPosition(current_group=root)

    def reset(self) -> None:
        """Reset matcher to start of document."""
        self.position = GroupPosition(current_group=self.root)

    def match_segment(self, segment_tag: str) -> MatchResult:
        """
        Attempt to match a segment tag against expected structure.

        Args:
            segment_tag: The segment tag to match (e.g., "NAD", "DTM")

        Returns:
            MatchResult indicating what action to take
        """
        current = self.position.current_group

        # Strategy 1: Exact match at current position
        if self._is_expected_next(segment_tag):
            return MatchResult(
                action=MatchAction.ACCEPT,
                group=current,
                advance_segment=True,
            )

        # Strategy 2: Start of a child group
        child_group = current.find_child_by_trigger(segment_tag)
        if child_group:
            return MatchResult(
                action=MatchAction.ENTER_CHILD_GROUP,
                group=child_group,
            )

        # Strategy 3: New iteration of current group (check before out-of-order
        # because the trigger segment is also in the group's segment set)
        trigger = current.trigger_tag
        if segment_tag == trigger and self.position._can_iterate():
            return MatchResult(
                action=MatchAction.NEW_ITERATION,
                group=current,
            )

        # Strategy 4: Out of order within current group
        if current.contains_segment(segment_tag):
            return MatchResult(
                action=MatchAction.ACCEPT_OUT_OF_ORDER,
                group=current,
                message=f"Segment {segment_tag} out of order in group",
            )

        # Strategy 5: Segment belongs to a parent group (current ended early)
        parent_group, levels = self._find_parent_containing(segment_tag)
        if parent_group:
            return MatchResult(
                action=MatchAction.POP_TO_PARENT,
                group=parent_group,
                levels_popped=levels,
                message="Group ended, returning to parent",
            )

        # Strategy 6: Segment starts a sibling group at parent level
        if self.position.parent_position:
            parent = self.position.parent_position.current_group
            sibling = parent.find_child_by_trigger(segment_tag)
            if sibling:
                return MatchResult(
                    action=MatchAction.ENTER_SIBLING_GROUP,
                    group=sibling,
                    levels_popped=1,
                )

        # Strategy 7: Unknown segment - will be recorded as error
        return MatchResult(
            action=MatchAction.UNKNOWN_SEGMENT,
            group=current,
            message=f"Unexpected segment {segment_tag}",
            expected=self.position.get_expected_segments(),
        )

    def _is_expected_next(self, segment_tag: str) -> bool:
        """Check if segment is the expected next segment."""
        refs = self.position.current_group.segment_refs
        idx = self.position.segment_index
        if idx < len(refs):
            return refs[idx].segment_tag == segment_tag
        return False

    def _find_parent_containing(self, segment_tag: str) -> tuple[GroupNode | None, int]:
        """
        Find a parent group that contains this segment.

        Returns:
            Tuple of (group, levels_popped) or (None, 0) if not found
        """
        levels = 0
        pos = self.position.parent_position

        while pos:
            levels += 1
            group = pos.current_group

            # Check if segment is in this group
            if group.contains_segment(segment_tag):
                return group, levels

            # Check if segment triggers a child of this group
            child = group.find_child_by_trigger(segment_tag)
            if child:
                return group, levels

            # Check trigger segment for new iteration
            if group.trigger_tag == segment_tag:
                return group, levels

            pos = pos.parent_position

        return None, 0

    def advance_to(self, result: MatchResult) -> None:
        """Update position based on match result."""
        if result.action == MatchAction.ACCEPT:
            self.position.segment_index += 1

        elif result.action == MatchAction.ACCEPT_OUT_OF_ORDER:
            # Don't advance index, segment was out of order
            pass

        elif result.action == MatchAction.ENTER_CHILD_GROUP:
            # Push current position and enter child
            new_pos = GroupPosition(
                current_group=result.group,
                segment_index=1,  # Already matched trigger segment
                iteration=1,
                parent_position=self.position,
            )
            self.position = new_pos

        elif result.action == MatchAction.NEW_ITERATION:
            # Increment iteration, reset segment index
            self.position.iteration += 1
            self.position.segment_index = 1  # Already matched trigger segment

        elif result.action in (MatchAction.POP_TO_PARENT, MatchAction.ENTER_SIBLING_GROUP):
            # Pop back up to parent
            for _ in range(result.levels_popped):
                if self.position.parent_position:
                    self.position = self.position.parent_position

            if result.action == MatchAction.ENTER_SIBLING_GROUP:
                # Then enter the sibling
                new_pos = GroupPosition(
                    current_group=result.group,
                    segment_index=1,
                    iteration=1,
                    parent_position=self.position,
                )
                self.position = new_pos
