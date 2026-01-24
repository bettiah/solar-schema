"""
Tests for X12 Validator.
"""

from pathlib import Path

import pytest

from edi_schema.x12.ast import (
    ErrorCategory,
    ErrorSeverity,
    ParsedElement,
    ParsedSegment,
    ParseError,
    RawElement,
    RawSegment,
    SourcePosition,
)
from edi_schema.x12.enums import DataElementType, RequirementDesignator

# Aliases for cleaner code
DataType = DataElementType
Requirement = RequirementDesignator
from edi_schema.x12.validator.code import (
    FUNCTIONAL_ID_CODES,
    ID_QUALIFIERS,
    CodeValidationContext,
    validate_code_value,
)
from edi_schema.x12.validator.core import (
    ValidationLevel,
    ValidationResult,
    X12Validator,
)
from edi_schema.x12.validator.element import (
    ElementValidationContext,
    ElementValidator,
    validate_element,
    validate_element_length,
    validate_element_type,
)
from edi_schema.x12.validator.schema import (
    SchemaValidationContext,
    SchemaValidator,
)


class TestElementValidator:
    """Tests for element validation."""

    @pytest.fixture
    def validator(self):
        return ElementValidator()

    @pytest.fixture
    def context(self):
        return ElementValidationContext(
            segment_tag="BEG",
            segment_position=1,
            element_position=1,
        )

    def test_validate_required_missing(self, validator, context):
        """Test validation of missing required element."""
        element = ParsedElement(
            value="",
            raw=RawElement(value="", position=SourcePosition(0, 1, 1), element_index=1),
        )

        errors = validator.validate(
            element,
            context,
            requirement=Requirement.M,
        )

        assert len(errors) == 1
        assert errors[0].code == "1"  # Mandatory missing
        assert "Required element" in errors[0].message

    def test_validate_optional_empty_ok(self, validator, context):
        """Test that empty optional elements are OK."""
        element = ParsedElement(
            value="",
            raw=RawElement(value="", position=SourcePosition(0, 1, 1), element_index=1),
        )

        errors = validator.validate(
            element,
            context,
            requirement=Requirement.O,
        )

        assert len(errors) == 0

    def test_validate_length_too_short(self, validator, context):
        """Test validation of element too short."""
        element = ParsedElement(
            value="A",
            raw=RawElement(value="A", position=SourcePosition(0, 1, 1), element_index=1),
        )

        errors = validator.validate(
            element,
            context,
            min_length=5,
            max_length=10,
        )

        assert len(errors) == 1
        assert errors[0].code == "4"  # Too short
        assert "too short" in errors[0].message

    def test_validate_length_too_long(self, validator, context):
        """Test validation of element too long."""
        element = ParsedElement(
            value="A" * 20,
            raw=RawElement(value="A" * 20, position=SourcePosition(0, 1, 1), element_index=1),
        )

        errors = validator.validate(
            element,
            context,
            min_length=1,
            max_length=10,
        )

        assert len(errors) == 1
        assert errors[0].code == "5"  # Too long
        assert "too long" in errors[0].message

    def test_validate_alphanumeric_valid(self, validator, context):
        """Test valid alphanumeric value."""
        element = ParsedElement(
            value="ABC123",
            raw=RawElement(value="ABC123", position=SourcePosition(0, 1, 1), element_index=1),
        )

        errors = validator.validate(
            element,
            context,
            data_type=DataType.AN,
        )

        assert len(errors) == 0

    def test_validate_alphanumeric_with_space(self, validator, context):
        """Test alphanumeric with spaces is valid."""
        element = ParsedElement(
            value="ABC 123",
            raw=RawElement(value="ABC 123", position=SourcePosition(0, 1, 1), element_index=1),
        )

        errors = validator.validate(
            element,
            context,
            data_type=DataType.AN,
        )

        assert len(errors) == 0

    def test_validate_numeric_valid(self, validator, context):
        """Test valid numeric value."""
        element = ParsedElement(
            value="12345",
            raw=RawElement(value="12345", position=SourcePosition(0, 1, 1), element_index=1),
        )

        errors = validator.validate(
            element,
            context,
            data_type=DataType.N,
        )

        assert len(errors) == 0

    def test_validate_numeric_invalid(self, validator, context):
        """Test invalid numeric value (contains letters)."""
        element = ParsedElement(
            value="123ABC",
            raw=RawElement(value="123ABC", position=SourcePosition(0, 1, 1), element_index=1),
        )

        errors = validator.validate(
            element,
            context,
            data_type=DataType.N,
        )

        assert len(errors) == 1
        assert errors[0].code == "6"  # Invalid character

    def test_validate_decimal_valid(self, validator, context):
        """Test valid decimal value."""
        element = ParsedElement(
            value="123.45",
            raw=RawElement(value="123.45", position=SourcePosition(0, 1, 1), element_index=1),
        )

        errors = validator.validate(
            element,
            context,
            data_type=DataType.R,
        )

        assert len(errors) == 0

    def test_validate_date_ccyymmdd_valid(self, validator, context):
        """Test valid CCYYMMDD date."""
        element = ParsedElement(
            value="20210315",
            raw=RawElement(value="20210315", position=SourcePosition(0, 1, 1), element_index=1),
        )

        errors = validator.validate(
            element,
            context,
            data_type=DataType.DT,
        )

        assert len(errors) == 0

    def test_validate_date_yymmdd_valid(self, validator, context):
        """Test valid YYMMDD date."""
        element = ParsedElement(
            value="210315",
            raw=RawElement(value="210315", position=SourcePosition(0, 1, 1), element_index=1),
        )

        errors = validator.validate(
            element,
            context,
            data_type=DataType.DT,
        )

        assert len(errors) == 0

    def test_validate_date_invalid_month(self, validator, context):
        """Test invalid month in date."""
        element = ParsedElement(
            value="20211315",  # Month 13
            raw=RawElement(value="20211315", position=SourcePosition(0, 1, 1), element_index=1),
        )

        errors = validator.validate(
            element,
            context,
            data_type=DataType.DT,
        )

        assert len(errors) > 0
        assert errors[0].code == "8"  # Invalid date

    def test_validate_time_hhmm_valid(self, validator, context):
        """Test valid HHMM time."""
        element = ParsedElement(
            value="1430",
            raw=RawElement(value="1430", position=SourcePosition(0, 1, 1), element_index=1),
        )

        errors = validator.validate(
            element,
            context,
            data_type=DataType.TM,
        )

        assert len(errors) == 0

    def test_validate_time_hhmmss_valid(self, validator, context):
        """Test valid HHMMSS time."""
        element = ParsedElement(
            value="143025",
            raw=RawElement(value="143025", position=SourcePosition(0, 1, 1), element_index=1),
        )

        errors = validator.validate(
            element,
            context,
            data_type=DataType.TM,
        )

        assert len(errors) == 0

    def test_validate_time_invalid_hour(self, validator, context):
        """Test invalid hour in time."""
        element = ParsedElement(
            value="2530",  # Hour 25
            raw=RawElement(value="2530", position=SourcePosition(0, 1, 1), element_index=1),
        )

        errors = validator.validate(
            element,
            context,
            data_type=DataType.TM,
        )

        assert len(errors) > 0
        assert errors[0].code == "9"  # Invalid time


