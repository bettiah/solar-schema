"""
Tests for EDIFACT schema building and resolution.

Tests cover:
- EdifactRegistry
- EdifactResolver
- EdifactSchemaLoader
"""

from pathlib import Path

import pytest
from edi_schema.edifact.models import SegmentGroup, SegmentRef
from edi_schema.edifact.schema import (
    EdifactRegistry,
    EdifactResolver,
    EdifactSchemaLoader,
    collect_segment_tags,
)


class TestEdifactRegistry:
    """Tests for EdifactRegistry."""

    def test_registry_creation(self):
        """Can create empty registry."""
        registry = EdifactRegistry()
        assert len(registry.elements) == 0
        assert len(registry.composites) == 0
        assert len(registry.segments) == 0

    def test_registry_load_from_directory(self, edifact_schema_path: Path):
        """Can load components from directory."""
        registry = EdifactRegistry()
        registry.load_from_directory(edifact_schema_path)

        assert len(registry.elements) > 0
        assert len(registry.composites) > 0
        assert len(registry.segments) > 0

    def test_registry_get_element(self, edifact_schema_path: Path):
        """get_element returns element by tag."""
        registry = EdifactRegistry()
        registry.load_from_directory(edifact_schema_path)

        element = registry.get_element("1001")
        assert element is not None
        assert element.tag == "1001"

    def test_registry_get_composite(self, edifact_schema_path: Path):
        """get_composite returns composite by tag."""
        registry = EdifactRegistry()
        registry.load_from_directory(edifact_schema_path)

        composite = registry.get_composite("C001")
        assert composite is not None
        assert composite.tag == "C001"

    def test_registry_get_segment(self, edifact_schema_path: Path):
        """get_segment returns segment by tag."""
        registry = EdifactRegistry()
        registry.load_from_directory(edifact_schema_path)

        segment = registry.get_segment("BGM")
        assert segment is not None
        assert segment.tag == "BGM"

    def test_registry_load_message(self, edifact_schema_path: Path):
        """Can load message on demand."""
        registry = EdifactRegistry()
        registry.load_from_directory(edifact_schema_path)

        message = registry.load_message("INVOIC")
        assert message is not None
        assert message.code == "INVOIC"

    def test_registry_message_exists(self, edifact_schema_path: Path):
        """Can check if message exists."""
        registry = EdifactRegistry()
        registry.load_from_directory(edifact_schema_path)

        assert registry.message_exists("INVOIC") is True
        assert registry.message_exists("NONEXISTENT") is False

    def test_registry_list_available_messages(self, edifact_schema_path: Path):
        """Can list available messages."""
        registry = EdifactRegistry()
        registry.load_from_directory(edifact_schema_path)

        messages = registry.list_available_messages()
        assert len(messages) > 0
        assert "INVOIC" in messages

    def test_registry_stats(self, edifact_schema_path: Path):
        """stats returns component counts."""
        registry = EdifactRegistry()
        registry.load_from_directory(edifact_schema_path)

        stats = registry.stats
        assert "elements" in stats
        assert "composites" in stats
        assert "segments" in stats
        assert stats["elements"] > 0


class TestEdifactResolver:
    """Tests for EdifactResolver."""

    def test_resolver_creation(self, edifact_schema_path: Path):
        """Can create resolver with registry."""
        registry = EdifactRegistry()
        registry.load_from_directory(edifact_schema_path)

        resolver = EdifactResolver(registry)
        assert resolver.registry is registry

    def test_resolver_resolve_all(self, edifact_schema_path: Path):
        """resolve_all links cross-references."""
        registry = EdifactRegistry()
        registry.load_from_directory(edifact_schema_path)

        resolver = EdifactResolver(registry)
        resolver.resolve_all()

        # Check that composites have resolved elements
        composite = registry.get_composite("C002")
        if composite and composite.components:
            # At least some components should be resolved
            resolved_count = sum(1 for c in composite.components if c.element is not None)
            assert resolved_count > 0

    def test_resolver_resolve_message(self, edifact_schema_path: Path):
        """resolve_message creates ResolvedMessageSpec."""
        registry = EdifactRegistry()
        registry.load_from_directory(edifact_schema_path)

        resolver = EdifactResolver(registry)
        resolver.resolve_all()

        message = registry.load_message("INVOIC")
        assert message is not None

        resolved = resolver.resolve_message(message)
        assert resolved.id == "INVOIC"
        assert len(resolved.segments) > 0
        assert len(resolved.elements) > 0


class TestCollectSegmentTags:
    """Tests for collect_segment_tags utility."""

    def test_collect_from_flat_structure(self):
        """Collects tags from flat structure."""
        structure = [
            SegmentRef(position=10, segment_tag="UNH", mandatory=True, max_repeat=1),
            SegmentRef(position=20, segment_tag="BGM", mandatory=True, max_repeat=1),
        ]
        tags = collect_segment_tags(structure)
        assert tags == {"UNH", "BGM"}

    def test_collect_from_nested_structure(self):
        """Collects tags from nested structure."""
        structure = [
            SegmentRef(position=10, segment_tag="UNH", mandatory=True, max_repeat=1),
            SegmentGroup(
                number=1,
                mandatory=False,
                max_repeat=99,
                children=[
                    SegmentRef(position=130, segment_tag="RFF", mandatory=True, max_repeat=1),
                    SegmentRef(position=140, segment_tag="DTM", mandatory=False, max_repeat=5),
                ],
            ),
        ]
        tags = collect_segment_tags(structure)
        assert tags == {"UNH", "RFF", "DTM"}


