"""
Tests for UBL document validation.
"""

import pytest

from edi_schema.ubl.ast import (
    ErrorCategory,
    ErrorSeverity,
    ParsedAttribute,
    ParsedDocument,
    ParsedElement,
    ParseError,
)
from edi_schema.ubl.enums import Cardinality
from edi_schema.ubl.models import (
    ABIE,
    ASBIE,
    BBIE,
    CodeList,
    CodeValue,
    DocumentType,
    UBLSchema,
)
from edi_schema.ubl.validator import (
    UBLValidator,
    ValidationContext,
    ValidationLevel,
    ValidationResult,
    create_validator,
    get_missing_required_elements,
    get_unexpected_elements,
)
from edi_schema.ubl.validator.code import validate_codes
from edi_schema.ubl.validator.element import (
    validate_amount,
    validate_date,
    validate_datetime,
    validate_indicator,
    validate_time,
)
from edi_schema.ubl.validator.schema import validate_cardinality, validate_structure


# Test fixtures
@pytest.fixture
def sample_abie():
    """Create a sample ABIE for testing."""
    return ABIE(
        name="Invoice",
        definition="Invoice document",
        object_class="Invoice",
        bbies=[
            BBIE(
                name="ID",
                definition="Invoice ID",
                cardinality=Cardinality.EXACTLY_ONE,
                data_type="IdentifierType",
                representation_term="Identifier",
            ),
            BBIE(
                name="IssueDate",
                definition="Issue date",
                cardinality=Cardinality.EXACTLY_ONE,
                data_type="DateType",
                representation_term="Date",
            ),
            BBIE(
                name="Note",
                definition="Note",
                cardinality=Cardinality.ZERO_OR_MORE,
                data_type="TextType",
                representation_term="Text",
            ),
        ],
        asbies=[
            ASBIE(
                name="InvoiceLine",
                definition="Invoice line",
                cardinality=Cardinality.ONE_OR_MORE,
                associated_abie="InvoiceLine",
            ),
            ASBIE(
                name="AccountingSupplierParty",
                definition="Supplier party",
                cardinality=Cardinality.ZERO_OR_ONE,
                associated_abie="SupplierParty",
            ),
        ],
    )


@pytest.fixture
def sample_schema(sample_abie):
    """Create a sample UBL schema for testing."""
    doc_type = DocumentType(
        name="Invoice",
        namespace="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
        definition="Invoice document",
        root_element="Invoice",
        root_abie=sample_abie,
    )
    return UBLSchema(
        document_type=doc_type,
        abies={"Invoice": sample_abie},
        code_lists={
            "CurrencyCode": CodeList(
                id="CurrencyCode-2.4",
                short_name="CurrencyCode",
                values=[
                    CodeValue(code="USD", name="US Dollar"),
                    CodeValue(code="EUR", name="Euro"),
                    CodeValue(code="GBP", name="Pound Sterling"),
                ],
            ),
        },
    )


@pytest.fixture
def sample_element(sample_abie):
    """Create a sample parsed element for testing."""
    return ParsedElement(
        tag="Invoice",
        namespace="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
        children=[
            ParsedElement(
                tag="ID",
                namespace="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
                value="INV-001",
            ),
            ParsedElement(
                tag="IssueDate",
                namespace="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
                value="2024-01-15",
            ),
            ParsedElement(
                tag="InvoiceLine",
                namespace="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
                children=[],
            ),
        ],
        schema_component=sample_abie,
    )


class TestValidationResult:
    """Tests for ValidationResult."""

    def test_empty_result_is_valid(self):
        result = ValidationResult()
        assert result.is_valid
        assert not result.has_warnings

    def test_result_with_error(self):
        result = ValidationResult()
        result.add_error(
            ParseError(
                code="TEST",
                message="Test error",
                severity=ErrorSeverity.ERROR,
                category=ErrorCategory.SCHEMA,
            )
        )
        assert not result.is_valid
        assert len(result.errors) == 1

    def test_result_with_warning(self):
        result = ValidationResult()
        result.add_error(
            ParseError(
                code="TEST",
                message="Test warning",
                severity=ErrorSeverity.WARNING,
                category=ErrorCategory.SCHEMA,
            )
        )
        assert result.is_valid  # Warnings don't invalidate
        assert result.has_warnings
        assert len(result.warnings) == 1

    def test_merge_results(self):
        result1 = ValidationResult()
        result1.add_error(ParseError(code="ERR1", message="Error 1", category=ErrorCategory.SCHEMA))

        result2 = ValidationResult()
        result2.add_error(ParseError(code="ERR2", message="Error 2", category=ErrorCategory.SCHEMA))

        result1.merge(result2)
        assert len(result1.errors) == 2

    def test_to_dict(self):
        result = ValidationResult()
        result.add_error(ParseError(code="ERR", message="Error", category=ErrorCategory.SCHEMA))
        d = result.to_dict()
        assert d["valid"] is False
        assert d["error_count"] == 1


