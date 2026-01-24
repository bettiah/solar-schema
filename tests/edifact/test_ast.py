"""
Tests for EDIFACT AST node types.
"""

import pytest

from edi_schema.edifact.ast import (
    Delimiters,
    ErrorCategory,
    ErrorSeverity,
    FunctionalGroupInstance,
    InterchangeInstance,
    MessageInstance,
    ParsedComponent,
    ParsedElement,
    ParsedSegment,
    ParseError,
    ParseResult,
    ParseStatistics,
    RawComponent,
    RawElement,
    RawSegment,
    RecoveryPoint,
    SegmentGroupInstance,
    SourcePosition,
)


class TestSourcePosition:
    """Tests for SourcePosition."""

    def test_creation(self):
        pos = SourcePosition(offset=100, line=5, column=10, length=15)
        assert pos.offset == 100
        assert pos.line == 5
        assert pos.column == 10
        assert pos.length == 15

    def test_defaults(self):
        pos = SourcePosition(offset=0, line=1, column=1)
        assert pos.length == 0

    def test_str(self):
        pos = SourcePosition(offset=0, line=1, column=5)
        assert str(pos) == "line 1, col 5"

    def test_to_dict(self):
        pos = SourcePosition(offset=100, line=5, column=10, length=15)
        d = pos.to_dict()
        assert d["offset"] == 100
        assert d["line"] == 5
        assert d["column"] == 10
        assert d["length"] == 15

    def test_frozen(self):
        pos = SourcePosition(offset=0, line=1, column=1)
        with pytest.raises(AttributeError):
            pos.line = 2  # type: ignore


class TestErrorEnums:
    """Tests for error-related enums."""

    def test_error_severity_values(self):
        assert ErrorSeverity.FATAL.value == "fatal"
        assert ErrorSeverity.ERROR.value == "error"
        assert ErrorSeverity.WARNING.value == "warning"

    def test_error_category_values(self):
        assert ErrorCategory.STRUCTURAL.value == "structural"
        assert ErrorCategory.ENVELOPE.value == "envelope"
        assert ErrorCategory.SCHEMA.value == "schema"
        assert ErrorCategory.ELEMENT.value == "element"
        assert ErrorCategory.CODE.value == "code"
        assert ErrorCategory.SEMANTIC.value == "semantic"

    def test_recovery_point_values(self):
        assert RecoveryPoint.SEGMENT_BOUNDARY.value == "segment"
        assert RecoveryPoint.MESSAGE_START.value == "unh"
        assert RecoveryPoint.MESSAGE_END.value == "unt"
        assert RecoveryPoint.INTERCHANGE_END.value == "unz"


class TestParseError:
    """Tests for ParseError."""

    def test_creation(self):
        error = ParseError(
            code="E001",
            message="Test error",
            category=ErrorCategory.STRUCTURAL,
            severity=ErrorSeverity.ERROR,
        )
        assert error.code == "E001"
        assert error.message == "Test error"
        assert error.category == ErrorCategory.STRUCTURAL
        assert error.severity == ErrorSeverity.ERROR

    def test_default_severity(self):
        error = ParseError(
            code="E001",
            message="Test error",
            category=ErrorCategory.STRUCTURAL,
        )
        assert error.severity == ErrorSeverity.ERROR

    def test_str_simple(self):
        error = ParseError(
            code="E001",
            message="Test error",
            category=ErrorCategory.STRUCTURAL,
        )
        assert str(error) == "[E001] Test error"

    def test_str_with_position(self):
        pos = SourcePosition(offset=0, line=5, column=10)
        error = ParseError(
            code="E001",
            message="Test error",
            category=ErrorCategory.STRUCTURAL,
            position=pos,
            segment_tag="NAD",
        )
        assert "NAD" in str(error)
        assert "line 5" in str(error)

    def test_to_dict(self):
        error = ParseError(
            code="E001",
            message="Test error",
            category=ErrorCategory.ELEMENT,
            severity=ErrorSeverity.WARNING,
            segment_tag="NAD",
            element_position=2,
            component_position=3,
            group_number=1,
        )
        d = error.to_dict()
        assert d["code"] == "E001"
        assert d["category"] == "element"
        assert d["severity"] == "warning"
        assert d["segment_tag"] == "NAD"
        assert d["element_position"] == 2
        assert d["component_position"] == 3
        assert d["group_number"] == 1


