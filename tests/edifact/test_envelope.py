"""
Tests for EDIFACT Envelope Parser.

Tests cover:
- UNB/UNZ interchange parsing
- UNG/UNE functional group parsing (optional)
- UNH/UNT message envelope parsing
- Control reference validation
- Count validation
- Error recovery for missing trailers
- Real-world message structures
"""

from edi_schema.edifact.ast import (
    ParseResult,
)
from edi_schema.edifact.parser.envelope import (
    EdifactEnvelopeParser,
    EnvelopeParserState,
    parse_envelope,
)
from edi_schema.edifact.parser.tokenizer import tokenize

# =============================================================================
# Helpers
# =============================================================================


def parse_edifact(data: str) -> ParseResult:
    """Tokenize and parse an EDIFACT document."""
    tokenizer_result = tokenize(data)
    return parse_envelope(tokenizer_result)


# =============================================================================
# Basic Parsing Tests
# =============================================================================


class TestEnvelopeParserBasics:
    """Test basic envelope parser functionality."""

    def test_parser_creation(self):
        """Test parser can be created."""
        parser = EdifactEnvelopeParser()
        assert parser is not None

    def test_parse_convenience_function(self):
        """Test parse_envelope convenience function."""
        data = "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'UNZ+0+12345'"
        result = parse_edifact(data)
        assert result is not None
        assert isinstance(result, ParseResult)

    def test_state_initialization(self):
        """Test parser state defaults."""
        state = EnvelopeParserState()
        assert state.in_interchange is False
        assert state.in_group is False
        assert state.in_message is False
        assert state.interchange_reference == ""

    def test_empty_input(self):
        """Test handling of empty input."""
        result = parse_edifact("")
        assert result.has_fatal_errors()
        assert any(e.code == "ENV01" for e in result.errors)


# =============================================================================
# UNB/UNZ Interchange Tests
# =============================================================================


class TestInterchangeParsing:
    """Test UNB/UNZ interchange envelope parsing."""

    def test_minimal_interchange(self):
        """Test parsing minimal valid interchange."""
        data = "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'UNZ+0+12345'"
        result = parse_edifact(data)

        assert len(result.interchanges) == 1
        interchange = result.interchanges[0]
        assert interchange.syntax_identifier == "UNOA"
        assert interchange.syntax_version == "3"
        assert interchange.sender_id == "SENDER"
        assert interchange.recipient_id == "RECEIVER"
        assert interchange.date == "231031"
        assert interchange.time == "1430"
        assert interchange.control_reference == "12345"

    def test_interchange_with_qualifiers(self):
        """Test parsing interchange with sender/recipient qualifiers."""
        data = "UNB+UNOA:3+SENDER:14+RECEIVER:14+231031:1430+12345'UNZ+0+12345'"
        result = parse_edifact(data)

        interchange = result.interchanges[0]
        assert interchange.sender_id == "SENDER"
        assert interchange.sender_qualifier == "14"
        assert interchange.recipient_id == "RECEIVER"
        assert interchange.recipient_qualifier == "14"

    def test_interchange_all_fields(self):
        """Test parsing interchange with all optional fields."""
        data = (
            "UNB+UNOC:4+SENDER:14+RECEIVER:ZZ+20231031:1430+REF123++"
            "APPREF+A+1+AGREEMENT+1'"
            "UNZ+0+REF123'"
        )
        result = parse_edifact(data)

        interchange = result.interchanges[0]
        assert interchange.syntax_identifier == "UNOC"
        assert interchange.syntax_version == "4"
        assert interchange.control_reference == "REF123"
        assert interchange.application_reference == "APPREF"
        assert interchange.processing_priority == "A"
        assert interchange.ack_request == "1"
        assert interchange.agreement_id == "AGREEMENT"
        assert interchange.test_indicator == "1"

    def test_test_indicator(self):
        """Test test indicator detection."""
        # Test interchange (test indicator at element 11)
        # Elements: 1=S001, 2=S002, 3=S003, 4=S004, 5=control_ref, 6=S005, 7=app_ref, 8=priority, 9=ack, 10=agreement, 11=test
        data = "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345++++++1'UNZ+0+12345'"
        result = parse_edifact(data)
        assert result.interchanges[0].is_test() is True
        assert result.interchanges[0].is_production() is False

        # Production interchange (no test indicator)
        data = "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'UNZ+0+12345'"
        result = parse_edifact(data)
        assert result.interchanges[0].is_test() is False
        assert result.interchanges[0].is_production() is True

    def test_unz_count_validation(self):
        """Test UNZ count validation."""
        # Correct count (0 messages)
        data = "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'UNZ+0+12345'"
        result = parse_edifact(data)
        assert result.interchanges[0].count == 0

    def test_unz_count_mismatch(self):
        """Test UNZ count mismatch detection."""
        data = "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'UNZ+5+12345'"
        result = parse_edifact(data)
        assert any(e.code == "UNZ01" for e in result.errors)

    def test_unz_reference_mismatch(self):
        """Test UNZ control reference mismatch detection."""
        data = "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'UNZ+0+99999'"
        result = parse_edifact(data)
        assert any(e.code == "UNZ04" for e in result.errors)

    def test_missing_unz(self):
        """Test error recovery for missing UNZ."""
        data = "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'"
        result = parse_edifact(data)
        assert any(e.code == "ENV12" for e in result.errors)
        # Should still have parsed interchange
        assert len(result.interchanges) == 1

    def test_multiple_interchanges(self):
        """Test parsing multiple interchanges in one document."""
        data = (
            "UNB+UNOA:3+S1+R1+231031:1430+111'UNZ+0+111'"
            "UNB+UNOA:3+S2+R2+231031:1431+222'UNZ+0+222'"
        )
        result = parse_edifact(data)
        assert len(result.interchanges) == 2
        assert result.interchanges[0].control_reference == "111"
        assert result.interchanges[1].control_reference == "222"


