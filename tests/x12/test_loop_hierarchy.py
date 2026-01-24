"""
Tests for X12 loop hierarchy builder.
"""

import pytest
from edi_schema.x12.parser.loop_hierarchy import (
    LoopMatcher,
    LoopNode,
    LoopPosition,
    MatchAction,
    build_loop_hierarchy,
)


class TestLoopNode:
    """Tests for LoopNode."""

    def test_creation(self):
        node = LoopNode(loop_id="N1", level=1, max_repeat=10)
        assert node.loop_id == "N1"
        assert node.level == 1
        assert node.max_repeat == 10
        assert node.segments == []
        assert node.children == []
        assert node.parent is None

    def test_str(self):
        node = LoopNode(loop_id="N1", level=1, max_repeat=">1")
        s = str(node)
        assert "N1" in s
        assert "unlimited" in s

    def test_add_child(self):
        parent = LoopNode(loop_id="ROOT", level=0, max_repeat=1)
        child = LoopNode(loop_id="N1", level=1, max_repeat=10)

        parent.add_child(child)

        assert len(parent.children) == 1
        assert parent.children[0] == child
        assert child.parent == parent

    def test_contains_segment(self):
        node = LoopNode(loop_id="ROOT", level=0, max_repeat=1)
        node._segment_set = {"N1", "N3", "N4"}

        assert node.contains_segment("N1")
        assert node.contains_segment("N3")
        assert not node.contains_segment("REF")

    def test_find_child_by_first_segment(self):
        parent = LoopNode(loop_id="ROOT", level=0, max_repeat=1)

        # Create a mock segment-like object
        class MockSegment:
            def __init__(self, seg_id):
                self.segment_id = seg_id

        child = LoopNode(loop_id="N1", level=1, max_repeat=10)
        child.segments = [MockSegment("N1")]
        parent.add_child(child)

        found = parent.find_child_by_first_segment("N1")
        assert found == child

        not_found = parent.find_child_by_first_segment("PO1")
        assert not_found is None

    def test_get_all_segment_ids(self):
        # Build a simple tree
        root = LoopNode(loop_id="ROOT", level=0, max_repeat=1)
        root._segment_set = {"ST", "BEG"}

        child = LoopNode(loop_id="N1", level=1, max_repeat=10)
        child._segment_set = {"N1", "N3", "N4"}
        root.add_child(child)

        grandchild = LoopNode(loop_id="REF", level=2, max_repeat=5)
        grandchild._segment_set = {"REF"}
        child.add_child(grandchild)

        all_ids = root.get_all_segment_ids()
        assert "ST" in all_ids
        assert "BEG" in all_ids
        assert "N1" in all_ids
        assert "N3" in all_ids
        assert "REF" in all_ids

    def test_get_depth(self):
        root = LoopNode(loop_id="ROOT", level=0, max_repeat=1)
        child = LoopNode(loop_id="L1", level=1, max_repeat=1)
        grandchild = LoopNode(loop_id="L2", level=2, max_repeat=1)

        root.add_child(child)
        child.add_child(grandchild)

        assert root.get_depth() == 3
        assert child.get_depth() == 2
        assert grandchild.get_depth() == 1

    def test_to_dict(self):
        node = LoopNode(loop_id="N1", level=1, max_repeat=10)
        d = node.to_dict()

        assert d["loop_id"] == "N1"
        assert d["level"] == 1
        assert d["max_repeat"] == 10
        assert d["segments"] == []
        assert d["children"] == []

    def test_print_tree(self):
        root = LoopNode(loop_id="ROOT", level=0, max_repeat=1)
        child = LoopNode(loop_id="N1", level=1, max_repeat=">1")
        root.add_child(child)

        tree_str = root.print_tree()
        assert "ROOT" in tree_str
        assert "N1" in tree_str


class TestLoopHierarchyBuilder:
    """Tests for LoopHierarchyBuilder with real transaction sets."""

    @pytest.fixture
    def x12_schema_loader(self):
        """Get the X12 schema loader."""
        from edi_schema.x12.schemas import GeneratedX12SchemaLoader

        return GeneratedX12SchemaLoader()

    def test_build_850_hierarchy(self, x12_schema_loader):
        """Test building loop hierarchy for 850 Purchase Order."""
        schema = x12_schema_loader.load("850")
        root = build_loop_hierarchy(schema)

        assert root.loop_id == "ROOT"
        assert root.level == 0

        # 850 should have multiple child loops
        assert len(root.children) > 0

        # Check that we have expected loops
        child_ids = [c.loop_id for c in root.children]
        assert child_ids == ["SAC", "LDT", "AMT", "N9", "N1", "LM", "SPI", "ADV", "PO1", "CTT"]
        # 850 has SAC, LDT, N9, N1 loops in heading
        # The exact loops depend on the schema version

    def test_build_810_hierarchy(self, x12_schema_loader):
        """Test building loop hierarchy for 810 Invoice."""
        schema = x12_schema_loader.load("810")
        root = build_loop_hierarchy(schema)

        assert root.loop_id == "ROOT"
        assert len(root.children) > 0

    def test_build_997_hierarchy(self, x12_schema_loader):
        """Test building loop hierarchy for 997 Functional Ack."""
        schema = x12_schema_loader.load("997")
        root = build_loop_hierarchy(schema)

        assert root.loop_id == "ROOT"
        # 997 has AK2 loop with nested AK3/AK4 loops

    def test_nested_loops(self, x12_schema_loader):
        """Test that nested loops have correct parent-child relationships."""
        schema = x12_schema_loader.load("850")
        root = build_loop_hierarchy(schema)

        # Find any nested loop (level 2+)
        def find_nested(node: LoopNode, depth: int = 0) -> list[tuple[LoopNode, int]]:
            result = []
            if depth > 1:
                result.append((node, depth))
            for child in node.children:
                result.extend(find_nested(child, depth + 1))
            return result

        nested = find_nested(root)
        # 850 should have some nested loops
        if nested:
            for node, depth in nested:
                # Verify parent chain
                current = node
                for _ in range(depth):
                    assert current.parent is not None
                    current = current.parent
                assert current == root

    def test_loop_segments_assigned(self, x12_schema_loader):
        """Test that segments are assigned to correct loops."""
        schema = x12_schema_loader.load("850")
        root = build_loop_hierarchy(schema)

        # Collect all segments from hierarchy
        def collect_segments(node: LoopNode) -> int:
            count = len(node.segments)
            for child in node.children:
                count += collect_segments(child)
            return count

        total_in_hierarchy = collect_segments(root)

        # Should account for all segments in the schema
        assert total_in_hierarchy == len(schema.get_structure())


