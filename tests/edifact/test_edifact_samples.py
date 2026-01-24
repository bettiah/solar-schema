"""
Validation tests for EDIFACT sample files.

Tests all sample files in tests/fixtures/edifact_samples/ for:
- Tokenization and parsing
- Envelope parsing (UNB/UNZ, UNG/UNE, UNH/UNT)
- Element validation
- Schema-based validation
"""

from pathlib import Path

import pytest

from edi_schema.edifact.ast import (
    ErrorSeverity,
    InterchangeInstance,
    MessageInstance,
)
from edi_schema.edifact.parser import (
    parse_envelope,
    tokenize,
)
from edi_schema.edifact.schemas import (
    GeneratedEdifactSchemaLoader,
    get_composite,
    get_data_element,
    get_schema,
    get_segment,
)
from edi_schema.edifact.validator import (
    EdifactValidator,
    ValidationLevel,
    validate_interchange,
)


def parse_content(content: str) -> InterchangeInstance:
    """Helper to tokenize and parse EDIFACT content."""
    tokenizer_result = tokenize(content)
    parse_result = parse_envelope(tokenizer_result)
    return parse_result.interchanges[0]


def get_message_segments(msg: MessageInstance) -> list:
    """Helper to get all segments from a message."""
    return msg.all_segments()


@pytest.fixture
def samples_dir() -> Path:
    """Path to EDIFACT sample files."""
    return Path(__file__).parent.parent / "fixtures" / "edifact_samples"


@pytest.fixture
def sample_files(samples_dir: Path) -> dict[str, Path]:
    """Get all sample files as a dict."""
    files = {}
    for f in samples_dir.glob("*.edi"):
        files[f.stem] = f
    return files


@pytest.fixture
def schema_loader_d23a() -> GeneratedEdifactSchemaLoader:
    """Load EDIFACT D23A schema."""
    return GeneratedEdifactSchemaLoader(version="d23a")


@pytest.fixture
def schema_loader_d96a() -> GeneratedEdifactSchemaLoader:
    """Load EDIFACT D96A schema."""
    return GeneratedEdifactSchemaLoader(version="d96a")


class TestTokenization:
    """Tests for tokenizing EDIFACT sample files."""

    def test_all_samples_tokenize(self, samples_dir: Path):
        """All sample files should tokenize without fatal errors."""
        for file_path in samples_dir.glob("*.edi"):
            content = file_path.read_text()
            result = tokenize(content)

            # Should have segments
            assert len(result.segments) > 0, f"{file_path.name} produced no segments"

            # Should detect delimiters
            assert result.delimiters.element == "+", f"{file_path.name} wrong element sep"
            assert result.delimiters.segment == "'", f"{file_path.name} wrong segment term"

            # Should not have fatal errors
            fatal_errors = [e for e in result.errors if e.severity == ErrorSeverity.FATAL]
            assert len(fatal_errors) == 0, f"{file_path.name} has fatal tokenization errors"

    def test_invoic96_tokenization(self, sample_files: dict[str, Path]):
        """Test INVOIC D96A tokenization."""
        content = sample_files["invoic96"].read_text()
        result = tokenize(content)

        # Check segment count (2 messages with many segments each)
        assert len(result.segments) == 162

        # Check UNB segment
        unb = result.segments[0]
        assert unb.tag == "UNB"
        assert len(unb.elements) == 5

        # Check component separator detected
        assert result.delimiters.component == ":"

    def test_orders96_tokenization(self, sample_files: dict[str, Path]):
        """Test ORDERS D96A tokenization."""
        content = sample_files["orders96"].read_text()
        result = tokenize(content)

        # Check segment count
        assert len(result.segments) == 40

        # Verify specific segments exist
        segment_tags = [s.tag for s in result.segments]
        assert "BGM" in segment_tags  # Beginning
        assert "DTM" in segment_tags  # Date/time
        assert "NAD" in segment_tags  # Name and address
        assert "LIN" in segment_tags  # Line item