# =============================================================================
# UNH/UNT Message Tests
# =============================================================================


class TestMessageParsing:
    """Test UNH/UNT message envelope parsing."""

    def test_single_message(self):
        """Test parsing single message without functional group."""
        data = (
            "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'"
            "UNH+1+INVOIC:D:23A:UN'"
            "BGM+380+INV001+9'"
            "UNT+3+1'"
            "UNZ+1+12345'"
        )
        result = parse_edifact(data)

        assert len(result.interchanges) == 1
        interchange = result.interchanges[0]
        assert len(interchange.messages) == 1
        assert len(interchange.groups) == 0

        message = interchange.messages[0]
        assert message.reference_number == "1"
        assert message.message_type == "INVOIC"
        assert message.version == "D"
        assert message.release == "23A"
        assert message.controlling_agency == "UN"

    def test_message_identifier(self):
        """Test message identifier property."""
        data = (
            "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'"
            "UNH+1+ORDERS:D:96A:UN:EAN008'"
            "UNT+2+1'"
            "UNZ+1+12345'"
        )
        result = parse_edifact(data)
        message = result.interchanges[0].messages[0]
        assert message.message_identifier == "ORDERS:D:96A:UN"
        assert message.association_code == "EAN008"

    def test_message_with_content(self):
        """Test message content segments are captured."""
        data = (
            "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'"
            "UNH+1+INVOIC:D:23A:UN'"
            "BGM+380+INV001+9'"
            "DTM+137:20231031:102'"
            "NAD+BY+BUYER::9'"
            "UNT+5+1'"
            "UNZ+1+12345'"
        )
        result = parse_edifact(data)
        message = result.interchanges[0].messages[0]

        # Content should have BGM, DTM, NAD (3 segments)
        assert len(message.content) == 3
        assert message.content[0].tag == "BGM"
        assert message.content[1].tag == "DTM"
        assert message.content[2].tag == "NAD"

    def test_unt_count_validation(self):
        """Test UNT segment count validation."""
        # UNH + BGM + UNT = 3 segments
        data = (
            "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'"
            "UNH+1+INVOIC:D:23A:UN'"
            "BGM+380+INV001+9'"
            "UNT+3+1'"  # Correct count
            "UNZ+1+12345'"
        )
        result = parse_edifact(data)
        message = result.interchanges[0].messages[0]
        assert message.segment_count == 3

    def test_unt_count_mismatch(self):
        """Test UNT segment count mismatch detection."""
        data = (
            "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'"
            "UNH+1+INVOIC:D:23A:UN'"
            "BGM+380+INV001+9'"
            "UNT+10+1'"  # Wrong count
            "UNZ+1+12345'"
        )
        result = parse_edifact(data)
        assert any(e.code == "UNT01" for e in result.all_errors())

    def test_unt_reference_mismatch(self):
        """Test UNT message reference mismatch detection."""
        data = (
            "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'"
            "UNH+1+INVOIC:D:23A:UN'"
            "UNT+2+999'"  # Wrong reference
            "UNZ+1+12345'"
        )
        result = parse_edifact(data)
        assert any(e.code == "UNT04" for e in result.all_errors())

    def test_missing_unt(self):
        """Test error recovery for missing UNT."""
        data = (
            "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'"
            "UNH+1+INVOIC:D:23A:UN'"
            "BGM+380+INV001+9'"
            "UNZ+1+12345'"  # Missing UNT
        )
        result = parse_edifact(data)
        assert any(e.code == "ENV30" for e in result.all_errors())
        # Message should still be parsed
        assert len(result.interchanges[0].messages) == 1

    def test_multiple_messages(self):
        """Test parsing multiple messages in interchange."""
        data = (
            "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'"
            "UNH+1+INVOIC:D:23A:UN'"
            "UNT+2+1'"
            "UNH+2+ORDERS:D:96A:UN'"
            "UNT+2+2'"
            "UNZ+2+12345'"
        )
        result = parse_edifact(data)
        interchange = result.interchanges[0]

        assert len(interchange.messages) == 2
        assert interchange.messages[0].message_type == "INVOIC"
        assert interchange.messages[0].reference_number == "1"
        assert interchange.messages[1].message_type == "ORDERS"
        assert interchange.messages[1].reference_number == "2"