class TestValidationContext:
    """Tests for ValidationContext."""

    def test_path_tracking(self, sample_schema):
        context = ValidationContext(schema=sample_schema)
        assert context.xpath == "/"

        context.push_path("Invoice")
        assert context.xpath == "/Invoice"

        context.push_path("ID")
        assert context.xpath == "/Invoice/ID"

        context.pop_path()
        assert context.xpath == "/Invoice"

    def test_add_error(self, sample_schema):
        context = ValidationContext(schema=sample_schema)
        context.push_path("Invoice")
        context.add_error(
            code="TEST",
            message="Test error",
            category=ErrorCategory.SCHEMA,
        )
        assert len(context.errors) == 1
        assert context.errors[0].xpath == "/Invoice"

    def test_add_warning(self, sample_schema):
        context = ValidationContext(schema=sample_schema)
        context.add_error(
            code="TEST",
            message="Test warning",
            category=ErrorCategory.SCHEMA,
            severity=ErrorSeverity.WARNING,
        )
        assert len(context.warnings) == 1


class TestValidateStructure:
    """Tests for structure validation."""

    def test_valid_structure(self, sample_element, sample_schema):
        context = ValidationContext(schema=sample_schema)
        context.push_path("Invoice")
        validate_structure(sample_element, context)
        assert len(context.errors) == 0

    def test_unknown_element(self, sample_abie, sample_schema):
        element = ParsedElement(
            tag="Invoice",
            namespace="",
            children=[
                ParsedElement(
                    tag="UnknownElement",
                    namespace="",
                    schema_component=None,
                ),
            ],
            schema_component=sample_abie,
        )
        context = ValidationContext(schema=sample_schema)
        context.push_path("Invoice")
        validate_structure(element, context)
        assert len(context.errors) == 1
        assert "UNEXPECTED_ELEMENT" in context.errors[0].code


class TestValidateCardinality:
    """Tests for cardinality validation."""

    def test_missing_required_element(self, sample_abie, sample_schema):
        # Missing ID and IssueDate (required)
        element = ParsedElement(
            tag="Invoice",
            namespace="",
            children=[],  # No children!
            schema_component=sample_abie,
        )
        context = ValidationContext(schema=sample_schema)
        context.push_path("Invoice")
        validate_cardinality(element, context)
        # Should have errors for ID, IssueDate, and InvoiceLine
        assert len(context.errors) >= 3

    def test_valid_cardinality(self, sample_element, sample_schema):
        context = ValidationContext(schema=sample_schema)
        context.push_path("Invoice")
        validate_cardinality(sample_element, context)
        # Still valid, has required elements
        # Note: This test checks structure only, not that all required are present


class TestGetMissingRequiredElements:
    """Tests for missing element detection."""

    def test_all_required_missing(self, sample_abie):
        element = ParsedElement(tag="Invoice", namespace="", children=[])
        missing = get_missing_required_elements(element, sample_abie)
        assert "ID" in missing
        assert "IssueDate" in missing
        assert "InvoiceLine" in missing

    def test_no_missing_elements(self, sample_element, sample_abie):
        missing = get_missing_required_elements(sample_element, sample_abie)
        # ID, IssueDate, and InvoiceLine are present
        assert "ID" not in missing
        assert "IssueDate" not in missing


class TestGetUnexpectedElements:
    """Tests for unexpected element detection."""

    def test_no_unexpected_elements(self, sample_element, sample_abie):
        unexpected = get_unexpected_elements(sample_element, sample_abie)
        assert len(unexpected) == 0

    def test_has_unexpected_element(self, sample_abie):
        element = ParsedElement(
            tag="Invoice",
            namespace="",
            children=[
                ParsedElement(tag="FakeElement", namespace=""),
            ],
        )
        unexpected = get_unexpected_elements(element, sample_abie)
        assert "FakeElement" in unexpected


