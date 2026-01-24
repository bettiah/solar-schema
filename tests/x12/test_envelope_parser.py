"""
Tests for X12 Envelope Parser.
"""

from pathlib import Path

import pytest

from edi_schema.x12.ast import (
    ErrorSeverity,
    ParseResult,
)
from edi_schema.x12.parser.envelope import (
    EnvelopeParser,
    EnvelopeParserState,
    parse_envelope,
)
from edi_schema.x12.parser.tokenizer import tokenize


class TestEnvelopeParserBasics:
    """Basic envelope parser tests."""

    def test_parser_creation(self):
        parser = EnvelopeParser()
        assert parser is not None

    def test_parse_convenience_function(self):
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "GS*PO*SENDER*RECEIVER*20210101*1200*1*X*005010~"
            "ST*850*0001~"
            "SE*2*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        tokenizer_result = tokenize(content)
        result = parse_envelope(tokenizer_result)

        assert isinstance(result, ParseResult)
        assert result.interchange is not None


class TestEnvelopeParserState:
    """Tests for EnvelopeParserState."""

    def test_initial_state(self):
        state = EnvelopeParserState()
        assert state.in_interchange is False
        assert state.in_group is False
        assert state.in_transaction is False
        assert state.current_isa_control == ""
        assert state.current_gs_control == ""
        assert state.current_st_control == ""
        assert state.group_count == 0
        assert state.transaction_count == 0
        assert state.segment_count == 0


class TestInterchangeParsing:
    """Tests for ISA/IEA interchange parsing."""

    def test_parse_minimal_interchange(self):
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "GS*PO*SENDER*RECEIVER*20210101*1200*1*X*005010~"
            "ST*850*0001~"
            "SE*2*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        result = parse_envelope(tokenize(content))

        assert result.interchange is not None
        interchange = result.interchange

        assert interchange.control_number == "000000001"
        assert interchange.sender_id == "SENDER"
        assert interchange.receiver_id == "RECEIVER"
        assert interchange.version == "00501"
        assert interchange.usage_indicator == "P"

    def test_parse_interchange_delimiters(self):
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "GS*PO*SENDER*RECEIVER*20210101*1200*1*X*005010~"
            "ST*850*0001~"
            "SE*2*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        result = parse_envelope(tokenize(content))

        assert result.interchange is not None
        delims = result.interchange.delimiters

        assert delims.element == "*"
        assert delims.segment == "~"
        assert delims.component == ":"
        assert delims.repetition == "^"

    def test_missing_iea_recovery(self):
        """Test that parser recovers from missing IEA."""
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "GS*PO*SENDER*RECEIVER*20210101*1200*1*X*005010~"
            "ST*850*0001~"
            "SE*2*0001~"
            "GE*1*1~"
            # Missing IEA
        )
        result = parse_envelope(tokenize(content))

        # Should still get interchange
        assert result.interchange is not None
        assert result.interchange.control_number == "000000001"

        # Should have error about missing IEA
        assert any("Missing IEA" in e.message for e in result.errors)

    def test_iea_control_number_mismatch(self):
        """Test detection of IEA control number mismatch."""
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "GS*PO*SENDER*RECEIVER*20210101*1200*1*X*005010~"
            "ST*850*0001~"
            "SE*2*0001~"
            "GE*1*1~"
            "IEA*1*000000999~"  # Wrong control number
        )
        result = parse_envelope(tokenize(content))

        # Should still parse
        assert result.interchange is not None

        # Should have error about control number mismatch
        errors_and_warnings = result.errors + result.warnings
        assert any("control" in e.message.lower() for e in errors_and_warnings)

    def test_iea_group_count_mismatch(self):
        """Test detection of IEA group count mismatch."""
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "GS*PO*SENDER*RECEIVER*20210101*1200*1*X*005010~"
            "ST*850*0001~"
            "SE*2*0001~"
            "GE*1*1~"
            "IEA*5*000000001~"  # Wrong count (says 5, should be 1)
        )
        result = parse_envelope(tokenize(content))

        assert result.interchange is not None
        # Should have error about count mismatch
        errors_and_warnings = result.errors + result.warnings
        assert any("count" in e.message.lower() for e in errors_and_warnings)


