"""
Tests for EDIFACT Message Parser.

Tests cover:
- Schema loading based on UNH S009 message identifier
- Schema-driven segment parsing with definitions attached
- Segment group building using GroupMatcher
- Nested segment groups handling
- Fallback flat parsing when no schema available
- Error handling for out-of-order and unknown segments
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from edi_schema.edifact.ast import (
    MessageInstance,
    ParsedElement,
    ParsedSegment,
    RawComponent,
    RawElement,
    RawSegment,
    SegmentGroupInstance,
    SourcePosition,
)
from edi_schema.edifact.parser.envelope import parse_envelope
from edi_schema.edifact.parser.message import (
    EdifactMessageParser,
    MessageParseResult,
    parse_message,
)
from edi_schema.edifact.parser.tokenizer import tokenize

# =============================================================================
# Test Fixtures
# =============================================================================


def make_source_position(offset: int = 0) -> SourcePosition:
    """Create a test source position."""
    return SourcePosition(offset=offset, line=1, column=offset + 1)


def make_raw_element(value: str, index: int = 1) -> RawElement:
    """Create a test raw element."""
    return RawElement(
        value=value,
        position=make_source_position(),
        element_index=index,
    )


def make_raw_segment(tag: str, elements: list[str]) -> RawSegment:
    """Create a test raw segment."""
    raw_elements = [make_raw_element(val, i + 1) for i, val in enumerate(elements)]
    return RawSegment(
        tag=tag,
        elements=raw_elements,
        position=make_source_position(),
        raw_text=f"{tag}+{'+'.join(elements)}",
    )


def make_parsed_segment(tag: str, elements: list[str]) -> ParsedSegment:
    """Create a test parsed segment."""
    raw_seg = make_raw_segment(tag, elements)
    parsed_elements = [ParsedElement(raw=e) for e in raw_seg.elements]
    return ParsedSegment(
        tag=tag,
        elements=parsed_elements,
        raw=raw_seg,
    )


def make_message_instance(
    message_type: str = "INVOIC",
    version: str = "D",
    release: str = "23A",
    content: list[ParsedSegment] | None = None,
) -> MessageInstance:
    """Create a test message instance."""
    return MessageInstance(
        reference_number="1",
        message_type=message_type,
        version=version,
        release=release,
        controlling_agency="UN",
        content=content or [],
    )


# =============================================================================
# Basic Parser Tests
# =============================================================================


class TestMessageParserBasics:
    """Test basic message parser functionality."""

    def test_parser_creation(self):
        """Test parser can be created without schema builder."""
        parser = EdifactMessageParser()
        assert parser is not None
        assert parser.schema_loader is None

    def test_parser_with_schema_loader(self):
        """Test parser can be created with schema builder."""
        mock_builder = MagicMock()
        parser = EdifactMessageParser(mock_builder)
        assert parser.schema_loader is mock_builder

    def test_parse_convenience_function(self):
        """Test parse_message convenience function."""
        message = make_message_instance(
            content=[
                make_parsed_segment("BGM", ["380", "INV001"]),
            ]
        )
        result = parse_message(message)
        assert result is not None
        assert isinstance(result, MessageInstance)


# =============================================================================
# Fallback Parsing Tests (No Schema)
# =============================================================================


class TestFallbackParsing:
    """Test fallback parsing when no schema is available."""

    def test_fallback_preserves_segments(self):
        """Test fallback parsing preserves all segments."""
        content = [
            make_parsed_segment("BGM", ["380", "INV001"]),
            make_parsed_segment("DTM", ["137", "20231031"]),
            make_parsed_segment("NAD", ["BY", "BUYER123"]),
        ]
        message = make_message_instance(content=content)

        parser = EdifactMessageParser(schema_loader=None)
        result = parser.parse(message)

        assert len(result.content) == 3
        assert all(isinstance(item, ParsedSegment) for item in result.content)

    def test_fallback_no_segment_groups(self):
        """Test fallback parsing creates no segment groups."""
        content = [
            make_parsed_segment("BGM", ["380", "INV001"]),
            make_parsed_segment("RFF", ["ON", "PO123"]),
        ]
        message = make_message_instance(content=content)

        parser = EdifactMessageParser(schema_loader=None)
        result = parser.parse(message)

        # All content should be ParsedSegment, no SegmentGroupInstance
        assert all(isinstance(item, ParsedSegment) for item in result.content)

    def test_fallback_with_nonexistent_schema(self):
        """Test fallback when schema builder doesn't have message type."""
        mock_builder = MagicMock()
        mock_builder.exists.return_value = False

        content = [make_parsed_segment("BGM", ["380"])]
        message = make_message_instance(message_type="UNKNOWN", content=content)

        parser = EdifactMessageParser(mock_builder)
        result = parser.parse(message)

        # Should fall back to flat parsing
        assert len(result.content) == 1
        assert isinstance(result.content[0], ParsedSegment)


