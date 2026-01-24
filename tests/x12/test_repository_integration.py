"""
Tests for X12 integration with the core SchemaRepository.

Verifies that the X12SchemaLoader works correctly when used through
the SchemaRepository interface.
"""

from pathlib import Path

import pytest

from edi_schema.core.repository import SchemaRepository
from edi_schema.x12.schema import X12Schema


class TestRepositoryIntegration:
    """Tests for X12 integration with SchemaRepository."""

    def test_repository_with_x12_path(self, x12_schema_path: Path):
        """Test creating a repository with X12 path."""
        repo = SchemaRepository(x12_path=x12_schema_path)
        assert repo is not None

    def test_exists_via_repository(self, x12_schema_path: Path):
        """Test checking schema existence via repository."""
        repo = SchemaRepository(x12_path=x12_schema_path)

        assert repo.exists("x12", "810")
        assert repo.exists("x12", "850")
        assert repo.exists("X12", "856")  # Case insensitive
        assert not repo.exists("x12", "999999")

    def test_load_via_repository(self, x12_schema_path: Path):
        """Test loading schema via repository."""
        repo = SchemaRepository(x12_path=x12_schema_path)

        schema = repo.load("x12", "810")
        assert isinstance(schema, X12Schema)
        assert schema.id == "810"
        assert schema.name == "Invoice"

    def test_list_schemas_via_repository(self, x12_schema_path: Path):
        """Test listing schemas via repository."""
        repo = SchemaRepository(x12_path=x12_schema_path)

        schemas = repo.list_schemas("x12")
        assert "810" in schemas
        assert "850" in schemas
        assert "997" in schemas

    def test_repository_caching(self, x12_schema_path: Path):
        """Test that repository caches loaded schemas."""
        repo = SchemaRepository(x12_path=x12_schema_path)

        schema1 = repo.load("x12", "810")
        schema2 = repo.load("x12", "810")

        assert schema1 is schema2

    def test_repository_clear_cache(self, x12_schema_path: Path):
        """Test clearing the repository cache."""
        repo = SchemaRepository(x12_path=x12_schema_path)

        schema1 = repo.load("x12", "810")
        repo.clear_cache()
        schema2 = repo.load("x12", "810")

        # After clearing cache, should be different instances
        # (but same content)
        assert schema2.id == schema1.id

    def test_repository_without_x12_path(self):
        """Test that repository uses GeneratedSchemaLoader without X12 path."""
        repo = SchemaRepository()  # No paths - uses GeneratedSchemaLoader

        # Should work because GeneratedSchemaLoader has pre-generated schemas
        assert repo.exists("x12", "810")

        schema = repo.load("x12", "810")
        assert schema.id == "810"
        assert schema.name == "Invoice"

    def test_repository_invalid_format(self, x12_schema_path: Path):
        """Test that repository rejects invalid format."""
        repo = SchemaRepository(x12_path=x12_schema_path)

        with pytest.raises(ValueError, match="Unknown format"):
            repo.exists("invalid", "810")

        with pytest.raises(ValueError, match="Unknown format"):
            repo.load("invalid", "810")


class TestSchemaLikeProtocol:
    """Tests that X12Schema implements the SchemaLike protocol."""

    def test_schema_has_format(self, x12_schema_path: Path):
        """Test that schema has format property."""
        repo = SchemaRepository(x12_path=x12_schema_path)
        schema = repo.load("x12", "810")

        assert schema.format == "x12"

    def test_schema_has_id(self, x12_schema_path: Path):
        """Test that schema has id property."""
        repo = SchemaRepository(x12_path=x12_schema_path)
        schema = repo.load("x12", "810")

        assert schema.id == "810"

    def test_schema_has_version(self, x12_schema_path: Path):
        """Test that schema has version property."""
        repo = SchemaRepository(x12_path=x12_schema_path)
        schema = repo.load("x12", "810")

        assert schema.version == "005010"

    def test_schema_has_name(self, x12_schema_path: Path):
        """Test that schema has name property."""
        repo = SchemaRepository(x12_path=x12_schema_path)
        schema = repo.load("x12", "810")

        assert schema.name == "Invoice"

    def test_schema_get_segment(self, x12_schema_path: Path):
        """Test that schema implements get_segment."""
        repo = SchemaRepository(x12_path=x12_schema_path)
        schema = repo.load("x12", "810")

        segment = schema.get_segment("ST")
        assert segment is not None
        assert segment.id == "ST"

    def test_schema_get_element(self, x12_schema_path: Path):
        """Test that schema implements get_element."""
        repo = SchemaRepository(x12_path=x12_schema_path)
        schema = repo.load("x12", "810")

        element = schema.get_element("143")
        assert element is not None
        assert element.id == "143"

    def test_schema_get_composite(self, x12_schema_path: Path):
        """Test that schema implements get_composite."""
        repo = SchemaRepository(x12_path=x12_schema_path)
        schema = repo.load("x12", "810")

        # May or may not have composites, but should not error
        composite = schema.get_composite("C001")
        # Just verify it returns None or a Composite

    def test_schema_get_structure(self, x12_schema_path: Path):
        """Test that schema implements get_structure."""
        repo = SchemaRepository(x12_path=x12_schema_path)
        schema = repo.load("x12", "810")

        structure = schema.get_structure()
        assert isinstance(structure, list)
        assert len(structure) > 0