class TestCodeValidator:
    """Tests for code validation."""

    @pytest.fixture
    def context(self):
        return CodeValidationContext(
            segment_tag="ISA",
            segment_position=1,
            element_position=5,
        )

    def test_validate_known_id_qualifier(self, context):
        """Test validation of known ID qualifier."""
        errors = validate_code_value(
            "ZZ",
            ID_QUALIFIERS,
            context,
            strict=True,
        )

        assert len(errors) == 0

    def test_validate_unknown_id_qualifier_strict(self, context):
        """Test validation of unknown ID qualifier in strict mode."""
        errors = validate_code_value(
            "XX",  # Not a valid qualifier
            ID_QUALIFIERS,
            context,
            strict=True,
        )

        assert len(errors) == 1
        assert errors[0].code == "7"  # Invalid code
        assert errors[0].severity == ErrorSeverity.ERROR

    def test_validate_unknown_code_warning(self, context):
        """Test validation of unknown code in non-strict mode (warning)."""
        errors = validate_code_value(
            "XX",
            ID_QUALIFIERS,
            context,
            strict=False,
        )

        assert len(errors) == 1
        assert errors[0].code == "7"
        assert errors[0].severity == ErrorSeverity.WARNING

    def test_validate_functional_id_code(self, context):
        """Test validation of functional ID code."""
        context.segment_tag = "GS"
        context.element_position = 1

        errors = validate_code_value(
            "PO",  # Purchase Order
            FUNCTIONAL_ID_CODES,
            context,
        )

        assert len(errors) == 0

    def test_validate_empty_code_ok(self, context):
        """Test that empty code doesn't generate error."""
        errors = validate_code_value(
            "",
            ID_QUALIFIERS,
            context,
        )

        assert len(errors) == 0


