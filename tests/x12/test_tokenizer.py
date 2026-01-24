"""
Tests for X12 Tokenizer.
"""

from pathlib import Path

import pytest

from edi_schema.x12.ast import (
    ErrorSeverity,
    RawComposite,
)
from edi_schema.x12.parser.tokenizer import (
    TokenizerResult,
    X12Tokenizer,
    tokenize,
)


class TestTokenizerBasics:
    """Basic tokenizer tests."""

    def test_tokenizer_creation(self):
        tokenizer = X12Tokenizer()
        assert tokenizer is not None

    def test_tokenize_convenience_function(self):
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "GS*PO*SENDER*RECEIVER*20210101*1200*1*X*005010~"
            "ST*850*0001~"
            "SE*3*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        result = tokenize(content)
        assert isinstance(result, TokenizerResult)
        assert len(result.segments) > 0


class TestDelimiterExtraction:
    """Tests for delimiter extraction from ISA."""

    def test_extract_standard_delimiters(self):
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "IEA*1*000000001~"
        )
        result = tokenize(content)

        assert result.delimiters.element == "*"
        assert result.delimiters.segment == "~"
        assert result.delimiters.component == ":"
        assert result.delimiters.repetition == "^"

    def test_extract_custom_delimiters(self):
        # Using pipe as element separator, > as component
        content = (
            "ISA|00|          |00|          |ZZ|SENDER         |ZZ|RECEIVER       "
            "|210101|1200|^|00501|000000001|0|P|>~"
            "IEA|1|000000001~"
        )
        result = tokenize(content)

        assert result.delimiters.element == "|"
        assert result.delimiters.component == ">"

    def test_missing_isa(self):
        content = "GS*PO*SENDER*RECEIVER*20210101*1200*1*X*005010~"
        result = tokenize(content)

        assert result.has_fatal_errors()
        assert any("ISA" in e.message for e in result.errors)

    def test_isa_too_short(self):
        content = "ISA*00*short"
        result = tokenize(content)

        assert result.has_fatal_errors()
        assert any("too short" in e.message.lower() for e in result.errors)


class TestSegmentParsing:
    """Tests for segment parsing."""

    def test_parse_simple_segment(self):
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "BEG*00*SA*PO123456**20210101~"
            "IEA*1*000000001~"
        )
        result = tokenize(content)

        # Find BEG segment
        beg = next((s for s in result.segments if s.tag == "BEG"), None)
        assert beg is not None
        assert len(beg.elements) == 5
        assert beg.get_element_value(1) == "00"
        assert beg.get_element_value(2) == "SA"
        assert beg.get_element_value(3) == "PO123456"
        assert beg.get_element_value(4) == ""  # Empty element
        assert beg.get_element_value(5) == "20210101"

    def test_parse_segment_with_composite(self):
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "SV1*HC:99213*150.00*UN*1~"
            "IEA*1*000000001~"
        )
        result = tokenize(content)

        sv1 = next((s for s in result.segments if s.tag == "SV1"), None)
        assert sv1 is not None

        # First element should be a composite
        elem1 = sv1.get_element(1)
        assert isinstance(elem1, RawComposite)
        assert elem1.components == ["HC", "99213"]
        assert elem1.get_component(1) == "HC"
        assert elem1.get_component(2) == "99213"

    def test_parse_segment_with_many_elements(self):
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "NM1*IL*1*DOE*JOHN****MI*12345~"
            "IEA*1*000000001~"
        )
        result = tokenize(content)

        nm1 = next((s for s in result.segments if s.tag == "NM1"), None)
        assert nm1 is not None
        assert len(nm1.elements) == 9
        assert nm1.get_element_value(1) == "IL"
        assert nm1.get_element_value(3) == "DOE"
        assert nm1.get_element_value(4) == "JOHN"
        assert nm1.get_element_value(9) == "12345"

    def test_segment_tag_extraction(self):
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "ST*850*0001~"
            "BEG*00*SA*PO123~"
            "SE*3*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        result = tokenize(content)

        tags = [s.tag for s in result.segments]
        assert "ISA" in tags
        assert "ST" in tags
        assert "BEG" in tags
        assert "SE" in tags
        assert "GE" in tags
        assert "IEA" in tags


