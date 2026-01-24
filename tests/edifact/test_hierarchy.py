"""
Tests for EDIFACT segment group hierarchy builder.
"""

from edi_schema.edifact.models import (
    MessageSpec,
    SegmentGroup,
    SegmentRef,
)
from edi_schema.edifact.parser.hierarchy import (
    GroupMatcher,
    GroupNode,
    GroupPosition,
    MatchAction,
    build_group_hierarchy,
)


class TestGroupNode:
    """Tests for GroupNode."""

    def test_creation(self):
        node = GroupNode(group_number=1, max_repeat=10, mandatory=False)
        assert node.group_number == 1
        assert node.max_repeat == 10
        assert not node.mandatory
        assert node.segment_refs == []
        assert node.children == []
        assert node.parent is None

    def test_root_node(self):
        root = GroupNode(group_number=None, max_repeat=1, mandatory=True)
        assert root.group_number is None
        assert root.mandatory

    def test_str(self):
        node = GroupNode(group_number=1, max_repeat=99999, mandatory=False)
        s = str(node)
        assert "SG1" in s
        assert "unlimited" in s
        assert "C" in s  # Conditional

    def test_str_root(self):
        root = GroupNode(group_number=None, max_repeat=1, mandatory=True)
        s = str(root)
        assert "ROOT" in s
        assert "M" in s  # Mandatory

    def test_add_child(self):
        parent = GroupNode(group_number=None, max_repeat=1, mandatory=True)
        child = GroupNode(group_number=1, max_repeat=10, mandatory=False)

        parent.add_child(child)

        assert len(parent.children) == 1
        assert parent.children[0] == child
        assert child.parent == parent

    def test_add_segment_ref(self):
        node = GroupNode(group_number=1, max_repeat=10, mandatory=False)
        ref = SegmentRef(position=10, segment_tag="NAD", mandatory=True, max_repeat=1)

        node.add_segment_ref(ref)

        assert len(node.segment_refs) == 1
        assert node.contains_segment("NAD")
        assert node.trigger_tag == "NAD"

    def test_trigger_tag(self):
        node = GroupNode(group_number=1, max_repeat=10, mandatory=False)
        ref1 = SegmentRef(position=10, segment_tag="NAD", mandatory=True, max_repeat=1)
        ref2 = SegmentRef(position=20, segment_tag="RFF", mandatory=False, max_repeat=1)

        node.add_segment_ref(ref1)
        node.add_segment_ref(ref2)

        # Trigger should be the first segment
        assert node.trigger_tag == "NAD"

    def test_contains_segment(self):
        node = GroupNode(group_number=1, max_repeat=10, mandatory=False)
        ref1 = SegmentRef(position=10, segment_tag="NAD", mandatory=True, max_repeat=1)
        ref2 = SegmentRef(position=20, segment_tag="RFF", mandatory=False, max_repeat=1)
        node.add_segment_ref(ref1)
        node.add_segment_ref(ref2)

        assert node.contains_segment("NAD")
        assert node.contains_segment("RFF")
        assert not node.contains_segment("DTM")

    def test_find_child_by_trigger(self):
        parent = GroupNode(group_number=None, max_repeat=1, mandatory=True)

        child = GroupNode(group_number=1, max_repeat=10, mandatory=False)
        ref = SegmentRef(position=10, segment_tag="NAD", mandatory=True, max_repeat=1)
        child.add_segment_ref(ref)
        parent.add_child(child)

        found = parent.find_child_by_trigger("NAD")
        assert found == child

        not_found = parent.find_child_by_trigger("RFF")
        assert not_found is None

    def test_find_child_by_number(self):
        parent = GroupNode(group_number=None, max_repeat=1, mandatory=True)

        child1 = GroupNode(group_number=1, max_repeat=10, mandatory=False)
        child2 = GroupNode(group_number=2, max_repeat=5, mandatory=True)
        parent.add_child(child1)
        parent.add_child(child2)

        found = parent.find_child_by_number(2)
        assert found == child2

        not_found = parent.find_child_by_number(3)
        assert not_found is None

    def test_get_all_segment_tags(self):
        # Build a simple tree
        root = GroupNode(group_number=None, max_repeat=1, mandatory=True)
        root.add_segment_ref(SegmentRef(10, "UNH", True, 1))
        root.add_segment_ref(SegmentRef(20, "BGM", True, 1))

        child = GroupNode(group_number=1, max_repeat=10, mandatory=False)
        child.add_segment_ref(SegmentRef(10, "NAD", True, 1))
        child.add_segment_ref(SegmentRef(20, "RFF", False, 5))
        root.add_child(child)

        grandchild = GroupNode(group_number=2, max_repeat=5, mandatory=False)
        grandchild.add_segment_ref(SegmentRef(10, "DTM", True, 1))
        child.add_child(grandchild)

        all_tags = root.get_all_segment_tags()
        assert "UNH" in all_tags
        assert "BGM" in all_tags
        assert "NAD" in all_tags
        assert "RFF" in all_tags
        assert "DTM" in all_tags

    def test_get_expected_segments(self):
        root = GroupNode(group_number=None, max_repeat=1, mandatory=True)
        root.add_segment_ref(SegmentRef(10, "UNH", True, 1))
        root.add_segment_ref(SegmentRef(20, "BGM", True, 1))

        child = GroupNode(group_number=1, max_repeat=10, mandatory=False)
        child.add_segment_ref(SegmentRef(10, "NAD", True, 1))
        root.add_child(child)

        expected = root.get_expected_segments()
        assert "UNH" in expected
        assert "BGM" in expected
        assert "NAD" in expected  # Child trigger

    def test_get_depth(self):
        root = GroupNode(group_number=None, max_repeat=1, mandatory=True)
        child = GroupNode(group_number=1, max_repeat=10, mandatory=False)
        grandchild = GroupNode(group_number=2, max_repeat=5, mandatory=False)

        root.add_child(child)
        child.add_child(grandchild)

        assert root.get_depth() == 3
        assert child.get_depth() == 2
        assert grandchild.get_depth() == 1

    def test_get_path(self):
        root = GroupNode(group_number=None, max_repeat=1, mandatory=True)
        child = GroupNode(group_number=1, max_repeat=10, mandatory=False)
        grandchild = GroupNode(group_number=2, max_repeat=5, mandatory=False)

        root.add_child(child)
        child.add_child(grandchild)

        assert root.get_path() == [None]
        assert child.get_path() == [None, 1]
        assert grandchild.get_path() == [None, 1, 2]

    def test_to_dict(self):
        node = GroupNode(group_number=1, max_repeat=10, mandatory=True)
        ref = SegmentRef(position=10, segment_tag="NAD", mandatory=True, max_repeat=1)
        node.add_segment_ref(ref)

        d = node.to_dict()

        assert d["group_number"] == 1
        assert d["max_repeat"] == 10
        assert d["mandatory"] is True
        assert d["trigger_tag"] == "NAD"
        assert d["segments"] == ["NAD"]
        assert d["children"] == []

    def test_print_tree(self):
        root = GroupNode(group_number=None, max_repeat=1, mandatory=True)
        root.add_segment_ref(SegmentRef(10, "UNH", True, 1))

        child = GroupNode(group_number=1, max_repeat=99999, mandatory=False)
        child.add_segment_ref(SegmentRef(10, "NAD", True, 1))
        root.add_child(child)

        tree_str = root.print_tree()
        assert "ROOT" in tree_str
        assert "SG1" in tree_str
        assert "UNH" in tree_str
        assert "NAD" in tree_str


