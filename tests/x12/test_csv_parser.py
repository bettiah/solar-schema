"""
Tests for the X12 CSV parser.

Tests parsing of quote-comma delimited schema definition files.
"""

from pathlib import Path

from edi_schema.x12.schema_parsers.csv_parser import (
    iter_csv_file,
    parse_comdetl,
    parse_comhead,
    parse_cs_cv,
    parse_cs_de,
    parse_cshead,
    parse_csv_file,
    parse_csv_grouped,
    parse_csv_to_dict,
    parse_eledetl,
    parse_elehead,
    parse_segdetl,
    parse_seghead,
    parse_setdetl,
    parse_sethead,
)


class TestCsvParser:
    """Tests for general CSV parsing functions."""

    def test_parse_csv_file_basic(self, x12_schema_path: Path):
        """Test basic CSV file parsing."""
        rows = parse_csv_file(x12_schema_path / "sethead.txt")
        assert len(rows) > 0
        # Each row should have at least 3 fields
        for row in rows:
            assert len(row) >= 3

    def test_iter_csv_file(self, x12_schema_path: Path):
        """Test iterating over CSV file."""
        count = 0
        for row in iter_csv_file(x12_schema_path / "sethead.txt"):
            count += 1
            assert len(row) >= 3
        assert count > 0

    def test_parse_csv_to_dict(self, x12_schema_path: Path):
        """Test parsing CSV to dictionary."""
        result = parse_csv_to_dict(x12_schema_path / "sethead.txt")
        assert "810" in result  # Invoice
        assert "850" in result  # Purchase Order
        assert len(result["810"]) >= 3

    def test_parse_csv_grouped(self, x12_schema_path: Path):
        """Test parsing CSV with grouping."""
        result = parse_csv_grouped(x12_schema_path / "setdetl.txt")
        assert "810" in result
        assert len(result["810"]) > 1  # Multiple segments in 810


class TestSetHeadParser:
    """Tests for sethead.txt parser."""

    def test_parse_sethead(self, x12_schema_path: Path):
        """Test parsing transaction set headers."""
        result = parse_sethead(x12_schema_path / "sethead.txt")

        # Check known transaction sets
        assert "810" in result
        assert result["810"] == ("810", "Invoice", "IN")

        assert "850" in result
        assert result["850"] == ("850", "Purchase Order", "PO")

        assert "856" in result
        assert result["856"] == ("856", "Ship Notice/Manifest", "SH")

        assert "997" in result
        assert result["997"] == ("997", "Functional Acknowledgment", "FA")

    def test_sethead_count(self, x12_schema_path: Path):
        """Test that we parse a reasonable number of transaction sets."""
        result = parse_sethead(x12_schema_path / "sethead.txt")
        assert len(result) > 200  # X12 005010 has many transaction sets


class TestSetDetlParser:
    """Tests for setdetl.txt parser."""

    def test_parse_setdetl(self, x12_schema_path: Path):
        """Test parsing transaction set details."""
        result = parse_setdetl(x12_schema_path / "setdetl.txt")

        assert "810" in result
        assert len(result["810"]) > 10  # Invoice has many segments

        # Check structure of first segment
        first = result["810"][0]
        assert len(first) == 8  # area, seq, seg, req, max, level, repeat, loop_id

    def test_setdetl_structure(self, x12_schema_path: Path):
        """Test that ST and SE segments are present."""
        result = parse_setdetl(x12_schema_path / "setdetl.txt")

        for set_id, segments in result.items():
            # First segment should typically be ST
            assert any(s[2] == "ST" for s in segments), f"No ST in {set_id}"
            # Last segment should typically be SE
            assert any(s[2] == "SE" for s in segments), f"No SE in {set_id}"