class TestLineEndingHandling:
    """Tests for handling various line ending styles."""

    def test_crlf_after_terminators(self):
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~\r\n"
            "GS*PO*SENDER*RECEIVER*20210101*1200*1*X*005010~\r\n"
            "IEA*1*000000001~\r\n"
        )
        result = tokenize(content)

        assert not result.has_fatal_errors()
        tags = [s.tag for s in result.segments]
        assert "ISA" in tags
        assert "GS" in tags
        assert "IEA" in tags

    def test_lf_after_terminators(self):
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~\n"
            "GS*PO*SENDER*RECEIVER*20210101*1200*1*X*005010~\n"
            "IEA*1*000000001~\n"
        )
        result = tokenize(content)

        assert not result.has_fatal_errors()
        assert len(result.segments) == 3


class TestErrorRecovery:
    """Tests for error recovery."""

    def test_recover_from_empty_segment(self):
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "~~"  # Empty segment
            "ST*850*0001~"
            "IEA*1*000000001~"
        )
        result = tokenize(content)

        # Should still parse ST
        tags = [s.tag for s in result.segments]
        assert "ST" in tags

    def test_recover_from_invalid_tag(self):
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "XX*invalid*segment~"  # Invalid tag
            "ST*850*0001~"
            "IEA*1*000000001~"
        )
        result = tokenize(content)

        # Should still parse valid segments
        tags = [s.tag for s in result.segments]
        assert "ST" in tags
        assert "IEA" in tags

    def test_statistics_tracking(self):
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "ST*850*0001~"
            "SE*2*0001~"
            "IEA*1*000000001~"
        )
        result = tokenize(content)

        assert result.total_characters == len(content)
        assert result.segments_parsed == 4


class TestSourcePositionTracking:
    """Tests for source position tracking."""

    def test_segment_positions(self):
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "ST*850*0001~"
            "IEA*1*000000001~"
        )
        result = tokenize(content)

        # ISA should be at position 0
        isa = result.segments[0]
        assert isa.tag == "ISA"
        assert isa.position.offset == 0

        # ST should be after ISA (106 chars)
        st = next(s for s in result.segments if s.tag == "ST")
        assert st.position.offset > 100

    def test_element_positions(self):
        content = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
            "BEG*00*SA*PO123~"
            "IEA*1*000000001~"
        )
        result = tokenize(content)

        beg = next(s for s in result.segments if s.tag == "BEG")

        # Elements should have positions relative to segment
        elem1 = beg.elements[0]
        assert elem1.element_index == 1


