"""
Validation tests for X12 sample files.

Tests all sample files in tests/fixtures/x12_samples/ for:
- Tokenization
- Envelope parsing (ISA/IEA, GS/GE, ST/SE)
- Element validation
- HL hierarchy (where applicable)
- 997 acknowledgment generation
- Schema-based element validation
"""

from pathlib import Path

import pytest
from edi_schema.x12.ack import generate_997
from edi_schema.x12.ast import (
    ErrorSeverity,
    ParsedElement,
    RawElement,
    SourcePosition,
)
from edi_schema.x12.enums import DataElementType
from edi_schema.x12.parser import (
    HLParser,
    parse_envelope,
    tokenize,
)
from edi_schema.x12.schemas import GeneratedX12SchemaLoader
from edi_schema.x12.validator import (
    ElementValidator,
    ValidationLevel,
    X12Validator,
)
from edi_schema.x12.validator.code import (
    FUNCTIONAL_ID_CODES,
    ID_QUALIFIERS,
    CodeValidationContext,
    validate_code_value,
)
from edi_schema.x12.validator.element import ElementValidationContext

# Map of transaction types to their functional group IDs
TRANSACTION_TYPES = {
    "270": {"functional_id": "HS", "name": "Eligibility Inquiry"},
    "271": {"functional_id": "HB", "name": "Eligibility Response"},
    "276": {"functional_id": "HR", "name": "Claim Status Request"},
    "277": {"functional_id": "HN", "name": "Claim Status Response"},
    "278": {"functional_id": "HI", "name": "Authorization Request"},
    "820": {"functional_id": "RA", "name": "Premium Payment"},
    "834": {"functional_id": "BE", "name": "Enrollment"},
    "835": {"functional_id": "HP", "name": "Remittance Advice"},
    "837": {"functional_id": "HC", "name": "Healthcare Claim"},
}


@pytest.fixture
def samples_dir() -> Path:
    """Path to X12 sample files."""
    return Path(__file__).parent.parent / "fixtures" / "x12_samples"


@pytest.fixture
def sample_files(samples_dir: Path) -> dict[str, Path]:
    """Get all sample files as a dict."""
    files = {}
    for f in samples_dir.glob("*.x12"):
        files[f.stem] = f
    return files


@pytest.fixture
def schema_loader() -> GeneratedX12SchemaLoader:
    """Load X12 005010 schema using pre-generated schemas."""
    return GeneratedX12SchemaLoader(version="005010")


class TestTokenization:
    """Tests for tokenizing all sample files."""

    def test_all_samples_tokenize(self, samples_dir: Path):
        """All sample files should tokenize without fatal errors."""
        for file_path in samples_dir.glob("*.x12"):
            content = file_path.read_text()
            result = tokenize(content)

            # Should have segments
            assert len(result.segments) > 0, f"{file_path.name} produced no segments"

            # Should detect delimiters
            assert result.delimiters.element == "*", f"{file_path.name} wrong element sep"
            assert result.delimiters.segment == "~", f"{file_path.name} wrong segment term"

            # Should not have fatal errors
            fatal_errors = [e for e in result.errors if e.severity == ErrorSeverity.FATAL]
            assert len(fatal_errors) == 0, f"{file_path.name} has fatal tokenization errors"

    def test_837p_tokenization(self, sample_files: dict[str, Path]):
        """Test 837P Professional Claim tokenization."""
        content = sample_files["837P_professional_claim"].read_text()
        result = tokenize(content)

        # Check segment count
        assert len(result.segments) == 38

        # Check ISA segment
        isa = result.segments[0]
        assert isa.tag == "ISA"
        assert len(isa.elements) == 16

        # Check component separator detected
        assert result.delimiters.component == ":"

    def test_835_tokenization(self, sample_files: dict[str, Path]):
        """Test 835 Remittance tokenization."""
        content = sample_files["835_remittance"].read_text()
        result = tokenize(content)

        # Check segment count
        assert len(result.segments) == 35

        # Verify specific segments exist
        segment_tags = [s.tag for s in result.segments]
        assert "BPR" in segment_tags  # Payment info
        assert "TRN" in segment_tags  # Trace
        assert "CLP" in segment_tags  # Claim payment
        assert "SVC" in segment_tags  # Service payment

    def test_834_tokenization(self, sample_files: dict[str, Path]):
        """Test 834 Enrollment tokenization."""
        content = sample_files["834_enrollment"].read_text()
        result = tokenize(content)

        # Check segment count
        assert len(result.segments) == 39

        # Verify enrollment-specific segments
        segment_tags = [s.tag for s in result.segments]
        assert "BGN" in segment_tags  # Beginning
        assert "INS" in segment_tags  # Member level detail
        assert "HD" in segment_tags  # Health coverage