class TestDelimiters:
    """Tests for EDIFACT Delimiters."""

    def test_defaults(self):
        delim = Delimiters()
        assert delim.component == ":"
        assert delim.element == "+"
        assert delim.decimal == "."
        assert delim.release == "?"
        assert delim.segment == "'"

    def test_custom(self):
        delim = Delimiters(
            component="#",
            element="|",
            decimal=",",
            release="!",
            segment="~",
        )
        assert delim.component == "#"
        assert delim.element == "|"
        assert delim.decimal == ","
        assert delim.release == "!"
        assert delim.segment == "~"

    def test_str(self):
        delim = Delimiters()
        s = str(delim)
        assert "component=" in s
        assert "element=" in s
        assert "decimal=" in s
        assert "release=" in s
        assert "segment=" in s

    def test_from_una_valid(self):
        # UNA:+.? '
        una = "UNA:+.? '"
        delim = Delimiters.from_una(una)
        assert delim.component == ":"
        assert delim.element == "+"
        assert delim.decimal == "."
        assert delim.release == "?"
        assert delim.segment == "'"

    def test_from_una_custom(self):
        # Custom delimiters
        una = "UNA#|,!~*"
        delim = Delimiters.from_una(una)
        assert delim.component == "#"
        assert delim.element == "|"
        assert delim.decimal == ","
        assert delim.release == "!"
        assert delim.segment == "*"

    def test_from_una_invalid_too_short(self):
        with pytest.raises(ValueError):
            Delimiters.from_una("UNA:+.")

    def test_from_una_invalid_prefix(self):
        with pytest.raises(ValueError):
            Delimiters.from_una("XXX:+.? '")

    def test_to_una(self):
        delim = Delimiters()
        una = delim.to_una()
        assert una == "UNA:+.? '"

    def test_to_una_roundtrip(self):
        original = Delimiters.from_una("UNA:+.? '")
        una = original.to_una()
        recovered = Delimiters.from_una(una)
        assert original.component == recovered.component
        assert original.element == recovered.element
        assert original.decimal == recovered.decimal
        assert original.release == recovered.release
        assert original.segment == recovered.segment


class TestRawComponent:
    """Tests for RawComponent."""

    def test_creation(self):
        pos = SourcePosition(0, 1, 1)
        comp = RawComponent(value="TEST", position=pos, component_index=1)
        assert comp.value == "TEST"
        assert comp.component_index == 1

    def test_is_empty(self):
        pos = SourcePosition(0, 1, 1)
        empty = RawComponent(value="", position=pos, component_index=1)
        not_empty = RawComponent(value="X", position=pos, component_index=1)
        assert empty.is_empty()
        assert not not_empty.is_empty()

    def test_str(self):
        pos = SourcePosition(0, 1, 1)
        comp = RawComponent(value="HELLO", position=pos, component_index=1)
        assert str(comp) == "HELLO"


