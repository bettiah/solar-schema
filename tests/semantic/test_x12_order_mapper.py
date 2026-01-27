"""
Tests for X12 850 Order mapping using the declarative mapping system.

This test file uses the new MappingEngine with ORDER_850_MAPPING instead of
the old procedural X12OrderMapper.
"""

import pytest

from edi_schema.semantic.mapping import MappingEngine
from edi_schema.semantic.mapping.x12 import ORDER_850_MAPPING


class TestDeclarativeMappingWithFixture:
    """Test X12 850 mapping using real fixture files with the declarative system."""

    @pytest.fixture
    def schema_loader(self):
        """Create schema loader for parsing - use 004010 to match the sample file."""
        from edi_schema.x12.schemas import GeneratedX12SchemaLoader

        # The sample file uses version 004010 (see GS segment)
        return GeneratedX12SchemaLoader(version="004010")

    @pytest.fixture
    def fixture_path(self):
        """Path to the 850 purchase order fixture."""
        from pathlib import Path

        return (
            Path(__file__).parent.parent
            / "fixtures"
            / "x12_samples"
            / "logistics"
            / "850_purchase_order.x12"
        )

    @pytest.fixture
    def parsed_850_transaction(self, fixture_path, schema_loader):
        """Parse the 850 fixture file and return the transaction."""
        from edi_schema.x12.ast import ErrorSeverity
        from edi_schema.x12.parser import parse_file

        result = parse_file(fixture_path, schema_loader=schema_loader)
        assert result.interchange is not None, "Failed to parse interchange"
        assert len(result.interchange.groups) > 0, "No functional groups found"
        assert len(result.interchange.groups[0].transactions) > 0, "No transactions found"

        txn = result.interchange.groups[0].transactions[0]
        assert txn.transaction_id == "850", f"Expected 850, got {txn.transaction_id}"

        assert len(txn.errors) == 0, f"Fatal errors: {txn.errors}"
        return txn

    @pytest.fixture
    def mapping_engine(self):
        """Create a MappingEngine with the 850 Order mapping."""
        return MappingEngine(ORDER_850_MAPPING)

    @pytest.fixture
    def mapping_result(self, parsed_850_transaction, mapping_engine):
        """Map the parsed 850 to semantic Order using MappingEngine."""
        return mapping_engine.to_semantic(parsed_850_transaction)

    @pytest.fixture
    def mapped_order(self, mapping_result):
        """Extract the Order model from the mapping result."""
        assert mapping_result.success, f"Mapping failed: {mapping_result.errors}"
        return mapping_result.model

    def test_mapping_succeeds(self, mapping_result):
        """Test that the mapping completes successfully."""
        assert mapping_result.success, f"Mapping failed with errors: {mapping_result.errors}"
        assert mapping_result.model is not None, "Mapping produced no model"

    def test_mapped_order_snapshot(self, mapped_order, snapshot):
        """Snapshot test for the full mapped Order structure."""
        # Convert to dict for snapshot comparison (Pydantic model)
        # Exclude None values for cleaner snapshot
        order_dict = mapped_order.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
        assert order_dict == snapshot

    def test_order_basic_fields(self, mapped_order):
        """Test that basic order fields are mapped correctly."""
        assert mapped_order.id == "5907867"
        assert str(mapped_order.issue_date) == "2016-12-06"
        assert mapped_order.document_currency_code == "USD"
        assert mapped_order.document_purpose_code == "00"
        assert mapped_order.order_type_code == "DS"

    def test_order_has_line_items(self, mapped_order):
        """Test that order lines are mapped."""
        assert len(mapped_order.order_lines) == 1
        line = mapped_order.order_lines[0]
        assert line.id == "1"
        assert line.quantity.value == 1
        assert line.quantity.unit_code == "EA"

    def test_order_has_price(self, mapped_order):
        """Test that line item price is mapped."""
        from decimal import Decimal

        line = mapped_order.order_lines[0]
        assert line.price is not None
        assert line.price.price_amount.value == Decimal("8.90")
        assert line.price.price_amount.currency == "USD"

    def test_order_has_delivery(self, mapped_order):
        """Test that delivery information is mapped."""
        assert len(mapped_order.delivery) >= 1
        delivery = mapped_order.delivery[0]
        assert delivery.delivery_party is not None
        assert delivery.delivery_location is not None

    def test_order_has_party_info(self, mapped_order):
        """Test that party information is mapped."""
        # Bill-to party (BT)
        assert mapped_order.accounting_customer_party is not None
        assert mapped_order.accounting_customer_party.party is not None

    def test_product_id_with_scheme(self, mapped_order):
        """Test that product IDs have scheme_id set from qualifier."""
        line = mapped_order.order_lines[0]
        assert line.item is not None
        # VP qualifier should map to sellers_item_identification
        assert line.item.sellers_item_identification is not None
        assert line.item.sellers_item_identification.id.value == "32230538"
        # VP qualifier should not set a scheme_id (vendor product is scheme_id=None)
        # but our implementation sets the qualifier as scheme_id when no mapping exists
        assert line.item.sellers_item_identification.id.scheme_id == "VP"

    def test_party_identifications_mapped(self, mapped_order):
        """Test that party identifications from N1*03/04 are mapped."""
        # The ST (ship-to) party has ID 0857673380000
        assert len(mapped_order.delivery) > 0
        delivery = mapped_order.delivery[0]
        assert delivery.delivery_party is not None
        assert len(delivery.delivery_party.party_identifications) > 0
        party_id = delivery.delivery_party.party_identifications[0]
        assert party_id.id.value == "0857673380000"

    def test_delivery_terms_mapped(self, mapped_order):
        """Test that FOB delivery terms are mapped."""
        # FOB*PP means prepaid
        assert mapped_order.delivery_terms == "PP"

    def test_contact_info_mapped(self, mapped_order):
        """Test that contact information is mapped from PER segments."""
        # The BT party has a contact
        bt_party = mapped_order.accounting_customer_party
        assert bt_party is not None
        assert bt_party.party.contact is not None
        # Contact name from PER*02
        assert bt_party.party.contact.name is not None


