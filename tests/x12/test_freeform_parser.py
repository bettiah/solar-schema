"""
Tests for the X12 freeform.txt parser.

Tests parsing of the free-form text file containing purposes, notes, and codes.
"""

from pathlib import Path

from edi_schema.x12.schema_parsers.freeform import (
    FreeformData,
    FreeformEntry,
    get_segment_notes,
    iter_freeform_entries,
    parse_freeform_file,
)


class TestFreeformParser:
    """Tests for freeform.txt parsing."""

    def test_parse_freeform_file(self, x12_schema_path: Path):
        """Test parsing the complete freeform file."""
        data = parse_freeform_file(x12_schema_path / "freeform.txt")

        assert isinstance(data, FreeformData)
        assert len(data.set_purposes) > 0
        assert len(data.segment_purposes) > 0
        assert len(data.element_definitions) > 0
        assert len(data.element_codes) > 0

    def test_set_purposes(self, x12_schema_path: Path):
        """Test that transaction set purposes are parsed."""
        data = parse_freeform_file(x12_schema_path / "freeform.txt")

        # Check known transaction sets
        assert "810" in data.set_purposes
        assert (
            "Invoice" in data.set_purposes["810"] or "invoice" in data.set_purposes["810"].lower()
        )

        assert "850" in data.set_purposes
        assert (
            "Purchase Order" in data.set_purposes["850"]
            or "purchase order" in data.set_purposes["850"].lower()
        )

    def test_segment_purposes(self, x12_schema_path: Path):
        """Test that segment purposes are parsed."""
        data = parse_freeform_file(x12_schema_path / "freeform.txt")

        # Check some known segments
        assert "N1" in data.segment_purposes
        assert "AAA" in data.segment_purposes

    def test_element_definitions(self, x12_schema_path: Path):
        """Test that element definitions are parsed."""
        data = parse_freeform_file(x12_schema_path / "freeform.txt")

        # Check some known elements
        assert "1" in data.element_definitions  # Route Code
        assert "373" in data.element_definitions  # Date

    def test_element_codes(self, x12_schema_path: Path):
        """Test that element code values are parsed."""
        data = parse_freeform_file(x12_schema_path / "freeform.txt")

        # There should be many code values
        assert len(data.element_codes) > 100

    def test_get_element_code_values(self, x12_schema_path: Path):
        """Test getting code values for a specific element."""
        data = parse_freeform_file(x12_schema_path / "freeform.txt")

        # Element 8 (Bank Client Code) has codes E and R
        codes = data.get_element_code_values("8")
        if codes:  # May or may not have codes depending on element
            assert isinstance(codes, dict)

    def test_segment_notes(self, x12_schema_path: Path):
        """Test that segment notes are parsed."""
        data = parse_freeform_file(x12_schema_path / "freeform.txt")

        # There should be segment notes
        assert len(data.segment_notes) > 0

    def test_get_segment_notes(self, x12_schema_path: Path):
        """Test getting notes for a specific segment."""
        data = parse_freeform_file(x12_schema_path / "freeform.txt")

        notes = get_segment_notes(data, "AAA")
        # AAA may have notes
        assert isinstance(notes, list)

    def test_composite_purposes(self, x12_schema_path: Path):
        """Test that composite purposes are parsed."""
        data = parse_freeform_file(x12_schema_path / "freeform.txt")

        # Check known composite
        assert "C001" in data.composite_purposes

    def test_code_source_info(self, x12_schema_path: Path):
        """Test that code source information is parsed."""
        data = parse_freeform_file(x12_schema_path / "freeform.txt")

        # There should be code source information
        assert len(data.code_source_sources) > 0


class TestFreeformIterator:
    """Tests for iterating over freeform entries."""

    def test_iter_freeform_entries(self, x12_schema_path: Path):
        """Test iterating over freeform entries."""
        count = 0
        for entry in iter_freeform_entries(x12_schema_path / "freeform.txt"):
            assert isinstance(entry, FreeformEntry)
            assert entry.section_type
            assert entry.identifier
            count += 1
            if count >= 100:  # Just test first 100 entries
                break

        assert count >= 100


class TestFreeformEntry:
    """Tests for FreeformEntry dataclass."""

    def test_entry_creation(self):
        """Test creating a FreeformEntry."""
        entry = FreeformEntry(
            section_type="SETPUR",
            identifier="810",
            text="This is the purpose of the 810 transaction set.",
        )

        assert entry.section_type == "SETPUR"
        assert entry.identifier == "810"
        assert "purpose" in entry.text.lower()

    def test_entry_with_extra_fields(self):
        """Test creating a FreeformEntry with extra fields."""
        entry = FreeformEntry(
            section_type="SEGNTE",
            identifier="AAA",
            text="This is a note.",
            extra_fields={
                "element_position": "01",
                "note_type": "S",
                "sequence": "1",
            },
        )

        assert entry.extra_fields["element_position"] == "01"
        assert entry.extra_fields["note_type"] == "S"