# =============================================================================
# UNG/UNE Functional Group Tests
# =============================================================================


class TestFunctionalGroupParsing:
    """Test UNG/UNE functional group parsing (optional in EDIFACT)."""

    def test_single_functional_group(self):
        """Test parsing single functional group."""
        data = (
            "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'"
            "UNG+INVOIC+APP_SENDER+APP_RECEIVER+231031:1430+GRP001+UN+D:23A'"
            "UNH+1+INVOIC:D:23A:UN'"
            "UNT+2+1'"
            "UNE+1+GRP001'"
            "UNZ+1+12345'"
        )
        result = parse_edifact(data)
        interchange = result.interchanges[0]

        assert len(interchange.groups) == 1
        assert len(interchange.messages) == 0  # Messages are in group

        group = interchange.groups[0]
        assert group.message_type == "INVOIC"
        assert group.sender_id == "APP_SENDER"
        assert group.recipient_id == "APP_RECEIVER"
        assert group.reference_number == "GRP001"

        assert len(group.messages) == 1

    def test_functional_group_version(self):
        """Test functional group message version parsing."""
        data = (
            "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'"
            "UNG+ORDERS+S+R+231031:1430+G1+UN+D:96A'"
            "UNH+1+ORDERS:D:96A:UN'"
            "UNT+2+1'"
            "UNE+1+G1'"
            "UNZ+1+12345'"
        )
        result = parse_edifact(data)
        group = result.interchanges[0].groups[0]
        assert group.message_version == "D"
        assert group.message_release == "96A"

    def test_une_count_validation(self):
        """Test UNE message count validation."""
        data = (
            "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'"
            "UNG+INVOIC+S+R+231031:1430+G1+UN'"
            "UNH+1+INVOIC:D:23A:UN'"
            "UNT+2+1'"
            "UNE+1+G1'"  # Correct count
            "UNZ+1+12345'"
        )
        result = parse_edifact(data)
        group = result.interchanges[0].groups[0]
        assert group.message_count == 1

    def test_une_count_mismatch(self):
        """Test UNE message count mismatch detection."""
        data = (
            "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'"
            "UNG+INVOIC+S+R+231031:1430+G1+UN'"
            "UNH+1+INVOIC:D:23A:UN'"
            "UNT+2+1'"
            "UNE+5+G1'"  # Wrong count
            "UNZ+1+12345'"
        )
        result = parse_edifact(data)
        assert any(e.code == "UNE01" for e in result.all_errors())

    def test_une_reference_mismatch(self):
        """Test UNE group reference mismatch detection."""
        data = (
            "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'"
            "UNG+INVOIC+S+R+231031:1430+G1+UN'"
            "UNH+1+INVOIC:D:23A:UN'"
            "UNT+2+1'"
            "UNE+1+WRONG'"  # Wrong reference
            "UNZ+1+12345'"
        )
        result = parse_edifact(data)
        assert any(e.code == "UNE04" for e in result.all_errors())

    def test_missing_une(self):
        """Test error recovery for missing UNE."""
        data = (
            "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'"
            "UNG+INVOIC+S+R+231031:1430+G1+UN'"
            "UNH+1+INVOIC:D:23A:UN'"
            "UNT+2+1'"
            "UNZ+1+12345'"  # Missing UNE
        )
        result = parse_edifact(data)
        assert any(e.code == "ENV21" for e in result.all_errors())
        # Group should still be parsed
        assert len(result.interchanges[0].groups) == 1

    def test_multiple_groups(self):
        """Test parsing multiple functional groups."""
        data = (
            "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'"
            "UNG+INVOIC+S+R+231031:1430+G1+UN'"
            "UNH+1+INVOIC:D:23A:UN'"
            "UNT+2+1'"
            "UNE+1+G1'"
            "UNG+ORDERS+S+R+231031:1430+G2+UN'"
            "UNH+2+ORDERS:D:96A:UN'"
            "UNT+2+2'"
            "UNE+1+G2'"
            "UNZ+2+12345'"
        )
        result = parse_edifact(data)
        interchange = result.interchanges[0]

        assert len(interchange.groups) == 2
        assert interchange.groups[0].message_type == "INVOIC"
        assert interchange.groups[0].reference_number == "G1"
        assert interchange.groups[1].message_type == "ORDERS"
        assert interchange.groups[1].reference_number == "G2"

    def test_all_messages_through_groups(self):
        """Test all_messages() returns messages from groups."""
        data = (
            "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'"
            "UNG+INVOIC+S+R+231031:1430+G1+UN'"
            "UNH+1+INVOIC:D:23A:UN'"
            "UNT+2+1'"
            "UNH+2+INVOIC:D:23A:UN'"
            "UNT+2+2'"
            "UNE+2+G1'"
            "UNZ+1+12345'"
        )
        result = parse_edifact(data)
        interchange = result.interchanges[0]

        all_messages = interchange.all_messages()
        assert len(all_messages) == 2