class TestRawElement:
    """Tests for RawElement."""

    def test_simple_element(self):
        pos = SourcePosition(0, 1, 1)
        elem = RawElement(value="TEST", position=pos, element_index=1)
        assert elem.value == "TEST"
        assert elem.element_index == 1
        assert not elem.is_composite
        assert elem.components is None

    def test_composite_element(self):
        pos = SourcePosition(0, 1, 1)
        comp1 = RawComponent(value="A", position=pos, component_index=1)
        comp2 = RawComponent(value="B", position=pos, component_index=2)
        elem = RawElement(value=None, position=pos, element_index=1, components=[comp1, comp2])
        assert elem.is_composite
        assert len(elem.components) == 2

    def test_is_empty_simple(self):
        pos = SourcePosition(0, 1, 1)
        empty = RawElement(value="", position=pos, element_index=1)
        not_empty = RawElement(value="X", position=pos, element_index=1)
        assert empty.is_empty()
        assert not not_empty.is_empty()

    def test_is_empty_composite(self):
        pos = SourcePosition(0, 1, 1)
        empty_comp = RawComponent(value="", position=pos, component_index=1)
        full_comp = RawComponent(value="X", position=pos, component_index=1)

        empty = RawElement(value=None, position=pos, element_index=1, components=[empty_comp])
        not_empty = RawElement(value=None, position=pos, element_index=1, components=[full_comp])

        assert empty.is_empty()
        assert not not_empty.is_empty()

    def test_get_component_composite(self):
        pos = SourcePosition(0, 1, 1)
        comp1 = RawComponent(value="A", position=pos, component_index=1)
        comp2 = RawComponent(value="B", position=pos, component_index=2)
        elem = RawElement(value=None, position=pos, element_index=1, components=[comp1, comp2])

        assert elem.get_component(1) == "A"
        assert elem.get_component(2) == "B"
        assert elem.get_component(0) is None
        assert elem.get_component(3) is None

    def test_get_component_simple(self):
        pos = SourcePosition(0, 1, 1)
        elem = RawElement(value="VALUE", position=pos, element_index=1)
        assert elem.get_component(1) == "VALUE"
        assert elem.get_component(2) is None

    def test_get_simple_value_simple(self):
        pos = SourcePosition(0, 1, 1)
        elem = RawElement(value="VALUE", position=pos, element_index=1)
        assert elem.get_simple_value() == "VALUE"

    def test_get_simple_value_composite(self):
        pos = SourcePosition(0, 1, 1)
        comp1 = RawComponent(value="FIRST", position=pos, component_index=1)
        comp2 = RawComponent(value="SECOND", position=pos, component_index=2)
        elem = RawElement(value=None, position=pos, element_index=1, components=[comp1, comp2])
        assert elem.get_simple_value() == "FIRST"

    def test_str_simple(self):
        pos = SourcePosition(0, 1, 1)
        elem = RawElement(value="HELLO", position=pos, element_index=1)
        assert str(elem) == "HELLO"

    def test_str_composite(self):
        pos = SourcePosition(0, 1, 1)
        comp1 = RawComponent(value="A", position=pos, component_index=1)
        comp2 = RawComponent(value="B", position=pos, component_index=2)
        elem = RawElement(value=None, position=pos, element_index=1, components=[comp1, comp2])
        assert str(elem) == "A:B"


class TestRawSegment:
    """Tests for RawSegment."""

    def test_creation(self):
        pos = SourcePosition(0, 1, 1)
        elem1 = RawElement(value="00", position=pos, element_index=1)
        elem2 = RawElement(value="SA", position=pos, element_index=2)
        seg = RawSegment(
            tag="BGM",
            elements=[elem1, elem2],
            position=pos,
            raw_text="BGM+00+SA",
        )
        assert seg.tag == "BGM"
        assert len(seg.elements) == 2

    def test_get_element(self):
        pos = SourcePosition(0, 1, 1)
        elem1 = RawElement(value="A", position=pos, element_index=1)
        elem2 = RawElement(value="B", position=pos, element_index=2)
        seg = RawSegment(tag="TST", elements=[elem1, elem2], position=pos, raw_text="TST+A+B")

        assert seg.get_element(1) == elem1
        assert seg.get_element(2) == elem2
        assert seg.get_element(0) is None
        assert seg.get_element(3) is None

    def test_get_element_value(self):
        pos = SourcePosition(0, 1, 1)
        elem = RawElement(value="VALUE", position=pos, element_index=1)
        seg = RawSegment(tag="TST", elements=[elem], position=pos, raw_text="")
        assert seg.get_element_value(1) == "VALUE"
        assert seg.get_element_value(2) is None

    def test_get_component_value(self):
        pos = SourcePosition(0, 1, 1)
        comp1 = RawComponent(value="FIRST", position=pos, component_index=1)
        comp2 = RawComponent(value="SECOND", position=pos, component_index=2)
        elem = RawElement(value=None, position=pos, element_index=1, components=[comp1, comp2])
        seg = RawSegment(tag="TST", elements=[elem], position=pos, raw_text="")

        assert seg.get_component_value(1, 1) == "FIRST"
        assert seg.get_component_value(1, 2) == "SECOND"
        assert seg.get_component_value(1, 3) is None
        assert seg.get_component_value(2, 1) is None

    def test_str(self):
        pos = SourcePosition(0, 1, 1)
        elem = RawElement(value="X", position=pos, element_index=1)
        seg = RawSegment(tag="NAD", elements=[elem], position=pos, raw_text="NAD+X")
        assert "NAD" in str(seg)
        assert "1 elements" in str(seg)


