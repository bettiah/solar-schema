"""
Tests for parsing X12 sample files.

These tests parse all sample files in tests/fixtures/x12_samples/ using the
high-level parse_file API and verify the parsed output matches expected structures.

Snapshot testing with syrupy:
  - First run creates snapshots: pytest tests/x12/test_x12_samples.py
  - Update snapshots: pytest tests/x12/test_x12_samples.py --snapshot-update
"""

from pathlib import Path

import pytest

from edi_schema.x12.ack import generate_997
from edi_schema.x12.ast import (
    ErrorSeverity,
    LoopInstance,
    ParsedSegment,
    RawSegment,
)
from edi_schema.x12.parser import parse_file, parse
from edi_schema.x12.schemas import GeneratedX12SchemaLoader
from edi_schema.x12.validator import (
    ValidationLevel,
    X12Validator,
)

# Path to X12 sample files
X12_SAMPLES_DIR = Path(__file__).parent.parent / "fixtures" / "x12_samples"


def get_sample_files() -> list[Path]:
    """Get all X12 sample files."""
    if not X12_SAMPLES_DIR.exists():
        return []
    return sorted(X12_SAMPLES_DIR.glob("*.x12"))


# Get list of sample files for parametrization
SAMPLE_FILES = get_sample_files()


@pytest.fixture
def schema_loader() -> GeneratedX12SchemaLoader:
    """Load X12 005010 schema using pre-generated schemas."""
    return GeneratedX12SchemaLoader(version="005010")


def interchange_to_dict(interchange) -> dict:
    """Convert an InterchangeInstance to a dictionary for snapshot comparison."""
    if interchange is None:
        return None

    return {
        "sender_id": interchange.sender_id.strip(),
        "receiver_id": interchange.receiver_id.strip(),
        "control_number": interchange.control_number,
        "version": interchange.version,
        "groups": [group_to_dict(g) for g in interchange.groups],
    }


def group_to_dict(group) -> dict:
    """Convert a FunctionalGroupInstance to a dictionary."""
    return {
        "functional_id": group.functional_id,
        "control_number": group.control_number,
        "version": group.version,
        "transactions": [transaction_to_dict(t) for t in group.transactions],
    }


def transaction_to_dict(txn) -> dict:
    """Convert a TransactionSetInstance to a dictionary."""
    return {
        "transaction_id": txn.transaction_id,
        "control_number": txn.control_number,
        "segment_count": txn.segment_count,
        "content": [content_item_to_dict(item) for item in txn.content],
    }


def content_item_to_dict(item) -> dict:
    """Convert content item (segment or loop) to a dictionary."""
    if isinstance(item, LoopInstance):
        return {
            "type": "loop",
            "loop_id": item.loop_id,
            "iteration": item.iteration,
            "segments": [segment_to_dict(s) for s in item.segments],
            "children": [content_item_to_dict(c) for c in item.children],
        }
    elif isinstance(item, ParsedSegment):
        return segment_to_dict(item)
    elif isinstance(item, RawSegment):
        return raw_segment_to_dict(item)
    else:
        return {"type": "unknown", "value": str(item)}


def segment_to_dict(seg: ParsedSegment) -> dict:
    """Convert a ParsedSegment to a dictionary."""
    return {
        "type": "segment",
        "tag": seg.tag,
        "elements": [elem.value for elem in seg.elements],
    }


def raw_segment_to_dict(seg: RawSegment) -> dict:
    """Convert a RawSegment to a dictionary."""
    elements = []
    for elem in seg.elements:
        if hasattr(elem, "value"):
            elements.append(elem.value)
        elif hasattr(elem, "components"):
            elements.append(":".join(elem.components))
        else:
            elements.append(str(elem))
    return {
        "type": "segment",
        "tag": seg.tag,
        "elements": elements,
    }


@pytest.mark.skipif(
    not SAMPLE_FILES,
    reason=f"X12 sample files not found at {X12_SAMPLES_DIR}",
)
class TestX12SampleFiles:
    """Tests for parsing X12 sample files with schema binding."""

    @pytest.mark.parametrize(
        "x12_file",
        SAMPLE_FILES,
        ids=[f.stem for f in SAMPLE_FILES],
    )
    def test_parse_sample_file_with_schema(
        self,
        x12_file: Path,
        schema_loader: GeneratedX12SchemaLoader,
        snapshot,
    ):
        """Parse sample file with schema binding and verify structure matches snapshot."""
        result = parse_file(x12_file, schema_loader=schema_loader)

        # Should parse without fatal errors
        fatal_errors = [e for e in result.errors if e.severity == ErrorSeverity.FATAL]
        assert len(fatal_errors) == 0, f"Parse failed: {fatal_errors}"
        assert result.interchange is not None

        parsed = interchange_to_dict(result.interchange)
        assert parsed == snapshot


