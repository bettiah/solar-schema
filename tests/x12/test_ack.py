"""
Tests for X12 Acknowledgment Generation.
"""

from pathlib import Path

import pytest

from edi_schema.x12.ack import (
    AK1Data,
    AK2Data,
    AK3Data,
    AK4Data,
    AK5Data,
    AK9Data,
    FA997Generator,
    generate_997,
)
from edi_schema.x12.ast import (
    ErrorCategory,
    ErrorSeverity,
    FunctionalGroupInstance,
    ParseError,
    TransactionSetInstance,
)
from edi_schema.x12.parser.envelope import parse_envelope
from edi_schema.x12.parser.tokenizer import tokenize


class TestFA997Generator:
    """Tests for FA997Generator."""

    @pytest.fixture
    def generator(self):
        return FA997Generator()

    @pytest.fixture
    def sample_group(self) -> FunctionalGroupInstance:
        """Create a sample functional group."""
        txn = TransactionSetInstance(
            transaction_id="850",
            control_number="0001",
            content=[],
            errors=[],
        )
        return FunctionalGroupInstance(
            functional_id="PO",
            sender_id="SENDER",
            receiver_id="RECEIVER",
            date="20210101",
            time="1200",
            control_number="1",
            responsible_agency="X",
            version="005010",
            transactions=[txn],
            errors=[],
        )

    def test_generator_creation(self, generator):
        """Test creating the generator."""
        assert generator is not None
        assert generator.element_sep == "*"
        assert generator.segment_term == "~"

    def test_generate_st_segment(self, generator):
        """Test generating ST segment."""
        result = generator._generate_st("0001")
        assert result == "ST*997*0001"

    def test_generate_se_segment(self, generator):
        """Test generating SE segment."""
        result = generator._generate_se(5, "0001")
        assert result == "SE*5*0001"

    def test_generate_ak1_segment(self, generator):
        """Test generating AK1 segment."""
        data = AK1Data(functional_id="PO", group_control="1")
        result = generator._generate_ak1(data)
        assert result == "AK1*PO*1"

    def test_generate_ak2_segment(self, generator):
        """Test generating AK2 segment."""
        data = AK2Data(transaction_id="850", control_number="0001")
        result = generator._generate_ak2(data)
        assert result == "AK2*850*0001"

    def test_generate_ak2_with_implementation(self, generator):
        """Test generating AK2 with implementation reference."""
        data = AK2Data(
            transaction_id="837",
            control_number="0001",
            implementation_reference="005010X222A1",
        )
        result = generator._generate_ak2(data)
        assert result == "AK2*837*0001*005010X222A1"

    def test_generate_ak3_segment(self, generator):
        """Test generating AK3 segment."""
        data = AK3Data(
            segment_id="NM1",
            segment_position=5,
            loop_identifier="2000A",
            error_code="8",
        )
        result = generator._generate_ak3(data)
        assert result == "AK3*NM1*5*2000A*8"

    def test_generate_ak4_segment(self, generator):
        """Test generating AK4 segment."""
        data = AK4Data(
            element_position=3,
            error_code="7",
            element_reference="98",
            copy_of_bad_element="XX",
        )
        result = generator._generate_ak4(data)
        assert result == "AK4*3*98*7*XX"

    def test_generate_ak5_accepted(self, generator):
        """Test generating AK5 for accepted transaction."""
        data = AK5Data(status_code="A")
        result = generator._generate_ak5(data)
        assert result == "AK5*A"

    def test_generate_ak5_rejected_with_codes(self, generator):
        """Test generating AK5 for rejected transaction with error codes."""
        data = AK5Data(status_code="R", error_codes=["1", "4", "7"])
        result = generator._generate_ak5(data)
        assert result == "AK5*R*1*4*7"

    def test_generate_ak9_accepted(self, generator):
        """Test generating AK9 for accepted group."""
        data = AK9Data(
            status_code="A",
            included_count=1,
            received_count=1,
            accepted_count=1,
        )
        result = generator._generate_ak9(data)
        assert result == "AK9*A*1*1*1"

    def test_generate_ak9_partially_accepted(self, generator):
        """Test generating AK9 for partially accepted group."""
        data = AK9Data(
            status_code="P",
            included_count=3,
            received_count=3,
            accepted_count=2,
        )
        result = generator._generate_ak9(data)
        assert result == "AK9*P*3*3*2"

    def test_generate_997_accepted(self, generator, sample_group):
        """Test generating 997 for accepted group."""
        result = generator.generate(sample_group, control_number="0001")

        assert "ST*997*0001" in result
        assert "AK1*PO*1" in result
        assert "AK2*850*0001" in result
        assert "AK5*A" in result
        assert "AK9*A*1*1*1" in result
        assert result.endswith("~")

    def test_generate_997_with_errors(self, generator):
        """Test generating 997 with transaction errors."""
        # Create transaction with errors
        txn = TransactionSetInstance(
            transaction_id="850",
            control_number="0001",
            content=[],
            errors=[
                ParseError(
                    code="3",
                    message="Mandatory segment BEG missing",
                    category=ErrorCategory.SCHEMA,
                    severity=ErrorSeverity.ERROR,
                    segment_tag="BEG",
                    segment_position=2,
                ),
            ],
        )
        group = FunctionalGroupInstance(
            functional_id="PO",
            sender_id="SENDER",
            receiver_id="RECEIVER",
            date="20210101",
            time="1200",
            control_number="1",
            responsible_agency="X",
            version="005010",
            transactions=[txn],
            errors=[],
        )

        result = generator.generate(group, control_number="0001")

        # Should be rejected
        assert "AK5*R" in result
        assert "AK9*R*1*1*0" in result

    def test_generate_997_multiple_transactions(self, generator):
        """Test generating 997 with multiple transactions."""
        txn1 = TransactionSetInstance(
            transaction_id="850",
            control_number="0001",
            content=[],
            errors=[],  # Accepted
        )
        txn2 = TransactionSetInstance(
            transaction_id="850",
            control_number="0002",
            content=[],
            errors=[
                ParseError(
                    code="1",
                    message="Error",
                    category=ErrorCategory.ELEMENT,
                    severity=ErrorSeverity.ERROR,
                ),
            ],  # Rejected
        )
        txn3 = TransactionSetInstance(
            transaction_id="850",
            control_number="0003",
            content=[],
            errors=[],  # Accepted
        )

        group = FunctionalGroupInstance(
            functional_id="PO",
            sender_id="SENDER",
            receiver_id="RECEIVER",
            date="20210101",
            time="1200",
            control_number="1",
            responsible_agency="X",
            version="005010",
            transactions=[txn1, txn2, txn3],
            errors=[],
        )

        result = generator.generate(group, control_number="0001")

        # Should have 3 AK2 loops
        assert result.count("AK2*850") == 3

        # Should be partially accepted (2 of 3)
        assert "AK9*P*3*3*2" in result