class TestParsedNodes:
    """Tests for parsed (schema-aware) nodes."""

    def test_parsed_component(self):
        pos = SourcePosition(0, 1, 1)
        raw = RawComponent(value="TEST", position=pos, component_index=1)
        parsed = ParsedComponent(value="TEST", raw=raw)
        assert parsed.value == "TEST"
        assert parsed.is_valid()

    def test_parsed_component_with_error(self):
        pos = SourcePosition(0, 1, 1)
        raw = RawComponent(value="TEST", position=pos, component_index=1)
        error = ParseError(code="E", message="Error", category=ErrorCategory.ELEMENT)
        parsed = ParsedComponent(value="TEST", raw=raw, errors=[error])
        assert not parsed.is_valid()

    def test_parsed_element(self):
        pos = SourcePosition(0, 1, 1)
        raw = RawElement(value="TEST", position=pos, element_index=1)
        parsed = ParsedElement(raw=raw)
        assert parsed.value == "TEST"
        assert not parsed.is_composite
        assert parsed.is_valid()

    def test_parsed_segment(self):
        pos = SourcePosition(0, 1, 1)
        raw_elem = RawElement(value="X", position=pos, element_index=1)
        raw_seg = RawSegment(tag="NAD", elements=[raw_elem], position=pos, raw_text="NAD+X")
        parsed_elem = ParsedElement(raw=raw_elem)
        parsed_seg = ParsedSegment(tag="NAD", elements=[parsed_elem], raw=raw_seg)

        assert parsed_seg.tag == "NAD"
        assert len(parsed_seg.elements) == 1
        assert parsed_seg.is_valid()
        assert parsed_seg.get_element(1) == parsed_elem
        assert parsed_seg.get_element_value(1) == "X"


class TestSegmentGroupInstance:
    """Tests for SegmentGroupInstance."""

    def test_creation(self):
        group = SegmentGroupInstance(group_number=1, iteration=1)
        assert group.group_number == 1
        assert group.iteration == 1
        assert group.segments == []
        assert group.children == []

    def test_is_valid_empty(self):
        group = SegmentGroupInstance(group_number=1)
        assert group.is_valid()

    def test_is_valid_with_errors(self):
        group = SegmentGroupInstance(
            group_number=1,
            errors=[ParseError(code="E001", message="Test", category=ErrorCategory.SCHEMA)],
        )
        assert not group.is_valid()

    def test_all_segments(self):
        pos = SourcePosition(0, 1, 1)
        raw1 = RawSegment(tag="NAD", elements=[], position=pos, raw_text="NAD")
        raw2 = RawSegment(tag="RFF", elements=[], position=pos, raw_text="RFF")
        seg1 = ParsedSegment(tag="NAD", elements=[], raw=raw1)
        seg2 = ParsedSegment(tag="RFF", elements=[], raw=raw2)

        child = SegmentGroupInstance(group_number=2, segments=[seg2])
        parent = SegmentGroupInstance(group_number=1, segments=[seg1], children=[child])

        all_segs = parent.all_segments()
        assert len(all_segs) == 2
        assert all_segs[0].tag == "NAD"
        assert all_segs[1].tag == "RFF"

    def test_str(self):
        group = SegmentGroupInstance(group_number=1, iteration=2)
        s = str(group)
        assert "SG1" in s
        assert "[2]" in s


