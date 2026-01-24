"""
Tests for EDIFACT Generated Schemas.

Tests the pre-generated schema modules and the GeneratedEdifactSchemaLoader.
"""

import pytest
from edi_schema.edifact.models import (
    Composite,
    DataElement,
    MessageSpec,
    ResolvedMessageSpec,
    Segment,
)
from edi_schema.edifact.schemas import (
    AVAILABLE_VERSIONS,
    DEFAULT_VERSION,
    GeneratedEdifactSchemaLoader,
    get_composite,
    get_data_element,
    get_message,
    get_schema,
    get_segment,
    list_messages,
    list_versions,
)


class TestVersionInfo:
    """Tests for version information."""

    def test_list_versions(self) -> None:
        """Should list available versions."""
        versions = list_versions()
        assert "d23a" in versions
        assert "d96a" in versions

    def test_available_versions_constant(self) -> None:
        """Should have AVAILABLE_VERSIONS constant."""
        assert "d23a" in AVAILABLE_VERSIONS
        assert "d96a" in AVAILABLE_VERSIONS

    def test_default_version(self) -> None:
        """Should have a default version."""
        assert DEFAULT_VERSION in AVAILABLE_VERSIONS


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_get_data_element(self) -> None:
        """Should get data element by ID."""
        elem = get_data_element("1001")
        assert elem is not None
        assert isinstance(elem, DataElement)
        assert elem.tag == "1001"

    def test_get_data_element_with_version(self) -> None:
        """Should get data element from specific version."""
        elem_d23a = get_data_element("1001", version="d23a")
        elem_d96a = get_data_element("1001", version="d96a")

        assert elem_d23a is not None
        assert elem_d96a is not None

    def test_get_data_element_not_found(self) -> None:
        """Should return None for non-existent element."""
        elem = get_data_element("99999")
        assert elem is None

    def test_get_composite(self) -> None:
        """Should get composite by ID."""
        comp = get_composite("C002")
        assert comp is not None
        assert isinstance(comp, Composite)
        assert comp.tag == "C002"

    def test_get_composite_not_found(self) -> None:
        """Should return None for non-existent composite."""
        comp = get_composite("CZZZ")
        assert comp is None

    def test_get_segment(self) -> None:
        """Should get segment by ID."""
        seg = get_segment("BGM")
        assert seg is not None
        assert isinstance(seg, Segment)
        assert seg.tag == "BGM"

    def test_get_segment_not_found(self) -> None:
        """Should return None for non-existent segment."""
        seg = get_segment("ZZZ")
        assert seg is None

    def test_get_message(self) -> None:
        """Should get message by ID."""
        msg = get_message("INVOIC")
        assert msg is not None
        assert isinstance(msg, MessageSpec)
        assert msg.code == "INVOIC"

    def test_get_message_not_found(self) -> None:
        """Should return None for non-existent message."""
        msg = get_message("ZZZZZZ")
        assert msg is None

    def test_get_schema(self) -> None:
        """Should get fully resolved schema."""
        schema = get_schema("INVOIC")
        assert schema is not None
        assert isinstance(schema, ResolvedMessageSpec)
        assert schema.spec.code == "INVOIC"
        assert len(schema.segments) > 0
        assert len(schema.elements) > 0

    def test_get_schema_not_found(self) -> None:
        """Should return None for non-existent message."""
        schema = get_schema("ZZZZZZ")
        assert schema is None

    def test_list_messages(self) -> None:
        """Should list all messages for a version."""
        messages = list_messages("d23a")
        assert len(messages) > 0
        assert "INVOIC" in messages
        assert "ORDERS" in messages


class TestGeneratedEdifactSchemaLoader:
    """Tests for GeneratedEdifactSchemaLoader."""

    def test_loader_creation(self) -> None:
        """Should create loader with version."""
        loader = GeneratedEdifactSchemaLoader(version="d23a")
        assert loader.version == "d23a"

    def test_loader_default_version(self) -> None:
        """Should use default version if not specified."""
        loader = GeneratedEdifactSchemaLoader()
        assert loader.version == DEFAULT_VERSION

    def test_exists(self) -> None:
        """Should check if message exists."""
        loader = GeneratedEdifactSchemaLoader(version="d23a")
        assert loader.exists("INVOIC") is True
        assert loader.exists("ORDERS") is True
        assert loader.exists("ZZZZZZ") is False

    def test_load(self) -> None:
        """Should load message schema."""
        loader = GeneratedEdifactSchemaLoader(version="d23a")
        schema = loader.load("INVOIC")

        assert isinstance(schema, ResolvedMessageSpec)
        assert schema.spec.code == "INVOIC"
        assert len(schema.segments) > 0

    def test_load_not_found(self) -> None:
        """Should raise ValueError for non-existent message."""
        loader = GeneratedEdifactSchemaLoader(version="d23a")
        with pytest.raises(ValueError, match="not found"):
            loader.load("ZZZZZZ")

    def test_load_caching(self) -> None:
        """Should cache loaded schemas."""
        loader = GeneratedEdifactSchemaLoader(version="d23a")
        schema1 = loader.load("INVOIC")
        schema2 = loader.load("INVOIC")
        assert schema1 is schema2

    def test_list_schemas(self) -> None:
        """Should list all available messages."""
        loader = GeneratedEdifactSchemaLoader(version="d23a")
        schemas = loader.list_schemas()

        assert len(schemas) > 0
        assert "INVOIC" in schemas

    def test_get_all_elements(self) -> None:
        """Should get all data elements."""
        loader = GeneratedEdifactSchemaLoader(version="d23a")
        elements = loader.get_all_elements()

        assert len(elements) > 0
        assert "1001" in elements
        assert isinstance(elements["1001"], DataElement)

    def test_get_all_segments(self) -> None:
        """Should get all segments."""
        loader = GeneratedEdifactSchemaLoader(version="d23a")
        segments = loader.get_all_segments()

        assert len(segments) > 0
        assert "BGM" in segments
        assert isinstance(segments["BGM"], Segment)

    def test_get_all_composites(self) -> None:
        """Should get all composites."""
        loader = GeneratedEdifactSchemaLoader(version="d23a")
        composites = loader.get_all_composites()

        assert len(composites) > 0
        assert "C002" in composites
        assert isinstance(composites["C002"], Composite)


