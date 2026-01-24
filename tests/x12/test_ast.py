"""
Tests for X12 AST node types.
"""

import pytest

from edi_schema.x12.ast import (
    Delimiters,
    ErrorCategory,
    ErrorSeverity,
    FunctionalGroupInstance,
    HLNode,
    InterchangeInstance,
    LoopInstance,
    ParsedSegment,
    ParseError,
    ParseResult,
    RawComposite,
    RawElement,
    RawSegment,
    SourcePosition,
    TransactionSetInstance,
)


class TestSourcePosition:
    """Tests for SourcePosition."""

    def test_creation(self):
        pos = SourcePosition(offset=100, line=5, column=10, length=15)
        assert pos.offset == 100
        assert pos.line == 5
        assert pos.column == 10
        assert pos.length == 15

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
            segment_tag="BEG",
        )
        assert "BEG" in str(error)
        assert "line 5" in str(error)

    def test_to_dict(self):
        error = ParseError(
            code="E001",
            message="Test error",
            category=ErrorCategory.ELEMENT,
            severity=ErrorSeverity.WARNING,
            segment_tag="N1",
            element_position=2,
        )
        d = error.to_dict()
        assert d["code"] == "E001"
        assert d["category"] == "element"
        assert d["severity"] == "warning"
        assert d["segment_tag"] == "N1"
        assert d["element_position"] == 2


class TestDelimiters:
    """Tests for Delimiters."""

    def test_defaults(self):
        delim = Delimiters()
        assert delim.element == "*"
        assert delim.component == ":"
        assert delim.repetition == "^"
        assert delim.segment == "~"

    def test_custom(self):
        delim = Delimiters(element="|", component=">", segment="\n")
        assert delim.element == "|"
        assert delim.component == ">"
        assert delim.segment == "\n"

    def test_str(self):
        delim = Delimiters()
        s = str(delim)
        assert "element=" in s
        assert "component=" in s
        assert "segment=" in s


class TestRawElement:
    """Tests for RawElement."""

    def test_creation(self):
        pos = SourcePosition(0, 1, 1)
        elem = RawElement(value="TEST", position=pos, element_index=1)
        assert elem.value == "TEST"
        assert elem.element_index == 1

    def test_is_empty(self):
        pos = SourcePosition(0, 1, 1)
        empty = RawElement(value="", position=pos, element_index=1)
        not_empty = RawElement(value="X", position=pos, element_index=1)
        assert empty.is_empty()
        assert not not_empty.is_empty()

    def test_str(self):
        pos = SourcePosition(0, 1, 1)
        elem = RawElement(value="HELLO", position=pos, element_index=1)
        assert str(elem) == "HELLO"


class TestRawComposite:
    """Tests for RawComposite."""

    def test_creation(self):
        pos = SourcePosition(0, 1, 1)
        comp = RawComposite(components=["A", "B", "C"], position=pos, element_index=1)
        assert comp.components == ["A", "B", "C"]

    def test_get_component(self):
        pos = SourcePosition(0, 1, 1)
        comp = RawComposite(components=["A", "B", "C"], position=pos, element_index=1)
        assert comp.get_component(1) == "A"
        assert comp.get_component(2) == "B"
        assert comp.get_component(3) == "C"
        assert comp.get_component(0) is None
        assert comp.get_component(4) is None

    def test_is_empty(self):
        pos = SourcePosition(0, 1, 1)
        empty1 = RawComposite(components=[], position=pos, element_index=1)
        empty2 = RawComposite(components=["", ""], position=pos, element_index=1)
        not_empty = RawComposite(components=["X"], position=pos, element_index=1)
        assert empty1.is_empty()
        assert empty2.is_empty()
        assert not not_empty.is_empty()

    def test_str(self):
        pos = SourcePosition(0, 1, 1)
        comp = RawComposite(components=["HC", "99213"], position=pos, element_index=1)
        assert str(comp) == "HC:99213"


class TestRawSegment:
    """Tests for RawSegment."""

    def test_creation(self):
        pos = SourcePosition(0, 1, 1)
        elem1 = RawElement(value="00", position=pos, element_index=1)
        elem2 = RawElement(value="SA", position=pos, element_index=2)
        seg = RawSegment(
            tag="BEG",
            elements=[elem1, elem2],
            position=pos,
            raw_text="BEG*00*SA",
        )
        assert seg.tag == "BEG"
        assert len(seg.elements) == 2

    def test_get_element(self):
        pos = SourcePosition(0, 1, 1)
        elem1 = RawElement(value="A", position=pos, element_index=1)
        elem2 = RawElement(value="B", position=pos, element_index=2)
        seg = RawSegment(tag="TST", elements=[elem1, elem2], position=pos, raw_text="TST*A*B")

        assert seg.get_element(1) == elem1
        assert seg.get_element(2) == elem2
        assert seg.get_element(0) is None
        assert seg.get_element(3) is None

    def test_get_element_value(self):
        pos = SourcePosition(0, 1, 1)
        elem = RawElement(value="VALUE", position=pos, element_index=1)
        comp = RawComposite(components=["FIRST", "SECOND"], position=pos, element_index=2)
        seg = RawSegment(tag="TST", elements=[elem, comp], position=pos, raw_text="")

        assert seg.get_element_value(1) == "VALUE"
        assert seg.get_element_value(2) == "FIRST"  # First component
        assert seg.get_element_value(3) is None


