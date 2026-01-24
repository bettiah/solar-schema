"""
Tests for EDIFACT Tokenizer.
"""

from edi_schema.edifact.ast import (
    Delimiters,
    ErrorCategory,
    ErrorSeverity,
    ParseError,
)
from edi_schema.edifact.parser.tokenizer import (
    EdifactTokenizer,
    TokenizerResult,
    tokenize,
)


class TestTokenizerBasics:
    """Basic tokenizer tests."""

    def test_tokenizer_creation(self):
        tokenizer = EdifactTokenizer()
        assert tokenizer is not None

    def test_tokenize_convenience_function(self):
        content = (
            "UNA:+.? '"
            "UNB+UNOC:3+SENDER:14+RECEIVER:14+231031:1430+12345'"
            "UNH+1+INVOIC:D:23A:UN'"
            "UNT+2+1'"
            "UNZ+1+12345'"
        )
        result = tokenize(content)
        assert isinstance(result, TokenizerResult)
        assert len(result.segments) > 0

    def test_tokenize_bytes_input(self):
        content = b"UNB+UNOC:3+SENDER+RECEIVER+231031:1430+1'UNZ+1+1'"
        result = tokenize(content)
        assert isinstance(result, TokenizerResult)
        assert len(result.segments) > 0


class TestUnaDetection:
    """Tests for UNA segment detection and delimiter extraction."""

    def test_detect_standard_una(self):
        content = "UNA:+.? 'UNB+UNOC:3+SENDER+RECEIVER+231031:1430+1'UNZ+1+1'"
        result = tokenize(content)

        assert result.has_una
        assert result.delimiters.component == ":"
        assert result.delimiters.element == "+"
        assert result.delimiters.decimal == "."
        assert result.delimiters.release == "?"
        assert result.delimiters.segment == "'"

    def test_detect_custom_una(self):
        # Using custom delimiters: # for component, | for element, ~ for segment
        content = "UNA#|.?~'UNB|UNOC#3|SENDER|RECEIVER|231031#1430|1'UNZ|1|1'"
        result = tokenize(content)

        assert result.has_una
        assert result.delimiters.component == "#"
        assert result.delimiters.element == "|"
        assert result.delimiters.segment == "'"

    def test_default_delimiters_without_una(self):
        content = "UNB+UNOC:3+SENDER+RECEIVER+231031:1430+1'UNZ+1+1'"
        result = tokenize(content)

        assert not result.has_una
        # Should use defaults
        assert result.delimiters.component == ":"
        assert result.delimiters.element == "+"
        assert result.delimiters.decimal == "."
        assert result.delimiters.release == "?"
        assert result.delimiters.segment == "'"

    def test_una_too_short(self):
        content = "UNA:+.'"  # Only 7 chars, needs 9
        result = tokenize(content)

        # Should fall back to defaults
        assert not result.has_una
        assert any("UNA" in str(e.message) for e in result.errors)

    def test_missing_unb(self):
        content = "UNH+1+INVOIC:D:23A:UN'"  # No UNB
        result = tokenize(content)

        assert result.has_fatal_errors()
        assert any("UNB" in str(e.message) for e in result.errors)

    def test_empty_document(self):
        result = tokenize("")
        assert result.has_fatal_errors()
        assert any("Empty" in str(e.message) for e in result.errors)

    def test_whitespace_only_document(self):
        result = tokenize("   \n\t  ")
        assert result.has_fatal_errors()


