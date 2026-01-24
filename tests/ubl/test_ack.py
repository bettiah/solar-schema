"""
Tests for UBL ApplicationResponse generation.
"""

import pytest

from edi_schema.ubl.ack import (
    ApplicationResponseBuilder,
    DocumentError,
    generate_application_response,
    LineError,
    ResponseCode,
)
from edi_schema.ubl.ast import (
    ErrorCategory,
    ParsedDocument,
    ParsedElement,
    ParseError,
)
from edi_schema.ubl.enums import Namespace
from edi_schema.ubl.validator import ValidationResult
from edi_schema.ubl.writer import DocumentBuilder, party


class TestResponseCode:
    """Tests for ResponseCode enum."""

    def test_accepted_code(self):
        assert ResponseCode.ACCEPTED.value == "AP"

    def test_rejected_code(self):
        assert ResponseCode.REJECTED.value == "RE"

    def test_acknowledged_code(self):
        assert ResponseCode.ACKNOWLEDGED.value == "AB"


class TestLineError:
    """Tests for LineError."""

    def test_basic_creation(self):
        error = LineError(line_id="1", description="Invalid amount")
        assert error.line_id == "1"
        assert error.response_code == ResponseCode.REJECTED
        assert error.description == "Invalid amount"

    def test_with_custom_code(self):
        error = LineError(
            line_id="2",
            response_code=ResponseCode.CONDITIONALLY_ACCEPTED,
            description="Warning",
        )
        assert error.response_code == ResponseCode.CONDITIONALLY_ACCEPTED


class TestDocumentError:
    """Tests for DocumentError."""

    def test_basic_creation(self):
        error = DocumentError(description="Validation failed")
        assert error.response_code == ResponseCode.REJECTED
        assert error.description == "Validation failed"
        assert len(error.line_errors) == 0

    def test_with_line_errors(self):
        error = DocumentError(
            description="Multiple errors",
            line_errors=[
                LineError(line_id="1", description="Error 1"),
                LineError(line_id="2", description="Error 2"),
            ],
        )
        assert len(error.line_errors) == 2


class TestApplicationResponseBuilder:
    """Tests for ApplicationResponseBuilder."""

    def test_basic_creation(self):
        builder = ApplicationResponseBuilder()
        builder.id("AR-001").issue_date("2024-01-15")
        doc = builder.build()

        assert doc.document_type == "ApplicationResponse"
        assert doc.root.find_child("ID").value == "AR-001"
        assert doc.root.find_child("IssueDate").value == "2024-01-15"

    def test_response_code(self):
        builder = (
            ApplicationResponseBuilder()
            .id("AR-001")
            .issue_date("2024-01-15")
            .response_code(ResponseCode.ACCEPTED)
        )
        doc = builder.build()

        # Check DocumentResponse exists
        doc_response = doc.root.find_child("DocumentResponse")
        assert doc_response is not None

    def test_document_reference(self):
        builder = (
            ApplicationResponseBuilder()
            .id("AR-001")
            .issue_date("2024-01-15")
            .document_reference("INV-001", "Invoice")
        )
        doc = builder.build()

        doc_ref = doc.root.find_child("DocumentReference")
        assert doc_ref is not None
        assert doc_ref.find_child("ID").value == "INV-001"
        assert doc_ref.find_child("DocumentType").value == "Invoice"

    def test_sender_party(self):
        builder = (
            ApplicationResponseBuilder()
            .id("AR-001")
            .issue_date("2024-01-15")
            .sender_party(lambda p: party(p).name("Sender Corp"))
        )
        doc = builder.build()

        sender = doc.root.find_child("SenderParty")
        assert sender is not None

    def test_receiver_party(self):
        builder = (
            ApplicationResponseBuilder()
            .id("AR-001")
            .issue_date("2024-01-15")
            .receiver_party(lambda p: party(p).name("Receiver Inc"))
        )
        doc = builder.build()

        receiver = doc.root.find_child("ReceiverParty")
        assert receiver is not None

    def test_add_document_error(self):
        error = DocumentError(
            response_code=ResponseCode.REJECTED,
            description="Validation failed",
            line_errors=[
                LineError(line_id="1", description="Invalid amount"),
            ],
        )
        builder = (
            ApplicationResponseBuilder()
            .id("AR-001")
            .issue_date("2024-01-15")
            .add_document_error(error)
        )
        doc = builder.build()

        doc_response = doc.root.find_child("DocumentResponse")
        assert doc_response is not None

    def test_to_xml(self):
        xml = (
            ApplicationResponseBuilder()
            .id("AR-001")
            .issue_date("2024-01-15")
            .response_code(ResponseCode.ACCEPTED)
            .to_xml()
        )

        assert "<?xml" in xml
        assert "ApplicationResponse" in xml
        assert "AR-001" in xml

    def test_note(self):
        builder = (
            ApplicationResponseBuilder()
            .id("AR-001")
            .issue_date("2024-01-15")
            .note("Document received successfully")
        )
        doc = builder.build()

        note = doc.root.find_child("Note")
        assert note is not None
        assert note.value == "Document received successfully"