class TestLoopPosition:
    """Tests for LoopPosition tracking."""

    def test_creation(self):
        root = LoopNode(loop_id="ROOT", level=0, max_repeat=1)
        pos = LoopPosition(current_loop=root)

        assert pos.current_loop == root
        assert pos.segment_index == 0
        assert pos.iteration == 1
        assert pos.parent_position is None

    def test_get_path(self):
        root = LoopNode(loop_id="ROOT", level=0, max_repeat=1)
        child = LoopNode(loop_id="N1", level=1, max_repeat=10)

        root_pos = LoopPosition(current_loop=root)
        child_pos = LoopPosition(
            current_loop=child,
            iteration=2,
            parent_position=root_pos,
        )

        path = child_pos.get_path()
        assert path == ["ROOT[1]", "N1[2]"]

    def test_can_iterate_unlimited(self):
        loop = LoopNode(loop_id="N1", level=1, max_repeat=">1")
        pos = LoopPosition(current_loop=loop, iteration=100)
        assert pos._can_iterate()

    def test_can_iterate_limited(self):
        loop = LoopNode(loop_id="N1", level=1, max_repeat=5)
        pos = LoopPosition(current_loop=loop, iteration=3)
        assert pos._can_iterate()  # 3 < 5

        pos2 = LoopPosition(current_loop=loop, iteration=5)
        assert not pos2._can_iterate()  # 5 >= 5


class TestLoopMatcher:
    """Tests for LoopMatcher."""

    def test_creation(self):
        root = LoopNode(loop_id="ROOT", level=0, max_repeat=1)
        matcher = LoopMatcher(root)

        assert matcher.root == root
        assert matcher.position.current_loop == root

    def test_match_unknown_segment(self):
        root = LoopNode(loop_id="ROOT", level=0, max_repeat=1)
        root._segment_set = {"ST", "BEG"}

        matcher = LoopMatcher(root)
        result = matcher.match_segment("XYZ")

        assert result.action == MatchAction.UNKNOWN_SEGMENT
        assert result.expected is not None

    def test_match_child_loop_start(self):
        # Create hierarchy with child loop
        class MockSegment:
            def __init__(self, seg_id):
                self.segment_id = seg_id

        root = LoopNode(loop_id="ROOT", level=0, max_repeat=1)
        root._segment_set = {"ST", "BEG"}

        child = LoopNode(loop_id="N1", level=1, max_repeat=10)
        child.segments = [MockSegment("N1")]
        child._segment_set = {"N1", "N3", "N4"}
        root.add_child(child)

        matcher = LoopMatcher(root)
        result = matcher.match_segment("N1")

        assert result.action == MatchAction.ENTER_CHILD_LOOP
        assert result.loop == child

    def test_advance_to_child_loop(self):
        class MockSegment:
            def __init__(self, seg_id):
                self.segment_id = seg_id

        root = LoopNode(loop_id="ROOT", level=0, max_repeat=1)
        child = LoopNode(loop_id="N1", level=1, max_repeat=10)
        child.segments = [MockSegment("N1")]
        child._segment_set = {"N1"}
        root.add_child(child)

        matcher = LoopMatcher(root)

        # Match N1 and advance
        result = matcher.match_segment("N1")
        matcher.advance_to(result)

        # Should now be in child loop
        assert matcher.position.current_loop == child
        assert matcher.position.iteration == 1
        assert matcher.position.parent_position is not None
        assert matcher.position.parent_position.current_loop == root

    def test_reset(self):
        root = LoopNode(loop_id="ROOT", level=0, max_repeat=1)
        child = LoopNode(loop_id="N1", level=1, max_repeat=10)
        root.add_child(child)

        matcher = LoopMatcher(root)

        # Move to child
        matcher.position = LoopPosition(
            current_loop=child,
            parent_position=LoopPosition(current_loop=root),
        )

        # Reset
        matcher.reset()

        assert matcher.position.current_loop == root
        assert matcher.position.parent_position is None
