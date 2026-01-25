"""
Tests for UBL document parser.
"""


import pytest

from edi_schema.ubl.ast import (
    ErrorCategory,
    ErrorSeverity,
    ParsedAttribute,
    ParsedDocument,
    ParsedElement,
    ParseError,
    ParseResult,
    ParseStatistics,
    SourcePosition,
)
from edi_schema.ubl.parser import parse, parse_with_schema, parse_xml

# Sample UBL Invoice XML
SAMPLE_INVOICE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
    <cbc:UBLVersionID>2.5</cbc:UBLVersionID>
    <cbc:ID>INV-001</cbc:ID>
    <cbc:IssueDate>2024-01-15</cbc:IssueDate>
    <cbc:Note>Test invoice</cbc:Note>
    <cac:AccountingSupplierParty>
        <cac:Party>
            <cbc:EndpointID>12345</cbc:EndpointID>
            <cac:PartyName>
                <cbc:Name>Supplier Corp</cbc:Name>
            </cac:PartyName>
        </cac:Party>
    </cac:AccountingSupplierParty>
    <cac:AccountingCustomerParty>
        <cac:Party>
            <cac:PartyName>
                <cbc:Name>Customer Inc</cbc:Name>
            </cac:PartyName>
        </cac:Party>
    </cac:AccountingCustomerParty>
    <cac:LegalMonetaryTotal>
        <cbc:PayableAmount currencyID="USD">100.00</cbc:PayableAmount>
    </cac:LegalMonetaryTotal>
    <cac:InvoiceLine>
        <cbc:ID>1</cbc:ID>
        <cbc:LineExtensionAmount currencyID="USD">100.00</cbc:LineExtensionAmount>
    </cac:InvoiceLine>
</Invoice>
"""

MALFORMED_XML = """<?xml version="1.0"?>
<Invoice>
    <ID>Test</ID>
    <Unclosed>