class TestLoopInstance:
    """Tests for LoopInstance."""

    def test_creation(self):
        loop = LoopInstance(loop_id="N1", iteration=1)
        assert loop.loop_id == "N1"
        assert loop.iteration == 1
        assert loop.segments == []
        assert loop.children == []

    def test_is_valid_empty(self):
        loop = LoopInstance(loop_id="N1")
        assert loop.is_valid()

    def test_is_valid_with_errors(self):
        loop = LoopInstance(
            loop_id="N1",
            errors=[ParseError(code="E001", message="Test", category=ErrorCategory.SCHEMA)],
        )
        assert not loop.is_valid()

    def test_all_segments(self):
        pos = SourcePosition(0, 1, 1)
        seg1 = ParsedSegment(
            tag="N1",
            elements=[],
            raw=RawSegment(tag="N1", elements=[], position=pos, raw_text="N1"),
        )
        seg2 = ParsedSegment(
            tag="N3",
            elements=[],
            raw=RawSegment(tag="N3", elements=[], position=pos, raw_text="N3"),
        )

        child = LoopInstance(loop_id="REF", segments=[seg2])
        parent = LoopInstance(loop_id="N1", segments=[seg1], children=[child])

        all_segs = parent.all_segments()
        assert len(all_segs) == 2
        assert all_segs[0].tag == "N1"
        assert all_segs[1].tag == "N3"


class TestHLNode:
    """Tests for HLNode."""

    def test_creation(self):
        node = HLNode(
            hl_id="1",
            parent_id=None,
            level_code="S",
            has_children=True,
        )
        assert node.hl_id == "1"
        assert node.parent_id is None
        assert node.level_code == "S"
        assert node.has_children

    def test_hierarchy(self):
        parent = HLNode(hl_id="1", parent_id=None, level_code="S", has_children=True)
        child = HLNode(hl_id="2", parent_id="1", level_code="O", has_children=False)
        child.parent = parent
        parent.children.append(child)

        assert len(parent.children) == 1
        assert parent.children[0].hl_id == "2"
        assert child.parent == parent

    def test_str(self):
        node = HLNode(hl_id="1", parent_id=None, level_code="S", has_children=True)
        s = str(node)
        assert "HL 1" in s
        assert "level=S" in s


class TestTransactionSetInstance:
    """Tests for TransactionSetInstance."""

    def test_creation(self):
        txn = TransactionSetInstance(
            transaction_id="850",
            control_number="0001",
        )
        assert txn.transaction_id == "850"
        assert txn.control_number == "0001"

    def test_is_valid_empty(self):
        txn = TransactionSetInstance(transaction_id="850", control_number="0001")
        assert txn.is_valid()

    def test_is_valid_with_errors(self):
        txn = TransactionSetInstance(
            transaction_id="850",
            control_number="0001",
            errors=[ParseError(code="E", message="Test", category=ErrorCategory.SCHEMA)],
        )
        assert not txn.is_valid()


class TestFunctionalGroupInstance:
    """Tests for FunctionalGroupInstance."""

    def test_creation(self):
        group = FunctionalGroupInstance(
            functional_id="PO",
            sender_id="SENDER",
            receiver_id="RECEIVER",
            date="20210101",
            time="1200",
            control_number="1",
            responsible_agency="X",
            version="005010",
        )
        assert group.functional_id == "PO"
        assert group.version == "005010"

    def test_is_valid(self):
        group = FunctionalGroupInstance(
            functional_id="PO",
            sender_id="S",
            receiver_id="R",
            date="20210101",
            time="1200",
            control_number="1",
            responsible_agency="X",
            version="005010",
        )
        assert group.is_valid()


class TestInterchangeInstance:
    """Tests for InterchangeInstance."""

    def test_creation(self):
        interchange = InterchangeInstance(
            auth_qualifier="00",
            auth_info="          ",
            security_qualifier="00",
            security_info="          ",
            sender_qualifier="ZZ",
            sender_id="SENDER         ",
            receiver_qualifier="ZZ",
            receiver_id="RECEIVER       ",
            date="210101",
            time="1200",
            repetition_separator="^",
            version="00501",
            control_number="000000001",
            ack_requested="0",
            usage_indicator="T",
            component_separator=":",
        )
        assert interchange.version == "00501"
        assert interchange.is_test()
        assert not interchange.is_production()

    def test_all_transactions(self):
        txn = TransactionSetInstance(transaction_id="850", control_number="0001")
        group = FunctionalGroupInstance(
            functional_id="PO",
            sender_id="S",
            receiver_id="R",
            date="20210101",
            time="1200",
            control_number="1",
            responsible_agency="X",
            version="005010",
            transactions=[txn],
        )
        interchange = InterchangeInstance(
            auth_qualifier="00",
            auth_info="",
            security_qualifier="00",
            security_info="",
            sender_qualifier="ZZ",
            sender_id="S",
            receiver_qualifier="ZZ",
            receiver_id="R",
            date="210101",
            time="1200",
            repetition_separator="^",
            version="00501",
            control_number="1",
            ack_requested="0",
            usage_indicator="P",
            component_separator=":",
            groups=[group],
        )

        all_txns = interchange.all_transactions()
        assert len(all_txns) == 1
        assert all_txns[0].transaction_id == "850"


class TestParseResult:
    """Tests for ParseResult."""

    def test_creation(self):
        result = ParseResult()
        assert result.interchange is None
        assert result.errors == []

    def test_is_valid_no_interchange(self):
        result = ParseResult()
        assert result.is_valid()

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

    def test_error_count(self):
        result = ParseResult(
            errors=[
                ParseError(code="1", message="A", category=ErrorCategory.SCHEMA),
                ParseError(code="2", message="B", category=ErrorCategory.SCHEMA),
            ]
        )
        assert result.error_count() == 2