class TestSegmentParsing:
    """Tests for segment parsing."""

    def test_parse_simple_segment(self):
        content = "UNB+UNOC:3+SENDER+RECEIVER+231031:1430+12345'BGM+380+INV001+9'UNZ+1+12345'"
        result = tokenize(content)

        # Find BGM segment
        bgm = next((s for s in result.segments if s.tag == "BGM"), None)
        assert bgm is not None
        assert len(bgm.elements) == 3
        assert bgm.get_element_value(1) == "380"
        assert bgm.get_element_value(2) == "INV001"
        assert bgm.get_element_value(3) == "9"

    def test_parse_segment_with_composite(self):
        content = "UNB+UNOC:3+SENDER:14+RECEIVER:ZZ+231031:1430+12345'UNZ+1+12345'"
        result = tokenize(content)

        unb = next((s for s in result.segments if s.tag == "UNB"), None)
        assert unb is not None

        # Element 1 should be composite (UNOC:3)
        elem1 = unb.get_element(1)
        assert elem1 is not None
        assert elem1.is_composite
        assert elem1.components is not None
        assert len(elem1.components) == 2
        assert elem1.get_component(1) == "UNOC"
        assert elem1.get_component(2) == "3"

        # Element 2 should be composite (SENDER:14)
        elem2 = unb.get_element(2)
        assert elem2 is not None
        assert elem2.is_composite
        assert elem2.get_component(1) == "SENDER"
        assert elem2.get_component(2) == "14"

    def test_parse_segment_with_empty_elements(self):
        content = "UNB+UNOC:3+SENDER+RECEIVER+231031:1430+12345'NAD+BY+++BUYER NAME'UNZ+1+12345'"
        result = tokenize(content)

        nad = next((s for s in result.segments if s.tag == "NAD"), None)
        assert nad is not None
        assert len(nad.elements) == 4
        assert nad.get_element_value(1) == "BY"
        assert nad.get_element_value(2) == ""  # Empty
        assert nad.get_element_value(3) == ""  # Empty
        assert nad.get_element_value(4) == "BUYER NAME"

    def test_segment_tag_extraction(self):
        content = (
            "UNB+UNOC:3+SENDER+RECEIVER+231031:1430+1'"
            "UNH+1+INVOIC:D:23A:UN'"
            "BGM+380+INV001+9'"
            "DTM+137:20231031:102'"
            "UNT+4+1'"
            "UNZ+1+1'"
        )
        result = tokenize(content)

        tags = [s.tag for s in result.segments]
        assert "UNB" in tags
        assert "UNH" in tags
        assert "BGM" in tags
        assert "DTM" in tags
        assert "UNT" in tags
        assert "UNZ" in tags

    def test_parse_many_elements(self):
        content = (
            "UNB+UNOC:3+SENDER+RECEIVER+231031:1430+1'"
            "NAD+BY+5412345678908::9++BUYER NAME+ADDRESS LINE 1+CITY++12345+US'"
            "UNZ+1+1'"
        )
        result = tokenize(content)

        nad = next((s for s in result.segments if s.tag == "NAD"), None)
        assert nad is not None
        assert len(nad.elements) == 9


class TestReleaseCharacter:
    """Tests for release character handling."""

    def test_escaped_element_separator(self):
        """Test ?+ → literal +"""
        content = (
            "UNA:+.? 'UNB+UNOC:3+SENDER+RECEIVER+231031:1430+1'FTX+AAA+++VALUE?+WITH?+PLUS'UNZ+1+1'"
        )
        result = tokenize(content)

        ftx = next((s for s in result.segments if s.tag == "FTX"), None)
        assert ftx is not None

        # The value should have literal + signs
        elem4 = ftx.get_element_value(4)
        assert elem4 == "VALUE+WITH+PLUS"

    def test_escaped_component_separator(self):
        """Test ?: → literal :"""
        content = (
            "UNA:+.? 'UNB+UNOC:3+SENDER+RECEIVER+231031:1430+1'FTX+AAA+++TIME?:12?:30'UNZ+1+1'"
        )
        result = tokenize(content)

        ftx = next((s for s in result.segments if s.tag == "FTX"), None)
        assert ftx is not None

        elem4 = ftx.get_element_value(4)
        assert elem4 == "TIME:12:30"

    def test_escaped_segment_terminator(self):
        """Test ?' → literal '"""
        content = (
            "UNA:+.? 'UNB+UNOC:3+SENDER+RECEIVER+231031:1430+1'FTX+AAA+++IT?'S A TEST'UNZ+1+1'"
        )
        result = tokenize(content)

        ftx = next((s for s in result.segments if s.tag == "FTX"), None)
        assert ftx is not None

        elem4 = ftx.get_element_value(4)
        assert elem4 == "IT'S A TEST"

    def test_escaped_release_character(self):
        """Test ?? → literal ?"""
        content = "UNA:+.? 'UNB+UNOC:3+SENDER+RECEIVER+231031:1430+1'FTX+AAA+++WHAT??'UNZ+1+1'"
        result = tokenize(content)

        ftx = next((s for s in result.segments if s.tag == "FTX"), None)
        assert ftx is not None

        elem4 = ftx.get_element_value(4)
        assert elem4 == "WHAT?"

    def test_multiple_escapes(self):
        """Test multiple escape sequences in one value."""
        content = (
            "UNA:+.? 'UNB+UNOC:3+SENDER+RECEIVER+231031:1430+1'FTX+AAA+++A?+B?:C?'D??E'UNZ+1+1'"
        )
        result = tokenize(content)

        ftx = next((s for s in result.segments if s.tag == "FTX"), None)
        assert ftx is not None

        elem4 = ftx.get_element_value(4)
        assert elem4 == "A+B:C'D?E"

    def test_escaped_in_composite(self):
        """Test escape sequences within composite elements."""
        content = "UNA:+.? 'UNB+UNOC:3+SENDER+RECEIVER+231031:1430+1'RFF+ON?:123:EXTRA'UNZ+1+1'"
        result = tokenize(content)

        rff = next((s for s in result.segments if s.tag == "RFF"), None)
        assert rff is not None

        elem1 = rff.get_element(1)
        assert elem1 is not None
        assert elem1.is_composite
        # First component should be "ON:123" (escaped :)
        assert elem1.get_component(1) == "ON:123"
        assert elem1.get_component(2) == "EXTRA"