class TestFromValidation:
    """Tests for ApplicationResponseBuilder.from_validation."""

    @pytest.fixture
    def valid_invoice(self):
        """Create a valid invoice document."""
        return (
            DocumentBuilder("Invoice")
            .id("INV-001")
            .issue_date("2024-01-15")
            .build()
        )

    @pytest.fixture
    def valid_result(self, valid_invoice):
        """Create a valid validation result."""
        return ValidationResult(document=valid_invoice)

    @pytest.fixture
    def invalid_result(self, valid_invoice):
        """Create an invalid validation result."""
        result = ValidationResult(document=valid_invoice)
        result.add_error(ParseError(
            code="MISSING_ELEMENT",
            message="Required element missing",
            category=ErrorCategory.SCHEMA,
        ))
        result.add_error(ParseError(
            code="INVALID_FORMAT",
            message="Invalid date format",
            category=ErrorCategory.ELEMENT,
            xpath="/Invoice/InvoiceLine[1]/Amount",
        ))
        return result

    def test_from_valid_result(self, valid_result, valid_invoice):
        builder = ApplicationResponseBuilder.from_validation(
            valid_result,
            valid_invoice,
        )
        doc = builder.build()

        assert doc.document_type == "ApplicationResponse"
        # Should have ID and IssueDate auto-generated
        assert doc.root.find_child("ID") is not None
        assert doc.root.find_child("IssueDate") is not None

    def test_accepted_for_valid(self, valid_result, valid_invoice):
        builder = ApplicationResponseBuilder.from_validation(
            valid_result,
            valid_invoice,
        )
        # Internal state should be ACCEPTED
        assert builder._response_code == ResponseCode.ACCEPTED

    def test_rejected_for_invalid(self, invalid_result, valid_invoice):
        builder = ApplicationResponseBuilder.from_validation(
            invalid_result,
            valid_invoice,
        )
        assert builder._response_code == ResponseCode.REJECTED

    def test_custom_response_id(self, valid_result, valid_invoice):
        builder = ApplicationResponseBuilder.from_validation(
            valid_result,
            valid_invoice,
            response_id="CUSTOM-AR-001",
        )
        doc = builder.build()
        assert doc.root.find_child("ID").value == "CUSTOM-AR-001"

    def test_custom_issue_date(self, valid_result, valid_invoice):
        builder = ApplicationResponseBuilder.from_validation(
            valid_result,
            valid_invoice,
            issue_date="2024-06-15",
        )
        doc = builder.build()
        assert doc.root.find_child("IssueDate").value == "2024-06-15"

    def test_document_reference_added(self, valid_result, valid_invoice):
        builder = ApplicationResponseBuilder.from_validation(
            valid_result,
            valid_invoice,
        )
        doc = builder.build()

        doc_ref = doc.root.find_child("DocumentReference")
        assert doc_ref is not None
        assert doc_ref.find_child("ID").value == "INV-001"
        assert doc_ref.find_child("DocumentType").value == "Invoice"

    def test_errors_converted(self, invalid_result, valid_invoice):
        builder = ApplicationResponseBuilder.from_validation(
            invalid_result,
            valid_invoice,
        )
        # Should have document errors
        assert len(builder._document_errors) > 0

    def test_with_sender_party(self, valid_result, valid_invoice):
        builder = ApplicationResponseBuilder.from_validation(
            valid_result,
            valid_invoice,
            sender_party=lambda p: party(p).name("Ack Sender"),
        )
        doc = builder.build()

        sender = doc.root.find_child("SenderParty")
        assert sender is not None


class TestGenerateApplicationResponse:
    """Tests for generate_application_response convenience function."""

    def test_generates_xml(self):
        doc = DocumentBuilder("Invoice").id("INV-001").build()
        result = ValidationResult(document=doc)

        xml = generate_application_response(result, doc)

        assert "<?xml" in xml
        assert "ApplicationResponse" in xml
        assert "INV-001" in xml

    def test_with_custom_options(self):
        doc = DocumentBuilder("Invoice").id("INV-001").build()
        result = ValidationResult(document=doc)

        xml = generate_application_response(
            result,
            doc,
            response_id="AR-CUSTOM",
            issue_date="2024-12-25",
        )

        assert "AR-CUSTOM" in xml
        assert "2024-12-25" in xml


class TestIntegration:
    """Integration tests for ApplicationResponse generation."""

    def test_complete_workflow(self):
        """Test complete validation and response workflow."""
        from edi_schema.ubl.parser import parse
        from edi_schema.ubl.writer import serialize

        # Build an invoice
        invoice = (
            DocumentBuilder("Invoice")
            .ubl_version_id("2.5")
            .id("INV-2024-001")
            .issue_date("2024-01-15")
            .document_currency_code("USD")
            .accounting_supplier_party(lambda p: party(p).name("Supplier"))
            .accounting_customer_party(lambda p: party(p).name("Customer"))
            .build()
        )

        # Parse it back (simulating receiving a document)
        invoice_xml = serialize(invoice)
        parse_result = parse(invoice_xml)
        assert parse_result.is_valid

        # Create validation result (assuming valid for this test)
        validation_result = ValidationResult(document=parse_result.document)

        # Generate ApplicationResponse
        response_xml = generate_application_response(
            validation_result,
            parse_result.document,
            response_id="AR-2024-001",
        )

        # Verify response
        assert "ApplicationResponse" in response_xml
        assert "AR-2024-001" in response_xml
        assert "INV-2024-001" in response_xml
        assert "Invoice" in response_xml

    def test_rejection_with_errors(self):
        """Test generating rejection response with errors."""
        # Build a document
        doc = (
            DocumentBuilder("Invoice")
            .id("INV-BAD-001")
            .issue_date("2024-01-15")
            .build()
        )

        # Create validation result with errors
        result = ValidationResult(document=doc)
        result.add_error(ParseError(
            code="MISSING_SUPPLIER",
            message="AccountingSupplierParty is required",
            category=ErrorCategory.SCHEMA,
        ))
        result.add_error(ParseError(
            code="MISSING_CUSTOMER",
            message="AccountingCustomerParty is required",
            category=ErrorCategory.SCHEMA,
        ))

        # Generate response
        response_xml = generate_application_response(result, doc)

        # Should be a rejection
        assert "RE" in response_xml or ResponseCode.REJECTED.value in response_xml
        assert "DocumentResponse" in response_xml