class TestConvenienceFunction:
    """Tests for generate_997 convenience function."""

    def test_generate_997_convenience(self):
        """Test generate_997 convenience function."""
        txn = TransactionSetInstance(
            transaction_id="850",
            control_number="0001",
            content=[],
            errors=[],
        )
        group = FunctionalGroupInstance(
            functional_id="PO",
            sender_id="SENDER",
            receiver_id="RECEIVER",
            date="20210101",
            time="1200",
            control_number="1",
            responsible_agency="X",
            version="005010",
            transactions=[txn],
            errors=[],
        )

        result = generate_997(group, control_number="0001")

        assert "ST*997*0001" in result
        assert "AK9*A*1*1*1" in result

    def test_generate_997_custom_delimiters(self):
        """Test generate_997 with custom delimiters."""
        txn = TransactionSetInstance(
            transaction_id="850",
            control_number="0001",
            content=[],
            errors=[],
        )
        group = FunctionalGroupInstance(
            functional_id="PO",
            sender_id="SENDER",
            receiver_id="RECEIVER",
            date="20210101",
            time="1200",
            control_number="1",
            responsible_agency="X",
            version="005010",
            transactions=[txn],
            errors=[],
        )

        result = generate_997(
            group,
            control_number="0001",
            element_separator="|",
            segment_terminator="\n",
        )

        assert "ST|997|0001" in result
        assert result.endswith("\n")