# =============================================================================
# Error Recovery Tests
# =============================================================================


class TestErrorRecovery:
    """Test error recovery scenarios."""

    def test_unexpected_segment_at_interchange(self):
        """Test handling unexpected segment at interchange level."""
        data = (
            "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'"
            "BGM+OOPS'"  # Unexpected
            "UNH+1+INVOIC:D:23A:UN'"
            "UNT+2+1'"
            "UNZ+1+12345'"
        )
        result = parse_edifact(data)
        # Should have warning about unexpected BGM
        assert any("BGM" in str(e) for e in result.warnings)
        # Should still parse the message
        assert len(result.interchanges[0].messages) == 1

    def test_unexpected_segment_at_group(self):
        """Test handling unexpected segment at group level."""
        data = (
            "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'"
            "UNG+INVOIC+S+R+231031:1430+G1+UN'"
            "BGM+OOPS'"  # Unexpected
            "UNH+1+INVOIC:D:23A:UN'"
            "UNT+2+1'"
            "UNE+1+G1'"
            "UNZ+1+12345'"
        )
        result = parse_edifact(data)
        # Should have warning about unexpected BGM
        assert any("BGM" in str(e) for e in result.warnings)

    def test_recovery_missing_all_trailers(self):
        """Test recovery when all trailers are missing."""
        data = (
            "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'"
            "UNH+1+INVOIC:D:23A:UN'"
            "BGM+380+INV001'"
        )
        result = parse_edifact(data)
        # Should have errors for missing UNT and UNZ
        assert any(e.code == "ENV30" for e in result.errors)  # Missing UNT
        assert any(e.code == "ENV12" for e in result.errors)  # Missing UNZ
        # Should still have some parsed data
        assert len(result.interchanges) == 1

    def test_invalid_unz_count_non_numeric(self):
        """Test handling non-numeric UNZ count."""
        data = "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'UNZ+ABC+12345'"
        result = parse_edifact(data)
        assert any(e.code == "UNZ02" for e in result.errors)


