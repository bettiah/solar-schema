"""
Tests for parsing official UBL 2.5 example files.

These tests parse all 76 example XML files from the UBL 2.5 distribution
and verify the parsed output matches expected structures.

Snapshot testing with syrupy:
  - First run creates snapshots: pytest tests/ubl/test_example_files.py
  - Update snapshots: pytest tests/ubl/test_example_files.py --snapshot-update
"""

from pathlib import Path

import pytest

from edi_schema.ubl.parser import parse_file

# Path to UBL 2.5 example XML files
UBL_EXAMPLES_DIR = Path("/Users/me/Downloads/edi/ubl/UBL-2.5/xml")


def get_example_files() -> list[Path]:
    """Get all XML example files from the UBL 2.5 distribution."""
    if not UBL_EXAMPLES_DIR.exists():
        return []
    return sorted(UBL_EXAMPLES_DIR.glob("*.xml"))


# Get list of example files for parametrization
EXAMPLE_FILES = get_example_files()


@pytest.mark.skipif(
    not EXAMPLE_FILES,
    reason=f"UBL example files not found at {UBL_EXAMPLES_DIR}",
)
class TestUBLExampleFiles:
    """Tests for parsing official UBL 2.5 example files."""

    @pytest.mark.parametrize(
        "xml_file",
        EXAMPLE_FILES,
        ids=[f.stem for f in EXAMPLE_FILES],
    )
    def test_parse_example_file(self, xml_file: Path, snapshot):
        """Parse example file and verify structure matches snapshot."""
        result = parse_file(xml_file)

        assert result.is_valid, f"Parse failed: {result.errors}"
        assert result.document is not None

        parsed = result.document.root.to_dict()
        assert parsed == snapshot


class TestSpecificExamples:
    """Tests for specific example files with exact output comparison."""

    @pytest.mark.skipif(
        not EXAMPLE_FILES,
        reason=f"UBL example files not found at {UBL_EXAMPLES_DIR}",
    )
    def test_invoice_trivial(self, snapshot):
        """Test parsing the trivial invoice example."""
        xml_file = UBL_EXAMPLES_DIR / "UBL-Invoice-2.1-Example-Trivial.xml"
        if not xml_file.exists():
            pytest.skip(f"File not found: {xml_file}")

        result = parse_file(xml_file)

        assert result.is_valid
        assert result.document is not None
        assert result.document.document_type == "Invoice"

        parsed = result.document.root.to_dict()
        assert parsed == snapshot

    @pytest.mark.skipif(
        not EXAMPLE_FILES,
        reason=f"UBL example files not found at {UBL_EXAMPLES_DIR}",
    )
    def test_order_example(self, snapshot):
        """Test parsing the Order 2.0 example."""
        xml_file = UBL_EXAMPLES_DIR / "UBL-Order-2.0-Example.xml"
        if not xml_file.exists():
            pytest.skip(f"File not found: {xml_file}")

        result = parse_file(xml_file)

        assert result.is_valid
        assert result.document is not None
        assert result.document.document_type == "Order"
        assert result.document.version == "2.0"

        parsed = result.document.root.to_dict()
        assert parsed == snapshot

    @pytest.mark.skipif(
        not EXAMPLE_FILES,
        reason=f"UBL example files not found at {UBL_EXAMPLES_DIR}",
    )
    def test_debit_note_example(self, snapshot):
        """Test parsing the DebitNote 2.5 example."""
        xml_file = UBL_EXAMPLES_DIR / "UBL-DebitNote-2.5-Example.xml"
        if not xml_file.exists():
            pytest.skip(f"File not found: {xml_file}")

        result = parse_file(xml_file)

        assert result.is_valid
        assert result.document is not None
        assert result.document.document_type == "DebitNote"
        assert result.document.version == "2.5"

        parsed = result.document.root.to_dict()
        assert parsed == snapshot