class TestLineEndingHandling:
    """Tests for handling various line ending styles."""

    def test_crlf_after_terminators(self):
        content = (
            "UNB+UNOC:3+SENDER+RECEIVER+231031:1430+1'\r\n"
            "UNH+1+INVOIC:D:23A:UN'\r\n"
            "UNT+2+1'\r\n"
            "UNZ+1+1'\r\n"
        )
        result = tokenize(content)

        assert not result.has_fatal_errors()
        tags = [s.tag for s in result.segments]
        assert "UNB" in tags
        assert "UNH" in tags
        assert "UNT" in tags
        assert "UNZ" in tags

    def test_lf_after_terminators(self):
        content = (
            "UNB+UNOC:3+SENDER+RECEIVER+231031:1430+1'\n"
            "UNH+1+INVOIC:D:23A:UN'\n"
            "UNT+2+1'\n"
            "UNZ+1+1'\n"
        )
        result = tokenize(content)

        assert not result.has_fatal_errors()
        assert len(result.segments) == 4

    def test_cr_after_terminators(self):
        content = (
            "UNB+UNOC:3+SENDER+RECEIVER+231031:1430+1'\r"
            "UNH+1+INVOIC:D:23A:UN'\r"
            "UNT+2+1'\r"
            "UNZ+1+1'\r"
        )
        result = tokenize(content)

        assert not result.has_fatal_errors()
        assert len(result.segments) == 4

    def test_no_line_endings(self):
        content = "UNB+UNOC:3+SENDER+RECEIVER+231031:1430+1'UNH+1+INVOIC:D:23A:UN'UNT+2+1'UNZ+1+1'"
        result = tokenize(content)

        assert not result.has_fatal_errors()
        assert len(result.segments) == 4


class TestErrorRecovery:
    """Tests for error recovery."""

    def test_recover_from_empty_segment(self):
        content = (
            "UNB+UNOC:3+SENDER+RECEIVER+231031:1430+1'"
            "''"  # Empty segments
            "UNH+1+INVOIC:D:23A:UN'"
            "UNZ+1+1'"
        )
        result = tokenize(content)

        # Should still parse UNH
        tags = [s.tag for s in result.segments]
        assert "UNH" in tags

    def test_recover_from_invalid_tag(self):
        content = (
            "UNB+UNOC:3+SENDER+RECEIVER+231031:1430+1'"
            "XX+invalid+segment'"  # Invalid tag (only 2 chars is ok in EDIFACT)
            "UNH+1+INVOIC:D:23A:UN'"
            "UNZ+1+1'"
        )
        result = tokenize(content)

        # Should still parse valid segments
        tags = [s.tag for s in result.segments]
        assert "UNH" in tags
        assert "UNZ" in tags

    def test_statistics_tracking(self):
        content = "UNB+UNOC:3+SENDER+RECEIVER+231031:1430+1'UNH+1+INVOIC:D:23A:UN'UNT+2+1'UNZ+1+1'"
        result = tokenize(content)

        assert result.total_bytes == len(content)
        assert result.segment_count == 4
        assert result.element_count > 0

    def test_component_count(self):
        content = "UNB+UNOC:3+SENDER:14+RECEIVER:ZZ+231031:1430+1'UNZ+1+1'"
        result = tokenize(content)

        # UNB has several composite elements
        assert result.component_count > 0