class TestMessageInstance:
    """Tests for MessageInstance."""

    def test_creation(self):
        msg = MessageInstance(
            reference_number="1",
            message_type="INVOIC",
            version="D",
            release="23A",
            controlling_agency="UN",
        )
        assert msg.reference_number == "1"
        assert msg.message_type == "INVOIC"
        assert msg.version == "D"
        assert msg.release == "23A"

    def test_message_identifier(self):
        msg = MessageInstance(
            reference_number="1",
            message_type="INVOIC",
            version="D",
            release="23A",
        )
        assert msg.message_identifier == "INVOIC:D:23A:UN"

    def test_is_valid_empty(self):
        msg = MessageInstance(
            reference_number="1",
            message_type="INVOIC",
            version="D",
            release="23A",
        )
        assert msg.is_valid()

    def test_is_valid_with_errors(self):
        msg = MessageInstance(
            reference_number="1",
            message_type="INVOIC",
            version="D",
            release="23A",
            errors=[ParseError(code="E", message="Test", category=ErrorCategory.SCHEMA)],
        )
        assert not msg.is_valid()

    def test_str(self):
        msg = MessageInstance(
            reference_number="123",
            message_type="INVOIC",
            version="D",
            release="23A",
        )
        s = str(msg)
        assert "INVOIC" in s
        assert "123" in s


class TestFunctionalGroupInstance:
    """Tests for FunctionalGroupInstance (optional in EDIFACT)."""

    def test_creation(self):
        group = FunctionalGroupInstance(
            message_type="INVOIC",
            sender_id="SENDER",
            recipient_id="RECEIVER",
            reference_number="1",
        )
        assert group.message_type == "INVOIC"
        assert group.reference_number == "1"

    def test_is_valid(self):
        group = FunctionalGroupInstance(
            message_type="INVOIC",
            sender_id="S",
            recipient_id="R",
            reference_number="1",
        )
        assert group.is_valid()

    def test_str(self):
        group = FunctionalGroupInstance(
            message_type="INVOIC",
            sender_id="S",
            recipient_id="R",
            reference_number="123",
        )
        s = str(group)
        assert "INVOIC" in s
        assert "123" in s


class TestInterchangeInstance:
    """Tests for InterchangeInstance."""

    def test_creation(self):
        interchange = InterchangeInstance(
            syntax_identifier="UNOC",
            syntax_version="3",
            sender_id="SENDER",
            recipient_id="RECEIVER",
            date="231031",
            time="1430",
            control_reference="12345",
        )
        assert interchange.syntax_identifier == "UNOC"
        assert interchange.syntax_version == "3"
        assert interchange.control_reference == "12345"

    def test_is_test(self):
        test_interchange = InterchangeInstance(
            syntax_identifier="UNOC",
            syntax_version="3",
            sender_id="S",
            recipient_id="R",
            control_reference="1",
            test_indicator="1",
        )
        assert test_interchange.is_test()
        assert not test_interchange.is_production()

    def test_is_production(self):
        prod_interchange = InterchangeInstance(
            syntax_identifier="UNOC",
            syntax_version="3",
            sender_id="S",
            recipient_id="R",
            control_reference="1",
            test_indicator=None,
        )
        assert prod_interchange.is_production()
        assert not prod_interchange.is_test()

    def test_all_messages_from_groups(self):
        msg = MessageInstance(
            reference_number="1",
            message_type="INVOIC",
            version="D",
            release="23A",
        )
        group = FunctionalGroupInstance(
            message_type="INVOIC",
            sender_id="S",
            recipient_id="R",
            reference_number="1",
            messages=[msg],
        )
        interchange = InterchangeInstance(
            syntax_identifier="UNOC",
            syntax_version="3",
            sender_id="S",
            recipient_id="R",
            control_reference="1",
            groups=[group],
        )

        all_msgs = interchange.all_messages()
        assert len(all_msgs) == 1
        assert all_msgs[0].message_type == "INVOIC"

    def test_all_messages_direct(self):
        """Test messages without UNG/UNE wrapper."""
        msg = MessageInstance(
            reference_number="1",
            message_type="ORDERS",
            version="D",
            release="23A",
        )
        interchange = InterchangeInstance(
            syntax_identifier="UNOC",
            syntax_version="3",
            sender_id="S",
            recipient_id="R",
            control_reference="1",
            messages=[msg],
        )

        all_msgs = interchange.all_messages()
        assert len(all_msgs) == 1
        assert all_msgs[0].message_type == "ORDERS"

    def test_str(self):
        interchange = InterchangeInstance(
            syntax_identifier="UNOC",
            syntax_version="3",
            sender_id="S",
            recipient_id="R",
            control_reference="12345",
        )
        s = str(interchange)
        assert "12345" in s