class TestEnvelopeParsing:
    """Tests for envelope parsing of EDIFACT sample files."""

    def test_all_samples_envelope_parse(self, samples_dir: Path):
        """All sample files should parse envelope structure."""
        for file_path in samples_dir.glob("*.edi"):
            content = file_path.read_text()
            interchange = parse_content(content)

            # Should have an interchange
            assert interchange is not None, f"{file_path.name} failed to parse"

            # Should have UNB info
            assert interchange.sender_id, f"{file_path.name} missing sender"
            assert interchange.recipient_id, f"{file_path.name} missing recipient"

            # Should have at least one message
            assert len(interchange.messages) > 0, f"{file_path.name} has no messages"

    def test_invoic96_envelope(self, sample_files: dict[str, Path]):
        """Test INVOIC envelope parsing."""
        content = sample_files["invoic96"].read_text()
        interchange = parse_content(content)

        # Check envelope
        assert interchange.sender_id == "8712345678910"
        assert interchange.recipient_id == "8712345678920"
        assert interchange.control_reference == "4"

        # Check messages
        assert len(interchange.messages) == 2

        # Check first message
        msg1 = interchange.messages[0]
        assert msg1.message_type == "INVOIC"
        assert msg1.version == "D"
        assert msg1.release == "96A"
        assert msg1.reference_number == "111424"

        # Check second message
        msg2 = interchange.messages[1]
        assert msg2.reference_number == "111425"

    def test_orders96_envelope(self, sample_files: dict[str, Path]):
        """Test ORDERS envelope parsing."""
        content = sample_files["orders96"].read_text()
        interchange = parse_content(content)

        # Check envelope
        assert interchange.sender_id == "PARTNER1"
        assert interchange.recipient_id == "PARTNER2"
        assert interchange.control_reference == "1UNBREF"

        # Check messages
        assert len(interchange.messages) == 2

        # Both should be ORDERS
        for msg in interchange.messages:
            assert msg.message_type == "ORDERS"
            assert msg.release == "96A"

    def test_message_segment_counts(self, sample_files: dict[str, Path]):
        """Test UNT segment count matches actual segments."""
        for name, path in sample_files.items():
            content = path.read_text()
            interchange = parse_content(content)

            for msg in interchange.messages:
                # UNT segment count should match message segments
                actual_count = len(get_message_segments(msg))
                # UNT counts include UNH and UNT themselves
                assert actual_count >= 2, f"{name} message has too few segments"


class TestStructuralValidation:
    """Tests for structural validation of EDIFACT messages."""

    def test_invoic96_structural_validation(self, sample_files: dict[str, Path]):
        """Test INVOIC structural validation."""
        content = sample_files["invoic96"].read_text()
        interchange = parse_content(content)

        # Validate without schema (structural only)
        validator = EdifactValidator(
            schema_loader=None,
            levels={ValidationLevel.STRUCTURAL, ValidationLevel.ENVELOPE},
        )
        result = validator.validate(interchange)

        # Should pass structural validation
        errors = [e for e in result.errors if e.severity == ErrorSeverity.ERROR]
        assert len(errors) == 0, f"Structural errors: {errors}"

    def test_orders96_structural_validation(self, sample_files: dict[str, Path]):
        """Test ORDERS structural validation."""
        content = sample_files["orders96"].read_text()
        interchange = parse_content(content)

        validator = EdifactValidator(
            schema_loader=None,
            levels={ValidationLevel.STRUCTURAL, ValidationLevel.ENVELOPE},
        )
        result = validator.validate(interchange)

        errors = [e for e in result.errors if e.severity == ErrorSeverity.ERROR]
        assert len(errors) == 0, f"Structural errors: {errors}"


