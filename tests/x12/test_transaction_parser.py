"""
Tests for X12 Transaction Parser.
"""

from pathlib import Path

import pytest

from edi_schema.x12.ast import (
    LoopInstance,
    ParsedSegment,
    RawElement,
    RawSegment,
    SourcePosition,
)
from edi_schema.x12.parser.envelope import parse_envelope
from edi_schema.x12.parser.tokenizer import tokenize
from edi_schema.x12.parser.transaction import (
    HLParser,
    TransactionParser,
    TransactionParserState,
    parse_transaction,
)


class TestTransactionParserBasics:
    """Basic transaction parser tests."""

    def test_parser_creation(self):
        parser = TransactionParser()
        assert parser is not None

    def test_parse_without_schema(self):
        """Test parsing without a schema - just converts segments."""
        # Create some mock raw segments
        segments = [
            RawSegment(
                tag="BEG",
                elements=[
                    RawElement(value="00", position=SourcePosition(0, 1, 1), element_index=1),
                    RawElement(value="SA", position=SourcePosition(0, 1, 1), element_index=2),
                    RawElement(value="PO123", position=SourcePosition(0, 1, 1), element_index=3),
                ],
                position=SourcePosition(0, 1, 1),
                raw_text="BEG*00*SA*PO123",
            ),
            RawSegment(
                tag="REF",
                elements=[
                    RawElement(value="DP", position=SourcePosition(0, 1, 1), element_index=1),
                    RawElement(value="123", position=SourcePosition(0, 1, 1), element_index=2),
                ],
                position=SourcePosition(0, 1, 1),
                raw_text="REF*DP*123",
            ),
        ]

        parser = TransactionParser()
        result = parser.parse(segments, "850")

        assert len(result) == 2
        assert all(isinstance(item, ParsedSegment) for item in result)
        assert result[0].tag == "BEG"
        assert result[1].tag == "REF"

    def test_parse_convenience_function(self):
        segments = [
            RawSegment(
                tag="BEG",
                elements=[
                    RawElement(value="00", position=SourcePosition(0, 1, 1), element_index=1),
                ],
                position=SourcePosition(0, 1, 1),
                raw_text="BEG*00",
            ),
        ]

        content, errors = parse_transaction(segments, "850")
        assert len(content) == 1
        assert errors == []


class TestTransactionParserState:
    """Tests for TransactionParserState."""

    def test_initial_state(self):
        state = TransactionParserState()
        assert state.in_hl_loop is False
        assert state.current_hl_node is None
        assert state.loop_iterations == {}


