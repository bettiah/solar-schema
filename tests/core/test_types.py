"""
Tests for core type definitions and protocols.
"""

from dataclasses import dataclass
from typing import Any

from edi_schema.core.types import (
    CompositeLike,
    ElementLike,
    RequirementDesignator,
    SchemaLike,
    SegmentLike,
)


class TestRequirementDesignator:
    """Tests for RequirementDesignator enum."""

    def test_mandatory_value(self):
        assert RequirementDesignator.MANDATORY.value == "M"

    def test_optional_value(self):
        assert RequirementDesignator.OPTIONAL.value == "O"

    def test_conditional_value(self):
        assert RequirementDesignator.CONDITIONAL.value == "C"

    def test_is_required_mandatory(self):
        assert RequirementDesignator.MANDATORY.is_required is True

    def test_is_required_optional(self):
        assert RequirementDesignator.OPTIONAL.is_required is False

    def test_is_required_conditional(self):
        assert RequirementDesignator.CONDITIONAL.is_required is False

    def test_is_conditional_mandatory(self):
        assert RequirementDesignator.MANDATORY.is_conditional is False

    def test_is_conditional_conditional(self):
        assert RequirementDesignator.CONDITIONAL.is_conditional is True


class TestProtocols:
    """Tests for protocol definitions."""

    def test_element_like_protocol(self):
        """Test that a class can satisfy ElementLike protocol."""

        @dataclass
        class MockElement:
            id: str
            name: str
            min_length: int
            max_length: int
            data_type: str

        elem = MockElement(
            id="1",
            name="Route Code",
            min_length=1,
            max_length=13,
            data_type="AN",
        )

        assert isinstance(elem, ElementLike)
        assert elem.id == "1"
        assert elem.name == "Route Code"

    def test_segment_like_protocol(self):
        """Test that a class can satisfy SegmentLike protocol."""

        @dataclass
        class MockSegment:
            id: str
            name: str
            elements: list

        seg = MockSegment(
            id="ISA",
            name="Interchange Control Header",
            elements=[],
        )

        assert isinstance(seg, SegmentLike)
        assert seg.id == "ISA"

    def test_composite_like_protocol(self):
        """Test that a class can satisfy CompositeLike protocol."""

        @dataclass
        class MockComposite:
            id: str
            name: str
            components: list

        comp = MockComposite(
            id="C001",
            name="Composite Unit of Measure",
            components=[],
        )

        assert isinstance(comp, CompositeLike)
        assert comp.id == "C001"

    def test_schema_like_protocol(self):
        """Test that a class can satisfy SchemaLike protocol."""

        class MockSchema:
            @property
            def format(self) -> str:
                return "x12"

            @property
            def id(self) -> str:
                return "850"

            @property
            def version(self) -> str:
                return "005010"

            @property
            def name(self) -> str:
                return "Purchase Order"

            def get_segment(self, segment_id: str) -> SegmentLike | None:
                return None

            def get_element(self, element_id: str) -> ElementLike | None:
                return None

            def get_composite(self, composite_id: str) -> CompositeLike | None:
                return None

            def get_structure(self) -> list[Any]:
                return []

        schema = MockSchema()
        assert isinstance(schema, SchemaLike)
        assert schema.format == "x12"
        assert schema.id == "850"