class TestSourcePositionTracking:
    """Tests for source position tracking."""

    def test_segment_positions(self):
        content = "UNB+UNOC:3+SENDER+RECEIVER+231031:1430+1'UNH+1+INVOIC:D:23A:UN'UNZ+1+1'"
        result = tokenize(content)

        # UNB should be at position 0
        unb = result.segments[0]
        assert unb.tag == "UNB"
        assert unb.position.offset == 0

        # UNH should be after UNB
        unh = next(s for s in result.segments if s.tag == "UNH")
        assert unh.position.offset > 0

    def test_element_positions(self):
        content = "UNB+UNOC:3+SENDER+RECEIVER+231031:1430+1'BGM+380+INV001+9'UNZ+1+1'"
        result = tokenize(content)

        bgm = next(s for s in result.segments if s.tag == "BGM")

        # Elements should have positions
        for i, elem in enumerate(bgm.elements, start=1):
            assert elem.element_index == i

    def test_position_with_una(self):
        content = (
            "UNA:+.? '"  # 9 bytes
            "UNB+UNOC:3+SENDER+RECEIVER+231031:1430+1'"
            "UNZ+1+1'"
        )
        result = tokenize(content)

        # UNB should be at position 9 (after UNA)
        unb = next(s for s in result.segments if s.tag == "UNB")
        assert unb.position.offset == 9


class TestTokenizerResult:
    """Tests for TokenizerResult."""

    def test_is_valid_no_errors(self):
        result = TokenizerResult()
        assert result.is_valid()

    def test_is_valid_with_errors(self):
        result = TokenizerResult(
            errors=[ParseError(code="E1", message="Test", category=ErrorCategory.STRUCTURAL)]
        )
        assert not result.is_valid()

    def test_has_fatal_errors(self):
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


class TestDelimitersClass:
    """Tests for the Delimiters class used by tokenizer."""

    def test_defaults(self):
        delim = Delimiters.defaults()
        assert delim.component == ":"
        assert delim.element == "+"
        assert delim.decimal == "."
        assert delim.release == "?"
        assert delim.segment == "'"

    def test_from_una(self):
        delim = Delimiters.from_una("UNA:+.? '")
        assert delim.component == ":"
        assert delim.element == "+"
        assert delim.decimal == "."
        assert delim.release == "?"
        assert delim.segment == "'"

    def test_to_una(self):
        delim = Delimiters.defaults()
        una = delim.to_una()
        assert una == "UNA:+.? '"