class TestHLParser:
    """Tests for HL hierarchy parser."""

    def test_hl_parser_creation(self):
        parser = HLParser()
        assert parser is not None
        assert parser.nodes == {}
        assert parser.roots == []

    def test_process_simple_hl(self):
        """Test processing a single HL segment."""
        parser = HLParser()

        segment = RawSegment(
            tag="HL",
            elements=[
                RawElement(value="1", position=SourcePosition(0, 1, 1), element_index=1),
                RawElement(value="", position=SourcePosition(0, 1, 1), element_index=2),
                RawElement(value="20", position=SourcePosition(0, 1, 1), element_index=3),
                RawElement(value="1", position=SourcePosition(0, 1, 1), element_index=4),
            ],
            position=SourcePosition(0, 1, 1),
            raw_text="HL*1**20*1",
        )

        node, error = parser.process_hl(segment, 1)

        assert error is None
        assert node is not None
        assert node.id == "1"
        assert node.parent_id is None
        assert node.level_code == "20"
        assert node.child_code == "1"
        assert len(parser.roots) == 1
        assert parser.roots[0] == node

    def test_process_hl_with_parent(self):
        """Test processing HL with parent reference."""
        parser = HLParser()

        # First HL - root
        root_seg = RawSegment(
            tag="HL",
            elements=[
                RawElement(value="1", position=SourcePosition(0, 1, 1), element_index=1),
                RawElement(value="", position=SourcePosition(0, 1, 1), element_index=2),
                RawElement(value="20", position=SourcePosition(0, 1, 1), element_index=3),
                RawElement(value="1", position=SourcePosition(0, 1, 1), element_index=4),
            ],
            position=SourcePosition(0, 1, 1),
            raw_text="HL*1**20*1",
        )
        root_node, _ = parser.process_hl(root_seg, 1)

        # Second HL - child
        child_seg = RawSegment(
            tag="HL",
            elements=[
                RawElement(value="2", position=SourcePosition(0, 1, 1), element_index=1),
                RawElement(
                    value="1", position=SourcePosition(0, 1, 1), element_index=2
                ),  # Parent ID
                RawElement(value="22", position=SourcePosition(0, 1, 1), element_index=3),
                RawElement(value="0", position=SourcePosition(0, 1, 1), element_index=4),
            ],
            position=SourcePosition(0, 1, 1),
            raw_text="HL*2*1*22*0",
        )
        child_node, error = parser.process_hl(child_seg, 2)

        assert error is None
        assert child_node is not None
        assert child_node.parent_id == "1"
        assert child_node.parent == root_node
        assert len(root_node.children) == 1
        assert root_node.children[0] == child_node

    def test_process_hl_invalid_parent(self):
        """Test processing HL with invalid parent reference."""
        parser = HLParser()

        # HL referencing non-existent parent
        segment = RawSegment(
            tag="HL",
            elements=[
                RawElement(value="1", position=SourcePosition(0, 1, 1), element_index=1),
                RawElement(
                    value="99", position=SourcePosition(0, 1, 1), element_index=2
                ),  # Invalid
                RawElement(value="20", position=SourcePosition(0, 1, 1), element_index=3),
                RawElement(value="0", position=SourcePosition(0, 1, 1), element_index=4),
            ],
            position=SourcePosition(0, 1, 1),
            raw_text="HL*1*99*20*0",
        )
        node, error = parser.process_hl(segment, 1)

        assert error is not None
        assert "HL03" in error.code
        assert "non-existent parent" in error.message
        # Should still create node as root (recovery)
        assert node is not None
        assert node in parser.roots

    def test_add_content_to_hl(self):
        """Test adding content segments to an HL node."""
        parser = HLParser()

        # Create HL
        hl_seg = RawSegment(
            tag="HL",
            elements=[
                RawElement(value="1", position=SourcePosition(0, 1, 1), element_index=1),
                RawElement(value="", position=SourcePosition(0, 1, 1), element_index=2),
                RawElement(value="20", position=SourcePosition(0, 1, 1), element_index=3),
                RawElement(value="1", position=SourcePosition(0, 1, 1), element_index=4),
            ],
            position=SourcePosition(0, 1, 1),
            raw_text="HL*1**20*1",
        )
        node, _ = parser.process_hl(hl_seg, 1)

        # Add content
        content_seg = RawSegment(
            tag="NM1",
            elements=[
                RawElement(value="85", position=SourcePosition(0, 1, 1), element_index=1),
            ],
            position=SourcePosition(0, 1, 1),
            raw_text="NM1*85",
        )
        parser.add_content_to_current(content_seg, node)

        assert len(node.content_segments) == 1
        assert node.content_segments[0].tag == "NM1"

    def test_convert_to_loop_instances(self):
        """Test converting HL hierarchy to LoopInstance."""
        parser = HLParser()

        # Create root HL
        root_seg = RawSegment(
            tag="HL",
            elements=[
                RawElement(value="1", position=SourcePosition(0, 1, 1), element_index=1),
                RawElement(value="", position=SourcePosition(0, 1, 1), element_index=2),
                RawElement(value="20", position=SourcePosition(0, 1, 1), element_index=3),
                RawElement(value="1", position=SourcePosition(0, 1, 1), element_index=4),
            ],
            position=SourcePosition(0, 1, 1),
            raw_text="HL*1**20*1",
        )
        root_node, _ = parser.process_hl(root_seg, 1)

        # Add content to root
        nm1_seg = RawSegment(
            tag="NM1",
            elements=[RawElement(value="85", position=SourcePosition(0, 1, 1), element_index=1)],
            position=SourcePosition(0, 1, 1),
            raw_text="NM1*85",
        )
        parser.add_content_to_current(nm1_seg, root_node)

        # Convert to LoopInstance
        loop = parser.to_loop_instances(root_node)

        assert loop is not None
        assert loop.loop_id == "HL_20"
        assert loop.hl_level_code == "20"
        assert len(loop.segments) == 2  # HL + NM1