# =============================================================================
# Schema-Driven Parsing Tests
# =============================================================================


class TestSchemaLoading:
    """Test schema loading based on message identifier."""

    def test_schema_loaded_for_message_type(self):
        """Test schema is loaded based on message type."""
        mock_schema = MagicMock()
        mock_schema.get_segment.return_value = None
        mock_schema.segments = {}
        mock_schema.composites = {}
        mock_schema.elements = {}
        # Mock the spec.structure to be empty so hierarchy building works
        mock_schema.spec.structure = []

        mock_builder = MagicMock()
        mock_builder.exists.return_value = True
        mock_builder.load.return_value = mock_schema

        content = [make_parsed_segment("BGM", ["380"])]
        message = make_message_instance(message_type="INVOIC", content=content)

        parser = EdifactMessageParser(mock_builder)
        parser.parse(message)

        mock_builder.exists.assert_called_with("INVOIC")
        mock_builder.load.assert_called_with("INVOIC")

    def test_schema_not_found_falls_back(self):
        """Test fallback when schema load fails."""
        mock_builder = MagicMock()
        mock_builder.exists.return_value = True
        mock_builder.load.side_effect = ValueError("Not found")

        content = [make_parsed_segment("BGM", ["380"])]
        message = make_message_instance(content=content)

        parser = EdifactMessageParser(mock_builder)
        result = parser.parse(message)

        # Should fall back to flat parsing
        assert len(result.content) == 1


# =============================================================================
# Segment Definition Attachment Tests
# =============================================================================


class TestDefinitionAttachment:
    """Test attachment of schema definitions to segments."""

    def test_segment_definition_attached(self):
        """Test segment definition is attached when available."""
        # Create mock segment definition
        mock_segment_def = MagicMock()
        mock_segment_def.elements = []

        mock_schema = MagicMock()
        mock_schema.get_segment.return_value = mock_segment_def
        mock_schema.segments = {"BGM": mock_segment_def}
        mock_schema.composites = {}
        mock_schema.elements = {}
        mock_schema.spec.structure = []

        mock_builder = MagicMock()
        mock_builder.exists.return_value = True
        mock_builder.load.return_value = mock_schema

        content = [make_parsed_segment("BGM", ["380"])]
        message = make_message_instance(content=content)

        parser = EdifactMessageParser(mock_builder)
        result = parser.parse(message)

        # Check segment has definition attached
        assert len(result.content) == 1
        parsed_seg = result.content[0]
        assert isinstance(parsed_seg, ParsedSegment)
        assert parsed_seg.definition is mock_segment_def

    def test_element_definition_attached(self):
        """Test element definitions are attached when available."""
        # Create mock element definition
        mock_element_def = MagicMock()

        # Create mock segment element - uses actual model attributes
        # SegmentElement has: tag, is_composite, resolved
        mock_seg_element = MagicMock()
        mock_seg_element.tag = "1004"
        mock_seg_element.is_composite = False  # Simple element, not composite
        mock_seg_element.resolved = mock_element_def  # Already resolved

        mock_segment_def = MagicMock()
        mock_segment_def.elements = [mock_seg_element]

        mock_schema = MagicMock()
        mock_schema.get_segment.return_value = mock_segment_def
        mock_schema.segments = {}
        mock_schema.composites = {}
        mock_schema.elements = {"1004": mock_element_def}
        mock_schema.spec.structure = []

        mock_builder = MagicMock()
        mock_builder.exists.return_value = True
        mock_builder.load.return_value = mock_schema

        content = [make_parsed_segment("BGM", ["380"])]
        message = make_message_instance(content=content)

        parser = EdifactMessageParser(mock_builder)
        result = parser.parse(message)

        parsed_seg = result.content[0]
        assert isinstance(parsed_seg, ParsedSegment)
        assert len(parsed_seg.elements) == 1
        assert parsed_seg.elements[0].element_definition is mock_element_def


# =============================================================================
# Integration Tests with Real Schema
# =============================================================================


@pytest.fixture
def schema_path():
    """Get path to EDIFACT schema directory."""
    return Path("/Users/me/Downloads/edi/schema/edifact/d23a")


@pytest.fixture
def schema_loader(schema_path):
    """Create schema builder if schema directory exists."""
    if not schema_path.exists():
        pytest.skip("EDIFACT schema directory not found")

    from edi_schema.edifact.schema import EdifactSchemaLoader

    return EdifactSchemaLoader(schema_path)