# =============================================================================
# Real-World Message Tests
# =============================================================================


class TestRealWorldMessages:
    """Test parsing real-world EDIFACT message structures."""

    def test_invoic_message(self):
        """Test parsing INVOIC message structure."""
        # UNB: test indicator at position 11 (6 empty elements after control ref)
        data = (
            "UNA:+.? '"
            "UNB+UNOC:3+SELLER:ZZ+BUYER:ZZ+231031:1430+12345++++++1'"
            "UNH+1+INVOIC:D:23A:UN'"
            "BGM+380+INV001+9'"
            "DTM+137:20231031:102'"
            "NAD+SE+SELLER_ID::9++SELLER NAME'"
            "NAD+BY+BUYER_ID::9++BUYER NAME'"
            "LIN+1++PRODUCT1:EN'"
            "QTY+47:10:PCE'"
            "MOA+203:100.00:EUR'"
            "UNT+9+1'"  # UNH + 7 content segments + UNT = 9
            "UNZ+1+12345'"
        )
        result = parse_edifact(data)

        assert len(result.interchanges) == 1
        interchange = result.interchanges[0]
        assert interchange.is_test() is True
        assert len(interchange.messages) == 1

        message = interchange.messages[0]
        assert message.message_type == "INVOIC"
        assert len(message.content) == 7  # BGM through MOA

    def test_orders_message(self):
        """Test parsing ORDERS message structure."""
        data = (
            "UNA:+.? '"
            "UNB+UNOA:3+BUYER+SELLER+231031:0900+ORDER001'"
            "UNH+1+ORDERS:D:96A:UN'"
            "BGM+220+PO12345+9'"
            "DTM+137:20231031:102'"
            "NAD+BY+BUYER123::9'"
            "NAD+SU+SELLER456::9'"
            "LIN+1++ITEM001:SA'"
            "QTY+21:100:PCE'"
            "PRI+AAA:10.50'"
            "LIN+2++ITEM002:SA'"
            "QTY+21:50:PCE'"
            "PRI+AAA:20.00'"
            "UNT+12+1'"  # UNH + 10 content segments + UNT = 12
            "UNZ+1+ORDER001'"
        )
        result = parse_edifact(data)

        assert result.is_valid() or len(result.errors) == 0
        message = result.interchanges[0].messages[0]
        assert message.message_type == "ORDERS"
        assert len(message.content) == 10

    def test_desadv_with_functional_group(self):
        """Test DESADV with functional group wrapper."""
        data = (
            "UNA:+.? '"
            "UNB+UNOA:3+SUPPLIER+CUSTOMER+231101:0800+REF001'"
            "UNG+DESADV+LOGISTICS+WAREHOUSE+231101:0800+GRP01+UN+D:23A'"
            "UNH+1+DESADV:D:23A:UN'"
            "BGM+351+SHIP001+9'"
            "DTM+137:20231101:102'"
            "NAD+CZ+CONSIGNEE::9'"
            "CPS+1'"
            "PAC+10+1+CT'"
            "UNT+7+1'"
            "UNE+1+GRP01'"
            "UNZ+1+REF001'"
        )
        result = parse_edifact(data)

        interchange = result.interchanges[0]
        assert len(interchange.groups) == 1

        group = interchange.groups[0]
        assert group.message_type == "DESADV"
        assert len(group.messages) == 1

        message = group.messages[0]
        assert message.message_type == "DESADV"

    def test_multiple_messages_same_type(self):
        """Test multiple messages of same type in interchange."""
        data = (
            "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'"
            "UNH+001+INVOIC:D:23A:UN'"
            "BGM+380+INV001'"
            "UNT+3+001'"
            "UNH+002+INVOIC:D:23A:UN'"
            "BGM+380+INV002'"
            "UNT+3+002'"
            "UNH+003+INVOIC:D:23A:UN'"
            "BGM+380+INV003'"
            "UNT+3+003'"
            "UNZ+3+12345'"
        )
        result = parse_edifact(data)

        interchange = result.interchanges[0]
        assert len(interchange.messages) == 3
        for i, msg in enumerate(interchange.messages, 1):
            assert msg.reference_number == f"00{i}"