@pytest.mark.skipif(
    not SAMPLE_FILES,
    reason=f"X12 sample files not found at {X12_SAMPLES_DIR}",
)
class TestX12SampleFilesWithoutSchema:
    """Tests for parsing X12 sample files without schema binding."""

    @pytest.mark.parametrize(
        "x12_file",
        SAMPLE_FILES,
        ids=[f.stem for f in SAMPLE_FILES],
    )
    def test_parse_sample_file_no_schema(self, x12_file: Path, snapshot):
        """Parse sample file without schema and verify structure matches snapshot."""
        result = parse(x12_file)

        # Should parse without fatal errors
        fatal_errors = [e for e in result.errors if e.severity == ErrorSeverity.FATAL]
        assert len(fatal_errors) == 0, f"Parse failed: {fatal_errors}"
        assert result.interchange is not None

        parsed = interchange_to_dict(result.interchange)
        assert parsed == snapshot


@pytest.mark.skipif(
    not SAMPLE_FILES,
    reason=f"X12 sample files not found at {X12_SAMPLES_DIR}",
)
class TestTransactionTypeDetection:
    """Tests for transaction type detection across all sample files."""

    # Expected transaction types and functional IDs for each file
    EXPECTED_TYPES = {
        "270_eligibility_inquiry": {"txn_id": "270", "func_id": "HS"},
        "271_eligibility_response": {"txn_id": "271", "func_id": "HB"},
        "276_claim_status_request": {"txn_id": "276", "func_id": "HR"},
        "277_claim_status_response": {"txn_id": "277", "func_id": "HN"},
        "278_authorization_request": {"txn_id": "278", "func_id": "HI"},
        "820_premium_payment": {"txn_id": "820", "func_id": "RA"},
        "834_enrollment": {"txn_id": "834", "func_id": "BE"},
        "835_remittance": {"txn_id": "835", "func_id": "HP"},
        "837P_professional_claim": {"txn_id": "837", "func_id": "HC"},
        "837I_institutional_claim": {"txn_id": "837", "func_id": "HC"},
    }

    @pytest.mark.parametrize(
        "x12_file",
        SAMPLE_FILES,
        ids=[f.stem for f in SAMPLE_FILES],
    )
    def test_transaction_type_matches_expected(self, x12_file: Path):
        """Verify transaction type matches expected for each file."""
        result = parse(x12_file)

        assert result.interchange is not None
        assert len(result.interchange.groups) > 0

        file_stem = x12_file.stem
        expected = self.EXPECTED_TYPES.get(file_stem)

        if expected:
            group = result.interchange.groups[0]
            txn = group.transactions[0]

            assert group.functional_id == expected["func_id"], (
                f"Functional ID mismatch for {file_stem}: "
                f"expected {expected['func_id']}, got {group.functional_id}"
            )
            assert txn.transaction_id == expected["txn_id"], (
                f"Transaction ID mismatch for {file_stem}: "
                f"expected {expected['txn_id']}, got {txn.transaction_id}"
            )


@pytest.mark.skipif(
    not SAMPLE_FILES,
    reason=f"X12 sample files not found at {X12_SAMPLES_DIR}",
)
class TestHLHierarchy:
    """Tests for HL (Hierarchical Level) parsing in sample files."""

    @pytest.mark.parametrize(
        "x12_file",
        SAMPLE_FILES,
        ids=[f.stem for f in SAMPLE_FILES],
    )
    def test_hl_hierarchy_parsed(
        self,
        x12_file: Path,
        schema_loader: GeneratedX12SchemaLoader,
    ):
        """Test HL hierarchy is properly parsed into LoopInstances."""
        result = parse_file(x12_file, schema_loader=schema_loader)

        assert result.interchange is not None

        txn = result.interchange.groups[0].transactions[0]

        # Check if this transaction uses HL (837, 270, 271, 276, 277, 278)
        hl_transactions = {"837", "270", "271", "276", "277", "278"}
        if txn.transaction_id in hl_transactions:
            # Should have LoopInstance items for HL-based transactions
            loop_instances = [
                item for item in txn.content if isinstance(item, LoopInstance)
            ]
            assert len(loop_instances) > 0, (
                f"{x12_file.stem}: Expected LoopInstances for HL-based transaction"
            )