class TestFunctionalGroupParsing:
    """Tests for GS/GE functional group parsing."""

    def test_parse_single_group(self):
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "GS*PO*SENDER*RECEIVER*20210101*1200*1*X*005010~"
            "ST*850*0001~"
            "SE*2*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        result = parse_envelope(tokenize(content))

        assert result.interchange is not None
        assert len(result.interchange.groups) == 1

        group = result.interchange.groups[0]
        assert group.functional_id == "PO"
        assert group.control_number == "1"
        assert group.version == "005010"

    def test_parse_multiple_groups(self):
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "GS*PO*SENDER*RECEIVER*20210101*1200*1*X*005010~"
            "ST*850*0001~"
            "SE*2*0001~"
            "GE*1*1~"
            "GS*IN*SENDER*RECEIVER*20210101*1201*2*X*005010~"
            "ST*810*0001~"
            "SE*2*0001~"
            "GE*1*2~"
            "IEA*2*000000001~"
        )
        result = parse_envelope(tokenize(content))

        assert result.interchange is not None
        assert len(result.interchange.groups) == 2

        assert result.interchange.groups[0].functional_id == "PO"
        assert result.interchange.groups[1].functional_id == "IN"

    def test_missing_ge_recovery(self):
        """Test that parser recovers from missing GE."""
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "GS*PO*SENDER*RECEIVER*20210101*1200*1*X*005010~"
            "ST*850*0001~"
            "SE*2*0001~"
            # Missing GE
            "GS*IN*SENDER*RECEIVER*20210101*1201*2*X*005010~"
            "ST*810*0001~"
            "SE*2*0001~"
            "GE*1*2~"
            "IEA*2*000000001~"
        )
        result = parse_envelope(tokenize(content))

        # Should still get both groups
        assert result.interchange is not None
        assert len(result.interchange.groups) == 2

        # Should have error about missing GE
        assert any("Missing GE" in e.message for e in result.errors)

    def test_ge_count_mismatch(self):
        """Test detection of GE transaction count mismatch."""
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "GS*PO*SENDER*RECEIVER*20210101*1200*1*X*005010~"
            "ST*850*0001~"
            "SE*2*0001~"
            "GE*5*1~"  # Wrong count (says 5, should be 1)
            "IEA*1*000000001~"
        )
        result = parse_envelope(tokenize(content))

        assert result.interchange is not None
        # Should have error about count mismatch
        errors_and_warnings = result.errors + result.warnings
        assert any("count" in e.message.lower() for e in errors_and_warnings)