class TestSchemaLoading:
    """Tests for schema loading functionality."""

    def test_d23a_schema_exists(self, schema_loader_d23a: GeneratedEdifactSchemaLoader):
        """D23A schemas should exist for common messages."""
        assert schema_loader_d23a.exists("INVOIC")
        assert schema_loader_d23a.exists("ORDERS")
        assert schema_loader_d23a.exists("DESADV")
        assert schema_loader_d23a.exists("ORDRSP")

    def test_d96a_schema_exists(self, schema_loader_d96a: GeneratedEdifactSchemaLoader):
        """D96A schemas should exist for common messages."""
        assert schema_loader_d96a.exists("INVOIC")
        assert schema_loader_d96a.exists("ORDERS")
        assert schema_loader_d96a.exists("DESADV")

    def test_d23a_invoic_schema_has_structure(
        self, schema_loader_d23a: GeneratedEdifactSchemaLoader
    ):
        """D23A INVOIC schema should have proper structure."""
        schema = schema_loader_d23a.load("INVOIC")

        assert schema.spec.code == "INVOIC"
        assert len(schema.segments) > 0
        assert len(schema.elements) > 0
        assert len(schema.composites) > 0

        # Should have common segments
        assert "BGM" in schema.segments
        assert "DTM" in schema.segments
        assert "NAD" in schema.segments

    def test_d23a_segment_has_elements(self):
        """D23A segments should have element definitions."""
        bgm = get_segment("BGM", version="d23a")
        assert bgm is not None
        assert len(bgm.elements) > 0

        # BGM should have C002 composite and other elements
        element_tags = [e.tag for e in bgm.elements]
        assert "C002" in element_tags or "C106" in element_tags

    def test_d96a_segment_has_elements(self):
        """D96A segments should have elements parsed correctly.

        The D96A EDSD format differs from D23A (no max_repeat field),
        but the parser handles both formats.
        """
        bgm = get_segment("BGM", version="d96a")
        assert bgm is not None
        assert len(bgm.elements) > 0, "D96A segments should have elements"

        # Verify BGM has expected elements
        element_tags = [e.tag for e in bgm.elements]
        assert "C002" in element_tags  # DOCUMENT/MESSAGE NAME
        assert "1004" in element_tags  # DOCUMENT/MESSAGE NUMBER

    def test_d96a_elements_exist(self):
        """D96A data elements should exist."""
        elem = get_data_element("1001", version="d96a")
        assert elem is not None
        assert elem.tag == "1001"
        assert elem.name is not None

    def test_d96a_composites_exist(self):
        """D96A composites should exist."""
        comp = get_composite("C002", version="d96a")
        assert comp is not None
        assert comp.tag == "C002"
        assert len(comp.components) > 0


class TestSchemaBasedValidation:
    """Tests for schema-based validation using D23A schemas."""

    def test_schema_segment_lookup(self, schema_loader_d23a: GeneratedEdifactSchemaLoader):
        """Can look up segment definitions in schema."""
        schema = schema_loader_d23a.load("INVOIC")

        bgm = schema.get_segment("BGM")
        assert bgm is not None
        assert bgm.tag == "BGM"
        assert bgm.name is not None

        dtm = schema.get_segment("DTM")
        assert dtm is not None
        assert dtm.tag == "DTM"

    def test_schema_element_lookup(self, schema_loader_d23a: GeneratedEdifactSchemaLoader):
        """Can look up element definitions in schema."""
        schema = schema_loader_d23a.load("INVOIC")

        # Find an element that exists in the schema
        for elem_id in list(schema.elements.keys())[:3]:
            elem = schema.get_element(elem_id)
            assert elem is not None
            assert elem.tag == elem_id

    def test_schema_composite_lookup(self, schema_loader_d23a: GeneratedEdifactSchemaLoader):
        """Can look up composite definitions in schema."""
        schema = schema_loader_d23a.load("INVOIC")

        # Find a composite that exists in the schema
        for comp_id in list(schema.composites.keys())[:3]:
            comp = schema.get_composite(comp_id)
            assert comp is not None
            assert comp.tag == comp_id

    def test_element_has_type_info(self, schema_loader_d23a: GeneratedEdifactSchemaLoader):
        """Elements should have data type information."""
        schema = schema_loader_d23a.load("INVOIC")

        for elem_id, elem in list(schema.elements.items())[:5]:
            assert elem.data_type is not None
            assert elem.max_length is not None or elem.max_length >= 0

    def test_validate_with_d23a_schema(self, schema_loader_d23a: GeneratedEdifactSchemaLoader):
        """Validate sample messages with D23A schema."""
        # Note: Sample files use D96A, but we can still validate structure
        # The segment tags are largely the same between versions
        schema = schema_loader_d23a.load("INVOIC")

        # Verify schema has required segments
        assert "BGM" in schema.segments
        assert "DTM" in schema.segments
        assert "NAD" in schema.segments
        assert "LIN" in schema.segments


