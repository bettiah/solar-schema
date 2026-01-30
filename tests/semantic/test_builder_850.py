"""Tests for BuilderMappingEngine with 850 Purchase Order."""

from decimal import Decimal

import pytest

from edi_schema.semantic.mapping import BuilderMappingEngine
from edi_schema.semantic.mapping.x12 import ORDER_850_MAPPING


@pytest.fixture
def schema_loader_004010():
    from edi_schema.x12.schemas import GeneratedX12SchemaLoader
    return GeneratedX12SchemaLoader(version="004010")


@pytest.fixture
def fixture_850_path():
    from pathlib import Path
    return (
        Path(__file__).parent.parent
        / "fixtures"
        / "x12_samples"
        / "logistics"
        / "850_purchase_order.x12"
    )


@pytest.fixture
def parsed_850(fixture_850_path, schema_loader_004010):
    from edi_schema.x12.parser import parse_file
    result = parse_file(fixture_850_path, schema_loader=schema_loader_004010)
    assert result.interchange is not None
    txn = result.interchange.groups[0].transactions[0]
    assert txn.transaction_id == "850"
    return txn


class TestBuilderEngine850:
    """Test BuilderMappingEngine with 850 Purchase Order."""

    @pytest.fixture
    def builder_engine(self):
        return BuilderMappingEngine(ORDER_850_MAPPING)

    @pytest.fixture
    def builder_result(self, parsed_850, builder_engine):
        return builder_engine.to_semantic(parsed_850)

    @pytest.fixture
    def builder_order(self, builder_result):
        assert builder_result.success, f"Builder mapping failed: {builder_result.errors}"
        return builder_result.model

    def test_builder_mapping_succeeds(self, builder_result):
        assert builder_result.success, f"Mapping failed: {builder_result.errors}"
        assert builder_result.model is not None

    def test_basic_fields(self, builder_order):
        assert builder_order.id == "5907867"
        assert str(builder_order.issue_date) == "2016-12-06"
        assert builder_order.document_currency_code == "USD"
        assert builder_order.document_purpose_code == "00"
        assert builder_order.order_type_code == "DS"

    def test_line_items(self, builder_order):
        assert len(builder_order.order_lines) == 1
        line = builder_order.order_lines[0]
        assert line.id == "1"
        assert line.quantity.value == 1
        assert line.quantity.unit_code == "EA"

    def test_price(self, builder_order):
        line = builder_order.order_lines[0]
        assert line.price is not None
        assert line.price.price_amount.value == Decimal("8.90")
        assert line.price.price_amount.currency == "USD"

    def test_delivery(self, builder_order):
        assert len(builder_order.delivery) >= 1
        delivery = builder_order.delivery[0]
        assert delivery.delivery_party is not None
        assert delivery.delivery_location is not None

    def test_party_info(self, builder_order):
        assert builder_order.accounting_customer_party is not None
        assert builder_order.accounting_customer_party.party is not None

    def test_product_id_with_scheme(self, builder_order):
        line = builder_order.order_lines[0]
        assert line.item is not None
        assert line.item.sellers_item_identification is not None
        assert line.item.sellers_item_identification.id.value == "32230538"
        assert line.item.sellers_item_identification.id.scheme_id == "VP"

    def test_party_identifications(self, builder_order):
        assert len(builder_order.delivery) > 0
        delivery = builder_order.delivery[0]
        assert delivery.delivery_party is not None
        assert len(delivery.delivery_party.party_identifications) > 0
        party_id = delivery.delivery_party.party_identifications[0]
        assert party_id.id.value == "0857673380000"

    def test_delivery_terms(self, builder_order):
        assert builder_order.delivery_terms == "PP"

    def test_fob_delivery_terms(self, builder_order):
        assert len(builder_order.delivery) >= 1
        delivery = builder_order.delivery[0]
        assert delivery.delivery_terms is not None
        assert delivery.delivery_terms.loss_risk_responsibility_code == "ZZ"
        assert delivery.delivery_terms.special_terms == "UPS Ground #442E1W"

    def test_header_per_mapped(self, builder_order):
        assert builder_order.buyer_customer_party is not None
        assert builder_order.buyer_customer_party.buyer_contact is not None
        contact = builder_order.buyer_customer_party.buyer_contact
        assert contact.name == "Donna Person"
        assert contact.telephone is not None
        assert "4255552515" in contact.telephone
        assert contact.telefax == "4255553875"

    def test_contact_info_mapped(self, builder_order):
        bt_party = builder_order.accounting_customer_party
        assert bt_party is not None
        assert bt_party.party.contact is not None
        assert bt_party.party.contact.name is not None

    def test_snapshot(self, builder_order, snapshot):
        """Snapshot test for full builder output."""
        order_dict = builder_order.model_dump(
            mode="json", exclude_none=True, exclude_defaults=True,
        )
        assert order_dict == snapshot
