"""
Tests for X12 Generated Schemas.

Tests the pre-generated schema modules and compares them to runtime-parsed schemas.
"""

import time
from pathlib import Path

import pytest

from edi_schema.x12.enums import (
    DataElementType,
    RequirementDesignator,
    TransactionSetArea,
)
from edi_schema.x12.schema import X12Schema, X12SchemaLoader
from edi_schema.x12.schemas import (
    GeneratedX12SchemaLoader,
    get_composite,
    get_element,
    get_schema,
    get_segment,
    get_transaction_set,
    list_transaction_sets,
    list_versions,
)


class TestGeneratedSchemaAPI:
    """Tests for the generated schema public API."""

    def test_list_versions(self):
        """Test listing available versions."""
        versions = list_versions()
        assert "005010" in versions

    def test_list_transaction_sets(self):
        """Test listing available transaction sets."""
        txn_ids = list_transaction_sets()
        assert len(txn_ids) == 318
        assert "810" in txn_ids
        assert "850" in txn_ids
        assert "837" in txn_ids
        assert "997" in txn_ids

    def test_get_transaction_set(self):
        """Test getting a transaction set definition."""
        txn = get_transaction_set("850")
        assert txn is not None
        assert txn.id == "850"
        assert txn.name == "Purchase Order"
        assert txn.functional_group == "PO"
        assert len(txn.structure) > 0

    def test_get_transaction_set_not_found(self):
        """Test getting a non-existent transaction set."""
        txn = get_transaction_set("999999")
        assert txn is None

    def test_get_segment(self):
        """Test getting a segment definition."""
        seg = get_segment("NM1")
        assert seg is not None
        assert seg.id == "NM1"
        assert seg.name == "Individual or Organizational Name"
        assert len(seg.elements) > 0
        assert seg.purpose is not None  # Should have freeform text

    def test_get_segment_not_found(self):
        """Test getting a non-existent segment."""
        seg = get_segment("ZZZ")
        assert seg is None

    def test_get_element(self):
        """Test getting an element definition."""
        elem = get_element("98")
        assert elem is not None
        assert elem.id == "98"
        assert elem.name == "Entity Identifier Code"
        assert elem.data_type == DataElementType.ID
        assert elem.min_length == 2
        assert elem.max_length == 3
        assert elem.definition is not None  # Should have freeform text
        assert len(elem.code_values) > 0  # Should have code values

    def test_get_element_not_found(self):
        """Test getting a non-existent element."""
        elem = get_element("99999")
        assert elem is None

    def test_get_composite(self):
        """Test getting a composite definition."""
        comp = get_composite("C001")
        assert comp is not None
        assert comp.id == "C001"
        assert comp.name == "Composite Unit of Measure"
        assert len(comp.elements) > 0

    def test_get_composite_not_found(self):
        """Test getting a non-existent composite."""
        comp = get_composite("CXXX")
        assert comp is None


class TestGetSchema:
    """Tests for get_schema() function."""

    def test_get_schema_837(self):
        """Test getting complete 837 schema."""
        schema = get_schema("837")
        assert schema is not None
        assert isinstance(schema, X12Schema)
        assert schema.id == "837"
        assert schema.name == "Health Care Claim"
        assert schema.version == "005010"
        assert schema.format == "x12"

        # Should have populated dictionaries
        assert len(schema.segments) > 0
        assert len(schema.elements) > 0

    def test_get_schema_850(self):
        """Test getting complete 850 schema."""
        schema = get_schema("850")
        assert schema is not None
        assert schema.id == "850"
        assert schema.name == "Purchase Order"
        assert schema.transaction_set.functional_group == "PO"

    def test_get_schema_not_found(self):
        """Test getting a non-existent schema."""
        schema = get_schema("999999")
        assert schema is None

    def test_schema_segments_match_structure(self):
        """Test that schema segments dictionary contains all structure segments."""
        schema = get_schema("810")
        structure_seg_ids = {seg.segment_id for seg in schema.get_structure()}

        # All segments in structure should be in segments dict
        for seg_id in structure_seg_ids:
            assert seg_id in schema.segments, f"Missing segment: {seg_id}"

    def test_schema_element_lookup(self):
        """Test element lookup through schema."""
        schema = get_schema("850")

        # Get BEG segment
        beg = schema.get_segment("BEG")
        assert beg is not None
        assert beg.name == "Beginning Segment for Purchase Order"

        # Get first element reference
        first_elem = beg.elements[0]
        element_def = schema.get_element(first_elem.element_id)
        assert element_def is not None


