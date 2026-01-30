"""Tests for BuilderMappingEngine with 810 Invoice."""

import pytest

from edi_schema.semantic.mapping import BuilderMappingEngine, MappingEngine
from edi_schema.semantic.mapping.x12 import INVOICE_810_MAPPING


@pytest.fixture
def schema_loader_004010():
    from edi_schema.x12.schemas import GeneratedX12SchemaLoader
    return GeneratedX12SchemaLoader(version="004010")


@pytest.fixture
def parsed_810(schema_loader_004010):
    from pathlib import Path

    path = (
        Path(__file__).parent.parent
        / "fixtures"
        / "x12_samples"
        / "logistics"
        / "810_invoice.x12"
    )
    if not path.exists():
        pytest.skip("810 fixture not found")

    from edi_schema.x12.parser import parse_file
    result = parse_file(path, schema_loader=schema_loader_004010)
    assert result.interchange is not None
    txn = result.interchange.groups[0].transactions[0]
    assert txn.transaction_id == "810"
    return txn


class TestBuilderEngine810:
    """Test BuilderMappingEngine with 810 Invoice."""

    @pytest.fixture
    def builder_engine(self):
        return BuilderMappingEngine(INVOICE_810_MAPPING)

    @pytest.fixture
    def builder_result(self, parsed_810, builder_engine):
        return builder_engine.to_semantic(parsed_810)

    @pytest.fixture
    def builder_invoice(self, builder_result):
        assert builder_result.success, f"Builder mapping failed: {builder_result.errors}"
        return builder_result.model

    def test_builder_mapping_succeeds(self, builder_result):
        assert builder_result.success, f"Mapping failed: {builder_result.errors}"
        assert builder_result.model is not None

    def test_basic_fields(self, builder_invoice):
        assert builder_invoice.id is not None
        assert builder_invoice.issue_date is not None

    def test_comparison_with_old_engine(self, parsed_810, builder_engine):
        """Compare builder output with old engine output."""
        old_engine = MappingEngine(INVOICE_810_MAPPING)
        builder_result = builder_engine.to_semantic(parsed_810)
        old_result = old_engine.to_semantic(parsed_810)

        assert builder_result.success == old_result.success

        builder_dict = builder_result.model.model_dump(
            mode="json", exclude_none=True, exclude_defaults=True,
        )
        old_dict = old_result.model.model_dump(
            mode="json", exclude_none=True, exclude_defaults=True,
        )

        assert builder_dict.get("id") == old_dict.get("id")
        assert builder_dict.get("issue_date") == old_dict.get("issue_date")

    def test_snapshot(self, builder_invoice, snapshot):
        """Snapshot test for full builder output."""
        invoice_dict = builder_invoice.model_dump(
            mode="json", exclude_none=True, exclude_defaults=True,
        )
        assert invoice_dict == snapshot