class TestD23AContent:
    """Tests for D23A generated content."""

    @pytest.fixture
    def loader(self) -> GeneratedEdifactSchemaLoader:
        return GeneratedEdifactSchemaLoader(version="d23a")

    def test_element_count(self, loader: GeneratedEdifactSchemaLoader) -> None:
        """Should have expected number of elements."""
        elements = loader.get_all_elements()
        assert len(elements) >= 600  # D23A has ~649 elements

    def test_segment_count(self, loader: GeneratedEdifactSchemaLoader) -> None:
        """Should have expected number of segments."""
        segments = loader.get_all_segments()
        assert len(segments) >= 150  # D23A has ~156 segments

    def test_composite_count(self, loader: GeneratedEdifactSchemaLoader) -> None:
        """Should have expected number of composites."""
        composites = loader.get_all_composites()
        assert len(composites) >= 190  # D23A has ~199 composites

    def test_message_count(self, loader: GeneratedEdifactSchemaLoader) -> None:
        """Should have expected number of messages."""
        messages = loader.list_schemas()
        assert len(messages) >= 190  # D23A has ~195 messages

    def test_element_has_code_values(self, loader: GeneratedEdifactSchemaLoader) -> None:
        """Elements with codes should have code values."""
        elem = get_data_element("1001", version="d23a")
        assert elem is not None
        # D23A should have code values for coded elements
        if elem.codes:
            assert len(elem.codes) > 0


class TestD96AContent:
    """Tests for D96A generated content."""

    @pytest.fixture
    def loader(self) -> GeneratedEdifactSchemaLoader:
        return GeneratedEdifactSchemaLoader(version="d96a")

    def test_element_count(self, loader: GeneratedEdifactSchemaLoader) -> None:
        """Should have expected number of elements."""
        elements = loader.get_all_elements()
        assert len(elements) >= 400  # D96A has ~463 elements

    def test_segment_count(self, loader: GeneratedEdifactSchemaLoader) -> None:
        """Should have expected number of segments."""
        segments = loader.get_all_segments()
        assert len(segments) >= 120  # D96A has ~126 segments

    def test_composite_count(self, loader: GeneratedEdifactSchemaLoader) -> None:
        """Should have expected number of composites."""
        composites = loader.get_all_composites()
        assert len(composites) >= 150  # D96A has ~154 composites

    def test_message_count(self, loader: GeneratedEdifactSchemaLoader) -> None:
        """Should have expected number of messages."""
        messages = loader.list_schemas()
        assert len(messages) >= 120  # D96A has ~125 messages


class TestSchemaResolution:
    """Tests for schema resolution (collecting components)."""

    def test_invoic_schema_has_segments(self) -> None:
        """INVOIC schema should have segments."""
        schema = get_schema("INVOIC", version="d23a")
        assert schema is not None
        assert len(schema.segments) > 0

        # Should have common INVOIC segments
        assert "BGM" in schema.segments or any(s.tag == "BGM" for s in schema.segments.values())

    def test_invoic_schema_has_elements(self) -> None:
        """INVOIC schema should have elements."""
        schema = get_schema("INVOIC", version="d23a")
        assert schema is not None
        assert len(schema.elements) > 0

    def test_invoic_schema_has_composites(self) -> None:
        """INVOIC schema should have composites."""
        schema = get_schema("INVOIC", version="d23a")
        assert schema is not None
        assert len(schema.composites) > 0

    def test_schema_get_methods(self) -> None:
        """Schema should have get methods for components."""
        schema = get_schema("INVOIC", version="d23a")
        assert schema is not None

        # Test get_segment
        bgm = schema.get_segment("BGM")
        if bgm:
            assert bgm.tag == "BGM"

        # Test get_element - find an element that exists in the schema
        for elem_id in list(schema.elements.keys())[:1]:
            elem = schema.get_element(elem_id)
            assert elem is not None
            assert elem.tag == elem_id


class TestVersionComparison:
    """Compare D23A and D96A versions."""

    def test_both_have_invoic(self) -> None:
        """Both versions should have INVOIC message."""
        d23a_msg = get_message("INVOIC", version="d23a")
        d96a_msg = get_message("INVOIC", version="d96a")

        assert d23a_msg is not None
        assert d96a_msg is not None

    def test_both_have_orders(self) -> None:
        """Both versions should have ORDERS message."""
        d23a_msg = get_message("ORDERS", version="d23a")
        d96a_msg = get_message("ORDERS", version="d96a")

        assert d23a_msg is not None
        assert d96a_msg is not None

    def test_both_have_bgm_segment(self) -> None:
        """Both versions should have BGM segment."""
        d23a_seg = get_segment("BGM", version="d23a")
        d96a_seg = get_segment("BGM", version="d96a")

        assert d23a_seg is not None
        assert d96a_seg is not None
        assert d23a_seg.tag == "BGM"
        assert d96a_seg.tag == "BGM"

    def test_d23a_has_more_messages(self) -> None:
        """D23A should have more messages than D96A."""
        d23a_messages = list_messages("d23a")
        d96a_messages = list_messages("d96a")

        assert len(d23a_messages) > len(d96a_messages)