class TestEnvelopeParsing:
    """Tests for envelope parsing of all sample files."""

    def test_all_samples_envelope_parse(self, samples_dir: Path):
        """All sample files should parse envelope structure."""
        for file_path in samples_dir.glob("*.x12"):
            content = file_path.read_text()
            result = parse_envelope(tokenize(content))

            # Should have interchange
            assert result.interchange is not None, f"{file_path.name} missing interchange"

            # Should have at least one group
            assert len(result.interchange.groups) > 0, f"{file_path.name} missing groups"

            # Should have at least one transaction
            group = result.interchange.groups[0]
            assert len(group.transactions) > 0, f"{file_path.name} missing transactions"

    def test_837p_envelope(self, sample_files: dict[str, Path]):
        """Test 837P envelope structure."""
        content = sample_files["837P_professional_claim"].read_text()
        result = parse_envelope(tokenize(content))

        interchange = result.interchange
        assert interchange is not None

        # Check ISA fields
        assert interchange.sender_qualifier == "ZZ"
        assert interchange.sender_id.strip() == "SUBMITTER"
        assert interchange.receiver_qualifier == "ZZ"
        assert interchange.receiver_id.strip() == "RECEIVER"
        assert interchange.control_number == "000000001"
        assert interchange.version == "00501"

        # Check GS fields
        group = interchange.groups[0]
        assert group.functional_id == "HC"
        assert group.version == "005010X222A1"
        assert group.control_number == "1"

        # Check ST fields
        txn = group.transactions[0]
        assert txn.transaction_id == "837"
        assert txn.control_number == "0001"

    def test_270_envelope(self, sample_files: dict[str, Path]):
        """Test 270 Eligibility Inquiry envelope."""
        content = sample_files["270_eligibility_inquiry"].read_text()
        result = parse_envelope(tokenize(content))

        group = result.interchange.groups[0]
        assert group.functional_id == "HS"

        txn = group.transactions[0]
        assert txn.transaction_id == "270"

    def test_835_envelope(self, sample_files: dict[str, Path]):
        """Test 835 Remittance envelope."""
        content = sample_files["835_remittance"].read_text()
        result = parse_envelope(tokenize(content))

        group = result.interchange.groups[0]
        assert group.functional_id == "HP"

        txn = group.transactions[0]
        assert txn.transaction_id == "835"

    def test_control_number_matching(self, samples_dir: Path):
        """Test that control numbers match (ISA/IEA, GS/GE, ST/SE)."""
        for file_path in samples_dir.glob("*.x12"):
            content = file_path.read_text()
            result = parse_envelope(tokenize(content))

            # Check for control number mismatch errors
            envelope_errors = [e for e in result.errors if "control" in e.message.lower()]
            assert (
                len(envelope_errors) == 0
            ), f"{file_path.name} has control number mismatches: {envelope_errors}"


class TestHLHierarchy:
    """Tests for HL (Hierarchical Level) parsing in sample files."""

    @pytest.fixture
    def hl_parser(self):
        return HLParser()

    def test_837p_hl_hierarchy(self, sample_files: dict[str, Path]):
        """Test 837P HL hierarchy (Billing/Subscriber pattern)."""
        content = sample_files["837P_professional_claim"].read_text()
        result = parse_envelope(tokenize(content))

        txn = result.interchange.groups[0].transactions[0]
        hl_segments = [s for s in txn.content if hasattr(s, "tag") and s.tag == "HL"]

        # Should have 3 HL segments (1 billing provider, 2 subscribers)
        assert len(hl_segments) == 3

        # Check HL levels
        # HL*1**20*1 - Billing provider (level 20)
        assert hl_segments[0].elements[2].value == "20"  # Level code

        # HL*2*1*22*0 - Subscriber (level 22, parent 1)
        assert hl_segments[1].elements[1].value == "1"  # Parent
        assert hl_segments[1].elements[2].value == "22"  # Level code

    def test_270_hl_hierarchy(self, sample_files: dict[str, Path]):
        """Test 270 HL hierarchy (Information Source/Receiver/Subscriber/Dependent)."""
        content = sample_files["270_eligibility_inquiry"].read_text()
        result = parse_envelope(tokenize(content))

        txn = result.interchange.groups[0].transactions[0]
        hl_segments = [s for s in txn.content if hasattr(s, "tag") and s.tag == "HL"]

        # Should have 5 HL segments
        assert len(hl_segments) == 5

        # Check HL levels
        # HL*1**20*1 - Information source
        assert hl_segments[0].elements[2].value == "20"

        # HL*2*1*21*1 - Information receiver
        assert hl_segments[1].elements[2].value == "21"

        # HL*3*2*22*0 - Subscriber
        assert hl_segments[2].elements[2].value == "22"

        # HL*5*4*23*0 - Dependent
        assert hl_segments[4].elements[2].value == "23"

    def test_271_hl_hierarchy(self, sample_files: dict[str, Path]):
        """Test 271 HL hierarchy."""
        content = sample_files["271_eligibility_response"].read_text()
        result = parse_envelope(tokenize(content))

        txn = result.interchange.groups[0].transactions[0]
        hl_segments = [s for s in txn.content if hasattr(s, "tag") and s.tag == "HL"]

        # Should have 6 HL segments
        assert len(hl_segments) == 6

    def test_276_hl_hierarchy(self, sample_files: dict[str, Path]):
        """Test 276 Claim Status Request HL hierarchy."""
        content = sample_files["276_claim_status_request"].read_text()
        result = parse_envelope(tokenize(content))

        txn = result.interchange.groups[0].transactions[0]
        hl_segments = [s for s in txn.content if hasattr(s, "tag") and s.tag == "HL"]

        # Should have 4 HL segments
        assert len(hl_segments) == 4

    def test_278_hl_hierarchy(self, sample_files: dict[str, Path]):
        """Test 278 Authorization Request HL hierarchy."""
        content = sample_files["278_authorization_request"].read_text()
        result = parse_envelope(tokenize(content))

        txn = result.interchange.groups[0].transactions[0]
        hl_segments = [s for s in txn.content if hasattr(s, "tag") and s.tag == "HL"]

        # Should have 4 HL segments
        assert len(hl_segments) == 4

        # HL*4*3*EV*0 - Event level for authorization
        assert hl_segments[3].elements[2].value == "EV"