class TestTransactionSetParsing:
    """Tests for ST/SE transaction set parsing."""

    def test_parse_single_transaction(self):
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "GS*PO*SENDER*RECEIVER*20210101*1200*1*X*005010~"
            "ST*850*0001~"
            "BEG*00*SA*PO123456**20210101~"
            "SE*3*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        result = parse_envelope(tokenize(content))

        assert result.interchange is not None
        assert len(result.interchange.groups) == 1

        group = result.interchange.groups[0]
        assert len(group.transactions) == 1

        txn = group.transactions[0]
        assert txn.transaction_id == "850"
        assert txn.control_number == "0001"
        assert len(txn.content) == 1  # BEG segment

    def test_parse_multiple_transactions(self):
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "GS*PO*SENDER*RECEIVER*20210101*1200*1*X*005010~"
            "ST*850*0001~"
            "BEG*00*SA*PO001**20210101~"
            "SE*3*0001~"
            "ST*850*0002~"
            "BEG*00*SA*PO002**20210101~"
            "SE*3*0002~"
            "GE*2*1~"
            "IEA*1*000000001~"
        )
        result = parse_envelope(tokenize(content))

        assert result.interchange is not None
        group = result.interchange.groups[0]
        assert len(group.transactions) == 2

        assert group.transactions[0].control_number == "0001"
        assert group.transactions[1].control_number == "0002"

    def test_missing_se_recovery(self):
        """Test that parser recovers from missing SE."""
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "GS*PO*SENDER*RECEIVER*20210101*1200*1*X*005010~"
            "ST*850*0001~"
            "BEG*00*SA*PO001**20210101~"
            # Missing SE
            "ST*850*0002~"
            "BEG*00*SA*PO002**20210101~"
            "SE*3*0002~"
            "GE*2*1~"
            "IEA*1*000000001~"
        )
        result = parse_envelope(tokenize(content))

        # Should still get both transactions
        assert result.interchange is not None
        group = result.interchange.groups[0]
        assert len(group.transactions) == 2

        # Should have error about missing SE
        assert any("Missing SE" in e.message for e in result.errors)

    def test_se_count_mismatch(self):
        """Test detection of SE segment count mismatch."""
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "GS*PO*SENDER*RECEIVER*20210101*1200*1*X*005010~"
            "ST*850*0001~"
            "BEG*00*SA*PO123456**20210101~"
            "SE*10*0001~"  # Wrong count (says 10, should be 3)
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        result = parse_envelope(tokenize(content))

        assert result.interchange is not None
        # Should have error about count mismatch
        errors_and_warnings = result.errors + result.warnings
        assert any("count" in e.message.lower() for e in errors_and_warnings)

    def test_transaction_content_captured(self):
        """Test that transaction content segments are captured."""
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "GS*PO*SENDER*RECEIVER*20210101*1200*1*X*005010~"
            "ST*850*0001~"
            "BEG*00*SA*PO123456**20210101~"
            "REF*PO*12345~"
            "N1*BY*BUYER NAME~"
            "SE*5*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        result = parse_envelope(tokenize(content))

        txn = result.interchange.groups[0].transactions[0]
        assert len(txn.content) == 3  # BEG, REF, N1

        tags = [seg.tag for seg in txn.content]
        assert "BEG" in tags
        assert "REF" in tags
        assert "N1" in tags


class TestEmptyAndEdgeCases:
    """Tests for empty and edge cases."""

    def test_empty_input(self):
        """Test handling of empty input."""
        result = parse_envelope(tokenize(""))

        assert result.interchange is None
        assert result.has_fatal_errors()

    def test_no_segments_after_tokenize(self):
        """Test handling when tokenizer produces no segments."""
        from edi_schema.x12.ast import Delimiters
        from edi_schema.x12.parser.tokenizer import TokenizerResult

        empty_result = TokenizerResult(
            segments=[],
            delimiters=Delimiters(),
            errors=[],
        )
        result = parse_envelope(empty_result)

        assert result.interchange is None
        assert any("No segments" in e.message for e in result.errors)

    def test_unexpected_segment_at_interchange_level(self):
        """Test handling of unexpected segments at interchange level."""
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "XYZ*unexpected*segment~"  # Not GS
            "GS*PO*SENDER*RECEIVER*20210101*1200*1*X*005010~"
            "ST*850*0001~"
            "SE*2*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        result = parse_envelope(tokenize(content))

        assert result.interchange is not None
        # Should have warning about unexpected segment
        all_issues = result.errors + result.warnings
        assert any("nexpected" in e.message for e in all_issues)


class TestParseResult:
    """Tests for ParseResult properties."""

    def test_segments_parsed_count(self):
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "GS*PO*SENDER*RECEIVER*20210101*1200*1*X*005010~"
            "ST*850*0001~"
            "BEG*00*SA*PO123~"
            "SE*3*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        result = parse_envelope(tokenize(content))

        # Should have parsed 7 segments
        assert result.segments_parsed == 7

    def test_has_fatal_errors_false(self):
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "GS*PO*SENDER*RECEIVER*20210101*1200*1*X*005010~"
            "ST*850*0001~"
            "SE*2*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        result = parse_envelope(tokenize(content))

        assert not result.has_fatal_errors()

    def test_warnings_separated_from_errors(self):
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "XYZ*warning*segment~"  # Generates warning
            "GS*PO*SENDER*RECEIVER*20210101*1200*1*X*005010~"
            "ST*850*0001~"
            "SE*2*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        result = parse_envelope(tokenize(content))

        # Warnings should be separated from errors
        for warning in result.warnings:
            assert warning.severity == ErrorSeverity.WARNING