class TestSegHeadParser:
    """Tests for seghead.txt parser."""

    def test_parse_seghead(self, x12_schema_path: Path):
        """Test parsing segment headers."""
        result = parse_seghead(x12_schema_path / "seghead.txt")

        # Check known segments
        assert "ST" in result
        assert result["ST"] == ("ST", "Transaction Set Header")

        assert "SE" in result
        assert result["SE"] == ("SE", "Transaction Set Trailer")

        assert "N1" in result
        assert "N1" in result["N1"][0]

    def test_seghead_count(self, x12_schema_path: Path):
        """Test that we parse a reasonable number of segments."""
        result = parse_seghead(x12_schema_path / "seghead.txt")
        assert len(result) > 300  # X12 has many segments


class TestSegDetlParser:
    """Tests for segdetl.txt parser."""

    def test_parse_segdetl(self, x12_schema_path: Path):
        """Test parsing segment details."""
        result = parse_segdetl(x12_schema_path / "segdetl.txt")

        assert "ST" in result
        assert len(result["ST"]) >= 2  # ST has at least 2 elements

        # Check structure
        first = result["ST"][0]
        assert len(first) == 4  # seq, elem_id, req, repetition


class TestEleHeadParser:
    """Tests for elehead.txt parser."""

    def test_parse_elehead(self, x12_schema_path: Path):
        """Test parsing element headers."""
        result = parse_elehead(x12_schema_path / "elehead.txt")

        # Check some known elements
        assert "1" in result  # Route Code
        assert "373" in result  # Date
        assert "143" in result  # Transaction Set Identifier Code

    def test_elehead_count(self, x12_schema_path: Path):
        """Test that we parse a reasonable number of elements."""
        result = parse_elehead(x12_schema_path / "elehead.txt")
        assert len(result) > 1000  # X12 has many elements


class TestEleDetlParser:
    """Tests for eledetl.txt parser."""

    def test_parse_eledetl(self, x12_schema_path: Path):
        """Test parsing element details."""
        result = parse_eledetl(x12_schema_path / "eledetl.txt")

        assert "373" in result  # Date
        _, data_type, min_len, max_len = result["373"]
        assert data_type == "DT"
        assert min_len == "8"
        assert max_len == "8"


class TestComHeadParser:
    """Tests for comhead.txt parser."""

    def test_parse_comhead(self, x12_schema_path: Path):
        """Test parsing composite headers."""
        result = parse_comhead(x12_schema_path / "comhead.txt")

        assert "C001" in result
        assert result["C001"] == ("C001", "Composite Unit of Measure")

    def test_comhead_count(self, x12_schema_path: Path):
        """Test that we parse composites."""
        result = parse_comhead(x12_schema_path / "comhead.txt")
        assert len(result) > 20  # X12 has around 34 composites


class TestComDetlParser:
    """Tests for comdetl.txt parser."""

    def test_parse_comdetl(self, x12_schema_path: Path):
        """Test parsing composite details."""
        result = parse_comdetl(x12_schema_path / "comdetl.txt")

        assert "C001" in result
        assert len(result["C001"]) > 1  # C001 has multiple elements

        # Check structure
        first = result["C001"][0]
        assert len(first) == 3  # seq, elem_id, req


class TestCsHeadParser:
    """Tests for cshead.txt parser."""

    def test_parse_cshead(self, x12_schema_path: Path):
        """Test parsing code source headers."""
        result = parse_cshead(x12_schema_path / "cshead.txt")

        # Check some known code sources
        assert "17" in result  # Standard Carrier Alpha Code
        assert "SCAC" in result["17"][1].upper() or "Carrier" in result["17"][1]


class TestCsDeParser:
    """Tests for cs_de.txt parser."""

    def test_parse_cs_de(self, x12_schema_path: Path):
        """Test parsing code source to element mappings."""
        result = parse_cs_de(x12_schema_path / "cs_de.txt")

        # Should have mappings
        assert len(result) > 0


class TestCsCvParser:
    """Tests for cs_cv.txt parser."""

    def test_parse_cs_cv(self, x12_schema_path: Path):
        """Test parsing code source to code value mappings."""
        result = parse_cs_cv(x12_schema_path / "cs_cv.txt")

        # Should have some mappings
        assert len(result) > 0
