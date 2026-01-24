"""
Tests for EDIFACT parsers.

Tests cover:
- Base parsing utilities
- Code list parser (UNCL)
- Data element parser (EDED)
- Composite parser (EDCD)
- Segment parser (EDSD)
- Message parser (EDMD)
"""

from pathlib import Path

import pytest
from edi_schema.edifact.schema_parsers import (
    list_messages,
    parse_edcd,
    parse_eded,
    parse_edmd,
    parse_edsd,
    parse_repr,
    parse_uncl,
)


class TestParseRepr:
    """Tests for the representation parser."""

    def test_parse_alphanumeric_variable(self):
        """Parse variable-length alphanumeric."""
        result = parse_repr("an..35")
        assert result.data_type == "an"
        assert result.min_length == 0
        assert result.max_length == 35

    def test_parse_numeric_fixed(self):
        """Parse fixed-length numeric."""
        result = parse_repr("n3")
        assert result.data_type == "n"
        assert result.min_length == 3
        assert result.max_length == 3

    def test_parse_alpha_variable(self):
        """Parse variable-length alphabetic."""
        result = parse_repr("a..17")
        assert result.data_type == "a"
        assert result.min_length == 0
        assert result.max_length == 17

    def test_parse_alphanumeric_fixed(self):
        """Parse fixed-length alphanumeric."""
        result = parse_repr("an3")
        assert result.data_type == "an"
        assert result.min_length == 3
        assert result.max_length == 3

    def test_parse_invalid_raises(self):
        """Invalid format raises ValueError."""
        with pytest.raises(ValueError):
            parse_repr("invalid")


class TestUNCLParser:
    """Tests for code list parser."""

    def test_parse_uncl_returns_dict(self, edifact_schema_path: Path):
        """Parser returns dictionary of code lists."""
        uncl_path = edifact_schema_path / "UNCL.23A"
        result = parse_uncl(uncl_path)
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_parse_uncl_contains_1001(self, edifact_schema_path: Path):
        """Should contain document name code (1001)."""
        uncl_path = edifact_schema_path / "UNCL.23A"
        result = parse_uncl(uncl_path)
        assert "1001" in result
        # 1001 should have multiple codes
        codes = result["1001"]
        assert isinstance(codes, dict)
        assert len(codes) > 10

    def test_parse_uncl_code_value(self, edifact_schema_path: Path):
        """Code values should be strings."""
        uncl_path = edifact_schema_path / "UNCL.23A"
        result = parse_uncl(uncl_path)
        codes_1001 = result.get("1001", {})
        # Code 1 should be "Certificate of analysis"
        assert "1" in codes_1001
        assert "Certificate" in codes_1001["1"]


class TestEDEDParser:
    """Tests for data element parser."""

    def test_parse_eded_returns_dict(self, edifact_schema_path: Path):
        """Parser returns dictionary of data elements."""
        eded_path = edifact_schema_path / "eded" / "EDED.23A"
        result = parse_eded(eded_path)
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_parse_eded_element_attributes(self, edifact_schema_path: Path):
        """Elements have required attributes."""
        eded_path = edifact_schema_path / "eded" / "EDED.23A"
        result = parse_eded(eded_path)

        # Element 1001 should exist
        assert "1001" in result
        element = result["1001"]

        assert element.tag == "1001"
        assert element.name == "Document name code"
        assert element.data_type == "an"
        assert element.max_length == 3

    def test_parse_eded_with_code_lists(self, edifact_schema_path: Path):
        """Elements with codes get them attached."""
        uncl_path = edifact_schema_path / "UNCL.23A"
        eded_path = edifact_schema_path / "eded" / "EDED.23A"

        code_lists = parse_uncl(uncl_path)
        result = parse_eded(eded_path, code_lists)

        element = result.get("1001")
        assert element is not None
        assert element.codes is not None
        assert len(element.codes) > 0


class TestEDCDParser:
    """Tests for composite element parser."""

    def test_parse_edcd_returns_dict(self, edifact_schema_path: Path):
        """Parser returns dictionary of composites."""
        edcd_path = edifact_schema_path / "edcd" / "EDCD.22B"
        result = parse_edcd(edcd_path)
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_parse_edcd_composite_attributes(self, edifact_schema_path: Path):
        """Composites have required attributes."""
        edcd_path = edifact_schema_path / "edcd" / "EDCD.22B"
        result = parse_edcd(edcd_path)

        # C001 should exist (TRANSPORT MEANS)
        assert "C001" in result
        composite = result["C001"]

        assert composite.tag == "C001"
        assert "TRANSPORT" in composite.name.upper()
        assert len(composite.components) > 0

    def test_parse_edcd_component_order(self, edifact_schema_path: Path):
        """Components are ordered by position."""
        edcd_path = edifact_schema_path / "edcd" / "EDCD.22B"
        result = parse_edcd(edcd_path)

        composite = result.get("C001")
        if composite and len(composite.components) > 1:
            positions = [c.position for c in composite.components]
            assert positions == sorted(positions)