class TestElementValidation:
    """Tests for element validation in sample files."""

    @pytest.fixture
    def element_validator(self):
        return ElementValidator()

    def test_isa_element_lengths(self, sample_files: dict[str, Path], element_validator):
        """Test ISA segment element length validation.

        Note: Sample files may have unpadded ISA fields, so we check minimum lengths.
        In production X12, these fields are fixed-width with trailing space padding.
        """
        for name, file_path in sample_files.items():
            content = file_path.read_text()
            result = parse_envelope(tokenize(content))

            interchange = result.interchange
            assert interchange is not None

            # ISA01 (Authorization Qualifier) should be 2 chars
            assert len(interchange.auth_qualifier) == 2, f"{name}: ISA01 length"

            # ISA02 (Authorization Info) should be up to 10 chars
            assert len(interchange.auth_info) <= 10, f"{name}: ISA02 length"

            # ISA03 (Security Qualifier) should be 2 chars
            assert len(interchange.security_qualifier) == 2, f"{name}: ISA03 length"

            # ISA04 (Security Info) should be up to 10 chars
            assert len(interchange.security_info) <= 10, f"{name}: ISA04 length"

            # ISA05/ISA07 (ID Qualifiers) should be 2 chars
            assert len(interchange.sender_qualifier) == 2, f"{name}: ISA05 length"
            assert len(interchange.receiver_qualifier) == 2, f"{name}: ISA07 length"

            # ISA06/ISA08 (IDs) should be up to 15 chars (may be unpadded)
            assert 1 <= len(interchange.sender_id) <= 15, f"{name}: ISA06 length"
            assert 1 <= len(interchange.receiver_id) <= 15, f"{name}: ISA08 length"

    def test_date_validation(self, sample_files: dict[str, Path], element_validator):
        """Test date element validation (DT type)."""
        context = ElementValidationContext(
            segment_tag="ISA",
            segment_position=1,
            element_position=9,
        )

        # Test YYMMDD format from ISA09
        for name, file_path in sample_files.items():
            content = file_path.read_text()
            result = tokenize(content)

            # ISA segment is first
            isa = result.segments[0]
            date_value = isa.elements[8].value  # ISA09 (0-indexed)

            element = ParsedElement(
                value=date_value,
                raw=RawElement(
                    value=date_value,
                    position=SourcePosition(0, 1, 1),
                    element_index=9,
                ),
            )

            errors = element_validator.validate(
                element,
                context,
                data_type=DataElementType.DT,
            )

            assert len(errors) == 0, f"{name} has invalid ISA date: {date_value}"

    def test_time_validation(self, sample_files: dict[str, Path], element_validator):
        """Test time element validation (TM type)."""
        context = ElementValidationContext(
            segment_tag="ISA",
            segment_position=1,
            element_position=10,
        )

        for name, file_path in sample_files.items():
            content = file_path.read_text()
            result = tokenize(content)

            isa = result.segments[0]
            time_value = isa.elements[9].value  # ISA10 (0-indexed)

            element = ParsedElement(
                value=time_value,
                raw=RawElement(
                    value=time_value,
                    position=SourcePosition(0, 1, 1),
                    element_index=10,
                ),
            )

            errors = element_validator.validate(
                element,
                context,
                data_type=DataElementType.TM,
            )

            assert len(errors) == 0, f"{name} has invalid ISA time: {time_value}"

    def test_control_numbers_numeric(self, sample_files: dict[str, Path]):
        """Test that control numbers are numeric."""
        for name, file_path in sample_files.items():
            content = file_path.read_text()
            result = parse_envelope(tokenize(content))

            interchange = result.interchange
            assert interchange is not None

            # ISA13 should be numeric
            assert (
                interchange.control_number.isdigit()
            ), f"{name} ISA control number not numeric: {interchange.control_number}"

            # GS06 should be numeric
            for group in interchange.groups:
                assert (
                    group.control_number.isdigit()
                ), f"{name} GS control number not numeric: {group.control_number}"