class TestRealSampleFiles:
    """Tests using real X12 sample files."""

    @pytest.fixture
    def samples_path(self) -> Path:
        return Path(__file__).parent.parent / "fixtures" / "x12_samples"

    def test_parse_835_remittance(self, samples_path: Path):
        """Test parsing 835 Remittance Advice."""
        file_path = samples_path / "835_remittance.x12"
        if not file_path.exists():
            pytest.skip(f"Sample file not found: {file_path}")

        content = file_path.read_text()
        result = parse_envelope(tokenize(content))

        assert not result.has_fatal_errors()
        assert result.interchange is not None
        assert len(result.interchange.groups) > 0

        # 835 should be in HP (Healthcare Claim Payment) group
        group = result.interchange.groups[0]
        assert group.functional_id in ("HP", "HR")  # HP or HR for remittance

        # Should have at least one 835 transaction
        assert len(group.transactions) > 0
        assert group.transactions[0].transaction_id == "835"

    def test_parse_837p_professional_claim(self, samples_path: Path):
        """Test parsing 837P Professional Claim."""
        file_path = samples_path / "837P_professional_claim.x12"
        if not file_path.exists():
            pytest.skip(f"Sample file not found: {file_path}")

        content = file_path.read_text()
        result = parse_envelope(tokenize(content))

        assert not result.has_fatal_errors()
        assert result.interchange is not None

        # Should have HC (Healthcare Claim) group
        group = result.interchange.groups[0]
        assert group.functional_id == "HC"

        # Should have 837 transaction
        assert group.transactions[0].transaction_id == "837"

    def test_parse_837i_institutional_claim(self, samples_path: Path):
        """Test parsing 837I Institutional Claim."""
        file_path = samples_path / "837I_institutional_claim.x12"
        if not file_path.exists():
            pytest.skip(f"Sample file not found: {file_path}")

        content = file_path.read_text()
        result = parse_envelope(tokenize(content))

        assert not result.has_fatal_errors()
        assert result.interchange is not None

    def test_parse_834_enrollment(self, samples_path: Path):
        """Test parsing 834 Benefit Enrollment."""
        file_path = samples_path / "834_enrollment.x12"
        if not file_path.exists():
            pytest.skip(f"Sample file not found: {file_path}")

        content = file_path.read_text()
        result = parse_envelope(tokenize(content))

        assert not result.has_fatal_errors()
        assert result.interchange is not None

    def test_parse_270_eligibility_inquiry(self, samples_path: Path):
        """Test parsing 270 Eligibility Inquiry."""
        file_path = samples_path / "270_eligibility_inquiry.x12"
        if not file_path.exists():
            pytest.skip(f"Sample file not found: {file_path}")

        content = file_path.read_text()
        result = parse_envelope(tokenize(content))

        assert not result.has_fatal_errors()

    def test_parse_271_eligibility_response(self, samples_path: Path):
        """Test parsing 271 Eligibility Response."""
        file_path = samples_path / "271_eligibility_response.x12"
        if not file_path.exists():
            pytest.skip(f"Sample file not found: {file_path}")

        content = file_path.read_text()
        result = parse_envelope(tokenize(content))

        assert not result.has_fatal_errors()

    def test_parse_all_samples(self, samples_path: Path):
        """Test that all sample files can be parsed through envelope parser."""
        if not samples_path.exists():
            pytest.skip(f"Samples directory not found: {samples_path}")

        for file_path in samples_path.glob("*.x12"):
            content = file_path.read_text()
            result = parse_envelope(tokenize(content))

            assert not result.has_fatal_errors(), f"Fatal error in {file_path.name}"
            assert result.interchange is not None, f"No interchange in {file_path.name}"
            assert len(result.interchange.groups) > 0, f"No groups in {file_path.name}"