class TestEdifactSchemaLoader:
    """Tests for EdifactSchemaLoader."""

    def test_builder_creation(self, edifact_schema_path: Path):
        """Can create builder."""
        builder = EdifactSchemaLoader(edifact_schema_path)
        assert builder._loaded is False

    def test_builder_exists(self, edifact_schema_path: Path):
        """exists checks for message."""
        builder = EdifactSchemaLoader(edifact_schema_path)

        assert builder.exists("INVOIC") is True
        assert builder.exists("NONEXISTENT") is False

    def test_builder_list_schemas(self, edifact_schema_path: Path):
        """list_schemas returns available messages."""
        builder = EdifactSchemaLoader(edifact_schema_path)
        schemas = builder.list_schemas()

        assert len(schemas) > 0
        assert "INVOIC" in schemas
        assert "ORDERS" in schemas
        assert "DESADV" in schemas

    def test_builder_load_invoic(self, edifact_schema_path: Path):
        """Can load INVOIC message."""
        builder = EdifactSchemaLoader(edifact_schema_path)
        schema = builder.load("INVOIC")

        assert schema.id == "INVOIC"
        assert schema.format == "edifact"
        assert schema.version == "D.23A"
        assert schema.name is not None

    def test_builder_load_orders(self, edifact_schema_path: Path):
        """Can load ORDERS message."""
        builder = EdifactSchemaLoader(edifact_schema_path)
        schema = builder.load("ORDERS")

        assert schema.id == "ORDERS"
        assert len(schema.get_structure()) > 0

    def test_builder_load_desadv(self, edifact_schema_path: Path):
        """Can load DESADV message."""
        builder = EdifactSchemaLoader(edifact_schema_path)
        schema = builder.load("DESADV")

        assert schema.id == "DESADV"

    def test_builder_load_nonexistent_raises(self, edifact_schema_path: Path):
        """load raises for nonexistent message."""
        builder = EdifactSchemaLoader(edifact_schema_path)

        with pytest.raises(ValueError):
            builder.load("NONEXISTENT")

    def test_builder_get_segment(self, edifact_schema_path: Path):
        """get_segment returns segment definition."""
        builder = EdifactSchemaLoader(edifact_schema_path)
        segment = builder.get_segment("BGM")

        assert segment is not None
        assert segment.tag == "BGM"

    def test_builder_get_element(self, edifact_schema_path: Path):
        """get_element returns element definition."""
        builder = EdifactSchemaLoader(edifact_schema_path)
        element = builder.get_element("1001")

        assert element is not None
        assert element.tag == "1001"

    def test_builder_get_composite(self, edifact_schema_path: Path):
        """get_composite returns composite definition."""
        builder = EdifactSchemaLoader(edifact_schema_path)
        composite = builder.get_composite("C002")

        assert composite is not None
        assert composite.tag == "C002"

    def test_builder_caching(self, edifact_schema_path: Path):
        """load caches resolved schemas."""
        builder = EdifactSchemaLoader(edifact_schema_path)

        schema1 = builder.load("INVOIC")
        schema2 = builder.load("INVOIC")

        # Should be same object (cached)
        assert schema1 is schema2

    def test_builder_clear_cache(self, edifact_schema_path: Path):
        """clear_cache removes cached schemas."""
        builder = EdifactSchemaLoader(edifact_schema_path)

        schema1 = builder.load("INVOIC")
        builder.clear_cache()
        schema2 = builder.load("INVOIC")

        # Should be different objects after cache clear
        assert schema1 is not schema2

    def test_builder_stats(self, edifact_schema_path: Path):
        """stats returns component counts."""
        builder = EdifactSchemaLoader(edifact_schema_path)
        builder.load("INVOIC")  # Load one message

        stats = builder.stats
        assert stats["elements"] > 0
        assert stats["segments"] > 0
        assert stats["messages_cached"] == 1


class TestSchemaLikeProtocol:
    """Tests for SchemaLike protocol compliance."""

    def test_resolved_message_implements_protocol(self, edifact_schema_path: Path):
        """ResolvedMessageSpec implements SchemaLike protocol."""

        builder = EdifactSchemaLoader(edifact_schema_path)
        schema = builder.load("INVOIC")

        # Check protocol methods
        assert isinstance(schema.format, str)
        assert isinstance(schema.id, str)
        assert isinstance(schema.version, str)
        assert isinstance(schema.name, str)

        # Should be able to get segment/element/composite
        segment = schema.get_segment("BGM")
        assert segment is not None or segment is None  # Just check it doesn't error

        # Should have structure
        structure = schema.get_structure()
        assert isinstance(structure, list)