class TestParseResult:
    """Tests for ParseResult."""

    def test_creation(self):
        result = ParseResult()
        assert result.interchanges == []
        assert result.errors == []

    def test_is_valid_empty(self):
        result = ParseResult()
        assert result.is_valid()

    def test_is_valid_with_interchange(self):
        interchange = InterchangeInstance(
            syntax_identifier="UNOC",
            syntax_version="3",
            sender_id="S",
            recipient_id="R",
            control_reference="1",
        )
        result = ParseResult(interchanges=[interchange])
        assert result.is_valid()

    def test_is_valid_with_errors(self):
        result = ParseResult(
            errors=[ParseError(code="E", message="Test", category=ErrorCategory.STRUCTURAL)]
        )
        assert not result.is_valid()

    def test_has_fatal_errors(self):
        result = ParseResult(
            errors=[
                ParseError(
                    code="F001",
                    message="Fatal",
                    category=ErrorCategory.STRUCTURAL,
                    severity=ErrorSeverity.FATAL,
                )
            ]
        )
        assert result.has_fatal_errors()

    def test_no_fatal_errors(self):
        result = ParseResult(
            errors=[
                ParseError(
                    code="E001",
                    message="Error",
                    category=ErrorCategory.STRUCTURAL,
                    severity=ErrorSeverity.ERROR,
                )
            ]
        )
        assert not result.has_fatal_errors()

    def test_error_count(self):
        result = ParseResult(
            errors=[
                ParseError(code="1", message="A", category=ErrorCategory.SCHEMA),
                ParseError(code="2", message="B", category=ErrorCategory.SCHEMA),
            ]
        )
        assert result.error_count() == 2

    def test_all_messages(self):
        msg = MessageInstance(
            reference_number="1",
            message_type="INVOIC",
            version="D",
            release="23A",
        )
        interchange = InterchangeInstance(
            syntax_identifier="UNOC",
            syntax_version="3",
            sender_id="S",
            recipient_id="R",
            control_reference="1",
            messages=[msg],
        )
        result = ParseResult(interchanges=[interchange])

        all_msgs = result.all_messages()
        assert len(all_msgs) == 1

    def test_str_with_interchange(self):
        interchange = InterchangeInstance(
            syntax_identifier="UNOC",
            syntax_version="3",
            sender_id="S",
            recipient_id="R",
            control_reference="1",
        )
        result = ParseResult(interchanges=[interchange])
        s = str(result)
        assert "1 interchange" in s
        assert "valid" in s

    def test_str_failed(self):
        result = ParseResult(
            errors=[ParseError(code="E", message="Error", category=ErrorCategory.STRUCTURAL)]
        )
        s = str(result)
        assert "Failed" in s


class TestParseStatistics:
    """Tests for ParseStatistics."""

    def test_defaults(self):
        stats = ParseStatistics()
        assert stats.total_bytes == 0
        assert stats.segment_count == 0
        assert stats.message_count == 0
        assert stats.group_count == 0
        assert stats.interchange_count == 0
        assert not stats.una_present

    def test_custom_values(self):
        stats = ParseStatistics(
            total_bytes=1000,
            segment_count=50,
            message_count=2,
            una_present=True,
        )
        assert stats.total_bytes == 1000
        assert stats.segment_count == 50
        assert stats.message_count == 2
        assert stats.una_present