class TestGroupHierarchyBuilder:
    """Tests for GroupHierarchyBuilder."""

    def test_build_simple_message(self):
        """Test building hierarchy from a simple message spec."""
        spec = MessageSpec(
            code="TEST",
            version="D",
            release="23A",
            name="Test Message",
            structure=[
                SegmentRef(10, "UNH", True, 1),
                SegmentRef(20, "BGM", True, 1),
                SegmentRef(30, "DTM", False, 5),
                SegmentRef(40, "UNT", True, 1),
            ],
        )

        root = build_group_hierarchy(spec)

        assert root.group_number is None
        assert len(root.segment_refs) == 4
        assert len(root.children) == 0
        assert root.trigger_tag == "UNH"

    def test_build_message_with_one_group(self):
        """Test building hierarchy with a segment group."""
        spec = MessageSpec(
            code="TEST",
            version="D",
            release="23A",
            name="Test Message",
            structure=[
                SegmentRef(10, "UNH", True, 1),
                SegmentRef(20, "BGM", True, 1),
                SegmentGroup(
                    number=1,
                    mandatory=False,
                    max_repeat=99999,
                    children=[
                        SegmentRef(10, "NAD", True, 1),
                        SegmentRef(20, "RFF", False, 5),
                    ],
                ),
                SegmentRef(30, "UNT", True, 1),
            ],
        )

        root = build_group_hierarchy(spec)

        assert root.group_number is None
        assert len(root.segment_refs) == 3  # UNH, BGM, UNT
        assert len(root.children) == 1

        sg1 = root.children[0]
        assert sg1.group_number == 1
        assert sg1.max_repeat == 99999
        assert not sg1.mandatory
        assert len(sg1.segment_refs) == 2
        assert sg1.trigger_tag == "NAD"

    def test_build_nested_groups(self):
        """Test building hierarchy with nested segment groups."""
        spec = MessageSpec(
            code="TEST",
            version="D",
            release="23A",
            name="Test Message",
            structure=[
                SegmentRef(10, "UNH", True, 1),
                SegmentGroup(
                    number=1,
                    mandatory=False,
                    max_repeat=99999,
                    children=[
                        SegmentRef(10, "NAD", True, 1),
                        SegmentGroup(
                            number=2,
                            mandatory=False,
                            max_repeat=10,
                            children=[
                                SegmentRef(10, "RFF", True, 1),
                                SegmentRef(20, "DTM", False, 5),
                            ],
                        ),
                    ],
                ),
                SegmentRef(20, "UNT", True, 1),
            ],
        )

        root = build_group_hierarchy(spec)

        assert len(root.children) == 1

        sg1 = root.children[0]
        assert sg1.group_number == 1
        assert len(sg1.segment_refs) == 1  # Just NAD
        assert len(sg1.children) == 1

        sg2 = sg1.children[0]
        assert sg2.group_number == 2
        assert sg2.max_repeat == 10
        assert len(sg2.segment_refs) == 2  # RFF, DTM
        assert sg2.trigger_tag == "RFF"
        assert sg2.parent == sg1

    def test_build_multiple_top_level_groups(self):
        """Test building hierarchy with multiple groups at the same level."""
        spec = MessageSpec(
            code="TEST",
            version="D",
            release="23A",
            name="Test Message",
            structure=[
                SegmentRef(10, "UNH", True, 1),
                SegmentGroup(
                    number=1,
                    mandatory=False,
                    max_repeat=10,
                    children=[SegmentRef(10, "NAD", True, 1)],
                ),
                SegmentGroup(
                    number=2,
                    mandatory=False,
                    max_repeat=5,
                    children=[SegmentRef(10, "RFF", True, 1)],
                ),
                SegmentRef(20, "UNT", True, 1),
            ],
        )

        root = build_group_hierarchy(spec)

        assert len(root.children) == 2
        assert root.children[0].group_number == 1
        assert root.children[1].group_number == 2


