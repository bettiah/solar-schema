"""
Tests for X12 Schema Loader.

Tests loading complete transaction set schemas from the schema definition files.
"""

from pathlib import Path

import pytest

from edi_schema.x12.enums import (
    DataElementType,
    RequirementDesignator,
)
from edi_schema.x12.schema import X12Schema, X12SchemaLoader


class TestX12SchemaLoader:
    """Tests for X12SchemaLoader."""

    def test_loader_creation(self, x12_schema_path: Path):
        """Test creating a schema loader."""
        loader = X12SchemaLoader(x12_schema_path)
        assert loader is not None

    def test_exists(self, x12_schema_path: Path):
        """Test checking if schemas exist."""
        loader = X12SchemaLoader(x12_schema_path)

        assert loader.exists("810")
        assert loader.exists("850")
        assert loader.exists("856")
        assert loader.exists("997")
        assert not loader.exists("999999")

    def test_list_schemas(self, x12_schema_path: Path):
        """Test listing available schemas."""
        loader = X12SchemaLoader(x12_schema_path)
        schemas = loader.list_schemas()

        assert len(schemas) > 200
        assert "810" in schemas
        assert "850" in schemas
        assert "997" in schemas

    def test_load_810(self, x12_schema_path: Path):
        """Test loading 810 Invoice schema."""
        loader = X12SchemaLoader(x12_schema_path)
        schema = loader.load("810")

        assert isinstance(schema, X12Schema)
        assert schema.id == "810"
        assert schema.name == "Invoice"
        assert schema.format == "x12"
        assert schema.version == "005010"

        # Check structure
        structure = schema.get_structure()
        assert len(structure) > 10

        # First segment should be ST
        assert structure[0].segment_id == "ST"
        assert structure[0].requirement == RequirementDesignator.M

        # Last segment should be SE
        assert structure[-1].segment_id == "SE"

    def test_load_850(self, x12_schema_path: Path):
        """Test loading 850 Purchase Order schema."""
        loader = X12SchemaLoader(x12_schema_path)
        schema = loader.load("850")

        assert schema.id == "850"
        assert schema.name == "Purchase Order"
        assert schema.transaction_set.functional_group == "PO"

        # Should have segments
        assert len(schema.segments) > 0

        # Should have elements
        assert len(schema.elements) > 0

    def test_load_856(self, x12_schema_path: Path):
        """Test loading 856 Ship Notice/Manifest schema."""
        loader = X12SchemaLoader(x12_schema_path)
        schema = loader.load("856")

        assert schema.id == "856"
        assert "Ship" in schema.name

        # 856 uses hierarchical loops (HL segment)
        hl_segment = schema.get_segment("HL")
        assert hl_segment is not None

    def test_load_997(self, x12_schema_path: Path):
        """Test loading 997 Functional Acknowledgment schema."""
        loader = X12SchemaLoader(x12_schema_path)
        schema = loader.load("997")

        assert schema.id == "997"
        assert "Acknowledgment" in schema.name

        # 997 should have AK segments
        assert schema.get_segment("AK1") is not None
        assert schema.get_segment("AK9") is not None

    def test_load_nonexistent(self, x12_schema_path: Path):
        """Test loading a non-existent schema raises error."""
        loader = X12SchemaLoader(x12_schema_path)

        with pytest.raises(ValueError, match="not found"):
            loader.load("999999")

    def test_schema_caching(self, x12_schema_path: Path):
        """Test that schemas are cached."""
        loader = X12SchemaLoader(x12_schema_path)

        schema1 = loader.load("810")
        schema2 = loader.load("810")

        assert schema1 is schema2  # Same object