class TestComplexScenarios:
    """Tests for complex parsing scenarios."""

    def test_deeply_nested_structure(self):
        """Test parsing a document with multiple groups and transactions."""
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            # Group 1 with 2 transactions
            "GS*PO*SENDER*RECEIVER*20210101*1200*1*X*005010~"
            "ST*850*0001~"
            "BEG*00*SA*PO001**20210101~"
            "SE*3*0001~"
            "ST*850*0002~"
            "BEG*00*SA*PO002**20210101~"
            "SE*3*0002~"
            "GE*2*1~"
            # Group 2 with 1 transaction
            "GS*IN*SENDER*RECEIVER*20210101*1201*2*X*005010~"
            "ST*810*0001~"
            "BIG*20210101*INV001~"
            "SE*3*0001~"
            "GE*1*2~"
            # Group 3 with 3 transactions
            "GS*SH*SENDER*RECEIVER*20210101*1202*3*X*005010~"
            "ST*856*0001~"
            "BSN*00*SHIP001*20210101*1200~"
            "SE*3*0001~"
            "ST*856*0002~"
            "BSN*00*SHIP002*20210101*1201~"
            "SE*3*0002~"
            "ST*856*0003~"
            "BSN*00*SHIP003*20210101*1202~"
            "SE*3*0003~"
            "GE*3*3~"
            "IEA*3*000000001~"
        )
        result = parse_envelope(tokenize(content))

        assert not result.has_fatal_errors()
        assert result.interchange is not None
        assert len(result.interchange.groups) == 3

        # Verify group 1
        assert len(result.interchange.groups[0].transactions) == 2
        assert result.interchange.groups[0].functional_id == "PO"

        # Verify group 2
        assert len(result.interchange.groups[1].transactions) == 1
        assert result.interchange.groups[1].functional_id == "IN"

        # Verify group 3
        assert len(result.interchange.groups[2].transactions) == 3
        assert result.interchange.groups[2].functional_id == "SH"

    def test_recovery_from_multiple_errors(self):
        """Test recovery from multiple errors in one document."""
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "GS*PO*SENDER*RECEIVER*20210101*1200*1*X*005010~"
            "ST*850*0001~"
            "BEG*00*SA*PO001**20210101~"
            # Missing SE for first transaction
            "ST*850*0002~"
            "BEG*00*SA*PO002**20210101~"
            "SE*3*0002~"
            # Missing GE for first group
            "GS*IN*SENDER*RECEIVER*20210101*1201*2*X*005010~"
            "ST*810*0001~"
            "SE*2*0001~"
            "GE*1*2~"
            # Missing IEA
        )
        result = parse_envelope(tokenize(content))

        # Should still parse structure
        assert result.interchange is not None
        assert len(result.interchange.groups) == 2

        # Should have multiple errors
        assert len(result.errors) >= 2  # At least SE and GE missing

    def test_transaction_with_many_segments(self):
        """Test parsing a transaction with many segments."""
        # Build a 997 with multiple AK2 loops
        segments = [
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~",
            "GS*FA*SENDER*RECEIVER*20210101*1200*1*X*005010~",
            "ST*997*0001~",
            "AK1*PO*1~",
        ]

        # Add many AK2 loops
        for i in range(10):
            segments.extend(
                [
                    f"AK2*850*{i:04d}~",
                    "AK5*A~",
                ]
            )

        segments.extend(
            [
                "AK9*A*10*10*10~",
                "SE*26*0001~",  # ST + AK1 + 20 AK2/AK5 + AK9 + SE = 24... but count includes all
                "GE*1*1~",
                "IEA*1*000000001~",
            ]
        )

        content = "".join(segments)
        result = parse_envelope(tokenize(content))

        assert result.interchange is not None
        txn = result.interchange.groups[0].transactions[0]

        # Should have captured all the content segments
        assert len(txn.content) > 10  # At least 20 AK2/AK5 segments

    def test_implementation_reference_in_st(self):
        """Test parsing ST with implementation reference (ST03)."""
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "GS*HC*SENDER*RECEIVER*20210101*1200*1*X*005010X222A1~"
            "ST*837*0001*005010X222A1~"  # With implementation reference
            "BHT*0019*00*12345*20210101*1200*CH~"
            "SE*3*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        result = parse_envelope(tokenize(content))

        assert not result.has_fatal_errors()
        txn = result.interchange.groups[0].transactions[0]
        assert txn.implementation_reference == "005010X222A1"
