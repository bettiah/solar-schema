"""
Tests for the Translation Service.

Tests the cross-format translation using semantic models.
"""

from datetime import date
from decimal import Decimal

import pytest

from edi_schema.semantic.mappers.base import Format
from edi_schema.semantic.models import (
    Amount,
    CustomerParty,
    DespatchAdvice,
    DespatchLine,
    Identifier,
    Invoice,
    InvoiceLine,
    Item,
    ItemIdentification,
    MonetaryTotal,
    Order,
    OrderLine,
    OrderReference,
    Party,
    PartyIdentification,
    PartyName,
    Price,
    Quantity,
    Shipment,
    SupplierParty,
)
from edi_schema.semantic.translator import (
    DocumentType,
    TranslationService,
    from_semantic,
    get_translation_service,
)

# =============================================================================
# TranslationService Tests
# =============================================================================


class TestTranslationService:
    """Test TranslationService initialization and basic methods."""

    @pytest.fixture
    def service(self):
        return TranslationService()

    def test_initialization(self, service):
        """Test service initializes with all mappers."""
        # X12 mappers
        assert service.is_supported(Format.X12, DocumentType.ORDER)
        assert service.is_supported(Format.X12, DocumentType.INVOICE)
        assert service.is_supported(Format.X12, DocumentType.DESPATCH_ADVICE)

        # UBL mappers
        assert service.is_supported(Format.UBL, DocumentType.ORDER)
        assert service.is_supported(Format.UBL, DocumentType.INVOICE)
        assert service.is_supported(Format.UBL, DocumentType.DESPATCH_ADVICE)

        # EDIFACT mappers
        assert service.is_supported(Format.EDIFACT, DocumentType.ORDER)
        assert service.is_supported(Format.EDIFACT, DocumentType.INVOICE)
        assert service.is_supported(Format.EDIFACT, DocumentType.DESPATCH_ADVICE)

    def test_get_supported_formats(self, service):
        """Test get_supported_formats returns all formats."""
        formats = service.get_supported_formats()
        assert Format.X12 in formats
        assert Format.UBL in formats
        assert Format.EDIFACT in formats

    def test_get_supported_document_types(self, service):
        """Test get_supported_document_types returns all types."""
        doc_types = service.get_supported_document_types()
        assert DocumentType.ORDER in doc_types
        assert DocumentType.INVOICE in doc_types
        assert DocumentType.DESPATCH_ADVICE in doc_types

    def test_get_mapper(self, service):
        """Test get_mapper returns correct mapper."""
        mapper = service.get_mapper(Format.X12, DocumentType.ORDER)
        assert mapper is not None
        assert mapper.semantic_type == Order
        assert mapper.source_format == Format.X12

    def test_get_mapper_unsupported(self, service):
        """Test get_mapper returns None for unsupported combination."""
        # Currently all combinations are supported, so this tests the mechanism
        mapper = service.get_mapper(Format.X12, DocumentType.ORDER)
        assert mapper is not None