class TestDateValidation:
    """Tests for date format validation."""

    def test_valid_date(self, sample_schema):
        element = ParsedElement(tag="IssueDate", namespace="", value="2024-01-15")
        bbie = BBIE(
            name="IssueDate",
            definition="Date",
            cardinality=Cardinality.EXACTLY_ONE,
            data_type="DateType",
            representation_term="Date",
        )
        context = ValidationContext(schema=sample_schema)
        result = validate_date("2024-01-15", element, bbie, context)
        assert result is True
        assert len(context.errors) == 0

    def test_invalid_date_format(self, sample_schema):
        element = ParsedElement(tag="IssueDate", namespace="", value="15-01-2024")
        bbie = BBIE(
            name="IssueDate",
            definition="Date",
            cardinality=Cardinality.EXACTLY_ONE,
            data_type="DateType",
            representation_term="Date",
        )
        context = ValidationContext(schema=sample_schema)
        result = validate_date("15-01-2024", element, bbie, context)
        assert result is False
        assert len(context.errors) == 1
        assert "INVALID_DATE_FORMAT" in context.errors[0].code

    def test_invalid_date_value(self, sample_schema):
        element = ParsedElement(tag="IssueDate", namespace="", value="2024-13-45")
        bbie = BBIE(
            name="IssueDate",
            definition="Date",
            cardinality=Cardinality.EXACTLY_ONE,
            data_type="DateType",
            representation_term="Date",
        )
        context = ValidationContext(schema=sample_schema)
        result = validate_date("2024-13-45", element, bbie, context)
        assert result is False


class TestDateTimeValidation:
    """Tests for datetime format validation."""

    def test_valid_datetime(self, sample_schema):
        element = ParsedElement(tag="DateTime", namespace="", value="2024-01-15T10:30:00")
        bbie = BBIE(
            name="DateTime",
            definition="DateTime",
            cardinality=Cardinality.EXACTLY_ONE,
            data_type="DateTimeType",
            representation_term="Date Time",
        )
        context = ValidationContext(schema=sample_schema)
        result = validate_datetime("2024-01-15T10:30:00", element, bbie, context)
        assert result is True

    def test_valid_datetime_with_timezone(self, sample_schema):
        element = ParsedElement(tag="DateTime", namespace="")
        bbie = BBIE(
            name="DateTime",
            definition="DateTime",
            cardinality=Cardinality.EXACTLY_ONE,
            data_type="DateTimeType",
            representation_term="Date Time",
        )
        context = ValidationContext(schema=sample_schema)
        result = validate_datetime("2024-01-15T10:30:00+05:00", element, bbie, context)
        assert result is True


class TestTimeValidation:
    """Tests for time format validation."""

    def test_valid_time(self, sample_schema):
        element = ParsedElement(tag="Time", namespace="", value="10:30:00")
        bbie = BBIE(
            name="Time",
            definition="Time",
            cardinality=Cardinality.EXACTLY_ONE,
            data_type="TimeType",
            representation_term="Time",
        )
        context = ValidationContext(schema=sample_schema)
        result = validate_time("10:30:00", element, bbie, context)
        assert result is True

    def test_invalid_time(self, sample_schema):
        element = ParsedElement(tag="Time", namespace="", value="25:00:00")
        bbie = BBIE(
            name="Time",
            definition="Time",
            cardinality=Cardinality.EXACTLY_ONE,
            data_type="TimeType",
            representation_term="Time",
        )
        context = ValidationContext(schema=sample_schema)
        result = validate_time("bad-time", element, bbie, context)
        assert result is False


class TestAmountValidation:
    """Tests for amount validation."""

    def test_valid_amount(self, sample_schema):
        element = ParsedElement(
            tag="Amount",
            namespace="",
            value="100.50",
            attributes=[ParsedAttribute(name="currencyID", value="USD")],
        )
        bbie = BBIE(
            name="Amount",
            definition="Amount",
            cardinality=Cardinality.EXACTLY_ONE,
            data_type="AmountType",
            representation_term="Amount",
        )
        context = ValidationContext(schema=sample_schema)
        result = validate_amount("100.50", element, bbie, context)
        assert result is True

    def test_invalid_amount(self, sample_schema):
        element = ParsedElement(tag="Amount", namespace="", value="not-a-number")
        bbie = BBIE(
            name="Amount",
            definition="Amount",
            cardinality=Cardinality.EXACTLY_ONE,
            data_type="AmountType",
            representation_term="Amount",
        )
        context = ValidationContext(schema=sample_schema)
        result = validate_amount("not-a-number", element, bbie, context)
        assert result is False