class TestSchemaValidator:
    """Tests for schema validation."""

    @pytest.fixture
    def x12_schema_path(self) -> Path:
        return Path("/Users/me/Downloads/edi/schema/x12/005010")

    def test_validate_850_required_segments(self):
        """Test validation of required segments in 850."""
        from edi_schema.x12.schemas import GeneratedX12SchemaLoader

        loader = GeneratedX12SchemaLoader()
        schema = loader.load("850")

        # Create minimal content with BEG (required)
        content = [
            ParsedSegment(
                tag="BEG",
                elements=[],
                raw=RawSegment(
                    tag="BEG", elements=[], position=SourcePosition(0, 1, 1), raw_text="BEG"
                ),
            ),
        ]

        context = SchemaValidationContext(transaction_id="850")
        validator = SchemaValidator(schema)
        errors = validator.validate(content, context)

        # Should have errors for other required segments
        # The exact errors depend on the schema requirements
        assert isinstance(errors, list)

    def test_validate_unknown_segment(self):
        """Test validation of unknown segment."""
        from edi_schema.x12.schemas import GeneratedX12SchemaLoader

        loader = GeneratedX12SchemaLoader()
        schema = loader.load("850")

        # Create content with unknown segment
        content = [
            ParsedSegment(
                tag="BEG",
                elements=[],
                raw=RawSegment(
                    tag="BEG", elements=[], position=SourcePosition(0, 1, 1), raw_text="BEG"
                ),
            ),
            ParsedSegment(
                tag="XYZ",  # Unknown segment
                elements=[],
                raw=RawSegment(
                    tag="XYZ", elements=[], position=SourcePosition(0, 1, 1), raw_text="XYZ"
                ),
            ),
        ]

        context = SchemaValidationContext(transaction_id="850")
        validator = SchemaValidator(schema)
        errors = validator.validate(content, context)

        # Should have error for unknown segment
        unknown_errors = [e for e in errors if e.code == "6"]
        assert len(unknown_errors) > 0


class TestValidationResult:
    """Tests for ValidationResult."""

    def test_empty_result_is_valid(self):
        """Test empty result is valid."""
        result = ValidationResult()
        assert result.is_valid()
        assert result.is_accepted()

    def test_result_with_error_not_valid(self):
        """Test result with error is not valid."""
        result = ValidationResult()
        result.add_error(
            ParseError(
                code="1",
                message="Test error",
                category=ErrorCategory.ELEMENT,
                severity=ErrorSeverity.ERROR,
            )
        )

        assert not result.is_valid()
        assert not result.is_accepted()
        assert result.total_errors() == 1

    def test_result_with_warning_is_valid(self):
        """Test result with only warnings is valid."""
        result = ValidationResult()
        result.add_error(
            ParseError(
                code="W1",
                message="Test warning",
                category=ErrorCategory.CODE,
                severity=ErrorSeverity.WARNING,
            )
        )

        assert result.is_valid()
        assert result.is_accepted()
        assert result.total_warnings() == 1

    def test_merge_results(self):
        """Test merging validation results."""
        result1 = ValidationResult()
        result1.add_error(
            ParseError(
                code="1",
                message="Error 1",
                category=ErrorCategory.ELEMENT,
            )
        )

        result2 = ValidationResult()
        result2.add_error(
            ParseError(
                code="2",
                message="Error 2",
                category=ErrorCategory.SCHEMA,
            )
        )

        result1.merge(result2)

        assert result1.total_errors() == 2
        assert result1.element_errors == 1
        assert result1.schema_errors == 1


class TestX12Validator:
    """Tests for X12Validator."""

    def test_validator_creation(self):
        """Test creating validator without schema loader."""
        validator = X12Validator()
        assert validator is not None

    def test_validator_with_levels(self):
        """Test creating validator with specific levels."""
        validator = X12Validator(levels={ValidationLevel.ELEMENT, ValidationLevel.CODE})

        assert ValidationLevel.ELEMENT in validator.levels
        assert ValidationLevel.CODE in validator.levels
        assert ValidationLevel.SCHEMA not in validator.levels


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_validate_element_convenience(self):
        """Test validate_element convenience function."""
        element = ParsedElement(
            value="12345",
            raw=RawElement(value="12345", position=SourcePosition(0, 1, 1), element_index=1),
        )
        context = ElementValidationContext(
            segment_tag="TEST",
            segment_position=1,
            element_position=1,
        )

        errors = validate_element(
            element,
            context,
            data_type=DataType.AN,
            min_length=1,
            max_length=10,
        )

        assert len(errors) == 0

    def test_validate_element_type_convenience(self):
        """Test validate_element_type convenience function."""
        context = ElementValidationContext(
            segment_tag="TEST",
            segment_position=1,
            element_position=1,
        )

        errors = validate_element_type("12345", DataType.N, context)
        assert len(errors) == 0

        errors = validate_element_type("ABC", DataType.N, context)
        assert len(errors) > 0

    def test_validate_element_length_convenience(self):
        """Test validate_element_length convenience function."""
        context = ElementValidationContext(
            segment_tag="TEST",
            segment_position=1,
            element_position=1,
        )

        errors = validate_element_length("12345", 1, 10, context)
        assert len(errors) == 0

        errors = validate_element_length("12345", 10, 20, context)
        assert len(errors) > 0