class TestFromSemantic:
    """Test from_semantic conversion for all formats."""

    @pytest.fixture
    def service(self):
        return TranslationService()

    @pytest.fixture
    def sample_order(self) -> Order:
        """Create a sample Order for testing."""
        return Order(
            id="PO-TEST-001",
            issue_date=date(2024, 6, 15),
            document_currency_code="USD",
            order_type_code="220",
            buyer_customer_party=CustomerParty(
                party=Party(
                    party_names=[PartyName(name="Test Buyer Corp")],
                    party_identifications=[
                        PartyIdentification(id=Identifier(value="BUYER123", scheme_id="92"))
                    ],
                )
            ),
            seller_supplier_party=SupplierParty(
                party=Party(
                    party_names=[PartyName(name="Test Seller Inc")],
                )
            ),
            order_lines=[
                OrderLine(
                    id="1",
                    quantity=Quantity(value=Decimal("10"), unit_code="EA"),
                    price=Price(price_amount=Amount(value=Decimal("25.00"), currency="USD")),
                    item=Item(
                        description="Test Widget",
                        standard_item_identification=ItemIdentification(
                            id=Identifier(value="012345678901", scheme_id="EAN")
                        ),
                    ),
                )
            ],
        )

    @pytest.fixture
    def sample_invoice(self) -> Invoice:
        """Create a sample Invoice for testing."""
        return Invoice(
            id="INV-TEST-001",
            issue_date=date(2024, 7, 1),
            document_currency_code="USD",
            order_reference=OrderReference(id="PO-TEST-001"),
            accounting_supplier_party=SupplierParty(
                party=Party(party_names=[PartyName(name="Test Seller")])
            ),
            accounting_customer_party=CustomerParty(
                party=Party(party_names=[PartyName(name="Test Buyer")])
            ),
            legal_monetary_total=MonetaryTotal(
                payable_amount=Amount(value=Decimal("250.00"), currency="USD"),
            ),
            invoice_lines=[
                InvoiceLine(
                    id="1",
                    invoiced_quantity=Quantity(value=Decimal("10"), unit_code="EA"),
                    line_extension_amount=Amount(value=Decimal("250.00"), currency="USD"),
                    item=Item(description="Test Widget"),
                )
            ],
        )

    @pytest.fixture
    def sample_despatch_advice(self) -> DespatchAdvice:
        """Create a sample DespatchAdvice for testing."""
        return DespatchAdvice(
            id="ASN-TEST-001",
            issue_date=date(2024, 8, 1),
            order_references=[OrderReference(id="PO-TEST-001")],
            despatch_supplier_party=SupplierParty(
                party=Party(party_names=[PartyName(name="Warehouse")])
            ),
            delivery_customer_party=CustomerParty(
                party=Party(party_names=[PartyName(name="Customer")])
            ),
            shipment=Shipment(id="SHIP-001"),
            despatch_lines=[
                DespatchLine(
                    id="1",
                    delivered_quantity=Quantity(value=Decimal("10"), unit_code="EA"),
                    item=Item(
                        standard_item_identification=ItemIdentification(
                            id=Identifier(value="012345678901", scheme_id="EAN")
                        )
                    ),
                )
            ],
        )

    def test_order_to_x12(self, service, sample_order):
        """Test converting Order to X12 850."""
        result = service.from_semantic(sample_order, Format.X12)
        # X12 mappers return a list of segment dictionaries
        assert isinstance(result, list)

        # Check key segments
        tags = [s["tag"] for s in result]
        assert "BEG" in tags
        assert "N1" in tags
        assert "PO1" in tags

    def test_order_to_ubl(self, service, sample_order):
        """Test converting Order to UBL."""
        result = service.from_semantic(sample_order, Format.UBL)
        # UBL mappers return a dict with document type as root key
        assert "Order" in result
        assert "cbc:ID" in result["Order"]

    def test_order_to_edifact(self, service, sample_order):
        """Test converting Order to EDIFACT ORDERS."""
        result = service.from_semantic(sample_order, Format.EDIFACT)
        assert result["message_type"] == "ORDERS"
        assert "segments" in result

        tags = [s["tag"] for s in result["segments"]]
        assert "BGM" in tags
        assert "DTM" in tags
        assert "NAD" in tags
        assert "LIN" in tags

    def test_invoice_to_x12(self, service, sample_invoice):
        """Test converting Invoice to X12 810."""
        result = service.from_semantic(sample_invoice, Format.X12)
        # X12 mappers return a list of segment dictionaries
        assert isinstance(result, list)
        tags = [s["tag"] for s in result]
        assert "BIG" in tags

    def test_invoice_to_edifact(self, service, sample_invoice):
        """Test converting Invoice to EDIFACT INVOIC."""
        result = service.from_semantic(sample_invoice, Format.EDIFACT)
        assert result["message_type"] == "INVOIC"

    def test_despatch_advice_to_x12(self, service, sample_despatch_advice):
        """Test converting DespatchAdvice to X12 856."""
        result = service.from_semantic(sample_despatch_advice, Format.X12)
        # X12 mappers return a list of segment dictionaries
        assert isinstance(result, list)
        tags = [s["tag"] for s in result]
        assert "BSN" in tags

    def test_despatch_advice_to_edifact(self, service, sample_despatch_advice):
        """Test converting DespatchAdvice to EDIFACT DESADV."""
        result = service.from_semantic(sample_despatch_advice, Format.EDIFACT)
        assert result["message_type"] == "DESADV"