# =============================================================================
# UNA Handling Tests
# =============================================================================


class TestUnaHandling:
    """Test UNA segment handling in envelope parsing."""

    def test_standard_una(self):
        """Test parsing with standard UNA."""
        data = "UNA:+.? 'UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'UNZ+0+12345'"
        result = parse_edifact(data)
        assert result.statistics.una_present is True

    def test_custom_delimiters(self):
        """Test parsing with custom delimiters via UNA."""
        # Use | as element separator, ~ as segment terminator
        data = "UNA;|,? ~UNB|UNOA;3|SENDER|RECEIVER|231031;1430|12345~UNZ|0|12345~"
        result = parse_edifact(data)
        assert len(result.interchanges) == 1
        assert result.interchanges[0].sender_id == "SENDER"

    def test_no_una(self):
        """Test parsing without UNA (default delimiters)."""
        data = "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'UNZ+0+12345'"
        result = parse_edifact(data)
        assert result.statistics.una_present is False
        assert len(result.interchanges) == 1


# =============================================================================
# Validation Helper Tests
# =============================================================================


class TestValidationHelpers:
    """Test validation and error collection helpers."""

    def test_is_valid_empty_interchange(self):
        """Test is_valid for interchange with no messages."""
        data = "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'UNZ+0+12345'"
        result = parse_edifact(data)
        # Empty but valid
        assert result.interchanges[0].is_valid()

    def test_all_errors_collection(self):
        """Test all_errors collects from all levels."""
        data = (
            "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'"
            "UNH+1+INVOIC:D:23A:UN'"
            "UNT+99+1'"  # Wrong count
            "UNZ+5+12345'"  # Wrong count
        )
        result = parse_edifact(data)
        all_errs = result.all_errors()
        # Should have errors from UNT and UNZ
        assert len(all_errs) >= 2

    def test_all_messages_from_result(self):
        """Test all_messages on ParseResult."""
        data = (
            "UNB+UNOA:3+S1+R1+231031:1430+111'"
            "UNH+1+INVOIC:D:23A:UN'"
            "UNT+2+1'"
            "UNZ+1+111'"
            "UNB+UNOA:3+S2+R2+231031:1431+222'"
            "UNH+2+ORDERS:D:96A:UN'"
            "UNT+2+2'"
            "UNZ+1+222'"
        )
        result = parse_edifact(data)
        all_msgs = result.all_messages()
        assert len(all_msgs) == 2


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_long_control_reference(self):
        """Test long control reference handling."""
        ref = "A" * 35  # EDIFACT allows up to 35 chars
        data = f"UNB+UNOA:3+SENDER+RECEIVER+231031:1430+{ref}'UNZ+0+{ref}'"
        result = parse_edifact(data)
        assert result.interchanges[0].control_reference == ref

    def test_empty_elements_in_unb(self):
        """Test UNB with empty optional elements."""
        data = "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345++++++++'UNZ+0+12345'"
        result = parse_edifact(data)
        assert len(result.interchanges) == 1

    def test_special_characters_in_values(self):
        """Test special characters escaped in values."""
        # Using release character ? to escape
        data = "UNA:+.? '" "UNB+UNOA:3+SEND?+ER+RECEIVER+231031:1430+12345'" "UNZ+0+12345'"
        result = parse_edifact(data)
        # The +ER should be part of sender_id due to escape
        assert result.interchanges[0].sender_id == "SEND+ER"

    def test_syntax_version_4_date(self):
        """Test syntax version 4 with CCYYMMDD date format."""
        data = "UNB+UNOC:4+SENDER+RECEIVER+20231031:1430+12345'UNZ+0+12345'"
        result = parse_edifact(data)
        interchange = result.interchanges[0]
        assert interchange.syntax_version == "4"
        assert interchange.date == "20231031"

    def test_missing_unh_s009_components(self):
        """Test error when S009 missing required components."""
        data = (
            "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'"
            "UNH+1+INVOIC'"  # Missing version, release, agency
            "UNT+2+1'"
            "UNZ+1+12345'"
        )
        result = parse_edifact(data)
        # Should have errors for missing S009 components
        errors = result.all_errors()
        assert any(e.code in ("UNH03", "UNH04") for e in errors)