</Invoice>
"""


class TestSourcePosition:
    """Tests for SourcePosition."""

    def test_basic_creation(self):
        pos = SourcePosition(line=10, column=5)
        assert pos.line == 10
        assert pos.column == 5
        assert pos.xpath == ""

    def test_with_xpath(self):
        pos = SourcePosition(line=10, column=5, xpath="/Invoice/ID")
        assert "/Invoice/ID" in str(pos)

    def test_str_representation(self):
        pos = SourcePosition(line=10, column=5)
        assert "line 10" in str(pos)
        assert "column 5" in str(pos)


class TestParsedElement:
    """Tests for ParsedElement."""

    def test_basic_creation(self):
        elem = ParsedElement(
            tag="ID",
            namespace="urn:test",
            value="TEST-001",
        )
        assert elem.tag == "ID"
        assert elem.value == "TEST-001"
        assert elem.qualified_name == "{urn:test}ID"

    def test_with_attributes(self):
        elem = ParsedElement(
            tag="Amount",
            namespace="",
            value="100.00",
            attributes=[
                ParsedAttribute(name="currencyID", value="USD"),
            ],
        )
        assert elem.get_attribute("currencyID") == "USD"
        assert elem.get_attribute("nonexistent") is None

    def test_with_children(self):
        child = ParsedElement(tag="Name", namespace="", value="Test")
        parent = ParsedElement(
            tag="Party",
            namespace="",
            children=[child],
        )
        assert parent.find_child("Name") == child
        assert parent.find_child("Unknown") is None
        assert parent.find_all_children("Name") == [child]

    def test_get_text(self):
        elem = ParsedElement(tag="ID", namespace="", value="TEST")
        assert elem.get_text() == "TEST"

    def test_to_dict(self):
        elem = ParsedElement(
            tag="ID",
            namespace="",
            value="TEST",
            attributes=[ParsedAttribute(name="scheme", value="ABC")],
        )
        d = elem.to_dict()
        assert d["tag"] == "ID"
        assert d["value"] == "TEST"
        assert d["attributes"]["scheme"] == "ABC"


class TestParsedDocument:
    """Tests for ParsedDocument."""

    def test_basic_creation(self):
        root = ParsedElement(tag="Invoice", namespace="urn:test")
        doc = ParsedDocument(
            document_type="Invoice",
            version="2.5",
            root=root,
        )
        assert doc.document_type == "Invoice"
        assert doc.version == "2.5"

    def test_get_value(self):
        child = ParsedElement(
            tag="ID",
            namespace="",
            value="INV-001",
        )
        root = ParsedElement(
            tag="Invoice",
            namespace="",
            children=[child],
        )
        doc = ParsedDocument(
            document_type="Invoice",
            version="2.5",
            root=root,
        )
        assert doc.get_value("ID") == "INV-001"
        assert doc.get_value("Unknown") is None


class TestParseError:
    """Tests for ParseError."""

    def test_basic_creation(self):
        error = ParseError(
            code="TEST_ERROR",
            message="Test error message",
        )
        assert error.code == "TEST_ERROR"
        assert error.severity == ErrorSeverity.ERROR
        assert "TEST_ERROR" in str(error)

    def test_with_position(self):
        error = ParseError(
            code="TEST_ERROR",
            message="Test error",
            position=SourcePosition(line=10, column=5),
        )
        assert "line 10" in str(error)


class TestParseResult:
    """Tests for ParseResult."""

    def test_valid_result(self):
        root = ParsedElement(tag="Invoice", namespace="")
        doc = ParsedDocument(
            document_type="Invoice",
            version="2.5",
            root=root,
        )
        result = ParseResult(document=doc)
        assert result.is_valid
        assert not result.has_warnings

    def test_result_with_errors(self):
        result = ParseResult()
        result.add_error(ParseError(code="ERR", message="Error"))
        assert not result.is_valid
        assert len(result.errors) == 1

    def test_result_with_warnings(self):
        root = ParsedElement(tag="Invoice", namespace="")
        doc = ParsedDocument(
            document_type="Invoice",
            version="2.5",
            root=root,
        )
        result = ParseResult(document=doc)
        result.add_error(
            ParseError(
                code="WARN",
                message="Warning",
                severity=ErrorSeverity.WARNING,
            )
        )
        assert result.is_valid  # Warnings don't invalidate
        assert result.has_warnings


class TestParseStatistics:
    """Tests for ParseStatistics."""

    def test_from_document(self):
        child = ParsedElement(tag="ID", namespace="", value="TEST")
        root = ParsedElement(
            tag="Invoice",
            namespace="",
            children=[child],
        )
        doc = ParsedDocument(
            document_type="Invoice",
            version="2.5",
            root=root,
        )
        stats = ParseStatistics.from_document(doc)
        assert stats.element_count == 2  # root + child
        assert stats.document_type == "Invoice"


class TestXMLParser:
    """Tests for XML parser."""

    def test_parse_valid_xml(self):
        root, nsmap = parse_xml(SAMPLE_INVOICE_XML)
        assert root.tag == "Invoice"
        assert "cbc" in nsmap
        assert "cac" in nsmap

    def test_parse_extracts_children(self):
        root, _ = parse_xml(SAMPLE_INVOICE_XML)
        # Should have children
        assert len(root.children) > 0
        # Find ID element
        id_elem = root.find_child("ID")
        assert id_elem is not None
        assert id_elem.value == "INV-001"

    def test_parse_extracts_attributes(self):
        root, _ = parse_xml(SAMPLE_INVOICE_XML)
        # Find PayableAmount with currencyID attribute
        legal_total = root.find_child("LegalMonetaryTotal")
        assert legal_total is not None
        payable = legal_total.find_child("PayableAmount")
        assert payable is not None
        assert payable.get_attribute("currencyID") == "USD"

    def test_parse_malformed_xml_recovers(self):
        # With recovery enabled, should not raise
        root, _ = parse_xml(MALFORMED_XML, recover=True)
        assert root.tag == "Invoice"


class TestDocumentParser:
    """Tests for document-level parser."""

    def test_parse_returns_result(self):
        result = parse(SAMPLE_INVOICE_XML)
        assert result.document is not None
        assert result.document.document_type == "Invoice"
        assert result.document.version == "2.5"

    def test_parse_extracts_document_type(self):
        result = parse(SAMPLE_INVOICE_XML)
        assert result.document.document_type == "Invoice"

    def test_parse_invalid_xml(self):
        result = parse("<broken", recover=False)
        assert not result.is_valid
        assert len(result.errors) > 0
        assert result.errors[0].category == ErrorCategory.STRUCTURAL


# Tests requiring generated schemas
from edi_schema.ubl.schemas import SCHEMAS_GENERATED


class TestParseWithSchema:
    """Tests for schema-bound parsing."""

    @pytest.mark.skipif(not SCHEMAS_GENERATED, reason="UBL schemas not generated")
    def test_parse_with_schema_binds_components(self):
        from edi_schema.ubl import GeneratedUBLSchemaLoader

        loader = GeneratedUBLSchemaLoader()
        schema = loader.load("Invoice")

        result = parse_with_schema(SAMPLE_INVOICE_XML, schema)

        assert result.is_valid
        # Root should be bound to Invoice ABIE
        assert result.document.root.schema_component is not None

    @pytest.mark.skipif(not SCHEMAS_GENERATED, reason="UBL schemas not generated")
    def test_parse_wrong_document_type(self):
        from edi_schema.ubl import GeneratedUBLSchemaLoader

        loader = GeneratedUBLSchemaLoader()
        schema = loader.load("Order")  # Wrong schema for Invoice

        result = parse_with_schema(SAMPLE_INVOICE_XML, schema)

        # Should have mismatch error
        assert not result.is_valid
        assert any("MISMATCH" in e.code for e in result.errors)