class TestIntegration:
    """Integration tests with real sample files."""

    @pytest.fixture
    def samples_path(self) -> Path:
        return Path(__file__).parent.parent / "fixtures" / "x12_samples"

    def test_generate_997_for_835(self, samples_path: Path):
        """Test generating 997 for parsed 835 sample."""
        file_path = samples_path / "835_remittance.x12"
        if not file_path.exists():
            pytest.skip(f"Sample file not found: {file_path}")

        content = file_path.read_text()
        envelope_result = parse_envelope(tokenize(content))

        assert envelope_result.interchange is not None
        assert len(envelope_result.interchange.groups) > 0

        group = envelope_result.interchange.groups[0]

        # Generate 997
        ack = generate_997(group, control_number="0001")

        # Should have valid structure
        assert "ST*997*0001" in ack
        assert "AK1*" in ack
        assert "AK2*835*" in ack
        assert "AK5*" in ack
        assert "AK9*" in ack
        assert "SE*" in ack

    def test_generate_997_for_837(self, samples_path: Path):
        """Test generating 997 for parsed 837 sample."""
        file_path = samples_path / "837P_professional_claim.x12"
        if not file_path.exists():
            pytest.skip(f"Sample file not found: {file_path}")

        content = file_path.read_text()
        envelope_result = parse_envelope(tokenize(content))

        assert envelope_result.interchange is not None

        group = envelope_result.interchange.groups[0]

        # Generate 997
        ack = generate_997(group, control_number="0001")

        assert "ST*997*0001" in ack
        assert "AK2*837*" in ack

    def test_997_segment_count(self, samples_path: Path):
        """Test that 997 segment count is correct."""
        # Create simple group
        txn = TransactionSetInstance(
            transaction_id="850",
            control_number="0001",
            content=[],
            errors=[],
        )
        group = FunctionalGroupInstance(
            functional_id="PO",
            sender_id="SENDER",
            receiver_id="RECEIVER",
            date="20210101",
            time="1200",
            control_number="1",
            responsible_agency="X",
            version="005010",
            transactions=[txn],
            errors=[],
        )

        ack = generate_997(group, control_number="0001")

        # Parse the 997 to verify structure
        lines = ack.strip().split("~")
        lines = [l for l in lines if l]  # Remove empty

        # Count segments
        segment_count = len(lines)

        # Extract SE count
        se_line = [l for l in lines if l.startswith("SE")][0]
        se_count = int(se_line.split("*")[1])

        # SE count should match actual segment count
        assert se_count == segment_count


class TestDataClasses:
    """Tests for acknowledgment data classes."""

    def test_ak1_data(self):
        """Test AK1Data creation."""
        data = AK1Data(functional_id="PO", group_control="1")
        assert data.functional_id == "PO"
        assert data.group_control == "1"

    def test_ak2_data(self):
        """Test AK2Data creation."""
        data = AK2Data(
            transaction_id="850",
            control_number="0001",
            implementation_reference="005010",
        )
        assert data.transaction_id == "850"
        assert data.implementation_reference == "005010"

    def test_ak3_data(self):
        """Test AK3Data creation."""
        data = AK3Data(
            segment_id="NM1",
            segment_position=5,
            loop_identifier="2000A",
            error_code="8",
        )
        assert data.segment_id == "NM1"
        assert data.segment_position == 5

    def test_ak4_data(self):
        """Test AK4Data creation."""
        data = AK4Data(
            element_position=3,
            error_code="7",
        )
        assert data.element_position == 3
        assert data.error_code == "7"

    def test_ak5_data(self):
        """Test AK5Data creation."""
        data = AK5Data(status_code="A", error_codes=["1", "2"])
        assert data.status_code == "A"
        assert len(data.error_codes) == 2

    def test_ak9_data(self):
        """Test AK9Data creation."""
        data = AK9Data(
            status_code="P",
            included_count=5,
            received_count=5,
            accepted_count=3,
        )
        assert data.status_code == "P"
        assert data.accepted_count == 3