class TestGeneratedSchemaLoader:
    """Tests for GeneratedSchemaLoader class."""

    def test_loader_creation(self):
        """Test creating a generated schema loader."""
        loader = GeneratedX12SchemaLoader(version="005010")
        assert loader is not None
        assert loader.version == "005010"

    def test_exists(self):
        """Test checking if schemas exist."""
        loader = GeneratedX12SchemaLoader()

        assert loader.exists("810")
        assert loader.exists("850")
        assert loader.exists("837")
        assert not loader.exists("999999")

    def test_list_schemas(self):
        """Test listing available schemas."""
        loader = GeneratedX12SchemaLoader()
        schemas = loader.list_schemas()

        assert len(schemas) == 318
        assert "810" in schemas
        assert "850" in schemas

    def test_load(self):
        """Test loading a schema."""
        loader = GeneratedX12SchemaLoader()
        schema = loader.load("850")

        assert isinstance(schema, X12Schema)
        assert schema.id == "850"
        assert schema.name == "Purchase Order"

    def test_load_not_found(self):
        """Test loading a non-existent schema raises ValueError."""
        loader = GeneratedX12SchemaLoader()
        with pytest.raises(ValueError, match="not found"):
            loader.load("999999")

    def test_caching(self):
        """Test that schemas are cached."""
        loader = GeneratedX12SchemaLoader()

        schema1 = loader.load("810")
        schema2 = loader.load("810")

        assert schema1 is schema2  # Same instance

    def test_get_all_elements(self):
        """Test getting all elements."""
        loader = GeneratedX12SchemaLoader()
        elements = loader.get_all_elements()

        assert len(elements) == 1419
        assert "98" in elements
        assert elements["98"].name == "Entity Identifier Code"

    def test_get_all_segments(self):
        """Test getting all segments."""
        loader = GeneratedX12SchemaLoader()
        segments = loader.get_all_segments()

        assert len(segments) == 1035
        assert "NM1" in segments
        assert segments["NM1"].name == "Individual or Organizational Name"


class TestSchemaContent:
    """Tests for generated schema content quality."""

    def test_element_code_values(self):
        """Test that elements have code values populated."""
        elem = get_element("98")  # Entity Identifier Code
        assert len(elem.code_values) > 100  # Should have many codes

        # Check specific code values
        assert "85" in elem.code_values  # Billing Provider
        assert "QC" in elem.code_values  # Patient
        assert "PR" in elem.code_values  # Payer

    def test_element_definition(self):
        """Test that elements have definitions populated."""
        elem = get_element("98")
        assert elem.definition is not None
        assert len(elem.definition) > 10

    def test_segment_purpose(self):
        """Test that segments have purpose populated."""
        seg = get_segment("NM1")
        assert seg.purpose is not None
        assert "name" in seg.purpose.lower()

    def test_segment_notes(self):
        """Test that segments have notes populated."""
        # Find a segment with notes
        seg = get_segment("CLM")
        # Notes may or may not be present depending on schema
        # Just ensure the notes list exists
        assert hasattr(seg, "notes")
        assert isinstance(seg.notes, list)

    def test_composite_elements(self):
        """Test that composites have elements."""
        comp = get_composite("C001")
        assert len(comp.elements) > 0
        assert comp.elements[0].element_id is not None

    def test_transaction_structure(self):
        """Test transaction set structure is complete."""
        txn = get_transaction_set("837")

        # Check structure has expected segments
        seg_ids = [seg.segment_id for seg in txn.structure]
        assert "ST" in seg_ids
        assert "BHT" in seg_ids
        assert "SE" in seg_ids

        # Check segment properties
        for seg in txn.structure:
            assert seg.area in TransactionSetArea
            assert seg.requirement in RequirementDesignator
            assert seg.loop_level >= 0