class TestGroupPosition:
    """Tests for GroupPosition tracking."""

    def test_creation(self):
        root = GroupNode(group_number=None, max_repeat=1, mandatory=True)
        pos = GroupPosition(current_group=root)

        assert pos.current_group == root
        assert pos.segment_index == 0
        assert pos.iteration == 1
        assert pos.parent_position is None

    def test_get_path(self):
        root = GroupNode(group_number=None, max_repeat=1, mandatory=True)
        child = GroupNode(group_number=1, max_repeat=10, mandatory=False)

        root_pos = GroupPosition(current_group=root)
        child_pos = GroupPosition(
            current_group=child,
            iteration=2,
            parent_position=root_pos,
        )

        path = child_pos.get_path()
        assert path == ["ROOT[1]", "SG1[2]"]

    def test_can_iterate_unlimited(self):
        group = GroupNode(group_number=1, max_repeat=99999, mandatory=False)
        pos = GroupPosition(current_group=group, iteration=100)
        assert pos._can_iterate()

    def test_can_iterate_limited(self):
        group = GroupNode(group_number=1, max_repeat=5, mandatory=False)
        pos = GroupPosition(current_group=group, iteration=3)
        assert pos._can_iterate()  # 3 < 5

        pos2 = GroupPosition(current_group=group, iteration=5)
        assert not pos2._can_iterate()  # 5 >= 5

    def test_get_expected_segments(self):
        root = GroupNode(group_number=None, max_repeat=1, mandatory=True)
        root.add_segment_ref(SegmentRef(10, "UNH", True, 1))
        root.add_segment_ref(SegmentRef(20, "BGM", True, 1))

        child = GroupNode(group_number=1, max_repeat=10, mandatory=False)
        child.add_segment_ref(SegmentRef(10, "NAD", True, 1))
        root.add_child(child)

        pos = GroupPosition(current_group=root, segment_index=1)  # After UNH
        expected = pos.get_expected_segments()

        assert "BGM" in expected  # Remaining segment
        assert "NAD" in expected  # Child trigger