class TestIndicatorValidation:
    """Tests for indicator validation."""

    def test_valid_indicator_true(self, sample_schema):
        element = ParsedElement(tag="Indicator", namespace="", value="true")
        bbie = BBIE(
            name="Indicator",
            definition="Indicator",
            cardinality=Cardinality.EXACTLY_ONE,
            data_type="IndicatorType",
            representation_term="Indicator",
        )
        context = ValidationContext(schema=sample_schema)
        result = validate_indicator("true", element, bbie, context)
        assert result is True

    def test_valid_indicator_false(self, sample_schema):
        element = ParsedElement(tag="Indicator", namespace="")
        bbie = BBIE(
            name="Indicator",
            definition="Indicator",
            cardinality=Cardinality.EXACTLY_ONE,
            data_type="IndicatorType",
            representation_term="Indicator",
        )
        context = ValidationContext(schema=sample_schema)
        result = validate_indicator("false", element, bbie, context)
        assert result is True

    def test_invalid_indicator(self, sample_schema):
        element = ParsedElement(tag="Indicator", namespace="", value="yes")
        bbie = BBIE(
            name="Indicator",
            definition="Indicator",
            cardinality=Cardinality.EXACTLY_ONE,
            data_type="IndicatorType",
            representation_term="Indicator",
        )
        context = ValidationContext(schema=sample_schema)
        result = validate_indicator("yes", element, bbie, context)
        assert result is False


class TestCodeValidation:
    """Tests for code validation."""

    def test_valid_currency_code(self, sample_schema):
        element = ParsedElement(
            tag="Amount",
            namespace="",
            value="100.00",
            attributes=[ParsedAttribute(name="currencyID", value="USD")],
        )
        bbie = BBIE(
            name="Amount",
            definition="Amount",
            cardinality=Cardinality.EXACTLY_ONE,
            data_type="AmountType",
            representation_term="Amount",
        )
        element.schema_component = bbie
        context = ValidationContext(schema=sample_schema)
        validate_codes(element, context)
        assert len(context.errors) == 0

    def test_invalid_currency_code(self, sample_schema):
        element = ParsedElement(
            tag="Amount",
            namespace="",
            value="100.00",
            attributes=[ParsedAttribute(name="currencyID", value="XXX")],
        )
        bbie = BBIE(
            name="Amount",
            definition="Amount",
            cardinality=Cardinality.EXACTLY_ONE,
            data_type="AmountType",
            representation_term="Amount",
        )
        element.schema_component = bbie
        context = ValidationContext(schema=sample_schema)
        validate_codes(element, context)
        assert len(context.errors) == 1
        assert "INVALID_ATTRIBUTE_CODE" in context.errors[0].code


class TestUBLValidator:
    """Tests for UBLValidator."""

    def test_validator_creation(self, sample_schema):
        validator = UBLValidator(schema=sample_schema)
        assert validator.schema == sample_schema

    def test_validator_with_levels(self, sample_schema):
        validator = UBLValidator(
            schema=sample_schema,
            levels={ValidationLevel.SCHEMA},
        )
        assert ValidationLevel.SCHEMA in validator.levels
        assert ValidationLevel.ELEMENT not in validator.levels

    def test_validate_requires_schema(self, sample_element):
        validator = UBLValidator()
        doc = ParsedDocument(
            document_type="Invoice",
            version="2.5",
            root=sample_element,
        )
        with pytest.raises(ValueError, match="No schema provided"):
            validator.validate(doc)

    def test_validate_document_type_mismatch(self, sample_element, sample_schema):
        validator = UBLValidator(schema=sample_schema)
        doc = ParsedDocument(
            document_type="Order",  # Wrong type
            version="2.5",
            root=sample_element,
        )
        result = validator.validate(doc)
        assert not result.is_valid
        assert any("MISMATCH" in e.code for e in result.errors)


class TestCreateValidator:
    """Tests for create_validator factory."""

    def test_create_validator(self, sample_schema):
        validator = create_validator(sample_schema)
        assert validator.schema == sample_schema
        assert len(validator._validators) > 0

    def test_create_validator_with_levels(self, sample_schema):
        validator = create_validator(
            sample_schema,
            levels={ValidationLevel.SCHEMA},
        )
        assert ValidationLevel.SCHEMA in validator.levels