class TestRealWorldMessages:
    """Tests with realistic EDIFACT message structures."""

    def test_invoic_message(self):
        """Test tokenizing a realistic INVOIC message structure."""
        content = (
            "UNA:+.? '"
            "UNB+UNOC:3+SENDER:14+RECEIVER:14+231031:1430+12345++INVOIC'"
            "UNH+1+INVOIC:D:96A:UN'"
            "BGM+380+INV2023001+9'"
            "DTM+137:20231031:102'"
            "NAD+BY+++BUYER COMPANY'"
            "NAD+SU+++SELLER COMPANY'"
            "LIN+1++PRODUCT123:SA'"
            "QTY+47:10'"
            "MOA+66:100.00'"
            "UNS+S'"
            "MOA+86:1000.00'"
            "UNT+12+1'"
            "UNZ+1+12345'"
        )
        result = tokenize(content)

        assert not result.has_fatal_errors()

        tags = [s.tag for s in result.segments]
        assert "UNB" in tags
        assert "UNH" in tags
        assert "BGM" in tags
        assert "DTM" in tags
        assert "NAD" in tags
        assert "LIN" in tags
        assert "QTY" in tags
        assert "MOA" in tags
        assert "UNS" in tags
        assert "UNT" in tags
        assert "UNZ" in tags

    def test_orders_message(self):
        """Test tokenizing a realistic ORDERS message structure."""
        content = (
            "UNB+UNOC:3+BUYER:14+SELLER:14+231031:0900+1'"
            "UNH+1+ORDERS:D:96A:UN'"
            "BGM+220+PO2023001+9'"
            "DTM+137:20231031:102'"
            "NAD+BY+++BUYER COMPANY+STREET 1+CITY++12345+US'"
            "NAD+SU+++SELLER COMPANY'"
            "LIN+1++SKU123:BP'"
            "QTY+21:5'"
            "PRI+AAA:10.00'"
            "LIN+2++SKU456:BP'"
            "QTY+21:10'"
            "PRI+AAA:20.00'"
            "UNS+S'"
            "CNT+2:2'"
            "UNT+14+1'"
            "UNZ+1+1'"
        )
        result = tokenize(content)

        assert not result.has_fatal_errors()
        assert result.segment_count == 16  # All segments including UNB/UNZ

        # Check line items
        lin_segments = [s for s in result.segments if s.tag == "LIN"]
        assert len(lin_segments) == 2

    def test_desadv_message(self):
        """Test tokenizing a DESADV (Dispatch Advice) message."""
        content = (
            "UNB+UNOC:3+SENDER+RECEIVER+231031:1200+1'"
            "UNH+1+DESADV:D:96A:UN'"
            "BGM+351+DESADV001+9'"
            "DTM+137:20231031:102'"
            "DTM+11:20231101:102'"
            "NAD+CZ+++CONSIGNEE'"
            "NAD+SU+++SUPPLIER'"
            "CPS+1'"
            "PAC+5++CT'"
            "LIN+1++ITEM001:SA'"
            "QTY+12:50'"
            "UNT+11+1'"
            "UNZ+1+1'"
        )
        result = tokenize(content)

        assert not result.has_fatal_errors()

        tags = [s.tag for s in result.segments]
        assert "DESADV" not in tags  # DESADV is the message type, not a segment
        assert "CPS" in tags
        assert "PAC" in tags

    def test_message_with_functional_group(self):
        """Test message with UNG/UNE functional group envelope."""
        content = (
            "UNB+UNOC:3+SENDER+RECEIVER+231031:1430+1'"
            "UNG+INVOIC+SENDER+RECEIVER+231031:1430+1+UN+D:96A'"
            "UNH+1+INVOIC:D:96A:UN'"
            "BGM+380+INV001+9'"
            "UNT+2+1'"
            "UNE+1+1'"
            "UNZ+1+1'"
        )
        result = tokenize(content)

        assert not result.has_fatal_errors()

        tags = [s.tag for s in result.segments]
        assert "UNG" in tags
        assert "UNE" in tags


class TestEdgeCases:
    """Tests for edge cases and unusual inputs."""

    def test_minimum_valid_document(self):
        """Test the minimum possible valid EDIFACT document."""
        content = "UNB+UNOC:3+S+R+231031:1430+1'UNZ+0+1'"
        result = tokenize(content)

        assert not result.has_fatal_errors()
        assert result.segment_count == 2

    def test_very_long_element(self):
        """Test handling of very long element values."""
        long_value = "A" * 1000
        content = f"UNB+UNOC:3+SENDER+RECEIVER+231031:1430+1'FTX+AAA+++{long_value}'UNZ+1+1'"
        result = tokenize(content)

        assert not result.has_fatal_errors()

        ftx = next(s for s in result.segments if s.tag == "FTX")
        assert ftx.get_element_value(4) == long_value

    def test_many_components(self):
        """Test element with many components."""
        content = "UNB+UNOC:3+SENDER+RECEIVER+231031:1430+1'TST+A:B:C:D:E:F:G:H:I:J'UNZ+1+1'"
        result = tokenize(content)

        assert not result.has_fatal_errors()

        tst = next(s for s in result.segments if s.tag == "TST")
        elem = tst.get_element(1)
        assert elem.is_composite
        assert len(elem.components) == 10

    def test_consecutive_separators(self):
        """Test handling of consecutive separators (empty elements/components)."""
        content = "UNB+UNOC:3+SENDER+RECEIVER+231031:1430+1'NAD+BY++:::+NAME'UNZ+1+1'"
        result = tokenize(content)

        assert not result.has_fatal_errors()

        nad = next(s for s in result.segments if s.tag == "NAD")
        # Element 2 should be empty
        assert nad.get_element_value(2) == ""
        # Element 3 has empty components
        elem3 = nad.get_element(3)
        assert elem3.is_composite
        assert all(c.value == "" for c in elem3.components)

    def test_trailing_segment_terminator(self):
        """Test document with trailing segment terminator."""
        content = "UNB+UNOC:3+SENDER+RECEIVER+231031:1430+1'UNZ+1+1'"
        result = tokenize(content)

        assert not result.has_fatal_errors()
        # Should not create empty segment from trailing terminator
        assert all(s.tag for s in result.segments)