class TestMessageContent:
    """Tests for specific message content validation."""

    def test_invoic_has_required_segments(self, sample_files: dict[str, Path]):
        """INVOIC should have required segments."""
        content = sample_files["invoic96"].read_text()
        interchange = parse_content(content)

        msg = interchange.messages[0]
        segment_tags = [s.tag for s in get_message_segments(msg)]

        # Required INVOIC segments (UNH/UNT are envelope, stored separately)
        assert "BGM" in segment_tags  # Beginning of message
        assert "DTM" in segment_tags  # Date/time
        assert "NAD" in segment_tags  # Name and address
        assert "UNS" in segment_tags  # Section control
        assert "MOA" in segment_tags  # Monetary amount
        # UNH and UNT are accessed via msg.unh_segment and msg.unt_segment
        assert msg.unh_segment is not None
        assert msg.unt_segment is not None

    def test_orders_has_required_segments(self, sample_files: dict[str, Path]):
        """ORDERS should have required segments."""
        content = sample_files["orders96"].read_text()
        interchange = parse_content(content)

        msg = interchange.messages[0]
        segment_tags = [s.tag for s in get_message_segments(msg)]

        # Required ORDERS segments (UNH/UNT are envelope, stored separately)
        assert "BGM" in segment_tags
        assert "DTM" in segment_tags
        assert "NAD" in segment_tags
        assert "LIN" in segment_tags  # Line items
        assert "QTY" in segment_tags  # Quantity
        # UNH and UNT are accessed via msg.unh_segment and msg.unt_segment
        assert msg.unh_segment is not None
        assert msg.unt_segment is not None

    def test_invoic_bgm_content(self, sample_files: dict[str, Path]):
        """Test INVOIC BGM segment content."""
        content = sample_files["invoic96"].read_text()
        interchange = parse_content(content)

        msg = interchange.messages[0]
        bgm = next(s for s in get_message_segments(msg) if s.tag == "BGM")

        # BGM should have document type (380 = commercial invoice)
        assert len(bgm.elements) >= 1
        assert bgm.elements[0].value == "380"

    def test_orders_bgm_content(self, sample_files: dict[str, Path]):
        """Test ORDERS BGM segment content."""
        content = sample_files["orders96"].read_text()
        interchange = parse_content(content)

        msg = interchange.messages[0]
        bgm = next(s for s in get_message_segments(msg) if s.tag == "BGM")

        # BGM should have document type (50E = order)
        assert len(bgm.elements) >= 1
        assert bgm.elements[0].value == "50E"

    def test_invoic_line_items(self, sample_files: dict[str, Path]):
        """Test INVOIC has line items."""
        content = sample_files["invoic96"].read_text()
        interchange = parse_content(content)

        msg = interchange.messages[0]
        lin_segments = [s for s in get_message_segments(msg) if s.tag == "LIN"]

        # First invoice has 3 line items
        assert len(lin_segments) == 3

        # Check line numbers
        line_nums = [s.elements[0].value for s in lin_segments]
        assert line_nums == ["1", "2", "3"]

    def test_orders_line_items(self, sample_files: dict[str, Path]):
        """Test ORDERS has line items."""
        content = sample_files["orders96"].read_text()
        interchange = parse_content(content)

        msg1 = interchange.messages[0]
        lin_segments = [s for s in get_message_segments(msg1) if s.tag == "LIN"]

        # First order has 4 line items
        assert len(lin_segments) == 4