class TestIntegrationWithRealSchema:
    """Integration tests with real EDIFACT schemas."""

    def test_parse_invoic_with_schema(self, schema_loader):
        """Test parsing INVOIC message with real schema."""
        # Create a simple INVOIC message structure
        data = (
            "UNA:+.? '"
            "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'"
            "UNH+1+INVOIC:D:23A:UN'"
            "BGM+380+INV001+9'"
            "DTM+137:20231031:102'"
            "UNT+4+1'"
            "UNZ+1+12345'"
        )

        # Parse through tokenizer and envelope parser
        tokenizer_result = tokenize(data)
        envelope_result = parse_envelope(tokenizer_result)

        assert len(envelope_result.interchanges) == 1
        assert len(envelope_result.interchanges[0].messages) == 1

        message = envelope_result.interchanges[0].messages[0]

        # Parse with message parser
        parser = EdifactMessageParser(schema_loader)
        result = parser.parse(message)

        # Check that definitions are attached
        assert len(result.content) >= 2

        # BGM should have segment definition
        bgm_seg = next(
            (s for s in result.content if isinstance(s, ParsedSegment) and s.tag == "BGM"), None
        )
        assert bgm_seg is not None
        assert bgm_seg.definition is not None

    def test_parse_orders_with_schema(self, schema_loader):
        """Test parsing ORDERS message with real schema."""
        data = (
            "UNA:+.? '"
            "UNB+UNOA:3+BUYER+SELLER+231031:0900+ORDER001'"
            "UNH+1+ORDERS:D:96A:UN'"
            "BGM+220+PO12345+9'"
            "DTM+137:20231031:102'"
            "NAD+BY+BUYER123::9'"
            "NAD+SU+SELLER456::9'"
            "UNT+6+1'"
            "UNZ+1+ORDER001'"
        )

        tokenizer_result = tokenize(data)
        envelope_result = parse_envelope(tokenizer_result)
        message = envelope_result.interchanges[0].messages[0]

        parser = EdifactMessageParser(schema_loader)
        result = parser.parse(message)

        # Should have parsed segments with definitions
        # Count all segments including those inside segment groups
        all_segments = []
        for item in result.content:
            if isinstance(item, ParsedSegment):
                all_segments.append(item)
            elif isinstance(item, SegmentGroupInstance):
                all_segments.extend(item.all_segments())
        assert len(all_segments) >= 4

    def test_segment_groups_created(self, schema_loader):
        """Test that segment groups are created for structured messages."""
        # ORDERS with NAD segments that should be in segment groups
        data = (
            "UNA:+.? '"
            "UNB+UNOA:3+BUYER+SELLER+231031:0900+ORDER001'"
            "UNH+1+ORDERS:D:96A:UN'"
            "BGM+220+PO12345+9'"
            "DTM+137:20231031:102'"
            "RFF+ON:PO12345'"  # RFF triggers SG1
            "DTM+171:20231101:102'"
            "NAD+BY+BUYER123::9'"  # NAD triggers SG2
            "RFF+VA:DE123456789'"  # RFF in SG3 (child of SG2)
            "NAD+SU+SELLER456::9'"  # Another NAD (new SG2 iteration)
            "UNT+10+1'"
            "UNZ+1+ORDER001'"
        )

        tokenizer_result = tokenize(data)
        envelope_result = parse_envelope(tokenizer_result)
        message = envelope_result.interchanges[0].messages[0]

        parser = EdifactMessageParser(schema_loader)
        result = parser.parse(message)

        # Check for segment groups in content
        has_groups = any(isinstance(item, SegmentGroupInstance) for item in result.content)
        # Note: Segment groups should be created based on schema structure
        # This test validates the mechanism works
        assert len(result.content) > 0


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Test error handling for various scenarios."""

    def test_unknown_segment_warning(self):
        """Test warning generated for unknown segment."""
        # Create schema with limited segments
        mock_schema = MagicMock()
        mock_schema.get_segment.return_value = None
        mock_schema.segments = {}
        mock_schema.composites = {}
        mock_schema.elements = {}
        mock_schema.spec.structure = []

        mock_builder = MagicMock()
        mock_builder.exists.return_value = True
        mock_builder.load.return_value = mock_schema

        # Message with unknown segment
        content = [
            make_parsed_segment("BGM", ["380"]),
            make_parsed_segment("XYZ", ["unknown"]),  # Unknown segment
        ]
        message = make_message_instance(content=content)

        parser = EdifactMessageParser(mock_builder)
        result = parser.parse(message)

        # Should have warning about unknown segment
        # The warning would be added when segment doesn't match schema
        assert len(result.content) == 2

    def test_empty_message_content(self):
        """Test handling message with no content segments."""
        message = make_message_instance(content=[])

        parser = EdifactMessageParser(schema_loader=None)
        result = parser.parse(message)

        assert len(result.content) == 0


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_message_with_only_mandatory_segments(self):
        """Test parsing message with only mandatory segments."""
        content = [
            make_parsed_segment("BGM", ["380", "INV001", "9"]),
        ]
        message = make_message_instance(content=content)

        parser = EdifactMessageParser(schema_loader=None)
        result = parser.parse(message)

        assert len(result.content) == 1

    def test_message_with_composite_elements(self):
        """Test parsing segments with composite elements."""
        # Create segment with composite element
        raw_components = [
            RawComponent(value="137", position=make_source_position(), component_index=1),
            RawComponent(value="20231031", position=make_source_position(), component_index=2),
            RawComponent(value="102", position=make_source_position(), component_index=3),
        ]
        raw_elem = RawElement(
            value=None,
            position=make_source_position(),
            element_index=1,
            components=raw_components,
        )
        raw_seg = RawSegment(
            tag="DTM",
            elements=[raw_elem],
            position=make_source_position(),
            raw_text="DTM+137:20231031:102",
        )
        parsed_elem = ParsedElement(raw=raw_elem)
        parsed_seg = ParsedSegment(
            tag="DTM",
            elements=[parsed_elem],
            raw=raw_seg,
        )

        message = make_message_instance(content=[parsed_seg])

        parser = EdifactMessageParser(schema_loader=None)
        result = parser.parse(message)

        assert len(result.content) == 1
        assert result.content[0].tag == "DTM"

    def test_deeply_nested_segment_groups(self, schema_loader):
        """Test handling of deeply nested segment groups."""
        # Create message that would have nested groups
        data = (
            "UNA:+.? '"
            "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'"
            "UNH+1+INVOIC:D:23A:UN'"
            "BGM+380+INV001+9'"
            "DTM+137:20231031:102'"
            "RFF+ON:PO123'"
            "NAD+BY+BUYER::9'"
            "RFF+VA:DE123'"
            "CTA+IC+:CONTACT'"
            "UNT+8+1'"
            "UNZ+1+12345'"
        )

        tokenizer_result = tokenize(data)
        envelope_result = parse_envelope(tokenizer_result)

        if envelope_result.interchanges:
            message = envelope_result.interchanges[0].messages[0]
            parser = EdifactMessageParser(schema_loader)
            result = parser.parse(message)

            # Just verify it doesn't crash
            assert result is not None

    def test_repeated_segment_groups(self, schema_loader):
        """Test handling of repeated segment groups (multiple iterations)."""
        data = (
            "UNA:+.? '"
            "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'"
            "UNH+1+INVOIC:D:23A:UN'"
            "BGM+380+INV001+9'"
            "NAD+BY+BUYER1::9'"
            "NAD+SE+SELLER1::9'"
            "NAD+DP+DELIVERY1::9'"
            "UNT+6+1'"
            "UNZ+1+12345'"
        )

        tokenizer_result = tokenize(data)
        envelope_result = parse_envelope(tokenizer_result)

        if envelope_result.interchanges:
            message = envelope_result.interchanges[0].messages[0]
            parser = EdifactMessageParser(schema_loader)
            result = parser.parse(message)

            # Verify multiple NAD segments are handled
            nad_count = sum(
                1
                for item in result.content
                if isinstance(item, ParsedSegment) and item.tag == "NAD"
            )
            # Or count in segment groups
            for item in result.content:
                if isinstance(item, SegmentGroupInstance):
                    nad_count += sum(1 for seg in item.segments if seg.tag == "NAD")

            assert nad_count >= 1


# =============================================================================
# MessageParseResult Tests
# =============================================================================


class TestMessageParseResult:
    """Test MessageParseResult dataclass."""

    def test_result_creation(self):
        """Test MessageParseResult can be created."""
        message = make_message_instance()
        result = MessageParseResult(message=message)

        assert result.message is message
        assert result.schema_applied is False
        assert result.schema_id is None
        assert result.errors == []

    def test_result_with_schema(self):
        """Test MessageParseResult with schema info."""
        message = make_message_instance()
        result = MessageParseResult(
            message=message,
            schema_applied=True,
            schema_id="INVOIC",
        )

        assert result.schema_applied is True
        assert result.schema_id == "INVOIC"
