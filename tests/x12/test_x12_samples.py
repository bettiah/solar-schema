"""
Non-snapshot tests for parsing X12 sample files.

These tests verify structural properties, transaction types, HL hierarchies,
schema validation, loop hierarchy caching, and parse statistics.

Snapshot tests are in separate modules:
  - test_x12_parse_with_schema.py
  - test_x12_parse_no_schema.py
  - test_x12_997_generation.py
  - test_x12_specific_samples.py
"""

from pathlib import Path

import pytest

from edi_schema.x12.ast import LoopInstance, ParsedSegment
from edi_schema.x12.parser import parse, parse_file
from edi_schema.x12.schemas import GeneratedX12SchemaLoader
from edi_schema.x12.validator import ValidationLevel, X12Validator

from .conftest import SAMPLE_FILES, get_schema_loader_for_file


@pytest.mark.skipif(
    not SAMPLE_FILES,
    reason="X12 sample files not found",
)
class TestTransactionTypeDetection:
    """Tests for transaction type detection across all sample files."""

    # Expected transaction types and functional IDs for each file
    EXPECTED_TYPES = {
        # HIPAA transactions
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
        # Logistics transactions
        "204_motor_carrier_load_tender": {"txn_id": "204", "func_id": "SM"},
        "210_freight_details_invoice": {"txn_id": "210", "func_id": "IM"},
        "211_motor_carrier_bill_of_lading": {"txn_id": "211", "func_id": "BL"},
        "214_shipment_status": {"txn_id": "214", "func_id": "QM"},
        "810_invoice": {"txn_id": "810", "func_id": "IN"},
        "820_remittance_advice": {"txn_id": "820", "func_id": "RA"},
        "846_inventory_inquiry": {"txn_id": "846", "func_id": "IB"},
        "850_purchase_order": {"txn_id": "850", "func_id": "PO"},
        "855_purchase_order_ack": {"txn_id": "855", "func_id": "PR"},
        "856_ship_notice": {"txn_id": "856", "func_id": "IN"},
        "940_warehouse_shipping_order": {"txn_id": "940", "func_id": "OW"},
        "945_warehouse_shipping_advice": {"txn_id": "945", "func_id": "SW"},
        "947_warehouse_inventory_adjustment": {"txn_id": "947", "func_id": "AW"},
        "997_functional_ack": {"txn_id": "997", "func_id": "FA"},
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
    reason="X12 sample files not found",
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
    ):
        """Test HL hierarchy is properly parsed into LoopInstances."""
        schema_loader = get_schema_loader_for_file(x12_file)
        result = parse_file(x12_file, schema_loader=schema_loader)

        assert result.interchange is not None

        txn = result.interchange.groups[0].transactions[0]

        # Check if this transaction uses HL (837, 270, 271, 276, 277, 278)
        hl_transactions = {"837", "270", "271", "276", "277", "278"}
        if txn.transaction_id in hl_transactions:
            # Should have LoopInstance items for HL-based transactions
            loop_instances = [item for item in txn.content if isinstance(item, LoopInstance)]
            assert len(loop_instances) > 0, (
                f"{x12_file.stem}: Expected LoopInstances for HL-based transaction"
            )


@pytest.mark.skipif(
    not SAMPLE_FILES,
    reason="X12 sample files not found",
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
    ):
        """Test that schema validation can be run on sample files.

        Note: Sample files may have implementation guide variations
        that don't match the base X12 schema perfectly. This test
        verifies validation runs without crashing, not that there
        are zero errors.
        """
        # Skip files with known issues
        known_bad_files = {
            "277_claim_status_response": "Sample file uses MSG segment not in base schema",
        }
        if x12_file.stem in known_bad_files:
            pytest.skip(known_bad_files[x12_file.stem])

        schema_loader = get_schema_loader_for_file(x12_file)
        result = parse_file(x12_file, schema_loader=schema_loader)

        assert result.interchange is not None

        assert len(result.interchange.groups) >= 1
        group = result.interchange.groups[0]

        txn = group.transactions[0]
        assert len(txn.errors) == 0, f"Expected no errors, got: {txn.errors}"

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
    ):
        """Test that element validation can be run on sample files."""
        schema_loader = get_schema_loader_for_file(x12_file)
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
    reason="X12 sample files not found",
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
    reason="X12 sample files not found",
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
    ):
        """Collect statistics for each parsed file."""
        schema_loader = get_schema_loader_for_file(x12_file)
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