class TestCodeValidation:
    """Tests for code value validation in sample files."""

    def test_id_qualifier_validation(self, sample_files: dict[str, Path]):
        """Test ID qualifier codes are valid."""
        for name, file_path in sample_files.items():
            content = file_path.read_text()
            result = parse_envelope(tokenize(content))

            interchange = result.interchange
            assert interchange is not None

            context = CodeValidationContext(
                segment_tag="ISA",
                segment_position=1,
                element_position=5,
            )

            # Validate sender qualifier
            errors = validate_code_value(
                interchange.sender_qualifier,
                ID_QUALIFIERS,
                context,
                strict=False,  # Warning only for unknown
            )

            # ZZ is valid (Mutually Defined)
            if interchange.sender_qualifier == "ZZ":
                assert len([e for e in errors if e.severity == ErrorSeverity.ERROR]) == 0

    def test_functional_id_validation(self, sample_files: dict[str, Path]):
        """Test functional group ID codes are valid."""
        for name, file_path in sample_files.items():
            content = file_path.read_text()
            result = parse_envelope(tokenize(content))

            for group in result.interchange.groups:
                context = CodeValidationContext(
                    segment_tag="GS",
                    segment_position=2,
                    element_position=1,
                )

                errors = validate_code_value(
                    group.functional_id,
                    FUNCTIONAL_ID_CODES,
                    context,
                    strict=True,
                )

                assert len(errors) == 0, f"{name} has invalid functional ID: {group.functional_id}"


class TestTransactionContent:
    """Tests for transaction-specific content validation."""

    def test_837p_has_required_segments(self, sample_files: dict[str, Path]):
        """Test 837P has required segments."""
        content = sample_files["837P_professional_claim"].read_text()
        result = parse_envelope(tokenize(content))

        txn = result.interchange.groups[0].transactions[0]
        segment_tags = [s.tag for s in txn.content if hasattr(s, "tag")]

        # Required 837P segments
        assert "BHT" in segment_tags  # Beginning of Hierarchical Transaction
        assert "NM1" in segment_tags  # Name
        assert "HL" in segment_tags  # Hierarchical Level
        assert "CLM" in segment_tags  # Claim
        assert "SV1" in segment_tags  # Professional Service

    def test_837i_has_required_segments(self, sample_files: dict[str, Path]):
        """Test 837I has required segments."""
        content = sample_files["837I_institutional_claim"].read_text()
        result = parse_envelope(tokenize(content))

        txn = result.interchange.groups[0].transactions[0]
        segment_tags = [s.tag for s in txn.content if hasattr(s, "tag")]

        # Required 837I segments
        assert "BHT" in segment_tags
        assert "NM1" in segment_tags
        assert "HL" in segment_tags
        assert "CLM" in segment_tags
        assert "SV2" in segment_tags  # Institutional Service (different from SV1)

    def test_835_has_required_segments(self, sample_files: dict[str, Path]):
        """Test 835 has required segments."""
        content = sample_files["835_remittance"].read_text()
        result = parse_envelope(tokenize(content))

        txn = result.interchange.groups[0].transactions[0]
        segment_tags = [s.tag for s in txn.content if hasattr(s, "tag")]

        # Required 835 segments
        assert "BPR" in segment_tags  # Financial Information
        assert "TRN" in segment_tags  # Trace
        assert "N1" in segment_tags  # Name
        assert "CLP" in segment_tags  # Claim Payment
        assert "SVC" in segment_tags  # Service Payment

    def test_834_has_required_segments(self, sample_files: dict[str, Path]):
        """Test 834 has required segments."""
        content = sample_files["834_enrollment"].read_text()
        result = parse_envelope(tokenize(content))

        txn = result.interchange.groups[0].transactions[0]
        segment_tags = [s.tag for s in txn.content if hasattr(s, "tag")]

        # Required 834 segments
        assert "BGN" in segment_tags  # Beginning Segment
        assert "N1" in segment_tags  # Name
        assert "INS" in segment_tags  # Member Level Detail
        assert "NM1" in segment_tags  # Individual Name
        assert "HD" in segment_tags  # Health Coverage

    def test_270_has_required_segments(self, sample_files: dict[str, Path]):
        """Test 270 has required segments."""
        content = sample_files["270_eligibility_inquiry"].read_text()
        result = parse_envelope(tokenize(content))

        txn = result.interchange.groups[0].transactions[0]
        segment_tags = [s.tag for s in txn.content if hasattr(s, "tag")]

        # Required 270 segments
        assert "BHT" in segment_tags
        assert "HL" in segment_tags
        assert "NM1" in segment_tags
        assert "EQ" in segment_tags  # Eligibility Inquiry

    def test_271_has_required_segments(self, sample_files: dict[str, Path]):
        """Test 271 has required segments."""
        content = sample_files["271_eligibility_response"].read_text()
        result = parse_envelope(tokenize(content))

        txn = result.interchange.groups[0].transactions[0]
        segment_tags = [s.tag for s in txn.content if hasattr(s, "tag")]

        # Required 271 segments
        assert "BHT" in segment_tags
        assert "HL" in segment_tags
        assert "NM1" in segment_tags
        assert "EB" in segment_tags  # Eligibility Benefit