class TestRealSampleFiles:
    """Tests using real X12 sample files."""

    @pytest.fixture
    def samples_path(self) -> Path:
        return Path(__file__).parent.parent / "fixtures" / "x12_samples"

    def test_tokenize_835_remittance(self, samples_path: Path):
        """Test tokenizing 835 Remittance Advice."""
        file_path = samples_path / "835_remittance.x12"
        if not file_path.exists():
            pytest.skip(f"Sample file not found: {file_path}")

        content = file_path.read_text()
        result = tokenize(content)

        assert not result.has_fatal_errors()
        assert result.segments_parsed > 0

        # Check for expected segments
        tags = [s.tag for s in result.segments]
        assert "ISA" in tags
        assert "GS" in tags
        assert "ST" in tags
        assert "BPR" in tags
        assert "CLP" in tags
        assert "SE" in tags
        assert "GE" in tags
        assert "IEA" in tags

    def test_tokenize_837p_professional_claim(self, samples_path: Path):
        """Test tokenizing 837P Professional Claim."""
        file_path = samples_path / "837P_professional_claim.x12"
        if not file_path.exists():
            pytest.skip(f"Sample file not found: {file_path}")

        content = file_path.read_text()
        result = tokenize(content)

        assert not result.has_fatal_errors()

        tags = [s.tag for s in result.segments]
        assert "ISA" in tags
        assert "ST" in tags
        assert "BHT" in tags
        assert "HL" in tags  # Hierarchical levels
        assert "CLM" in tags  # Claim
        assert "SV1" in tags  # Service line

    def test_tokenize_837i_institutional_claim(self, samples_path: Path):
        """Test tokenizing 837I Institutional Claim."""
        file_path = samples_path / "837I_institutional_claim.x12"
        if not file_path.exists():
            pytest.skip(f"Sample file not found: {file_path}")

        content = file_path.read_text()
        result = tokenize(content)

        assert not result.has_fatal_errors()
        assert result.segments_parsed > 0

    def test_tokenize_834_enrollment(self, samples_path: Path):
        """Test tokenizing 834 Benefit Enrollment."""
        file_path = samples_path / "834_enrollment.x12"
        if not file_path.exists():
            pytest.skip(f"Sample file not found: {file_path}")

        content = file_path.read_text()
        result = tokenize(content)

        assert not result.has_fatal_errors()
        tags = [s.tag for s in result.segments]
        assert "ISA" in tags
        assert "INS" in tags or "ST" in tags

    def test_tokenize_270_eligibility_inquiry(self, samples_path: Path):
        """Test tokenizing 270 Eligibility Inquiry."""
        file_path = samples_path / "270_eligibility_inquiry.x12"
        if not file_path.exists():
            pytest.skip(f"Sample file not found: {file_path}")

        content = file_path.read_text()
        result = tokenize(content)

        assert not result.has_fatal_errors()

    def test_tokenize_271_eligibility_response(self, samples_path: Path):
        """Test tokenizing 271 Eligibility Response."""
        file_path = samples_path / "271_eligibility_response.x12"
        if not file_path.exists():
            pytest.skip(f"Sample file not found: {file_path}")

        content = file_path.read_text()
        result = tokenize(content)

        assert not result.has_fatal_errors()

    def test_tokenize_all_samples(self, samples_path: Path):
        """Test that all sample files can be tokenized."""
        if not samples_path.exists():
            pytest.skip(f"Samples directory not found: {samples_path}")

        for file_path in samples_path.glob("*.x12"):
            content = file_path.read_text()
            result = tokenize(content)

            assert not result.has_fatal_errors(), f"Fatal error in {file_path.name}"
            assert result.segments_parsed > 0, f"No segments in {file_path.name}"

            # All files should have ISA/IEA envelope
            tags = [s.tag for s in result.segments]
            assert "ISA" in tags, f"Missing ISA in {file_path.name}"
            assert "IEA" in tags, f"Missing IEA in {file_path.name}"


class TestTokenizerResult:
    """Tests for TokenizerResult."""

    def test_is_valid_no_errors(self):
        result = TokenizerResult()
        assert result.is_valid()

    def test_is_valid_with_errors(self):
        from edi_schema.x12.ast import ErrorCategory, ParseError

        result = TokenizerResult(
            errors=[ParseError(code="E1", message="Test", category=ErrorCategory.STRUCTURAL)]
        )
        assert not result.is_valid()

    def test_has_fatal_errors(self):
        from edi_schema.x12.ast import ErrorCategory, ParseError

        result = TokenizerResult(
            errors=[
                ParseError(
                    code="F1",
                    message="Fatal",
                    category=ErrorCategory.STRUCTURAL,
                    severity=ErrorSeverity.FATAL,
                )
            ]
        )
        assert result.has_fatal_errors()

    def test_has_no_fatal_errors(self):
        from edi_schema.x12.ast import ErrorCategory, ParseError

        result = TokenizerResult(
            errors=[
                ParseError(
                    code="W1",
                    message="Warning",
                    category=ErrorCategory.STRUCTURAL,
                    severity=ErrorSeverity.WARNING,
                )
            ]
        )
        assert not result.has_fatal_errors()