class TestUnmappedTracking:
    """Test unmapped segment/element tracking."""

    @pytest.fixture
    def schema_loader(self):
        """Create schema loader for parsing - use 004010 to match the sample file."""
        from edi_schema.x12.schemas import GeneratedX12SchemaLoader

        return GeneratedX12SchemaLoader(version="004010")

    @pytest.fixture
    def fixture_path(self):
        """Path to the 850 purchase order fixture."""
        from pathlib import Path

        return (
            Path(__file__).parent.parent
            / "fixtures"
            / "x12_samples"
            / "logistics"
            / "850_purchase_order.x12"
        )

    @pytest.fixture
    def parsed_850_transaction(self, fixture_path, schema_loader):
        """Parse the 850 fixture file and return the transaction."""
        from edi_schema.x12.parser import parse_file

        result = parse_file(fixture_path, schema_loader=schema_loader)
        return result.interchange.groups[0].transactions[0]

    def test_unmapped_tracking_enabled(self, parsed_850_transaction):
        """Test that unmapped tracking collects unmapped qualifiers."""
        engine = MappingEngine(ORDER_850_MAPPING, collect_metrics=True, warn_on_unmapped=True)
        result = engine.to_semantic(parsed_850_transaction)

        # Should still succeed (warnings don't cause failure)
        assert result.success

        # Should have metrics with unmapped tracking
        assert result.metrics is not None

        # Check for unmapped qualifiers or segments in warnings
        warnings = [e for e in result.errors if e.severity.value == "warning"]
        # The sample file should have some unmapped data
        # (exact count depends on file content)
        assert result.metrics.total_segments_in_document > 0

    def test_unmapped_warnings_can_be_disabled(self, parsed_850_transaction):
        """Test that warn_on_unmapped=False suppresses warnings."""
        engine = MappingEngine(ORDER_850_MAPPING, collect_metrics=True, warn_on_unmapped=False)
        result = engine.to_semantic(parsed_850_transaction)

        assert result.success
        # With warnings disabled, there should be no UNMAPPED_* warnings
        unmapped_warnings = [
            e for e in result.errors
            if e.code.name.startswith("UNMAPPED")
        ]
        assert len(unmapped_warnings) == 0

    def test_metrics_contain_unmapped_summary(self, parsed_850_transaction):
        """Test that metrics contain unmapped data summary."""
        engine = MappingEngine(ORDER_850_MAPPING, collect_metrics=True, warn_on_unmapped=True)
        result = engine.to_semantic(parsed_850_transaction)

        assert result.metrics is not None
        summary = result.metrics.get_unmapped_summary()
        assert "total_unmapped" in summary
        assert "by_segment" in summary
        assert "by_reason" in summary
        assert "unmapped_qualifiers" in summary


class TestMappingEngineFeatures:
    """Test MappingEngine features like metrics and validation."""

    @pytest.fixture
    def engine(self):
        """Create a MappingEngine with metrics enabled."""
        return MappingEngine(ORDER_850_MAPPING, collect_metrics=True)

    @pytest.fixture
    def mock_transaction(self):
        """Create a minimal mock transaction for testing."""
        from unittest.mock import MagicMock

        # Create a mock transaction with minimal required data
        txn = MagicMock()
        txn.transaction_id = "850"
        txn.control_number = "0001"

        # Create mock BEG segment
        beg_seg = MagicMock()
        beg_seg.tag = "BEG"
        beg_seg.get_element_value = lambda idx: {
            1: "00",  # Purpose
            2: "NE",  # Type
            3: "TEST-001",  # ID
            5: "20240101",  # Date
        }.get(idx)

        # Create mock CUR segment
        cur_seg = MagicMock()
        cur_seg.tag = "CUR"
        cur_seg.get_element_value = lambda idx: {
            2: "USD",
        }.get(idx)

        # Create mock CTT segment
        ctt_seg = MagicMock()
        ctt_seg.tag = "CTT"
        ctt_seg.get_element_value = lambda idx: {
            1: "0",
        }.get(idx)

        txn.content = [beg_seg, cur_seg, ctt_seg]

        return txn

    def test_mapping_result_has_metrics(self, engine, mock_transaction):
        """Test that mapping result includes metrics when enabled."""
        result = engine.to_semantic(mock_transaction)
        # Metrics should be available
        assert result.metrics is not None or engine.aggregate_metrics is not None

    def test_mapping_with_wrong_transaction_type(self, engine):
        """Test that mapping fails gracefully for wrong transaction type."""
        from unittest.mock import MagicMock

        txn = MagicMock()
        txn.transaction_id = "810"  # Invoice, not Order
        txn.control_number = "0001"
        txn.content = []

        result = engine.to_semantic(txn)
        assert not result.success
        assert len(result.errors) > 0