class TestHLTransactionParsing:
    """Tests for parsing HL-based transactions."""

    def test_parse_837_hl_structure(self):
        """Test parsing 837-like HL hierarchy."""
        # Simplified 837 structure
        segments = [
            # Header
            RawSegment(
                tag="BHT",
                elements=[
                    RawElement(value="0019", position=SourcePosition(0, 1, 1), element_index=1)
                ],
                position=SourcePosition(0, 1, 1),
                raw_text="BHT*0019",
            ),
            # Billing Provider HL
            RawSegment(
                tag="HL",
                elements=[
                    RawElement(value="1", position=SourcePosition(0, 1, 1), element_index=1),
                    RawElement(value="", position=SourcePosition(0, 1, 1), element_index=2),
                    RawElement(value="20", position=SourcePosition(0, 1, 1), element_index=3),
                    RawElement(value="1", position=SourcePosition(0, 1, 1), element_index=4),
                ],
                position=SourcePosition(0, 1, 1),
                raw_text="HL*1**20*1",
            ),
            RawSegment(
                tag="NM1",
                elements=[
                    RawElement(value="85", position=SourcePosition(0, 1, 1), element_index=1)
                ],
                position=SourcePosition(0, 1, 1),
                raw_text="NM1*85",
            ),
            # Subscriber HL
            RawSegment(
                tag="HL",
                elements=[
                    RawElement(value="2", position=SourcePosition(0, 1, 1), element_index=1),
                    RawElement(value="1", position=SourcePosition(0, 1, 1), element_index=2),
                    RawElement(value="22", position=SourcePosition(0, 1, 1), element_index=3),
                    RawElement(value="0", position=SourcePosition(0, 1, 1), element_index=4),
                ],
                position=SourcePosition(0, 1, 1),
                raw_text="HL*2*1*22*0",
            ),
            RawSegment(
                tag="NM1",
                elements=[
                    RawElement(value="IL", position=SourcePosition(0, 1, 1), element_index=1)
                ],
                position=SourcePosition(0, 1, 1),
                raw_text="NM1*IL",
            ),
        ]

        parser = TransactionParser()
        result = parser.parse(segments, "837")

        # Should have header + 2 HL loops
        assert len(result) >= 2

        # First should be header (BHT)
        assert isinstance(result[0], ParsedSegment)
        assert result[0].tag == "BHT"

        # Rest should include HL loops
        hl_loops = [item for item in result if isinstance(item, LoopInstance)]
        assert len(hl_loops) > 0

    def test_parse_856_hl_structure(self):
        """Test parsing 856-like HL hierarchy (shipment structure)."""
        segments = [
            # BSN header
            RawSegment(
                tag="BSN",
                elements=[
                    RawElement(value="00", position=SourcePosition(0, 1, 1), element_index=1)
                ],
                position=SourcePosition(0, 1, 1),
                raw_text="BSN*00",
            ),
            # Shipment HL
            RawSegment(
                tag="HL",
                elements=[
                    RawElement(value="1", position=SourcePosition(0, 1, 1), element_index=1),
                    RawElement(value="", position=SourcePosition(0, 1, 1), element_index=2),
                    RawElement(value="S", position=SourcePosition(0, 1, 1), element_index=3),
                    RawElement(value="1", position=SourcePosition(0, 1, 1), element_index=4),
                ],
                position=SourcePosition(0, 1, 1),
                raw_text="HL*1**S*1",
            ),
            # Order HL
            RawSegment(
                tag="HL",
                elements=[
                    RawElement(value="2", position=SourcePosition(0, 1, 1), element_index=1),
                    RawElement(value="1", position=SourcePosition(0, 1, 1), element_index=2),
                    RawElement(value="O", position=SourcePosition(0, 1, 1), element_index=3),
                    RawElement(value="1", position=SourcePosition(0, 1, 1), element_index=4),
                ],
                position=SourcePosition(0, 1, 1),
                raw_text="HL*2*1*O*1",
            ),
            # Item HL
            RawSegment(
                tag="HL",
                elements=[
                    RawElement(value="3", position=SourcePosition(0, 1, 1), element_index=1),
                    RawElement(value="2", position=SourcePosition(0, 1, 1), element_index=2),
                    RawElement(value="I", position=SourcePosition(0, 1, 1), element_index=3),
                    RawElement(value="0", position=SourcePosition(0, 1, 1), element_index=4),
                ],
                position=SourcePosition(0, 1, 1),
                raw_text="HL*3*2*I*0",
            ),
        ]

        parser = TransactionParser()
        result = parser.parse(segments, "856")

        # Check structure
        assert len(result) >= 2  # BSN + HL loops

        # Find the shipment loop
        hl_loops = [item for item in result if isinstance(item, LoopInstance)]
        assert len(hl_loops) > 0

        # Shipment should have Order as child, which should have Item as child
        shipment = hl_loops[0]
        assert "S" in shipment.loop_id or shipment.hl_level_code == "S"


class TestSchemaBasedParsing:
    """Tests for schema-based transaction parsing."""

    @pytest.fixture
    def x12_schema_path(self) -> Path:
        return Path("/Users/me/Downloads/edi/schema/x12/005010")

    def test_parse_850_with_schema(self):
        """Test parsing 850 with schema."""
        from edi_schema.x12.schemas import GeneratedX12SchemaLoader

        loader = GeneratedX12SchemaLoader()
        schema = loader.load("850")

        # Simple 850 content
        segments = [
            RawSegment(
                tag="BEG",
                elements=[
                    RawElement(value="00", position=SourcePosition(0, 1, 1), element_index=1),
                    RawElement(value="SA", position=SourcePosition(0, 1, 1), element_index=2),
                    RawElement(value="PO123", position=SourcePosition(0, 1, 1), element_index=3),
                ],
                position=SourcePosition(0, 1, 1),
                raw_text="BEG*00*SA*PO123",
            ),
            RawSegment(
                tag="N1",
                elements=[
                    RawElement(value="BY", position=SourcePosition(0, 1, 1), element_index=1),
                    RawElement(value="BUYER", position=SourcePosition(0, 1, 1), element_index=2),
                ],
                position=SourcePosition(0, 1, 1),
                raw_text="N1*BY*BUYER",
            ),
        ]

        parser = TransactionParser(schema)
        result = parser.parse(segments, "850")

        assert len(result) > 0


