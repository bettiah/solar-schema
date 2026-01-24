"""
Tests for X12 data models.

Tests the dataclass models for elements, segments, composites, and transactions.
"""

from edi_schema.x12.enums import (
    DataElementType,
    RequirementDesignator,
    TransactionSetArea,
)
from edi_schema.x12.models import (
    CodeSource,
    Composite,
    CompositeElement,
    DataElement,
    Segment,
    SegmentElement,
    TransactionSet,
    TransactionSetSegment,
)


class TestDataElement:
    """Tests for DataElement model."""

    def test_create_element(self):
        """Test creating a DataElement."""
        element = DataElement(
            id="373",
            name="Date",
            data_type=DataElementType.DT,
            min_length=8,
            max_length=8,
            definition="Date expressed as CCYYMMDD",
        )

        assert element.id == "373"
        assert element.name == "Date"
        assert element.data_type == DataElementType.DT
        assert element.min_length == 8
        assert element.max_length == 8
        assert element.definition == "Date expressed as CCYYMMDD"

    def test_element_with_codes(self):
        """Test element with code values."""
        element = DataElement(
            id="66",
            name="Identification Code Qualifier",
            data_type=DataElementType.ID,
            min_length=1,
            max_length=2,
            code_values={
                "1": "D-U-N-S Number",
                "2": "SCAC",
                "9": "D-U-N-S+4",
            },
        )

        assert element.has_code_list()
        assert element.is_valid_code("1")
        assert element.is_valid_code("2")
        assert not element.is_valid_code("99")

    def test_element_without_codes(self):
        """Test element without code values."""
        element = DataElement(
            id="19",
            name="City Name",
            data_type=DataElementType.AN,
            min_length=2,
            max_length=30,
        )

        assert not element.has_code_list()
        assert element.is_valid_code("anything")  # No code list means any value valid

    def test_element_str(self):
        """Test string representation."""
        element = DataElement(
            id="373",
            name="Date",
            data_type=DataElementType.DT,
            min_length=8,
            max_length=8,
        )

        str_repr = str(element)
        assert "373" in str_repr
        assert "Date" in str_repr
        assert "DT" in str_repr


class TestComposite:
    """Tests for Composite model."""

    def test_create_composite(self):
        """Test creating a Composite."""
        composite = Composite(
            id="C001",
            name="Composite Unit of Measure",
            purpose="To identify a composite unit of measure",
            elements=[
                CompositeElement(
                    sequence="01", element_id="355", requirement=RequirementDesignator.M
                ),
                CompositeElement(
                    sequence="02", element_id="1018", requirement=RequirementDesignator.O
                ),
            ],
        )

        assert composite.id == "C001"
        assert composite.name == "Composite Unit of Measure"
        assert len(composite.elements) == 2

    def test_composite_get_element(self):
        """Test getting element by sequence."""
        composite = Composite(
            id="C001",
            name="Composite Unit of Measure",
            elements=[
                CompositeElement(
                    sequence="01", element_id="355", requirement=RequirementDesignator.M
                ),
                CompositeElement(
                    sequence="02", element_id="1018", requirement=RequirementDesignator.O
                ),
            ],
        )

        elem = composite.get_element("01")
        assert elem is not None
        assert elem.element_id == "355"

        assert composite.get_element("99") is None


class TestSegment:
    """Tests for Segment model."""

    def test_create_segment(self):
        """Test creating a Segment."""
        segment = Segment(
            id="N1",
            name="Party Identification",
            purpose="To identify a party by type of organization, name, and code",
            elements=[
                SegmentElement(sequence="01", element_id="98", requirement=RequirementDesignator.M),
                SegmentElement(sequence="02", element_id="93", requirement=RequirementDesignator.O),
                SegmentElement(sequence="03", element_id="66", requirement=RequirementDesignator.C),
                SegmentElement(sequence="04", element_id="67", requirement=RequirementDesignator.C),
            ],
        )

        assert segment.id == "N1"
        assert segment.name == "Party Identification"
        assert len(segment.elements) == 4

    def test_segment_get_element(self):
        """Test getting element by sequence."""
        segment = Segment(
            id="N1",
            name="Party Identification",
            elements=[
                SegmentElement(sequence="01", element_id="98", requirement=RequirementDesignator.M),
                SegmentElement(sequence="02", element_id="93", requirement=RequirementDesignator.O),
            ],
        )

        elem = segment.get_element("01")
        assert elem is not None
        assert elem.element_id == "98"

    def test_segment_mandatory_elements(self):
        """Test getting mandatory elements."""
        segment = Segment(
            id="N1",
            name="Party Identification",
            elements=[
                SegmentElement(sequence="01", element_id="98", requirement=RequirementDesignator.M),
                SegmentElement(sequence="02", element_id="93", requirement=RequirementDesignator.O),
                SegmentElement(sequence="03", element_id="66", requirement=RequirementDesignator.M),
            ],
        )

        mandatory = segment.mandatory_elements()
        assert len(mandatory) == 2
        assert all(e.requirement == RequirementDesignator.M for e in mandatory)