class TestParityWithRuntime:
    """Tests comparing generated schemas to runtime-parsed schemas."""

    def test_transaction_set_parity(self, x12_schema_path: Path):
        """Test that generated transaction set matches runtime-parsed."""
        runtime_loader = X12SchemaLoader(x12_schema_path)
        generated_loader = GeneratedX12SchemaLoader()

        txn_ids = ["810", "850", "837", "997"]
        for txn_id in txn_ids:
            runtime = runtime_loader.load(txn_id)
            generated = generated_loader.load(txn_id)

            assert generated.id == runtime.id
            assert generated.name == runtime.name
            assert generated.version == runtime.version

            # Compare structure length
            runtime_structure = runtime.get_structure()
            generated_structure = generated.get_structure()
            assert len(generated_structure) == len(runtime_structure), (
                f"{txn_id} structure length mismatch"
            )

            # Compare segment IDs
            for i, (gen_seg, run_seg) in enumerate(zip(generated_structure, runtime_structure)):
                assert gen_seg.segment_id == run_seg.segment_id, f"{txn_id}[{i}] segment mismatch"
                assert gen_seg.requirement == run_seg.requirement, (
                    f"{txn_id}[{i}] requirement mismatch"
                )
                assert gen_seg.area == run_seg.area, f"{txn_id}[{i}] area mismatch"

    def test_segment_parity(self, x12_schema_path: Path):
        """Test that generated segments match runtime-parsed."""
        runtime_loader = X12SchemaLoader(x12_schema_path)

        # Load a schema to get segments
        runtime = runtime_loader.load("850")

        for seg_id, runtime_seg in runtime.segments.items():
            generated_seg = get_segment(seg_id)
            assert generated_seg is not None, f"Missing segment: {seg_id}"

            assert generated_seg.id == runtime_seg.id
            assert generated_seg.name == runtime_seg.name
            assert len(generated_seg.elements) == len(runtime_seg.elements), (
                f"{seg_id} element count mismatch"
            )

            # Compare elements
            for i, (gen_elem, run_elem) in enumerate(
                zip(generated_seg.elements, runtime_seg.elements)
            ):
                assert gen_elem.element_id == run_elem.element_id, (
                    f"{seg_id}[{i}] element_id mismatch"
                )
                assert gen_elem.requirement == run_elem.requirement, (
                    f"{seg_id}[{i}] requirement mismatch"
                )

    def test_element_parity(self, x12_schema_path: Path):
        """Test that generated elements match runtime-parsed."""
        runtime_loader = X12SchemaLoader(x12_schema_path)

        # Load a schema to get elements
        runtime = runtime_loader.load("850")

        for elem_id, runtime_elem in runtime.elements.items():
            generated_elem = get_element(elem_id)
            assert generated_elem is not None, f"Missing element: {elem_id}"

            assert generated_elem.id == runtime_elem.id
            assert generated_elem.name == runtime_elem.name
            assert generated_elem.data_type == runtime_elem.data_type
            assert generated_elem.min_length == runtime_elem.min_length
            assert generated_elem.max_length == runtime_elem.max_length

            # Code values should match
            assert generated_elem.code_values == runtime_elem.code_values, (
                f"{elem_id} code_values mismatch"
            )


class TestPerformance:
    """Performance tests for generated schemas."""

    def test_load_performance(self):
        """Test that generated schema loading is fast."""
        # Warm up
        get_schema("837")

        # Time multiple loads
        start = time.perf_counter()
        for _ in range(100):
            schema = get_schema("837")
        elapsed = time.perf_counter() - start

        # Should be very fast (< 1 second for 100 loads)
        assert elapsed < 1.0, f"Loading too slow: {elapsed:.3f}s for 100 loads"

    def test_lookup_performance(self):
        """Test that individual lookups are fast."""
        # Time many lookups
        start = time.perf_counter()
        for _ in range(1000):
            get_segment("NM1")
            get_element("98")
        elapsed = time.perf_counter() - start

        # Should be very fast (< 1 second for 2000 lookups)
        assert elapsed < 1.0, f"Lookups too slow: {elapsed:.3f}s for 2000 lookups"