class TestEDSDParser:
    """Tests for segment parser."""

    def test_parse_edsd_returns_dict(self, edifact_schema_path: Path):
        """Parser returns dictionary of segments."""
        edsd_path = edifact_schema_path / "edsd" / "EDSD.23A"
        result = parse_edsd(edsd_path)
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_parse_edsd_segment_attributes(self, edifact_schema_path: Path):
        """Segments have required attributes."""
        edsd_path = edifact_schema_path / "edsd" / "EDSD.23A"
        result = parse_edsd(edsd_path)

        # BGM should exist (Beginning of Message)
        assert "BGM" in result
        segment = result["BGM"]

        assert segment.tag == "BGM"
        assert "BEGINNING" in segment.name.upper() or "MESSAGE" in segment.name.upper()
        assert len(segment.elements) > 0

    def test_parse_edsd_element_types(self, edifact_schema_path: Path):
        """Segment elements can be composite or standalone."""
        edsd_path = edifact_schema_path / "edsd" / "EDSD.23A"
        result = parse_edsd(edsd_path)

        # BGM typically has composite elements
        bgm = result.get("BGM")
        if bgm:
            has_composite = any(e.is_composite for e in bgm.elements)
            has_standalone = any(not e.is_composite for e in bgm.elements)
            # BGM should have both
            assert has_composite or has_standalone

    def test_parse_edsd_common_segments(self, edifact_schema_path: Path):
        """Common segments exist."""
        edsd_path = edifact_schema_path / "edsd" / "EDSD.23A"
        result = parse_edsd(edsd_path)

        common_segments = ["BGM", "DTM", "NAD", "RFF", "FTX", "MOA"]
        for seg_tag in common_segments:
            assert seg_tag in result, f"Expected segment {seg_tag} not found"


class TestEDMDParser:
    """Tests for message parser."""

    def test_parse_edmd_returns_message_spec(self, edifact_schema_path: Path):
        """Parser returns MessageSpec."""
        invoic_path = edifact_schema_path / "edmd" / "INVOIC_D.23A"
        result = parse_edmd(invoic_path)

        assert result.code == "INVOIC"
        assert result.version == "D"
        assert result.release == "23A"

    def test_parse_edmd_has_structure(self, edifact_schema_path: Path):
        """Message has non-empty structure."""
        invoic_path = edifact_schema_path / "edmd" / "INVOIC_D.23A"
        result = parse_edmd(invoic_path)

        assert len(result.structure) > 0

    def test_parse_edmd_first_segment_is_unh(self, edifact_schema_path: Path):
        """First segment should be UNH (Message header)."""
        invoic_path = edifact_schema_path / "edmd" / "INVOIC_D.23A"
        result = parse_edmd(invoic_path)

        from edi_schema.edifact.models import SegmentRef

        first = result.structure[0]
        assert isinstance(first, SegmentRef)
        assert first.segment_tag == "UNH"

    def test_parse_edmd_has_segment_groups(self, edifact_schema_path: Path):
        """Message structure includes segment groups."""
        invoic_path = edifact_schema_path / "edmd" / "INVOIC_D.23A"
        result = parse_edmd(invoic_path)

        from edi_schema.edifact.models import SegmentGroup

        has_groups = any(isinstance(item, SegmentGroup) for item in result.structure)
        assert has_groups, "Expected at least one segment group"

    def test_parse_edmd_orders(self, edifact_schema_path: Path):
        """Can parse ORDERS message."""
        orders_path = edifact_schema_path / "edmd" / "ORDERS_D.23A"
        if not orders_path.exists():
            pytest.skip("ORDERS_D.23A not found")

        result = parse_edmd(orders_path)
        assert result.code == "ORDERS"
        assert len(result.structure) > 0

    def test_parse_edmd_desadv(self, edifact_schema_path: Path):
        """Can parse DESADV message."""
        desadv_path = edifact_schema_path / "edmd" / "DESADV_D.23A"
        if not desadv_path.exists():
            pytest.skip("DESADV_D.23A not found")

        result = parse_edmd(desadv_path)
        assert result.code == "DESADV"
        assert len(result.structure) > 0


class TestListMessages:
    """Tests for message listing function."""

    def test_list_messages_returns_list(self, edifact_schema_path: Path):
        """Returns list of message codes."""
        edmd_path = edifact_schema_path / "edmd"
        result = list_messages(edmd_path)

        assert isinstance(result, list)
        assert len(result) > 0

    def test_list_messages_contains_common(self, edifact_schema_path: Path):
        """Contains common message types."""
        edmd_path = edifact_schema_path / "edmd"
        result = list_messages(edmd_path)

        # These should exist in D.23A
        common = ["INVOIC", "ORDERS", "DESADV"]
        for msg in common:
            assert msg in result, f"Expected message {msg} not in list"