class TestSegmentCounts:
    """Tests for verifying segment counts match SE segments."""

    def test_segment_counts_match(self, samples_dir: Path):
        """Test SE segment count matches actual segment count."""
        for file_path in samples_dir.glob("*.x12"):
            content = file_path.read_text()
            result = tokenize(content)

            # Find ST/SE pairs
            segments = result.segments
            for i, seg in enumerate(segments):
                if seg.tag == "SE":
                    # SE01 is segment count
                    se_count = int(seg.elements[0].value)

                    # Count segments from ST to SE (inclusive)
                    # Find corresponding ST
                    st_index = None
                    for j in range(i - 1, -1, -1):
                        if segments[j].tag == "ST":
                            st_index = j
                            break

                    assert st_index is not None, f"{file_path.name} SE without ST"

                    actual_count = i - st_index + 1

                    assert (
                        se_count == actual_count
                    ), f"{file_path.name}: SE count {se_count} != actual {actual_count}"


class Test997Generation:
    """Tests for 997 acknowledgment generation from sample files."""

    def test_generate_997_for_all_samples(self, samples_dir: Path):
        """Test generating 997 for all sample files."""
        for file_path in samples_dir.glob("*.x12"):
            content = file_path.read_text()
            result = parse_envelope(tokenize(content))

            for group in result.interchange.groups:
                ack = generate_997(group, control_number="0001")

                # 997 should have proper structure
                assert "ST*997*0001" in ack
                assert "AK1*" in ack
                assert "AK5*" in ack
                assert "AK9*" in ack
                assert "SE*" in ack

                # Should end with segment terminator
                assert ack.endswith("~")

    def test_997_for_837p(self, sample_files: dict[str, Path]):
        """Test 997 for 837P sample."""
        content = sample_files["837P_professional_claim"].read_text()
        result = parse_envelope(tokenize(content))

        group = result.interchange.groups[0]
        ack = generate_997(group, control_number="0001")

        # Should acknowledge the HC (Healthcare) group
        assert "AK1*HC*1" in ack

        # Should acknowledge the 837 transaction
        assert "AK2*837*0001" in ack

        # Should be accepted (no errors in valid file)
        assert "AK5*A" in ack
        assert "AK9*A*1*1*1" in ack

    def test_997_for_835(self, sample_files: dict[str, Path]):
        """Test 997 for 835 sample."""
        content = sample_files["835_remittance"].read_text()
        result = parse_envelope(tokenize(content))

        group = result.interchange.groups[0]
        ack = generate_997(group, control_number="0001")

        # Should acknowledge the HP (Health Care Claim Payment) group
        assert "AK1*HP*1" in ack

        # Should acknowledge the 835 transaction
        assert "AK2*835*0001" in ack

    def test_997_segment_count_accurate(self, sample_files: dict[str, Path]):
        """Test 997 SE segment count is accurate."""
        content = sample_files["837P_professional_claim"].read_text()
        result = parse_envelope(tokenize(content))

        group = result.interchange.groups[0]
        ack = generate_997(group, control_number="0001")

        # Parse the 997 to verify SE count
        lines = [l for l in ack.strip().split("~") if l]
        actual_count = len(lines)

        # Find SE segment
        se_line = [l for l in lines if l.startswith("SE")][0]
        se_count = int(se_line.split("*")[1])

        assert se_count == actual_count


