"""
Tests for X12 envelope segment parsing.
"""

from edi_schema.x12.ast import ErrorSeverity
from edi_schema.x12.envelope.gs import (
    GE_SEGMENT,
    GS_SEGMENT,
    SE_SEGMENT,
    ST_SEGMENT,
    parse_ge_segment,
    parse_gs_segment,
    parse_se_segment,
    parse_st_segment,
)
from edi_schema.x12.envelope.isa import (
    ISA_ELEMENT_POSITIONS,
    ISA_SEGMENT,
    parse_iea_segment,
    parse_isa_segment,
)


class TestISASegmentDef:
    """Tests for ISA segment definition."""

    def test_segment_id(self):
        assert ISA_SEGMENT.id == "ISA"

    def test_element_count(self):
        assert ISA_SEGMENT.element_count == 16

    def test_fixed_length(self):
        assert ISA_SEGMENT.fixed_length == 106

    def test_element_positions(self):
        # ISA01 should be at position 4-5 (after "ISA*")
        pos = ISA_SEGMENT.get_element_position(1)
        assert pos is not None
        assert pos.start == 4
        assert pos.length == 2
        assert pos.name == "Authorization Information Qualifier"

    def test_element_positions_count(self):
        # Should have 17 entries (ISA + 16 elements)
        assert len(ISA_ELEMENT_POSITIONS) == 17


class TestParseISA:
    """Tests for ISA segment parsing."""

    def test_parse_valid_isa(self):
        # Standard ISA segment (exactly 106 chars)
        isa = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*P*:~"
        )
        assert len(isa) == 106

        parsed, errors = parse_isa_segment(isa)

        assert parsed is not None
        assert parsed.auth_qualifier == "00"
        assert parsed.security_qualifier == "00"
        assert parsed.sender_qualifier == "ZZ"
        assert parsed.sender_id == "SENDER         "
        assert parsed.receiver_qualifier == "ZZ"
        assert parsed.receiver_id == "RECEIVER       "
        assert parsed.date == "210101"
        assert parsed.time == "1200"
        assert parsed.version == "00501"
        assert parsed.control_number == "000000001"
        assert parsed.ack_requested == "0"
        assert parsed.usage_indicator == "P"
        assert parsed.component_separator == ":"

        # Check delimiters
        assert parsed.delimiters.element == "*"
        assert parsed.delimiters.segment == "~"
        assert parsed.delimiters.component == ":"

    def test_parse_isa_extracts_delimiters(self):
        # ISA with pipe delimiter
        isa = (
            "ISA|00|          |00|          |ZZ|SENDER         |ZZ|RECEIVER       "
            "|210101|1200|^|00501|000000001|0|P|>~"
        )
        parsed, errors = parse_isa_segment(isa)

        assert parsed is not None
        assert parsed.delimiters.element == "|"
        assert parsed.delimiters.component == ">"

    def test_parse_isa_missing_content(self):
        # ISA that's too short
        isa = "ISA*00"
        parsed, errors = parse_isa_segment(isa)

        # Should still try to parse with errors
        assert len(errors) > 0
        assert any(e.severity == ErrorSeverity.ERROR for e in errors)

    def test_parse_isa_not_starting_with_isa(self):
        # Document not starting with ISA
        content = "GS*PO*SENDER*RECEIVER"
        parsed, errors = parse_isa_segment(content)

        assert parsed is None
        assert len(errors) > 0
        assert any(e.severity == ErrorSeverity.FATAL for e in errors)

    def test_parse_isa_invalid_usage_indicator(self):
        # ISA with invalid usage indicator
        isa = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*210101*1200*^*00501*000000001*0*X*:~"  # X is invalid
        )
        parsed, errors = parse_isa_segment(isa)

        assert parsed is not None
        # Should have warning/error about invalid usage indicator
        assert any("Usage Indicator" in e.message for e in errors)


class TestParseIEA:
    """Tests for IEA segment parsing."""

    def test_parse_valid_iea(self):
        elements = ["1", "000000001"]
        parsed, errors = parse_iea_segment(
            elements,
            expected_control="000000001",
            expected_count=1,
        )

        assert parsed.group_count == 1
        assert parsed.control_number == "000000001"
        assert len(errors) == 0

    def test_parse_iea_count_mismatch(self):
        elements = ["2", "000000001"]
        parsed, errors = parse_iea_segment(
            elements,
            expected_control="000000001",
            expected_count=1,  # Actual is 2
        )

        assert parsed.group_count == 2
        assert any("mismatch" in e.message.lower() for e in errors)

    def test_parse_iea_control_mismatch(self):
        elements = ["1", "000000002"]
        parsed, errors = parse_iea_segment(
            elements,
            expected_control="000000001",  # Doesn't match
            expected_count=1,
        )

        assert any("mismatch" in e.message.lower() for e in errors)

    def test_parse_iea_invalid_count(self):
        elements = ["ABC", "000000001"]  # Non-numeric count
        parsed, errors = parse_iea_segment(
            elements,
            expected_control="000000001",
            expected_count=1,
        )

        assert any("Invalid" in e.message for e in errors)