class TestSegmentElement:
    """Tests for SegmentElement model."""

    def test_is_composite(self):
        """Test is_composite detection."""
        elem1 = SegmentElement(sequence="01", element_id="98", requirement=RequirementDesignator.M)
        elem2 = SegmentElement(
            sequence="02", element_id="C001", requirement=RequirementDesignator.O
        )

        assert not elem1.is_composite()
        assert elem2.is_composite()


class TestTransactionSet:
    """Tests for TransactionSet model."""

    def test_create_transaction_set(self):
        """Test creating a TransactionSet."""
        ts = TransactionSet(
            id="810",
            name="Invoice",
            functional_group="IN",
            purpose="This transaction set is used to transmit invoice data.",
            structure=[
                TransactionSetSegment(
                    area=TransactionSetArea.HEADING,
                    sequence="0100",
                    segment_id="ST",
                    requirement=RequirementDesignator.M,
                    max_use=1,
                ),
                TransactionSetSegment(
                    area=TransactionSetArea.HEADING,
                    sequence="0200",
                    segment_id="BIG",
                    requirement=RequirementDesignator.M,
                    max_use=1,
                ),
            ],
        )

        assert ts.id == "810"
        assert ts.name == "Invoice"
        assert ts.functional_group == "IN"
        assert len(ts.structure) == 2

    def test_get_area_segments(self):
        """Test getting segments by area."""
        ts = TransactionSet(
            id="810",
            name="Invoice",
            functional_group="IN",
            structure=[
                TransactionSetSegment(
                    area=TransactionSetArea.HEADING,
                    sequence="0100",
                    segment_id="ST",
                    requirement=RequirementDesignator.M,
                ),
                TransactionSetSegment(
                    area=TransactionSetArea.DETAIL,
                    sequence="0100",
                    segment_id="IT1",
                    requirement=RequirementDesignator.O,
                ),
                TransactionSetSegment(
                    area=TransactionSetArea.SUMMARY,
                    sequence="0100",
                    segment_id="SE",
                    requirement=RequirementDesignator.M,
                ),
            ],
        )

        assert len(ts.get_heading_segments()) == 1
        assert len(ts.get_detail_segments()) == 1
        assert len(ts.get_summary_segments()) == 1

    def test_get_loops(self):
        """Test getting loop definitions."""
        ts = TransactionSet(
            id="850",
            name="Purchase Order",
            functional_group="PO",
            structure=[
                TransactionSetSegment(
                    area=TransactionSetArea.HEADING,
                    sequence="0100",
                    segment_id="ST",
                    requirement=RequirementDesignator.M,
                ),
                TransactionSetSegment(
                    area=TransactionSetArea.HEADING,
                    sequence="0300",
                    segment_id="N1",
                    requirement=RequirementDesignator.O,
                    loop_level=1,
                    loop_repeat=">1",
                    loop_id="N1",
                ),
                TransactionSetSegment(
                    area=TransactionSetArea.HEADING,
                    sequence="0400",
                    segment_id="N3",
                    requirement=RequirementDesignator.O,
                    loop_level=1,
                    loop_repeat=0,
                    loop_id="N1",
                ),
            ],
        )

        loops = ts.get_loops()
        assert "N1" in loops
        assert len(loops["N1"].segments) == 2


class TestTransactionSetSegment:
    """Tests for TransactionSetSegment model."""

    def test_is_loop_start(self):
        """Test is_loop_start detection."""
        seg1 = TransactionSetSegment(
            area=TransactionSetArea.HEADING,
            sequence="0100",
            segment_id="ST",
            requirement=RequirementDesignator.M,
        )
        seg2 = TransactionSetSegment(
            area=TransactionSetArea.HEADING,
            sequence="0300",
            segment_id="N1",
            requirement=RequirementDesignator.O,
            loop_id="N1",
        )

        assert not seg1.is_loop_start()
        assert seg2.is_loop_start()

    def test_unlimited_detection(self):
        """Test unlimited max_use detection."""
        seg1 = TransactionSetSegment(
            area=TransactionSetArea.DETAIL,
            sequence="0100",
            segment_id="IT1",
            requirement=RequirementDesignator.O,
            max_use=1,
        )
        seg2 = TransactionSetSegment(
            area=TransactionSetArea.DETAIL,
            sequence="0100",
            segment_id="IT1",
            requirement=RequirementDesignator.O,
            max_use=">1",
        )

        assert not seg1.is_unlimited()
        assert seg2.is_unlimited()
        assert seg1.get_max_use_int() == 1
        assert seg2.get_max_use_int() == -1


class TestCodeSource:
    """Tests for CodeSource model."""

    def test_create_code_source(self):
        """Test creating a CodeSource."""
        cs = CodeSource(
            id="17",
            name="Standard Carrier Alpha Code (SCAC)",
            source_info="National Motor Freight Traffic Association",
            elements=["140", "206"],
        )

        assert cs.id == "17"
        assert cs.name == "Standard Carrier Alpha Code (SCAC)"
        assert len(cs.elements) == 2

    def test_code_source_values(self):
        """Test code source with values."""
        cs = CodeSource(
            id="1",
            name="Test Code Source",
        )
        cs.add_code_value("66", "1", "D-U-N-S Number")
        cs.add_code_value("66", "2", "SCAC")

        assert cs.get_code_value("66", "1") == "D-U-N-S Number"
        assert cs.get_code_value("66", "2") == "SCAC"
        assert cs.get_code_value("66", "99") is None