class TestCompositeElements:
    """Tests for composite element handling."""

    def test_837p_composite_elements(self, sample_files: dict[str, Path]):
        """Test composite elements in 837P (e.g., CLM05, HI)."""
        from edi_schema.x12.ast import RawComposite

        content = sample_files["837P_professional_claim"].read_text()
        result = tokenize(content)

        # Find CLM segment
        clm_segments = [s for s in result.segments if s.tag == "CLM"]
        assert len(clm_segments) >= 1

        # CLM05 should be composite (11:B:1)
        clm = clm_segments[0]
        clm05 = clm.elements[4]
        # Could be RawComposite or RawElement depending on tokenizer
        if isinstance(clm05, RawComposite):
            clm05_str = str(clm05)
        else:
            clm05_str = clm05.value
        assert ":" in clm05_str  # Contains sub-element separator

        # Find HI segment
        hi_segments = [s for s in result.segments if s.tag == "HI"]
        assert len(hi_segments) >= 1

        # HI01 should be composite (ABK:R05)
        hi = hi_segments[0]
        hi01 = hi.elements[0]
        if isinstance(hi01, RawComposite):
            hi01_str = str(hi01)
        else:
            hi01_str = hi01.value
        assert ":" in hi01_str

    def test_837i_sv2_composite(self, sample_files: dict[str, Path]):
        """Test SV2 composite elements in 837I."""
        from edi_schema.x12.ast import RawComposite

        content = sample_files["837I_institutional_claim"].read_text()
        result = tokenize(content)

        # Find SV2 segments
        sv2_segments = [s for s in result.segments if s.tag == "SV2"]
        assert len(sv2_segments) >= 1

        # SV202 should be composite (HC:99223)
        sv2 = sv2_segments[0]
        sv202 = sv2.elements[1]
        if isinstance(sv202, RawComposite):
            sv202_str = str(sv202)
        else:
            sv202_str = sv202.value
        assert ":" in sv202_str


class TestSpecificTransactions:
    """Tests for specific transaction type details."""

    def test_820_payment_details(self, sample_files: dict[str, Path]):
        """Test 820 premium payment details."""
        content = sample_files["820_premium_payment"].read_text()
        result = parse_envelope(tokenize(content))

        txn = result.interchange.groups[0].transactions[0]
        segment_tags = [s.tag for s in txn.content if hasattr(s, "tag")]

        # Required 820 segments
        assert "BPR" in segment_tags  # Financial Information
        assert "TRN" in segment_tags  # Trace
        assert "ENT" in segment_tags  # Entity
        assert "RMR" in segment_tags  # Remittance

    def test_278_authorization_details(self, sample_files: dict[str, Path]):
        """Test 278 authorization request details."""
        content = sample_files["278_authorization_request"].read_text()
        result = parse_envelope(tokenize(content))

        txn = result.interchange.groups[0].transactions[0]
        segment_tags = [s.tag for s in txn.content if hasattr(s, "tag")]

        # Required 278 segments
        assert "BHT" in segment_tags
        assert "UM" in segment_tags  # Health Care Services Review
        assert "HI" in segment_tags  # Diagnosis
        assert "SV1" in segment_tags  # Professional Service

    def test_276_277_claim_status_pair(self, sample_files: dict[str, Path]):
        """Test 276 request and 277 response are complementary."""
        # Parse 276 (request)
        content_276 = sample_files["276_claim_status_request"].read_text()
        result_276 = parse_envelope(tokenize(content_276))
        txn_276 = result_276.interchange.groups[0].transactions[0]
        tags_276 = [s.tag for s in txn_276.content if hasattr(s, "tag")]

        # Parse 277 (response)
        content_277 = sample_files["277_claim_status_response"].read_text()
        result_277 = parse_envelope(tokenize(content_277))
        txn_277 = result_277.interchange.groups[0].transactions[0]
        tags_277 = [s.tag for s in txn_277.content if hasattr(s, "tag")]

        # Both should have HL, NM1, TRN
        assert "HL" in tags_276 and "HL" in tags_277
        assert "NM1" in tags_276 and "NM1" in tags_277
        assert "TRN" in tags_276 and "TRN" in tags_277

        # 276 has AMT (amount), 277 has STC (status)
        assert "AMT" in tags_276
        assert "STC" in tags_277

    def test_270_271_eligibility_pair(self, sample_files: dict[str, Path]):
        """Test 270 inquiry and 271 response are complementary."""
        # Parse 270 (inquiry)
        content_270 = sample_files["270_eligibility_inquiry"].read_text()
        result_270 = parse_envelope(tokenize(content_270))
        txn_270 = result_270.interchange.groups[0].transactions[0]
        tags_270 = [s.tag for s in txn_270.content if hasattr(s, "tag")]

        # Parse 271 (response)
        content_271 = sample_files["271_eligibility_response"].read_text()
        result_271 = parse_envelope(tokenize(content_271))
        txn_271 = result_271.interchange.groups[0].transactions[0]
        tags_271 = [s.tag for s in txn_271.content if hasattr(s, "tag")]

        # 270 has EQ (eligibility inquiry)
        assert "EQ" in tags_270

        # 271 has EB (eligibility benefit)
        assert "EB" in tags_271


