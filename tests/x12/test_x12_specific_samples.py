"""Snapshot tests for specific X12 sample files with detailed verification."""

from pathlib import Path

import pytest

from edi_schema.x12.ast import LoopInstance
from edi_schema.x12.parser import parse_file
from edi_schema.x12.schemas import GeneratedX12SchemaLoader

from .conftest import (
    HIPAA_SAMPLES_DIR,
    LOGISTICS_SAMPLES_DIR,
    SAMPLE_FILES,
    content_item_to_dict,
    interchange_to_dict,
)


@pytest.mark.skipif(
    not SAMPLE_FILES,
    reason="X12 sample files not found",
)
class TestSpecificSamples:
    """Tests for specific sample files with detailed verification."""

    def test_837p_professional_claim(
        self,
        schema_loader: GeneratedX12SchemaLoader,
        snapshot,
    ):
        """Test parsing 837P Professional Claim sample."""
        x12_file = HIPAA_SAMPLES_DIR / "837P_professional_claim.x12"
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
        loop_instances = [item for item in txn.content if isinstance(item, LoopInstance)]
        assert len(loop_instances) > 0

        parsed = interchange_to_dict(result.interchange)
        assert parsed == snapshot

    def test_835_remittance(
        self,
        schema_loader: GeneratedX12SchemaLoader,
        snapshot,
    ):
        """Test parsing 835 Remittance Advice sample."""
        x12_file = HIPAA_SAMPLES_DIR / "835_remittance.x12"
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
        x12_file = HIPAA_SAMPLES_DIR / "270_eligibility_inquiry.x12"
        if not x12_file.exists():
            pytest.skip(f"File not found: {x12_file}")

        result = parse_file(x12_file, schema_loader=schema_loader)

        assert result.interchange is not None

        group = result.interchange.groups[0]
        assert group.functional_id == "HS"

        txn = group.transactions[0]
        assert txn.transaction_id == "270"

        # 270 uses HL hierarchy
        loop_instances = [item for item in txn.content if isinstance(item, LoopInstance)]
        assert len(loop_instances) > 0

        parsed = interchange_to_dict(result.interchange)
        assert parsed == snapshot

    def test_850_purchase_order(
        self,
        snapshot,
    ):
        """Test parsing 850 Purchase Order sample from logistics directory."""
        x12_file = LOGISTICS_SAMPLES_DIR / "850_purchase_order.x12"
        if not x12_file.exists():
            pytest.skip(f"File not found: {x12_file}")

        # Use 004010 schema to match the sample file version
        schema_loader = GeneratedX12SchemaLoader(version="004010")
        result = parse_file(x12_file, schema_loader=schema_loader)

        assert result.interchange is not None

        # Verify structure
        assert result.interchange.version == "00401"
        assert len(result.interchange.groups) == 1

        group = result.interchange.groups[0]
        assert group.functional_id == "PO"

        txn = group.transactions[0]
        assert txn.transaction_id == "850"
        assert txn.schema is not None  # Schema should be attached

        # Verify no parsing errors
        assert len(txn.errors) == 0, f"Expected no errors, got: {txn.errors}"

        # Snapshot the parsed content structure
        content = [content_item_to_dict(item) for item in txn.content]
        assert content == snapshot