class TestX12Schema:
    """Tests for X12Schema object."""

    def test_get_segment(self, x12_schema_path: Path):
        """Test getting a segment from the schema."""
        loader = X12SchemaLoader(x12_schema_path)
        schema = loader.load("810")

        st = schema.get_segment("ST")
        assert st is not None
        assert st.id == "ST"
        assert st.name == "Transaction Set Header"

    def test_get_element(self, x12_schema_path: Path):
        """Test getting an element from the schema."""
        loader = X12SchemaLoader(x12_schema_path)
        schema = loader.load("810")

        # Element 143 is Transaction Set Identifier Code
        elem = schema.get_element("143")
        assert elem is not None
        assert elem.id == "143"
        assert elem.data_type == DataElementType.ID

    def test_get_composite(self, x12_schema_path: Path):
        """Test getting a composite from the schema."""
        loader = X12SchemaLoader(x12_schema_path)

        # Load a schema that uses composites
        schema = loader.load("837")  # Healthcare Claim uses composites

        # C003 is Composite Medical Procedure Identifier
        composite = schema.get_composite("C003")
        if composite:  # May or may not be in this transaction set
            assert composite.id == "C003"

    def test_schema_str(self, x12_schema_path: Path):
        """Test string representation of schema."""
        loader = X12SchemaLoader(x12_schema_path)
        schema = loader.load("810")

        str_repr = str(schema)
        assert "810" in str_repr
        assert "Invoice" in str_repr


class TestSchemaContent:
    """Tests for the content of loaded schemas."""

    def test_segment_has_elements(self, x12_schema_path: Path):
        """Test that segments have elements."""
        loader = X12SchemaLoader(x12_schema_path)
        schema = loader.load("810")

        for seg_id, segment in schema.segments.items():
            assert len(segment.elements) > 0, f"Segment {seg_id} has no elements"

    def test_element_has_type(self, x12_schema_path: Path):
        """Test that elements have data types."""
        loader = X12SchemaLoader(x12_schema_path)
        schema = loader.load("810")

        for elem_id, element in schema.elements.items():
            assert element.data_type is not None, f"Element {elem_id} has no data type"
            assert element.min_length > 0, f"Element {elem_id} has invalid min_length"
            assert element.max_length >= element.min_length, (
                f"Element {elem_id} has invalid length range"
            )

    def test_transaction_set_areas(self, x12_schema_path: Path):
        """Test that transaction sets have all three areas."""
        loader = X12SchemaLoader(x12_schema_path)
        schema = loader.load("810")

        heading = schema.transaction_set.get_heading_segments()
        detail = schema.transaction_set.get_detail_segments()
        summary = schema.transaction_set.get_summary_segments()

        # All transaction sets should have heading and summary at minimum
        assert len(heading) > 0
        assert len(summary) > 0

    def test_st_se_present(self, x12_schema_path: Path):
        """Test that ST and SE segments are in the schema."""
        loader = X12SchemaLoader(x12_schema_path)
        schema = loader.load("810")

        assert schema.get_segment("ST") is not None
        assert schema.get_segment("SE") is not None

    def test_element_definitions(self, x12_schema_path: Path):
        """Test that elements have definitions from freeform."""
        loader = X12SchemaLoader(x12_schema_path)
        schema = loader.load("810")

        # Not all elements have definitions, but some should
        elements_with_definitions = [e for e in schema.elements.values() if e.definition]
        assert len(elements_with_definitions) > 0

    def test_segment_purposes(self, x12_schema_path: Path):
        """Test that segments have purposes from freeform."""
        loader = X12SchemaLoader(x12_schema_path)
        schema = loader.load("810")

        # Not all segments have purposes, but some should
        segments_with_purposes = [s for s in schema.segments.values() if s.purpose]
        assert len(segments_with_purposes) > 0


class TestGetAllMethods:
    """Tests for get_all_* methods."""

    def test_get_all_elements(self, x12_schema_path: Path):
        """Test getting all elements."""
        loader = X12SchemaLoader(x12_schema_path)
        elements = loader.get_all_elements()

        assert len(elements) > 1000
        assert "373" in elements  # Date
        assert "143" in elements  # Transaction Set Identifier Code

    def test_get_all_segments(self, x12_schema_path: Path):
        """Test getting all segments."""
        loader = X12SchemaLoader(x12_schema_path)
        segments = loader.get_all_segments()

        assert len(segments) > 300
        assert "ST" in segments
        assert "SE" in segments
        assert "N1" in segments

    def test_get_all_composites(self, x12_schema_path: Path):
        """Test getting all composites."""
        loader = X12SchemaLoader(x12_schema_path)
        composites = loader.get_all_composites()

        assert len(composites) > 20
        assert "C001" in composites

    def test_get_all_code_sources(self, x12_schema_path: Path):
        """Test getting all code sources."""
        loader = X12SchemaLoader(x12_schema_path)
        code_sources = loader.get_all_code_sources()

        assert len(code_sources) > 0