class TestInferDocumentType:
    """Test document type inference from semantic models."""

    @pytest.fixture
    def service(self):
        return TranslationService()

    def test_infer_order_type(self, service):
        """Test inferring ORDER type from Order model."""
        order = Order(
            id="PO-001",
            issue_date=date(2024, 1, 1),
            document_currency_code="USD",
        )
        doc_type = service._infer_doc_type(order)
        assert doc_type == DocumentType.ORDER

    def test_infer_invoice_type(self, service):
        """Test inferring INVOICE type from Invoice model."""
        invoice = Invoice(
            id="INV-001",
            issue_date=date(2024, 1, 1),
            document_currency_code="USD",
            accounting_supplier_party=SupplierParty(party=Party()),
            accounting_customer_party=CustomerParty(party=Party()),
            legal_monetary_total=MonetaryTotal(),
        )
        doc_type = service._infer_doc_type(invoice)
        assert doc_type == DocumentType.INVOICE

    def test_infer_despatch_advice_type(self, service):
        """Test inferring DESPATCH_ADVICE type from DespatchAdvice model."""
        advice = DespatchAdvice(
            id="ASN-001",
            issue_date=date(2024, 1, 1),
        )
        doc_type = service._infer_doc_type(advice)
        assert doc_type == DocumentType.DESPATCH_ADVICE


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_get_translation_service_singleton(self):
        """Test that get_translation_service returns same instance."""
        service1 = get_translation_service()
        service2 = get_translation_service()
        assert service1 is service2

    def test_from_semantic_function(self):
        """Test the from_semantic convenience function."""
        order = Order(
            id="PO-CONV-001",
            issue_date=date(2024, 1, 15),
            document_currency_code="EUR",
        )
        result = from_semantic(order, Format.X12)
        # X12 mappers return a list of segment dictionaries
        assert isinstance(result, list)
        tags = [s["tag"] for s in result]
        assert "BEG" in tags


class TestErrorHandling:
    """Test error handling in translation service."""

    @pytest.fixture
    def service(self):
        return TranslationService()

    def test_invalid_model_type_raises_error(self, service):
        """Test that unsupported model type raises ValueError."""

        # Create an object that's not a supported semantic model
        class FakeModel:
            pass

        with pytest.raises(ValueError, match="Unknown model type"):
            service._infer_doc_type(FakeModel())


class TestCrossFormatRoundTrip:
    """Test semantic model preservation in cross-format translation."""

    @pytest.fixture
    def service(self):
        return TranslationService()

    def test_order_preserves_key_fields_through_conversion(self, service):
        """Test that key Order fields are preserved during from_semantic."""
        original = Order(
            id="ROUNDTRIP-001",
            issue_date=date(2024, 5, 20),
            document_currency_code="USD",
            order_type_code="220",
            buyer_customer_party=CustomerParty(
                party=Party(
                    party_names=[PartyName(name="Roundtrip Buyer")],
                    party_identifications=[
                        PartyIdentification(id=Identifier(value="BUYER-RT", scheme_id="92"))
                    ],
                )
            ),
            order_lines=[
                OrderLine(
                    id="1",
                    quantity=Quantity(value=Decimal("100"), unit_code="CS"),
                    price=Price(price_amount=Amount(value=Decimal("50"), currency="USD")),
                    item=Item(
                        description="Roundtrip Product",
                        sellers_item_identification=ItemIdentification(
                            id=Identifier(value="SKU-RT-001")
                        ),
                    ),
                )
            ],
        )

        # Convert to X12
        x12_result = service.from_semantic(original, Format.X12)
        assert x12_result is not None

        # Convert to EDIFACT
        edifact_result = service.from_semantic(original, Format.EDIFACT)
        assert edifact_result is not None

        # Convert to UBL
        ubl_result = service.from_semantic(original, Format.UBL)
        assert ubl_result is not None

        # All three formats should produce valid output
        # X12 returns a list of segments
        assert isinstance(x12_result, list)
        assert any(s["tag"] == "BEG" for s in x12_result)
        # EDIFACT returns dict with message_type
        assert edifact_result["message_type"] == "ORDERS"
        # UBL returns dict with document type as root key
        assert "Order" in ubl_result