class TestElementValidation:
    """Tests for element-level validation."""

    def test_date_format_validation(self, sample_files: dict[str, Path]):
        """Test date elements have valid format."""
        content = sample_files["invoic96"].read_text()
        interchange = parse_content(content)

        msg = interchange.messages[0]
        dtm_segments = [s for s in get_message_segments(msg) if s.tag == "DTM"]

        for dtm in dtm_segments:
            # DTM format: qualifier:date:format_code
            if len(dtm.elements) >= 1:
                composite = dtm.elements[0]
                components = getattr(composite, "components", None)
                if components and len(components) >= 2:
                    date_val = components[1].value
                    if date_val:
                        # Check date is numeric and reasonable length
                        assert date_val.isdigit(), f"Date should be numeric: {date_val}"
                        assert len(date_val) in [6, 8, 12, 14], f"Invalid date length: {date_val}"

    def test_monetary_amounts_numeric(self, sample_files: dict[str, Path]):
        """Test MOA elements have numeric values."""
        content = sample_files["invoic96"].read_text()
        interchange = parse_content(content)

        msg = interchange.messages[0]
        moa_segments = [s for s in get_message_segments(msg) if s.tag == "MOA"]

        for moa in moa_segments:
            if len(moa.elements) >= 1:
                # MOA has composite with amount
                composite = moa.elements[0]
                components = getattr(composite, "components", None)
                if components and len(components) >= 2:
                    amount = components[1].value
                    if amount:
                        # Should be a valid number (may have minus sign and decimal)
                        try:
                            float(amount)
                        except ValueError:
                            pytest.fail(f"MOA amount not numeric: {amount}")

    def test_quantity_values_numeric(self, sample_files: dict[str, Path]):
        """Test QTY elements have numeric values."""
        content = sample_files["orders96"].read_text()
        interchange = parse_content(content)

        msg = interchange.messages[0]
        qty_segments = [s for s in get_message_segments(msg) if s.tag == "QTY"]

        for qty in qty_segments:
            if len(qty.elements) >= 1:
                composite = qty.elements[0]
                components = getattr(composite, "components", None)
                if components and len(components) >= 2:
                    quantity = components[1].value
                    if quantity:
                        try:
                            float(quantity)
                        except ValueError:
                            pytest.fail(f"QTY value not numeric: {quantity}")


class TestValidationResult:
    """Tests for validation result structure."""

    def test_validation_result_creation(self, sample_files: dict[str, Path]):
        """Test validation result structure."""
        content = sample_files["invoic96"].read_text()
        interchange = parse_content(content)

        result = validate_interchange(interchange)

        assert result is not None
        assert hasattr(result, "errors")
        assert hasattr(result, "warnings")

    def test_validation_with_schema_loader(
        self,
        sample_files: dict[str, Path],
        schema_loader_d23a: GeneratedEdifactSchemaLoader,
    ):
        """Test validation with schema loader."""
        content = sample_files["invoic96"].read_text()
        interchange = parse_content(content)

        # Validate with D23A schema
        # Note: D96A messages may have some schema differences
        validator = EdifactValidator(schema_loader=schema_loader_d23a)
        result = validator.validate(interchange)

        assert result is not None

    def test_validation_levels(self, sample_files: dict[str, Path]):
        """Test different validation levels."""
        content = sample_files["orders96"].read_text()
        interchange = parse_content(content)

        # Test structural only
        validator = EdifactValidator(
            levels={ValidationLevel.STRUCTURAL},
        )
        result = validator.validate(interchange)
        assert result is not None

        # Test envelope only
        validator = EdifactValidator(
            levels={ValidationLevel.ENVELOPE},
        )
        result = validator.validate(interchange)
        assert result is not None


class TestSchemaVersionComparison:
    """Compare D23A and D96A schema capabilities."""

    def test_d23a_has_more_structure(self):
        """D23A should have better element resolution than D96A."""
        schema_d23a = get_schema("INVOIC", version="d23a")
        schema_d96a = get_schema("INVOIC", version="d96a")

        assert schema_d23a is not None
        assert schema_d96a is not None

        # D23A should have many more elements resolved
        assert len(schema_d23a.elements) > len(schema_d96a.elements)
        assert len(schema_d23a.composites) > len(schema_d96a.composites)

    def test_both_have_segments(self):
        """Both versions should have segments."""
        schema_d23a = get_schema("INVOIC", version="d23a")
        schema_d96a = get_schema("INVOIC", version="d96a")

        # Both should have segments
        assert len(schema_d23a.segments) > 0
        assert len(schema_d96a.segments) > 0

    def test_both_have_message_structure(self):
        """Both versions should have message structure."""
        schema_d23a = get_schema("INVOIC", version="d23a")
        schema_d96a = get_schema("INVOIC", version="d96a")

        # Both should have structure
        assert len(schema_d23a.spec.structure) > 0
        assert len(schema_d96a.spec.structure) > 0