class TestDocumentTypeDetection:
    """Tests for document type detection across all example files."""

    # Expected document types for each file
    EXPECTED_TYPES = {
        "MyTransportationStatus": "TransportationStatus",
        "UBL-BusinessCard-2.2-Example": "BusinessCard",
        "UBL-CommonTransportationReport-2.3-Example": "CommonTransportationReport",
        "UBL-CreditNote-2.0-Example": "CreditNote",
        "UBL-CreditNote-2.1-Example": "CreditNote",
        "UBL-DebitNote-2.5-Example": "DebitNote",
        "UBL-DespatchAdvice-2.0-Example": "DespatchAdvice",
        "UBL-DigitalAgreement-2.2-Example": "DigitalAgreement",
        "UBL-DigitalAgreement-2.2-Example-Multilateral": "DigitalAgreement",
        "UBL-DigitalCapability-2.2-Example": "DigitalCapability",
        "UBL-ExceptionCriteria-2.1-Example": "ExceptionCriteria",
        "UBL-ExceptionNotification-2.1-Example": "ExceptionNotification",
        "UBL-ExportCustomsDeclaration-2.3-Example": "ExportCustomsDeclaration",
        "UBL-ExpressionOfInterestRequest-2.2-Example": "ExpressionOfInterestRequest",
        "UBL-Forecast-2.1-Example": "Forecast",
        "UBL-ForecastRevision-2.1-Example": "ForecastRevision",
        "UBL-ForwardingInstructions-2.0-Example-International": "ForwardingInstructions",
        "UBL-FulfilmentCancellation-2.1-Example": "FulfilmentCancellation",
        "UBL-GoodsCertificate-2.3-Example": "GoodsCertificate",
        "UBL-GoodsItemItinerary-2.1-Example": "GoodsItemItinerary",
        "UBL-GoodsItemPassport-2.3-Example-Issued": "GoodsItemPassport",
        "UBL-ImportCustomsDeclaration-2.3-Example": "ImportCustomsDeclaration",
        "UBL-InstructionForReturns-2.1-Example": "InstructionForReturns",
        "UBL-InventoryReport-2.1-Example": "InventoryReport",
        "UBL-Invoice-2.0-Detached": "Invoice",
        "UBL-Invoice-2.0-Detached-Signature": "Signature",
        "UBL-Invoice-2.0-Enveloped": "Invoice",
        "UBL-Invoice-2.0-Example": "Invoice",
        "UBL-Invoice-2.0-Example-NS1": "Invoice",
        "UBL-Invoice-2.0-Example-NS2": "Invoice",
        "UBL-Invoice-2.0-Example-NS3": "Invoice",
        "UBL-Invoice-2.0-Example-NS4": "Invoice",
        "UBL-Invoice-2.1-Example": "Invoice",
        "UBL-Invoice-2.1-Example-Trivial": "Invoice",
        "UBL-Manifest-2.3-Example-Reference-Only": "Manifest",
        "UBL-Manifest-2.3-Example-Shipment": "Manifest",
        "UBL-Order-2.0-Example": "Order",
        "UBL-Order-2.0-Example-International": "Order",
        "UBL-Order-2.1-Example": "Order",
        "UBL-OrderCancellation-2.1-Example": "OrderCancellation",
        "UBL-OrderChange-2.1-Example": "OrderChange",
        "UBL-OrderResponse-2.1-Example": "OrderResponse",
        "UBL-OrderResponseSimple-2.0-Example": "OrderResponseSimple",
        "UBL-OrderResponseSimple-2.1-Example": "OrderResponseSimple",
        "UBL-PriorInformationNotice-2.2-Example-Embedded": "PriorInformationNotice",
        "UBL-PriorInformationNotice-2.2-Example-External": "PriorInformationNotice",
        "UBL-ProductActivity-2.1-Example-1": "ProductActivity",
        "UBL-ProductActivity-2.1-Example-2": "ProductActivity",
        "UBL-ProductActivity-2.1-Example-3": "ProductActivity",
        "UBL-ProofOfReexportation-2.3-Example": "ProofOfReexportation",
        "UBL-ProofOfReexportationReminder-2.3-Example": "ProofOfReexportationReminder",
        "UBL-ProofOfReexportationRequest-2.3-Example": "ProofOfReexportationRequest",
        "UBL-PurchaseReceipt-2.4-Example": "PurchaseReceipt",
        "UBL-Quotation-2.0-Example": "Quotation",
        "UBL-Quotation-2.1-Example": "Quotation",
        "UBL-ReceiptAdvice-2.0-Example": "ReceiptAdvice",
        "UBL-Reminder-2.1-Example": "Reminder",
        "UBL-RemittanceAdvice-2.0-Example": "RemittanceAdvice",
        "UBL-RequestForQuotation-2.0-Example": "RequestForQuotation",
        "UBL-RequestForQuotation-2.1-Example": "RequestForQuotation",
        "UBL-RetailEvent-2.1-Example": "RetailEvent",
        "UBL-SelfBilledCreditNote-2.1-Example": "SelfBilledCreditNote",
        "UBL-Statement-2.0-Example": "Statement",
        "UBL-StockAvailabilityReport-2.1-Example": "StockAvailabilityReport",
        "UBL-TradeItemLocationProfile-2.1-Example": "TradeItemLocationProfile",
        "UBL-TransitCustomsDeclaration-2.3-Example": "TransitCustomsDeclaration",
        "UBL-TransportExecutionPlan-2.1-Example": "TransportExecutionPlan",
        "UBL-TransportExecutionPlanRequest-2.1-Example": "TransportExecutionPlanRequest",
        "UBL-TransportProgressStatus-2.1-Example": "TransportProgressStatus",
        "UBL-TransportProgressStatusRequest-2.1-Example": "TransportProgressStatusRequest",
        "UBL-TransportServiceDescription-2.1-Example": "TransportServiceDescription",
        "UBL-TransportServiceDescriptionRequest-2.1-Example": "TransportServiceDescriptionRequest",
        "UBL-TransportationStatus-2.1-Example": "TransportationStatus",
        "UBL-TransportationStatusRequest-2.1-Example": "TransportationStatusRequest",
        "UBL-Waybill-2.0-Example-International": "Waybill",
        "UBL-WeightStatement-2.2-Example": "WeightStatement",
    }

    @pytest.mark.skipif(
        not EXAMPLE_FILES,
        reason=f"UBL example files not found at {UBL_EXAMPLES_DIR}",
    )
    @pytest.mark.parametrize(
        "xml_file",
        EXAMPLE_FILES,
        ids=[f.stem for f in EXAMPLE_FILES],
    )
    def test_document_type_matches_expected(self, xml_file: Path):
        """Verify document type matches expected for each file."""
        result = parse_file(xml_file)

        assert result.is_valid, f"Parse failed: {result.errors}"
        assert result.document is not None

        file_stem = xml_file.stem
        expected_type = self.EXPECTED_TYPES.get(file_stem)

        # TEMP: Print for verification
        print(f"\nFile: {file_stem}")
        print(f"Expected: {expected_type}")
        print(f"Actual: {result.document.document_type}")

        if expected_type:
            assert result.document.document_type == expected_type, (
                f"Document type mismatch for {file_stem}: "
                f"expected {expected_type}, got {result.document.document_type}"
            )


class TestParseStatistics:
    """Tests for parse statistics across example files."""

    @pytest.mark.skipif(
        not EXAMPLE_FILES,
        reason=f"UBL example files not found at {UBL_EXAMPLES_DIR}",
    )
    @pytest.mark.parametrize(
        "xml_file",
        EXAMPLE_FILES,
        ids=[f.stem for f in EXAMPLE_FILES],
    )
    def test_statistics_for_example_file(self, xml_file: Path):
        """Collect statistics for each parsed file."""
        from edi_schema.ubl.ast import ParseStatistics

        result = parse_file(xml_file)

        assert result.is_valid
        assert result.document is not None

        stats = ParseStatistics.from_document(result.document)

        # TEMP: Print statistics
        print(f"\n=== Stats for {xml_file.name} ===")
        print(f"Document Type: {stats.document_type}")
        print(f"Element Count: {stats.element_count}")
        print(f"Attribute Count: {stats.attribute_count}")
        print(f"Max Depth: {stats.depth}")

        # Basic sanity checks
        assert stats.element_count > 0
        assert stats.depth > 0