@pytest.mark.skipif(
    not SAMPLE_FILES,
    reason=f"X12 sample files not found at {X12_SAMPLES_DIR}",
)
class Test997Generation:
    """Tests for 997 acknowledgment generation from sample files."""

    @pytest.mark.parametrize(
        "x12_file",
        SAMPLE_FILES,
        ids=[f.stem for f in SAMPLE_FILES],
    )
    def test_generate_997_for_sample(self, x12_file: Path, snapshot):
        """Generate 997 for sample file and verify structure matches snapshot."""
        result = parse(x12_file)

        assert result.interchange is not None

        for group in result.interchange.groups:
            ack = generate_997(group, control_number="0001")

            # 997 should have proper structure
            assert "ST*997*0001" in ack
            assert "AK1*" in ack
            assert "AK5*" in ack
            assert "AK9*" in ack
            assert "SE*" in ack
            assert ack.endswith("~")

        # Snapshot the 997 for first group
        ack = generate_997(result.interchange.groups[0], control_number="0001")
        assert ack == snapshot


@pytest.mark.skipif(
    not SAMPLE_FILES,
    reason=f"X12 sample files not found at {X12_SAMPLES_DIR}",
)
class TestSchemaValidation:
    """Tests for schema-based validation of sample files."""

    @pytest.mark.parametrize(
        "x12_file",
        SAMPLE_FILES,
        ids=[f.stem for f in SAMPLE_FILES],
    )
    def test_schema_validation_runs(
        self,
        x12_file: Path,
        schema_loader: GeneratedX12SchemaLoader,
    ):
        """Test that schema validation can be run on sample files.

        Note: Sample files may have implementation guide variations
        that don't match the base X12 schema perfectly. This test
        verifies validation runs without crashing, not that there
        are zero errors.
        """
        result = parse_file(x12_file, schema_loader=schema_loader)

        assert result.interchange is not None

        validator = X12Validator(
            schema_loader=schema_loader,
            levels={ValidationLevel.SCHEMA},
        )
        validation = validator.validate(result.interchange)

        # Validation should complete and return a result
        assert validation is not None
        assert hasattr(validation, "errors")
        assert hasattr(validation, "is_valid")

    @pytest.mark.parametrize(
        "x12_file",
        SAMPLE_FILES,
        ids=[f.stem for f in SAMPLE_FILES],
    )
    def test_element_validation_runs(
        self,
        x12_file: Path,
        schema_loader: GeneratedX12SchemaLoader,
    ):
        """Test that element validation can be run on sample files."""
        result = parse_file(x12_file, schema_loader=schema_loader)

        assert result.interchange is not None

        validator = X12Validator(
            schema_loader=schema_loader,
            levels={ValidationLevel.ELEMENT},
        )
        validation = validator.validate(result.interchange)

        # Validation should complete and return a result
        assert validation is not None


