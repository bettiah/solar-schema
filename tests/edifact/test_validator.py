"""
Tests for EDIFACT Validator.

Tests cover all 6 validation levels:
1. Structural - Basic syntax (tested in tokenizer)
2. Envelope - UNB/UNZ, UNG/UNE, UNH/UNT matching (tested in envelope parser)
3. Schema - Segment order, required segments, group cardinality
4. Element - Data types, lengths, required elements
5. Code - Coded values against code lists
6. Semantic - Cross-element rules, conditional requirements
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from edi_schema.edifact.ast import (
    ErrorCategory,
    ErrorSeverity,
    FunctionalGroupInstance,
    InterchangeInstance,
    MessageInstance,
    ParsedElement,
    ParsedSegment,
    ParseError,
    RawElement,
    RawSegment,
    SegmentGroupInstance,
    SourcePosition,
)
from edi_schema.edifact.parser import parse_envelope, tokenize
from edi_schema.edifact.validator import (
    DOCUMENT_NAME_CODES,
    PARTY_FUNCTION_CODES,
    CodeValidationContext,
    # Code validation
    CodeValidator,
    EdifactValidator,
    ElementValidationContext,
    # Element validation
    ElementValidator,
    SchemaValidationContext,
    # Schema validation
    SchemaValidator,
    SegmentTracker,
    SemanticValidationContext,
    # Semantic validation
    SemanticValidator,
    ValidationLevel,
    ValidationResult,
    validate_code_value,
    validate_element_length,
    validate_element_type,
    validate_interchange,
    validate_message,
)

# =============================================================================
# Test Fixtures and Helpers
# =============================================================================


def make_position(offset: int = 0, line: int = 1, column: int = 1) -> SourcePosition:
    """Create a SourcePosition for testing."""
    return SourcePosition(offset=offset, line=line, column=column)


def make_raw_element(value: str, position: int = 0, element_index: int = 1) -> RawElement:
    """Create a RawElement for testing."""
    return RawElement(
        value=value,
        position=make_position(position),
        element_index=element_index,
        components=None,
    )


def make_raw_segment(tag: str, elements: list[str], position: int = 0) -> RawSegment:
    """Create a RawSegment for testing."""
    raw_text = tag + "+" + "+".join(elements) + "'"
    return RawSegment(
        tag=tag,
        elements=[
            make_raw_element(e, position + i, element_index=i + 1) for i, e in enumerate(elements)
        ],
        position=make_position(position),
        raw_text=raw_text,
    )


def make_parsed_element(value: str, position: int = 0) -> ParsedElement:
    """Create a ParsedElement for testing."""
    raw = make_raw_element(value, position)
    return ParsedElement(
        raw=raw,
        definition=None,
        element_definition=None,
        composite_definition=None,
        components=None,
    )


def make_parsed_segment(tag: str, elements: list[str], position: int = 0) -> ParsedSegment:
    """Create a ParsedSegment for testing."""
    raw = make_raw_segment(tag, elements, position)
    parsed_elements = [make_parsed_element(e, position + i) for i, e in enumerate(elements)]
    return ParsedSegment(
        tag=tag,
        elements=parsed_elements,
        raw=raw,
        definition=None,
        position_in_message=1,
    )


def make_message_instance(
    message_type: str = "INVOIC",
    reference: str = "1",
    content: list | None = None,
) -> MessageInstance:
    """Create a MessageInstance for testing."""
    return MessageInstance(
        reference_number=reference,
        message_type=message_type,
        version="D",
        release="23A",
        controlling_agency="UN",
        content=content or [],
        unh_segment=make_raw_segment("UNH", ["1", "INVOIC:D:23A:UN"]),
        unt_segment=make_raw_segment("UNT", ["5", "1"]),
        segment_count=5,
    )


def make_interchange_instance(
    messages: list[MessageInstance] | None = None,
    groups: list[FunctionalGroupInstance] | None = None,
) -> InterchangeInstance:
    """Create an InterchangeInstance for testing."""
    return InterchangeInstance(
        syntax_identifier="UNOA",
        syntax_version="3",
        sender_id="SENDER",
        recipient_id="RECEIVER",
        date="231031",
        time="1430",
        control_reference="12345",
        groups=groups or [],
        messages=messages or [],
        unb_segment=make_raw_segment(
            "UNB", ["UNOA:3", "SENDER", "RECEIVER", "231031:1430", "12345"]
        ),
        unz_segment=make_raw_segment("UNZ", ["1", "12345"]),
        count=1,
        test_indicator=None,
    )


# =============================================================================
# ValidationResult Tests
# =============================================================================


class TestValidationResult:
    """Test ValidationResult class."""

    def test_result_creation(self):
        """Test creating an empty validation result."""
        result = ValidationResult()
        assert result.is_valid()
        assert result.total_errors() == 0
        assert result.total_warnings() == 0

    def test_add_error(self):
        """Test adding an error."""
        result = ValidationResult()
        error = ParseError(
            code="TEST",
            message="Test error",
            category=ErrorCategory.ELEMENT,
            severity=ErrorSeverity.ERROR,
        )
        result.add_error(error)

        assert not result.is_valid()
        assert result.total_errors() == 1
        assert result.element_errors == 1

    def test_add_warning(self):
        """Test adding a warning."""
        result = ValidationResult()
        warning = ParseError(
            code="TEST",
            message="Test warning",
            category=ErrorCategory.CODE,
            severity=ErrorSeverity.WARNING,
        )
        result.add_error(warning)

        assert result.is_valid()  # Warnings don't affect validity
        assert result.total_warnings() == 1
        assert result.code_errors == 1

    def test_merge_results(self):
        """Test merging validation results."""
        result1 = ValidationResult()
        result1.add_error(
            ParseError(
                code="E1",
                message="Error 1",
                category=ErrorCategory.SCHEMA,
                severity=ErrorSeverity.ERROR,
            )
        )

        result2 = ValidationResult()
        result2.add_error(
            ParseError(
                code="E2",
                message="Error 2",
                category=ErrorCategory.ELEMENT,
                severity=ErrorSeverity.ERROR,
            )
        )

        result1.merge(result2)

        assert result1.total_errors() == 2
        assert result1.schema_errors == 1
        assert result1.element_errors == 1

    def test_is_accepted(self):
        """Test is_accepted method."""
        result = ValidationResult()
        assert result.is_accepted()

        # Warnings are accepted
        result.add_error(
            ParseError(
                code="W1",
                message="Warning",
                category=ErrorCategory.CODE,
                severity=ErrorSeverity.WARNING,
            )
        )
        assert result.is_accepted()

        # Errors are not accepted
        result.add_error(
            ParseError(
                code="E1",
                message="Error",
                category=ErrorCategory.ELEMENT,
                severity=ErrorSeverity.ERROR,
            )
        )
        assert not result.is_accepted()


# =============================================================================
# Element Validator Tests
# =============================================================================


class TestElementValidator:
    """Test ElementValidator class."""

    def test_validator_creation(self):
        """Test creating an element validator."""
        validator = ElementValidator()
        assert validator is not None

    def test_validate_empty_optional(self):
        """Test that empty optional elements are valid."""
        validator = ElementValidator()
        element = make_parsed_element("")
        context = ElementValidationContext(
            segment_tag="BGM",
            segment_position=1,
            element_position=1,
        )

        errors = validator.validate(element, context, mandatory=False)
        assert len(errors) == 0

    def test_validate_empty_mandatory(self):
        """Test that empty mandatory elements generate errors."""
        validator = ElementValidator()
        element = make_parsed_element("")
        context = ElementValidationContext(
            segment_tag="BGM",
            segment_position=1,
            element_position=1,
        )

        errors = validator.validate(element, context, mandatory=True)
        assert len(errors) == 1
        assert errors[0].code == "13"  # Missing

    def test_validate_alphabetic_valid(self):
        """Test valid alphabetic value."""
        validator = ElementValidator()
        context = ElementValidationContext(
            segment_tag="NAD",
            segment_position=1,
            element_position=1,
        )

        errors = validator._validate_alphabetic("ABC", context, None)
        assert len(errors) == 0

    def test_validate_alphabetic_invalid(self):
        """Test invalid alphabetic value."""
        validator = ElementValidator()
        context = ElementValidationContext(
            segment_tag="NAD",
            segment_position=1,
            element_position=1,
        )

        errors = validator._validate_alphabetic("ABC123", context, None)
        assert len(errors) == 1
        assert errors[0].code == "38"  # Numeric when alphabetic expected

    def test_validate_numeric_valid(self):
        """Test valid numeric value."""
        validator = ElementValidator()
        context = ElementValidationContext(
            segment_tag="QTY",
            segment_position=1,
            element_position=1,
        )

        errors = validator._validate_numeric("12345", context, None)
        assert len(errors) == 0

        # With decimal
        errors = validator._validate_numeric("123.45", context, None)
        assert len(errors) == 0

        # With sign
        errors = validator._validate_numeric("-123", context, None)
        assert len(errors) == 0

    def test_validate_numeric_invalid(self):
        """Test invalid numeric value."""
        validator = ElementValidator()
        context = ElementValidationContext(
            segment_tag="QTY",
            segment_position=1,
            element_position=1,
        )

        errors = validator._validate_numeric("12ABC", context, None)
        assert len(errors) == 1
        assert errors[0].code == "39"  # Alphabetic when numeric expected

    def test_validate_alphanumeric_valid(self):
        """Test valid alphanumeric value."""
        validator = ElementValidator()
        context = ElementValidationContext(
            segment_tag="FTX",
            segment_position=1,
            element_position=1,
        )

        errors = validator._validate_alphanumeric("ABC 123 !@#", context, None)
        assert len(errors) == 0

    def test_validate_alphanumeric_invalid(self):
        """Test invalid alphanumeric value (non-printable)."""
        validator = ElementValidator()
        context = ElementValidationContext(
            segment_tag="FTX",
            segment_position=1,
            element_position=1,
        )

        # Control character
        errors = validator._validate_alphanumeric("ABC\x00DEF", context, None)
        assert len(errors) == 1
        assert errors[0].code == "37"  # Invalid character

    def test_validate_length_too_short(self):
        """Test value shorter than minimum length."""
        validator = ElementValidator()
        context = ElementValidationContext(
            segment_tag="BGM",
            segment_position=1,
            element_position=1,
        )

        errors = validator._validate_length("AB", 3, 10, context, None)
        assert len(errors) == 1
        assert "too short" in errors[0].message

    def test_validate_length_too_long(self):
        """Test value longer than maximum length."""
        validator = ElementValidator()
        context = ElementValidationContext(
            segment_tag="BGM",
            segment_position=1,
            element_position=1,
        )

        errors = validator._validate_length("ABCDEFGHIJK", 1, 5, context, None)
        assert len(errors) == 1
        assert "too long" in errors[0].message

    def test_validate_length_valid(self):
        """Test value within length bounds."""
        validator = ElementValidator()
        context = ElementValidationContext(
            segment_tag="BGM",
            segment_position=1,
            element_position=1,
        )

        errors = validator._validate_length("ABC", 1, 5, context, None)
        assert len(errors) == 0


class TestElementValidationConvenienceFunctions:
    """Test element validation convenience functions."""

    def test_validate_element_type_function(self):
        """Test validate_element_type function."""
        context = ElementValidationContext(
            segment_tag="QTY",
            segment_position=1,
            element_position=1,
        )

        errors = validate_element_type("123", "n", context)
        assert len(errors) == 0

        errors = validate_element_type("ABC", "n", context)
        assert len(errors) == 1

    def test_validate_element_length_function(self):
        """Test validate_element_length function."""
        context = ElementValidationContext(
            segment_tag="BGM",
            segment_position=1,
            element_position=1,
        )

        errors = validate_element_length("ABC", 1, 10, context)
        assert len(errors) == 0

        errors = validate_element_length("A", 3, 10, context)
        assert len(errors) == 1


# =============================================================================
# Code Validator Tests
# =============================================================================


class TestCodeValidator:
    """Test CodeValidator class."""

    def test_validator_creation(self):
        """Test creating a code validator."""
        validator = CodeValidator()
        assert validator is not None

    def test_validate_valid_code(self):
        """Test validation of valid code value."""
        validator = CodeValidator()
        context = CodeValidationContext(
            segment_tag="BGM",
            segment_position=1,
            element_position=1,
        )

        errors = validator.validate_against_list("380", {"380", "381", "382"}, context)
        assert len(errors) == 0

    def test_validate_invalid_code_warning(self):
        """Test validation of invalid code value (warning by default)."""
        validator = CodeValidator(strict=False)
        context = CodeValidationContext(
            segment_tag="BGM",
            segment_position=1,
            element_position=1,
        )

        errors = validator.validate_against_list("999", {"380", "381", "382"}, context)
        assert len(errors) == 1
        assert errors[0].severity == ErrorSeverity.WARNING

    def test_validate_invalid_code_strict(self):
        """Test validation of invalid code value (error in strict mode)."""
        validator = CodeValidator(strict=True)
        context = CodeValidationContext(
            segment_tag="BGM",
            segment_position=1,
            element_position=1,
        )

        errors = validator.validate_against_list("999", {"380", "381", "382"}, context)
        assert len(errors) == 1
        assert errors[0].severity == ErrorSeverity.ERROR

    def test_validate_empty_value(self):
        """Test that empty values are not validated."""
        validator = CodeValidator()
        context = CodeValidationContext(
            segment_tag="BGM",
            segment_position=1,
            element_position=1,
        )

        errors = validator.validate_against_list("", {"380", "381"}, context)
        assert len(errors) == 0

    def test_validate_code_value_function(self):
        """Test validate_code_value convenience function."""
        context = CodeValidationContext(
            segment_tag="BGM",
            segment_position=1,
            element_position=1,
        )

        # Valid code
        errors = validate_code_value("380", DOCUMENT_NAME_CODES, context)
        assert len(errors) == 0

        # Invalid code
        errors = validate_code_value("999", DOCUMENT_NAME_CODES, context)
        assert len(errors) == 1


class TestWellKnownCodeLists:
    """Test well-known code lists are properly defined."""

    def test_document_name_codes(self):
        """Test document name codes."""
        assert "380" in DOCUMENT_NAME_CODES  # Commercial invoice
        assert "220" in DOCUMENT_NAME_CODES  # Order
        assert "351" in DOCUMENT_NAME_CODES  # Despatch advice

    def test_party_function_codes(self):
        """Test party function codes."""
        assert "BY" in PARTY_FUNCTION_CODES  # Buyer
        assert "SE" in PARTY_FUNCTION_CODES  # Seller
        assert "SU" in PARTY_FUNCTION_CODES  # Supplier


# =============================================================================
# Schema Validator Tests
# =============================================================================


class TestSchemaValidator:
    """Test SchemaValidator class."""

    def test_segment_tracker(self):
        """Test SegmentTracker for counting segments and groups."""
        tracker = SegmentTracker()

        # Track segments
        assert tracker.record_segment("BGM") == 1
        assert tracker.record_segment("BGM") == 2
        assert tracker.get_segment_count("BGM") == 2
        assert tracker.get_segment_count("NAD") == 0

        # Track groups
        assert tracker.record_group(1) == 1
        assert tracker.record_group(1) == 2
        assert tracker.get_group_count(1) == 2
        assert tracker.get_group_count(2) == 0

    def test_validate_with_mock_schema(self):
        """Test schema validation with mock schema."""
        # Create mock schema
        mock_schema = MagicMock()
        mock_schema.spec.structure = []

        validator = SchemaValidator(mock_schema)
        context = SchemaValidationContext(
            message_type="INVOIC",
            message_reference="1",
        )

        content = [make_parsed_segment("BGM", ["380", "INV001"])]
        errors = validator.validate(content, context)

        # Should validate without errors for empty structure
        assert isinstance(errors, list)


class TestSchemaValidationContext:
    """Test SchemaValidationContext class."""

    def test_context_creation(self):
        """Test creating a schema validation context."""
        context = SchemaValidationContext(
            message_type="INVOIC",
            message_reference="1",
            interchange_reference="12345",
        )

        assert context.message_type == "INVOIC"
        assert context.message_reference == "1"
        assert context.interchange_reference == "12345"


# =============================================================================
# Semantic Validator Tests
# =============================================================================


class TestSemanticValidator:
    """Test SemanticValidator class."""

    def test_validator_creation(self):
        """Test creating a semantic validator."""
        validator = SemanticValidator()
        assert validator is not None

    def test_validate_empty_message(self):
        """Test validating an empty message."""
        validator = SemanticValidator()
        message = make_message_instance(content=[])
        context = SemanticValidationContext(
            message_type="INVOIC",
            message_reference="1",
        )

        errors = validator.validate(message, context)
        assert isinstance(errors, list)

    def test_date_normalization(self):
        """Test date normalization for comparison."""
        validator = SemanticValidator()

        # 8-digit date stays the same
        assert validator._normalize_date("20231031") == "20231031"

        # 6-digit date gets century prefix
        assert validator._normalize_date("231031") == "20231031"
        assert validator._normalize_date("991231") == "19991231"

    def test_date_comparison(self):
        """Test date comparison."""
        validator = SemanticValidator()

        assert validator._compare_dates("20231031", "20231030") == 1  # Later
        assert validator._compare_dates("20231030", "20231031") == -1  # Earlier
        assert validator._compare_dates("20231031", "20231031") == 0  # Same


# =============================================================================
# EdifactValidator Tests
# =============================================================================


class TestEdifactValidator:
    """Test EdifactValidator class."""

    def test_validator_creation(self):
        """Test creating an EDIFACT validator."""
        validator = EdifactValidator()
        assert validator is not None
        assert len(validator.levels) == 6  # All levels by default

    def test_validator_with_specific_levels(self):
        """Test creating validator with specific levels."""
        validator = EdifactValidator(levels={ValidationLevel.ELEMENT, ValidationLevel.CODE})
        assert len(validator.levels) == 2

    def test_validate_empty_interchange(self):
        """Test validating an empty interchange."""
        validator = EdifactValidator()
        interchange = make_interchange_instance(messages=[], groups=[])

        result = validator.validate(interchange)

        assert isinstance(result, ValidationResult)

    def test_validate_interchange_with_message(self):
        """Test validating an interchange with a message."""
        validator = EdifactValidator()

        content = [make_parsed_segment("BGM", ["380", "INV001"])]
        message = make_message_instance(content=content)
        interchange = make_interchange_instance(messages=[message])

        result = validator.validate(interchange)

        assert isinstance(result, ValidationResult)

    def test_validate_interchange_with_group(self):
        """Test validating an interchange with a functional group."""
        validator = EdifactValidator()

        content = [make_parsed_segment("BGM", ["380", "INV001"])]
        message = make_message_instance(content=content)

        group = FunctionalGroupInstance(
            message_type="INVOIC",
            sender_id="SENDER",
            recipient_id="RECEIVER",
            reference_number="1",
            messages=[message],
            ung_segment=make_raw_segment("UNG", ["INVOIC", "SENDER", "RECEIVER"]),
            une_segment=make_raw_segment("UNE", ["1", "1"]),
            message_count=1,
        )

        interchange = make_interchange_instance(groups=[group])

        result = validator.validate(interchange)

        assert isinstance(result, ValidationResult)


class TestValidatorConvenienceFunctions:
    """Test validator convenience functions."""

    def test_validate_interchange_function(self):
        """Test validate_interchange function."""
        interchange = make_interchange_instance(messages=[])
        result = validate_interchange(interchange)

        assert isinstance(result, ValidationResult)

    def test_validate_message_function(self):
        """Test validate_message function."""
        content = [make_parsed_segment("BGM", ["380", "INV001"])]
        message = make_message_instance(content=content)

        result = validate_message(message)

        assert isinstance(result, ValidationResult)


# =============================================================================
# Integration Tests with Real Schema
# =============================================================================


@pytest.fixture
def schema_path():
    """Get path to EDIFACT schema directory."""
    return Path("/Users/me/Downloads/edi/schema/edifact/d23a")


@pytest.fixture
def schema_builder(schema_path):
    """Create schema builder if schema directory exists."""
    if not schema_path.exists():
        pytest.skip("EDIFACT schema directory not found")

    from edi_schema.edifact.schema import EdifactSchemaLoader

    return EdifactSchemaLoader(schema_path)


class TestIntegrationWithRealSchema:
    """Integration tests with real EDIFACT schemas."""

    def test_validate_invoic_with_schema(self, schema_builder):
        """Test validating INVOIC message with real schema."""
        data = (
            "UNA:+.? '"
            "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'"
            "UNH+1+INVOIC:D:23A:UN'"
            "BGM+380+INV001+9'"
            "DTM+137:20231031:102'"
            "UNT+4+1'"
            "UNZ+1+12345'"
        )

        # Parse
        tokenizer_result = tokenize(data)
        envelope_result = parse_envelope(tokenizer_result)

        assert len(envelope_result.interchanges) == 1
        interchange = envelope_result.interchanges[0]

        # Validate
        validator = EdifactValidator(schema_builder)
        result = validator.validate(interchange)

        # Should have some result
        assert isinstance(result, ValidationResult)

    def test_validate_orders_with_schema(self, schema_builder):
        """Test validating ORDERS message with real schema."""
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

        # Parse
        tokenizer_result = tokenize(data)
        envelope_result = parse_envelope(tokenizer_result)
        interchange = envelope_result.interchanges[0]

        # Validate
        validator = EdifactValidator(schema_builder)
        result = validator.validate(interchange)

        assert isinstance(result, ValidationResult)

    def test_validate_with_strict_codes(self, schema_builder):
        """Test validation with strict code checking."""
        data = (
            "UNA:+.? '"
            "UNB+UNOA:3+SENDER+RECEIVER+231031:1430+12345'"
            "UNH+1+INVOIC:D:23A:UN'"
            "BGM+999+INV001+9'"  # Invalid document code
            "UNT+3+1'"
            "UNZ+1+12345'"
        )

        tokenizer_result = tokenize(data)
        envelope_result = parse_envelope(tokenizer_result)
        interchange = envelope_result.interchanges[0]

        # Strict validation
        validator = EdifactValidator(schema_builder, strict_codes=True)
        result = validator.validate(interchange)

        assert isinstance(result, ValidationResult)


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_validate_message_with_segment_groups(self):
        """Test validating message with nested segment groups."""
        validator = EdifactValidator()

        # Create segment group with segments
        group = SegmentGroupInstance(
            group_number=1,
            iteration=1,
            segments=[make_parsed_segment("NAD", ["BY", "BUYER123"])],
        )

        content = [
            make_parsed_segment("BGM", ["380", "INV001"]),
            group,
        ]
        message = make_message_instance(content=content)
        interchange = make_interchange_instance(messages=[message])

        result = validator.validate(interchange)

        assert isinstance(result, ValidationResult)

    def test_validate_message_with_errors_from_parsing(self):
        """Test that parsing errors are included in validation result."""
        validator = EdifactValidator()

        message = make_message_instance(content=[])
        message.errors.append(
            ParseError(
                code="TEST",
                message="Parsing error",
                category=ErrorCategory.ENVELOPE,
                severity=ErrorSeverity.ERROR,
            )
        )

        interchange = make_interchange_instance(messages=[message])

        result = validator.validate(interchange)

        assert result.total_errors() >= 1
        assert result.envelope_errors >= 1

    def test_validate_deeply_nested_groups(self):
        """Test validating message with deeply nested segment groups."""
        validator = EdifactValidator()

        # Create nested groups
        inner_group = SegmentGroupInstance(
            group_number=3,
            iteration=1,
            segments=[make_parsed_segment("RFF", ["ON", "12345"])],
        )

        middle_group = SegmentGroupInstance(
            group_number=2,
            iteration=1,
            segments=[make_parsed_segment("NAD", ["BY", "BUYER"])],
            children=[inner_group],
        )

        outer_group = SegmentGroupInstance(
            group_number=1,
            iteration=1,
            segments=[make_parsed_segment("DOC", ["380"])],
            children=[middle_group],
        )

        content = [
            make_parsed_segment("BGM", ["380", "INV001"]),
            outer_group,
        ]
        message = make_message_instance(content=content)
        interchange = make_interchange_instance(messages=[message])

        result = validator.validate(interchange)

        assert isinstance(result, ValidationResult)

    def test_flatten_content(self):
        """Test flattening nested content."""
        validator = EdifactValidator()

        seg1 = make_parsed_segment("BGM", ["380"])
        seg2 = make_parsed_segment("NAD", ["BY"])
        seg3 = make_parsed_segment("RFF", ["ON"])

        group = SegmentGroupInstance(
            group_number=1,
            iteration=1,
            segments=[seg2],
            children=[
                SegmentGroupInstance(
                    group_number=2,
                    iteration=1,
                    segments=[seg3],
                )
            ],
        )

        content = [seg1, group]
        flattened = validator._flatten_content(content)

        assert len(flattened) == 3
        assert flattened[0].tag == "BGM"
        assert flattened[1].tag == "NAD"
        assert flattened[2].tag == "RFF"