class TestGroupMatcher:
    """Tests for GroupMatcher."""

    def test_creation(self):
        root = GroupNode(group_number=None, max_repeat=1, mandatory=True)
        matcher = GroupMatcher(root)

        assert matcher.root == root
        assert matcher.position.current_group == root

    def test_match_expected_segment(self):
        root = GroupNode(group_number=None, max_repeat=1, mandatory=True)
        root.add_segment_ref(SegmentRef(10, "UNH", True, 1))
        root.add_segment_ref(SegmentRef(20, "BGM", True, 1))

        matcher = GroupMatcher(root)
        result = matcher.match_segment("UNH")

        assert result.action == MatchAction.ACCEPT
        assert result.advance_segment

    def test_match_unknown_segment(self):
        root = GroupNode(group_number=None, max_repeat=1, mandatory=True)
        root.add_segment_ref(SegmentRef(10, "UNH", True, 1))

        matcher = GroupMatcher(root)
        result = matcher.match_segment("XYZ")

        assert result.action == MatchAction.UNKNOWN_SEGMENT
        assert result.expected is not None

    def test_match_out_of_order(self):
        root = GroupNode(group_number=None, max_repeat=1, mandatory=True)
        root.add_segment_ref(SegmentRef(10, "UNH", True, 1))
        root.add_segment_ref(SegmentRef(20, "BGM", True, 1))
        root.add_segment_ref(SegmentRef(30, "DTM", False, 5))

        matcher = GroupMatcher(root)
        # Skip UNH and try DTM
        matcher.position.segment_index = 1  # After UNH

        result = matcher.match_segment("DTM")

        assert result.action == MatchAction.ACCEPT_OUT_OF_ORDER

    def test_match_child_group_start(self):
        root = GroupNode(group_number=None, max_repeat=1, mandatory=True)
        root.add_segment_ref(SegmentRef(10, "UNH", True, 1))

        child = GroupNode(group_number=1, max_repeat=10, mandatory=False)
        child.add_segment_ref(SegmentRef(10, "NAD", True, 1))
        root.add_child(child)

        matcher = GroupMatcher(root)
        matcher.position.segment_index = 1  # After UNH

        result = matcher.match_segment("NAD")

        assert result.action == MatchAction.ENTER_CHILD_GROUP
        assert result.group == child

    def test_match_new_iteration(self):
        root = GroupNode(group_number=None, max_repeat=1, mandatory=True)

        group = GroupNode(group_number=1, max_repeat=10, mandatory=False)
        group.add_segment_ref(SegmentRef(10, "NAD", True, 1))
        group.add_segment_ref(SegmentRef(20, "RFF", False, 5))
        root.add_child(group)

        matcher = GroupMatcher(root)
        # Enter the group
        root_pos = matcher.position
        group_pos = GroupPosition(
            current_group=group,
            segment_index=2,  # Past all segments
            iteration=1,
            parent_position=root_pos,
        )
        matcher.position = group_pos

        result = matcher.match_segment("NAD")

        assert result.action == MatchAction.NEW_ITERATION

    def test_advance_to_child_group(self):
        root = GroupNode(group_number=None, max_repeat=1, mandatory=True)

        child = GroupNode(group_number=1, max_repeat=10, mandatory=False)
        child.add_segment_ref(SegmentRef(10, "NAD", True, 1))
        root.add_child(child)

        matcher = GroupMatcher(root)

        # Match NAD and advance
        result = matcher.match_segment("NAD")
        matcher.advance_to(result)

        # Should now be in child group
        assert matcher.position.current_group == child
        assert matcher.position.iteration == 1
        assert matcher.position.segment_index == 1  # Past trigger
        assert matcher.position.parent_position is not None
        assert matcher.position.parent_position.current_group == root

    def test_advance_accept(self):
        root = GroupNode(group_number=None, max_repeat=1, mandatory=True)
        root.add_segment_ref(SegmentRef(10, "UNH", True, 1))
        root.add_segment_ref(SegmentRef(20, "BGM", True, 1))

        matcher = GroupMatcher(root)

        result = matcher.match_segment("UNH")
        assert matcher.position.segment_index == 0
        matcher.advance_to(result)
        assert matcher.position.segment_index == 1

    def test_advance_new_iteration(self):
        root = GroupNode(group_number=None, max_repeat=1, mandatory=True)

        group = GroupNode(group_number=1, max_repeat=10, mandatory=False)
        group.add_segment_ref(SegmentRef(10, "NAD", True, 1))
        root.add_child(group)

        matcher = GroupMatcher(root)
        # Start in the group
        group_pos = GroupPosition(
            current_group=group,
            segment_index=1,
            iteration=1,
            parent_position=GroupPosition(current_group=root),
        )
        matcher.position = group_pos

        result = matcher.match_segment("NAD")
        assert result.action == MatchAction.NEW_ITERATION
        matcher.advance_to(result)

        assert matcher.position.iteration == 2
        assert matcher.position.segment_index == 1

    def test_reset(self):
        root = GroupNode(group_number=None, max_repeat=1, mandatory=True)
        child = GroupNode(group_number=1, max_repeat=10, mandatory=False)
        root.add_child(child)

        matcher = GroupMatcher(root)

        # Move to child
        matcher.position = GroupPosition(
            current_group=child,
            parent_position=GroupPosition(current_group=root),
        )

        # Reset
        matcher.reset()

        assert matcher.position.current_group == root
        assert matcher.position.parent_position is None


class TestBuildGroupHierarchyFunction:
    """Tests for the convenience build_group_hierarchy function."""

    def test_with_message_spec(self):
        spec = MessageSpec(
            code="TEST",
            version="D",
            release="23A",
            name="Test",
            structure=[SegmentRef(10, "UNH", True, 1)],
        )
        root = build_group_hierarchy(spec)
        assert root is not None
        assert root.group_number is None