class TestRealSampleFiles:
    """Tests using real X12 sample files."""

    @pytest.fixture
    def samples_path(self) -> Path:
        return Path(__file__).parent.parent / "fixtures" / "x12_samples"

    def test_parse_837_sample(self, samples_path: Path):
        """Test parsing 837 sample file."""
        file_path = samples_path / "837P_professional_claim.x12"
        if not file_path.exists():
            pytest.skip(f"Sample file not found: {file_path}")

        content = file_path.read_text()
        envelope_result = parse_envelope(tokenize(content))

        assert envelope_result.interchange is not None
        assert len(envelope_result.interchange.groups) > 0

        # Get transaction content
        txn = envelope_result.interchange.groups[0].transactions[0]
        raw_segments = txn.content  # These are RawSegments

        # Parse the transaction content
        parser = TransactionParser()
        result = parser.parse(raw_segments, "837")

        # 837 uses HL hierarchy
        assert len(result) > 0

        # Should have some HL loops
        hl_loops = [
            item for item in result if isinstance(item, LoopInstance) and "HL" in item.loop_id
        ]
        assert len(hl_loops) > 0

    def test_parse_835_sample(self, samples_path: Path):
        """Test parsing 835 sample file."""
        file_path = samples_path / "835_remittance.x12"
        if not file_path.exists():
            pytest.skip(f"Sample file not found: {file_path}")

        content = file_path.read_text()
        envelope_result = parse_envelope(tokenize(content))

        assert envelope_result.interchange is not None

        txn = envelope_result.interchange.groups[0].transactions[0]
        raw_segments = txn.content

        # Parse without schema
        parser = TransactionParser()
        result = parser.parse(raw_segments, "835")

        # Should have parsed all segments
        assert len(result) > 0

    def test_parse_all_samples(self, samples_path: Path):
        """Test that all sample files can be parsed."""
        if not samples_path.exists():
            pytest.skip(f"Samples directory not found: {samples_path}")

        for file_path in samples_path.glob("*.x12"):
            content = file_path.read_text()
            envelope_result = parse_envelope(tokenize(content))

            if envelope_result.interchange is None:
                continue

            for group in envelope_result.interchange.groups:
                for txn in group.transactions:
                    parser = TransactionParser()
                    result = parser.parse(txn.content, txn.transaction_id)

                    assert len(result) > 0, f"No content parsed from {file_path.name}"


class TestErrorRecovery:
    """Tests for error recovery in transaction parsing."""

    def test_recover_from_unknown_segment(self):
        """Test recovery from unknown segment (not in schema)."""
        segments = [
            RawSegment(
                tag="BEG",
                elements=[
                    RawElement(value="00", position=SourcePosition(0, 1, 1), element_index=1)
                ],
                position=SourcePosition(0, 1, 1),
                raw_text="BEG*00",
            ),
            RawSegment(
                tag="XYZ",  # Unknown segment
                elements=[
                    RawElement(value="123", position=SourcePosition(0, 1, 1), element_index=1)
                ],
                position=SourcePosition(0, 1, 1),
                raw_text="XYZ*123",
            ),
            RawSegment(
                tag="REF",
                elements=[
                    RawElement(value="PO", position=SourcePosition(0, 1, 1), element_index=1)
                ],
                position=SourcePosition(0, 1, 1),
                raw_text="REF*PO",
            ),
        ]

        # Parse without schema - should just convert everything
        parser = TransactionParser()
        result = parser.parse(segments, "850")

        # Should have all 3 segments
        assert len(result) == 3

    def test_hl_missing_id(self):
        """Test handling HL with missing ID."""
        segments = [
            RawSegment(
                tag="HL",
                elements=[
                    RawElement(
                        value="", position=SourcePosition(0, 1, 1), element_index=1
                    ),  # Empty ID
                ],
                position=SourcePosition(0, 1, 1),
                raw_text="HL*",
            ),
        ]

        parser = TransactionParser()
        parser.parse(segments, "837")

        # Should have error about missing ID
        assert len(parser.errors) > 0
        assert any("HL01" in e.code for e in parser.errors)