class TestGSSegment:
    """Tests for GS segment."""

    def test_segment_def(self):
        assert GS_SEGMENT.id == "GS"
        assert GS_SEGMENT.element_count == 8

    def test_parse_valid_gs(self):
        elements = ["PO", "SENDER", "RECEIVER", "20210101", "1200", "1", "X", "005010"]
        parsed, errors = parse_gs_segment(elements)

        assert parsed.functional_id == "PO"
        assert parsed.sender_id == "SENDER"
        assert parsed.receiver_id == "RECEIVER"
        assert parsed.date == "20210101"
        assert parsed.time == "1200"
        assert parsed.control_number == "1"
        assert parsed.responsible_agency == "X"
        assert parsed.version == "005010"
        assert len([e for e in errors if e.severity != ErrorSeverity.WARNING]) == 0

    def test_parse_gs_missing_elements(self):
        elements = ["PO", "SENDER"]  # Missing most elements
        parsed, errors = parse_gs_segment(elements)

        # Should have errors for missing required elements
        assert len(errors) > 0

    def test_parse_gs_unknown_functional_id(self):
        elements = ["XX", "SENDER", "RECEIVER", "20210101", "1200", "1", "X", "005010"]
        parsed, errors = parse_gs_segment(elements)

        assert any("Unknown Functional Identifier" in e.message for e in errors)


class TestGESegment:
    """Tests for GE segment."""

    def test_segment_def(self):
        assert GE_SEGMENT.id == "GE"
        assert GE_SEGMENT.element_count == 2

    def test_parse_valid_ge(self):
        elements = ["3", "1"]
        parsed, errors = parse_ge_segment(
            elements,
            expected_control="1",
            expected_count=3,
        )

        assert parsed.transaction_count == 3
        assert parsed.control_number == "1"
        assert len(errors) == 0

    def test_parse_ge_count_mismatch(self):
        elements = ["5", "1"]
        parsed, errors = parse_ge_segment(
            elements,
            expected_control="1",
            expected_count=3,  # GE says 5
        )

        assert any("mismatch" in e.message.lower() for e in errors)


class TestSTSegment:
    """Tests for ST segment."""

    def test_segment_def(self):
        assert ST_SEGMENT.id == "ST"
        assert ST_SEGMENT.element_count == 3

    def test_parse_valid_st(self):
        elements = ["850", "0001"]
        parsed, errors = parse_st_segment(elements)

        assert parsed.transaction_id == "850"
        assert parsed.control_number == "0001"
        assert parsed.implementation_reference is None
        assert len([e for e in errors if e.severity != ErrorSeverity.WARNING]) == 0

    def test_parse_st_with_implementation_ref(self):
        elements = ["837", "0001", "005010X222A1"]
        parsed, errors = parse_st_segment(elements)

        assert parsed.transaction_id == "837"
        assert parsed.implementation_reference == "005010X222A1"

    def test_parse_st_missing_id(self):
        elements = []
        parsed, errors = parse_st_segment(elements)

        assert any("Missing" in e.message for e in errors)


class TestSESegment:
    """Tests for SE segment."""

    def test_segment_def(self):
        assert SE_SEGMENT.id == "SE"
        assert SE_SEGMENT.element_count == 2

    def test_parse_valid_se(self):
        elements = ["15", "0001"]
        parsed, errors = parse_se_segment(
            elements,
            expected_control="0001",
            expected_count=15,
        )

        assert parsed.segment_count == 15
        assert parsed.control_number == "0001"
        assert len(errors) == 0

    def test_parse_se_count_mismatch(self):
        elements = ["20", "0001"]
        parsed, errors = parse_se_segment(
            elements,
            expected_control="0001",
            expected_count=15,  # SE says 20
        )

        assert any("mismatch" in e.message.lower() for e in errors)

    def test_parse_se_control_mismatch(self):
        elements = ["15", "0002"]
        parsed, errors = parse_se_segment(
            elements,
            expected_control="0001",  # SE says 0002
            expected_count=15,
        )

        assert any("mismatch" in e.message.lower() for e in errors)