@pytest.mark.skipif(
    not SAMPLE_FILES,
    reason=f"X12 sample files not found at {X12_SAMPLES_DIR}",
)
class TestSpecificSamples:
    """Tests for specific sample files with detailed verification."""

    def test_837p_professional_claim(
        self,
        schema_loader: GeneratedX12SchemaLoader,
        snapshot,
    ):
        """Test parsing 837P Professional Claim sample."""
        x12_file = X12_SAMPLES_DIR / "837P_professional_claim.x12"
        if not x12_file.exists():
            pytest.skip(f"File not found: {x12_file}")

        result = parse_file(x12_file, schema_loader=schema_loader)

        assert result.interchange is not None

        # Verify structure
        assert result.interchange.version == "00501"
        assert len(result.interchange.groups) == 1

        group = result.interchange.groups[0]
        assert group.functional_id == "HC"

        txn = group.transactions[0]
        assert txn.transaction_id == "837"
        assert txn.schema is not None  # Schema should be attached

        # Content should have LoopInstances (parsed with schema)
        loop_instances = [
            item for item in txn.content if isinstance(item, LoopInstance)
        ]
        assert len(loop_instances) > 0

        parsed = interchange_to_dict(result.interchange)
        assert parsed == snapshot

    def test_835_remittance(
        self,
        schema_loader: GeneratedX12SchemaLoader,
        snapshot,
    ):
        """Test parsing 835 Remittance Advice sample."""
        x12_file = X12_SAMPLES_DIR / "835_remittance.x12"
        if not x12_file.exists():
            pytest.skip(f"File not found: {x12_file}")

        result = parse_file(x12_file, schema_loader=schema_loader)

        assert result.interchange is not None

        group = result.interchange.groups[0]
        assert group.functional_id == "HP"

        txn = group.transactions[0]
        assert txn.transaction_id == "835"
        assert txn.schema is not None

        parsed = interchange_to_dict(result.interchange)
        assert parsed == snapshot

    def test_270_eligibility_inquiry(
        self,
        schema_loader: GeneratedX12SchemaLoader,
        snapshot,
    ):
        """Test parsing 270 Eligibility Inquiry sample."""
        x12_file = X12_SAMPLES_DIR / "270_eligibility_inquiry.x12"
        if not x12_file.exists():
            pytest.skip(f"File not found: {x12_file}")

        result = parse_file(x12_file, schema_loader=schema_loader)

        assert result.interchange is not None

        group = result.interchange.groups[0]
        assert group.functional_id == "HS"

        txn = group.transactions[0]
        assert txn.transaction_id == "270"

        # 270 uses HL hierarchy
        loop_instances = [
            item for item in txn.content if isinstance(item, LoopInstance)
        ]
        assert len(loop_instances) > 0

        parsed = interchange_to_dict(result.interchange)
        assert parsed == snapshot


@pytest.mark.skipif(
    not SAMPLE_FILES,
    reason=f"X12 sample files not found at {X12_SAMPLES_DIR}",
)
class TestLoopHierarchyCaching:
    """Tests for loop_hierarchy caching on X12Schema."""

    def test_loop_hierarchy_cached_on_schema(
        self,
        schema_loader: GeneratedX12SchemaLoader,
    ):
        """Test that loop_hierarchy is built and cached on schema load."""
        schema = schema_loader.load("837")

        # loop_hierarchy should be pre-built
        assert schema.loop_hierarchy is not None
        assert schema.loop_hierarchy.loop_id == "ROOT"

    def test_loop_hierarchy_same_object_on_reload(
        self,
        schema_loader: GeneratedX12SchemaLoader,
    ):
        """Test that loop_hierarchy is the same object when loading same schema twice."""
        schema1 = schema_loader.load("850")
        schema2 = schema_loader.load("850")

        # Should be the same cached object
        assert schema1.loop_hierarchy is schema2.loop_hierarchy

    def test_parser_uses_cached_loop_hierarchy(
        self,
        schema_loader: GeneratedX12SchemaLoader,
    ):
        """Test that TransactionParser uses pre-built loop_hierarchy."""
        from edi_schema.x12.parser.transaction import TransactionParser

        schema = schema_loader.load("837")

        parser = TransactionParser(schema)

        # Parser should use schema's loop_hierarchy
        assert parser.loop_hierarchy is schema.loop_hierarchy


@pytest.mark.skipif(
    not SAMPLE_FILES,
    reason=f"X12 sample files not found at {X12_SAMPLES_DIR}",
)
class TestParseStatistics:
    """Tests for parse statistics across sample files."""

    @pytest.mark.parametrize(
        "x12_file",
        SAMPLE_FILES,
        ids=[f.stem for f in SAMPLE_FILES],
    )
    def test_statistics_for_sample_file(
        self,
        x12_file: Path,
        schema_loader: GeneratedX12SchemaLoader,
    ):
        """Collect statistics for each parsed file."""
        result = parse_file(x12_file, schema_loader=schema_loader)

        assert result.interchange is not None

        # Count segments and loops
        total_segments = 0
        total_loops = 0

        for group in result.interchange.groups:
            for txn in group.transactions:
                for item in txn.content:
                    if isinstance(item, ParsedSegment):
                        total_segments += 1
                    elif isinstance(item, LoopInstance):
                        total_loops += 1
                        total_segments += len(item.segments)

        # Basic sanity checks
        assert total_segments > 0 or total_loops > 0