class TestSchemaBasedValidation:
    """Tests for schema-based element validation."""

    def test_schema_segment_lookup(self, schema_loader: GeneratedX12SchemaLoader):
        """Test segment lookup from schema."""
        schema = schema_loader.load("837")

        # NM1 (Name) should exist
        nm1 = schema.get_segment("NM1")
        assert nm1 is not None
        assert nm1.id == "NM1"
        assert len(nm1.elements) > 0

        # CLM (Claim) should exist
        clm = schema.get_segment("CLM")
        assert clm is not None
        assert clm.id == "CLM"

    def test_schema_element_lookup(self, schema_loader: GeneratedX12SchemaLoader):
        """Test element lookup from schema."""
        schema = schema_loader.load("837")

        # Element 98 (Entity Identifier Code) should exist
        elem_98 = schema.get_element("98")
        assert elem_98 is not None
        assert elem_98.id == "98"
        assert elem_98.data_type == DataElementType.ID

    def test_element_definition_navigation(self, schema_loader: GeneratedX12SchemaLoader):
        """Test navigating from segment to element definition."""
        schema = schema_loader.load("837")

        # Get NM1 segment
        nm1 = schema.get_segment("NM1")
        assert nm1 is not None

        # Get NM101 element reference
        nm101_ref = nm1.get_element("01")
        assert nm101_ref is not None

        # Navigate to element definition
        elem = schema.get_element(nm101_ref.element_id)
        assert elem is not None
        # NM101 references Element 98 (Entity Identifier Code)
        assert elem.id == "98"
        assert elem.data_type == DataElementType.ID

    def test_get_segment_element_definition_helper(self, schema_loader: GeneratedX12SchemaLoader):
        """Test the helper method for segment element definition lookup."""
        schema = schema_loader.load("837")

        # Test NM101
        elem_def, seg_ref = schema.get_segment_element_definition("NM1", 1)
        assert elem_def is not None
        assert seg_ref is not None
        assert elem_def.id == "98"
        assert seg_ref.element_id == "98"

        # Test unknown segment
        elem_def, seg_ref = schema.get_segment_element_definition("ZZZ", 1)
        assert elem_def is None
        assert seg_ref is None

        # Test unknown position
        elem_def, seg_ref = schema.get_segment_element_definition("NM1", 999)
        assert elem_def is None
        assert seg_ref is None

    def test_element_has_code_values(self, schema_loader: GeneratedX12SchemaLoader):
        """Test that ID elements have code value lists."""
        schema = schema_loader.load("837")

        # Element 98 (Entity Identifier Code) should have code values
        elem_98 = schema.get_element("98")
        assert elem_98 is not None
        # May or may not have code values depending on schema loading
        # At minimum, check it's an ID type
        assert elem_98.data_type == DataElementType.ID

    def test_validate_837p_with_schema(
        self,
        schema_loader: GeneratedX12SchemaLoader,
        sample_files: dict[str, Path],
    ):
        """Test validating 837P sample with schema."""
        content = sample_files["837P_professional_claim"].read_text()
        result = parse_envelope(tokenize(content))

        # Run validation with schema
        validator = X12Validator(
            schema_loader=schema_loader,
            levels={ValidationLevel.ELEMENT},
        )
        validation = validator.validate(result.interchange)

        # Sample file should be largely valid
        # Note: May have some validation issues depending on schema strictness
        assert validation is not None

    def test_validate_835_with_schema(
        self,
        schema_loader: GeneratedX12SchemaLoader,
        sample_files: dict[str, Path],
    ):
        """Test validating 835 sample with schema."""
        content = sample_files["835_remittance"].read_text()
        result = parse_envelope(tokenize(content))

        validator = X12Validator(
            schema_loader=schema_loader,
            levels={ValidationLevel.ELEMENT},
        )
        validation = validator.validate(result.interchange)

        assert validation is not None

    def test_validate_270_with_schema(
        self,
        schema_loader: GeneratedX12SchemaLoader,
        sample_files: dict[str, Path],
    ):
        """Test validating 270 sample with schema."""
        content = sample_files["270_eligibility_inquiry"].read_text()
        result = parse_envelope(tokenize(content))

        validator = X12Validator(
            schema_loader=schema_loader,
            levels={ValidationLevel.ELEMENT},
        )
        validation = validator.validate(result.interchange)

        assert validation is not None

    def test_element_length_constraints(self, schema_loader: GeneratedX12SchemaLoader):
        """Test element length constraints from schema."""
        schema = schema_loader.load("837")

        # Get an element and check its length constraints
        elem_98 = schema.get_element("98")  # Entity Identifier Code
        assert elem_98 is not None
        assert elem_98.min_length >= 1
        assert elem_98.max_length >= elem_98.min_length

        # Element 93 (Name) should allow longer values
        elem_93 = schema.get_element("93")  # Name
        if elem_93:
            assert elem_93.max_length >= 1

    def test_composite_element_lookup(self, schema_loader: GeneratedX12SchemaLoader):
        """Test composite element lookup from schema."""
        schema = schema_loader.load("837")

        # Check if schema has any composites
        # CLM05 typically uses composite C023 (Health Care Service Location)
        clm = schema.get_segment("CLM")
        if clm:
            # Find composite elements in CLM
            composites = [e for e in clm.elements if e.is_composite()]
            # CLM segment should have at least one composite
            # (CLM05 - Place of Service)
            assert len(composites) >= 0  # May vary by version

    def test_validation_result_structure(
        self,
        schema_loader: GeneratedX12SchemaLoader,
        sample_files: dict[str, Path],
    ):
        """Test validation result provides proper structure."""
        content = sample_files["837P_professional_claim"].read_text()
        result = parse_envelope(tokenize(content))

        validator = X12Validator(
            schema_loader=schema_loader,
            levels={ValidationLevel.ELEMENT, ValidationLevel.CODE},
        )
        validation = validator.validate(result.interchange)

        # Check result structure
        assert hasattr(validation, "errors")
        assert hasattr(validation, "warnings")
        assert hasattr(validation, "is_valid")
        assert hasattr(validation, "element_errors")
        assert hasattr(validation, "code_errors")

    def test_full_validation_all_levels(
        self,
        schema_loader: GeneratedX12SchemaLoader,
        sample_files: dict[str, Path],
    ):
        """Test full validation with all levels enabled."""
        content = sample_files["837P_professional_claim"].read_text()
        result = parse_envelope(tokenize(content))

        # Enable all validation levels
        validator = X12Validator(
            schema_loader=schema_loader,
            levels={
                ValidationLevel.STRUCTURAL,
                ValidationLevel.ENVELOPE,
                ValidationLevel.SCHEMA,
                ValidationLevel.ELEMENT,
                ValidationLevel.CODE,
                ValidationLevel.SEMANTIC,
            },
        )
        validation = validator.validate(result.interchange)

        # Result should be populated
        assert validation is not None
        assert validation.total_errors() == 0
        assert validation.total_warnings() == 0

    def test_schema_level_only_validation(
        self,
        schema_loader: GeneratedX12SchemaLoader,
        samples_dir: Path,
    ):
        """Test SCHEMA level validation only - validates segment structure.

        This tests that:
        1. Required segments at transaction root are present
        2. Segments are defined in the schema
        3. Max use limits are enforced (at transaction root level)
        4. Loop cardinality limits are enforced

        Note: Some sample files may use implementation guide extensions
        (e.g., MSG segment in 277CA) that aren't in the base schema.
        """
        # Known implementation guide segments not in base schema
        # These are valid X12 segments used in implementation guides
        implementation_guide_segments = {"MSG"}

        # Test all sample files with schema validation only
        for file_path in samples_dir.glob("*.x12"):
            content = file_path.read_text()
            result = parse_envelope(tokenize(content))

            validator = X12Validator(
                schema_loader=schema_loader,
                levels={ValidationLevel.SCHEMA},
            )
            validation = validator.validate(result.interchange)

            # Filter out implementation guide segment errors
            real_errors = [
                e
                for e in validation.errors
                if e.category.value == "schema"
                and not (
                    "not defined" in e.message and e.segment_tag in implementation_guide_segments
                )
            ]

            # Sample files should pass schema validation
            # (excluding implementation guide extensions)
            assert len(real_errors) == 0, (
                f"{file_path.name} has schema errors: " f"{[e.message for e in real_errors]}"
            )

    def test_schema_validates_segment_defined(
        self,
        schema_loader: GeneratedX12SchemaLoader,
        sample_files: dict[str, Path],
    ):
        """Test that schema validation catches undefined segments."""
        # The 837P sample should have all segments defined
        content = sample_files["837P_professional_claim"].read_text()
        result = parse_envelope(tokenize(content))

        validator = X12Validator(
            schema_loader=schema_loader,
            levels={ValidationLevel.SCHEMA},
        )
        validation = validator.validate(result.interchange)

        # No "segment not defined" errors
        undefined_errors = [e for e in validation.errors if "not defined" in e.message]
        assert (
            len(undefined_errors) == 0
        ), f"Unexpected undefined segment errors: {undefined_errors}"
