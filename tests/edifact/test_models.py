"""
Tests for EDIFACT models.

Tests cover dataclass creation and protocol compliance.
"""

from edi_schema.edifact.models import (
    Component,
    Composite,
    DataElement,
    MessageSpec,
    ResolvedMessageSpec,
    Segment,
    SegmentElement,
    SegmentGroup,
    SegmentRef,
)


class TestDataElement:
    """Tests for DataElement model."""

    def test_create_data_element(self):
        """Can create a DataElement."""
        element = DataElement(
            tag="1001",
            name="Document name code",
            description="Code specifying the document name.",
            data_type="an",
            max_length=3,
            min_length=0,
        )
        assert element.tag == "1001"
        assert element.name == "Document name code"
        assert element.data_type == "an"

    def test_data_element_id_property(self):
        """id property returns tag."""
        element = DataElement(
            tag="1001",
            name="Test",
            description="",
            data_type="an",
            max_length=3,
        )
        assert element.id == "1001"

    def test_data_element_with_codes(self):
        """DataElement can have codes."""
        element = DataElement(
            tag="1001",
            name="Test",
            description="",
            data_type="an",
            max_length=3,
            codes={"1": "Option 1", "2": "Option 2"},
        )
        assert element.codes is not None
        assert "1" in element.codes


class TestComponent:
    """Tests for Component model."""

    def test_create_component(self):
        """Can create a Component."""
        component = Component(
            position=10,
            element_tag="1001",
            mandatory=True,
        )
        assert component.position == 10
        assert component.element_tag == "1001"
        assert component.mandatory is True
        assert component.element is None

    def test_component_with_resolved_element(self):
        """Component can have resolved element."""
        element = DataElement(
            tag="1001",
            name="Test",
            description="",
            data_type="an",
            max_length=3,
        )
        component = Component(
            position=10,
            element_tag="1001",
            mandatory=True,
            element=element,
        )
        assert component.element is not None
        assert component.element.tag == "1001"


class TestComposite:
    """Tests for Composite model."""

    def test_create_composite(self):
        """Can create a Composite."""
        composite = Composite(
            tag="C001",
            name="TRANSPORT MEANS",
            description="Identification of transport means.",
            components=[
                Component(position=10, element_tag="8179", mandatory=False),
                Component(position=20, element_tag="1131", mandatory=False),
            ],
        )
        assert composite.tag == "C001"
        assert len(composite.components) == 2

    def test_composite_id_property(self):
        """id property returns tag."""
        composite = Composite(tag="C001", name="Test", description="")
        assert composite.id == "C001"


class TestSegment:
    """Tests for Segment model."""

    def test_create_segment(self):
        """Can create a Segment."""
        segment = Segment(
            tag="BGM",
            name="BEGINNING OF MESSAGE",
            function="To indicate message type and function.",
            elements=[
                SegmentElement(
                    position=10,
                    tag="C002",
                    name="DOCUMENT NAME",
                    mandatory=False,
                    is_composite=True,
                ),
            ],
        )
        assert segment.tag == "BGM"
        assert len(segment.elements) == 1

    def test_segment_id_property(self):
        """id property returns tag."""
        segment = Segment(tag="BGM", name="Test", function="")
        assert segment.id == "BGM"


class TestSegmentGroup:
    """Tests for SegmentGroup model."""

    def test_create_segment_group(self):
        """Can create a SegmentGroup."""
        group = SegmentGroup(
            number=1,
            mandatory=False,
            max_repeat=99999,
            children=[
                SegmentRef(position=130, segment_tag="RFF", mandatory=True, max_repeat=1),
                SegmentRef(position=140, segment_tag="DTM", mandatory=False, max_repeat=5),
            ],
        )
        assert group.number == 1
        assert len(group.children) == 2

    def test_nested_segment_groups(self):
        """SegmentGroup can contain nested groups."""
        inner_group = SegmentGroup(
            number=2,
            mandatory=False,
            max_repeat=9999,
            children=[
                SegmentRef(position=280, segment_tag="RFF", mandatory=True, max_repeat=1),
            ],
        )
        outer_group = SegmentGroup(
            number=1,
            mandatory=False,
            max_repeat=99,
            children=[
                SegmentRef(position=230, segment_tag="NAD", mandatory=True, max_repeat=1),
                inner_group,
            ],
        )
        assert outer_group.number == 1
        assert len(outer_group.children) == 2
        assert isinstance(outer_group.children[1], SegmentGroup)


class TestMessageSpec:
    """Tests for MessageSpec model."""

    def test_create_message_spec(self):
        """Can create a MessageSpec."""
        msg = MessageSpec(
            code="INVOIC",
            version="D",
            release="23A",
            name="Invoice message",
            structure=[
                SegmentRef(position=10, segment_tag="UNH", mandatory=True, max_repeat=1),
                SegmentRef(position=20, segment_tag="BGM", mandatory=True, max_repeat=1),
            ],
        )
        assert msg.code == "INVOIC"
        assert msg.version == "D"
        assert msg.release == "23A"
        assert len(msg.structure) == 2

    def test_message_spec_format(self):
        """format property returns 'edifact'."""
        msg = MessageSpec(code="INVOIC", version="D", release="23A", name="Invoice")
        assert msg.format == "edifact"

    def test_message_spec_full_version(self):
        """full_version combines version and release."""
        msg = MessageSpec(code="INVOIC", version="D", release="23A", name="Invoice")
        assert msg.full_version == "D.23A"


class TestResolvedMessageSpec:
    """Tests for ResolvedMessageSpec model."""

    def test_create_resolved_message_spec(self):
        """Can create a ResolvedMessageSpec."""
        msg = MessageSpec(
            code="INVOIC",
            version="D",
            release="23A",
            name="Invoice message",
        )
        resolved = ResolvedMessageSpec(
            spec=msg,
            segments={"BGM": Segment(tag="BGM", name="Beginning", function="")},
            composites={},
            elements={},
        )
        assert resolved.id == "INVOIC"
        assert resolved.format == "edifact"
        assert resolved.version == "D.23A"

    def test_resolved_message_get_segment(self):
        """get_segment returns segment from dictionary."""
        msg = MessageSpec(code="TEST", version="D", release="23A", name="Test")
        segment = Segment(tag="BGM", name="Beginning", function="")
        resolved = ResolvedMessageSpec(
            spec=msg,
            segments={"BGM": segment},
            composites={},
            elements={},
        )
        assert resolved.get_segment("BGM") is segment
        assert resolved.get_segment("XXX") is None

    def test_resolved_message_get_structure(self):
        """get_structure returns spec structure."""
        msg = MessageSpec(
            code="TEST",
            version="D",
            release="23A",
            name="Test",
            structure=[
                SegmentRef(position=10, segment_tag="UNH", mandatory=True, max_repeat=1),
            ],
        )
        resolved = ResolvedMessageSpec(spec=msg)
        structure = resolved.get_structure()
        assert len(structure) == 1
        assert structure[0].segment_tag == "UNH"
