"""
Tests for UBL document writer.
"""

import tempfile
from pathlib import Path

import pytest

from edi_schema.ubl.writer import (
    DocumentBuilder,
    ElementBuilder,
    PartyBuilder,
    party,
    serialize,
    serialize_to_file,
    XMLSerializer,
)
from edi_schema.ubl.ast import ParsedDocument, ParsedElement, ParsedAttribute
from edi_schema.ubl.enums import Namespace


class TestElementBuilder:
    """Tests for ElementBuilder."""

    def test_basic_creation(self):
        elem = ElementBuilder(tag="ID", namespace="", value="INV-001")
        assert elem.tag == "ID"
        assert elem.value == "INV-001"

    def test_set_value(self):
        elem = ElementBuilder(tag="ID", namespace="")
        elem.set_value("TEST-001")
        assert elem.value == "TEST-001"

    def test_add_attribute(self):
        elem = ElementBuilder(tag="Amount", namespace="")
        elem.add_attribute("currencyID", "USD")
        assert len(elem.attributes) == 1
        assert elem.attributes[0].name == "currencyID"
        assert elem.attributes[0].value == "USD"

    def test_add_child(self):
        parent = ElementBuilder(tag="Party", namespace="")
        child = ElementBuilder(tag="Name", namespace="", value="Test Corp")
        parent.add_child(child)
        assert len(parent.children) == 1
        assert parent.children[0].tag == "Name"

    def test_add_element(self):
        parent = ElementBuilder(tag="Party", namespace="")
        parent.add_element("Name", value="Test Corp")
        assert len(parent.children) == 1
        assert parent.children[0].value == "Test Corp"

    def test_add_element_with_attrs(self):
        parent = ElementBuilder(tag="Total", namespace="")
        parent.add_element("Amount", value="100.00", currencyID="USD")
        assert len(parent.children) == 1
        assert len(parent.children[0].attributes) == 1

    def test_with_child(self):
        parent = ElementBuilder(tag="Invoice", namespace="")
        parent.with_child("Party", lambda p: p.add_element("Name", "Test"))
        assert len(parent.children) == 1
        assert parent.children[0].tag == "Party"
        assert len(parent.children[0].children) == 1

    def test_build(self):
        elem = ElementBuilder(tag="ID", namespace="", value="INV-001")
        elem.add_attribute("schemeID", "ABC")
        parsed = elem.build()

        assert isinstance(parsed, ParsedElement)
        assert parsed.tag == "ID"
        assert parsed.value == "INV-001"
        assert parsed.get_attribute("schemeID") == "ABC"

    def test_build_with_children(self):
        parent = ElementBuilder(tag="Party", namespace="")
        parent.add_element("Name", value="Test Corp")
        parent.add_element("ID", value="123")
        parsed = parent.build()

        assert len(parsed.children) == 2
        assert parsed.find_child("Name").value == "Test Corp"
        assert parsed.find_child("ID").value == "123"

    def test_fluent_chaining(self):
        elem = (
            ElementBuilder(tag="Amount", namespace="")
            .set_value("100.00")
            .add_attribute("currencyID", "USD")
        )
        assert elem.value == "100.00"
        assert len(elem.attributes) == 1


class TestDocumentBuilder:
    """Tests for DocumentBuilder."""

    def test_basic_creation(self):
        builder = DocumentBuilder("Invoice")
        assert builder.document_type == "Invoice"
        assert builder.version == "2.5"

    def test_id(self):
        doc = DocumentBuilder("Invoice").id("INV-001").build()
        id_elem = doc.root.find_child("ID")
        assert id_elem is not None
        assert id_elem.value == "INV-001"

    def test_issue_date(self):
        doc = DocumentBuilder("Invoice").issue_date("2024-01-15").build()
        date_elem = doc.root.find_child("IssueDate")
        assert date_elem is not None
        assert date_elem.value == "2024-01-15"

    def test_note(self):
        doc = DocumentBuilder("Invoice").note("Test note").build()
        note_elem = doc.root.find_child("Note")
        assert note_elem is not None
        assert note_elem.value == "Test note"

    def test_note_with_language(self):
        doc = DocumentBuilder("Invoice").note("Test", language_id="en").build()
        note_elem = doc.root.find_child("Note")
        assert note_elem.get_attribute("languageID") == "en"

    def test_document_currency_code(self):
        doc = DocumentBuilder("Invoice").document_currency_code("USD").build()
        elem = doc.root.find_child("DocumentCurrencyCode")
        assert elem is not None
        assert elem.value == "USD"

    def test_accounting_supplier_party(self):
        doc = (
            DocumentBuilder("Invoice")
            .accounting_supplier_party(
                lambda p: p.add_element("ID", "SUPP-001", namespace=Namespace.CBC.value)
            )
            .build()
        )
        party_elem = doc.root.find_child("AccountingSupplierParty")
        assert party_elem is not None

    def test_build_document(self):
        doc = (
            DocumentBuilder("Invoice")
            .id("INV-001")
            .issue_date("2024-01-15")
            .build()
        )
        assert isinstance(doc, ParsedDocument)
        assert doc.document_type == "Invoice"
        assert doc.version == "2.5"

    def test_namespaces(self):
        doc = DocumentBuilder("Invoice").build()
        assert "cbc" in doc.namespaces
        assert "cac" in doc.namespaces

    def test_fluent_chaining(self):
        doc = (
            DocumentBuilder("Invoice")
            .ubl_version_id("2.5")
            .id("INV-001")
            .issue_date("2024-01-15")
            .document_currency_code("USD")
            .build()
        )
        assert doc.root.find_child("UBLVersionID") is not None
        assert doc.root.find_child("ID") is not None
        assert doc.root.find_child("IssueDate") is not None
        assert doc.root.find_child("DocumentCurrencyCode") is not None


class TestPartyBuilder:
    """Tests for PartyBuilder."""

    def test_basic_creation(self):
        parent = ElementBuilder(tag="AccountingSupplierParty", namespace=Namespace.CAC.value)
        party_builder = PartyBuilder(parent)
        assert party_builder._party.tag == "Party"

    def test_name(self):
        parent = ElementBuilder(tag="AccountingSupplierParty", namespace=Namespace.CAC.value)
        PartyBuilder(parent).name("Test Corp")
        built = parent.build()
        party = built.find_child("Party")
        party_name = party.find_child("PartyName")
        name = party_name.find_child("Name")
        assert name.value == "Test Corp"

    def test_postal_address(self):
        parent = ElementBuilder(tag="AccountingSupplierParty", namespace=Namespace.CAC.value)
        PartyBuilder(parent).postal_address(
            street="123 Main St",
            city="Boston",
            postal_zone="02101",
            country="US",
        )
        built = parent.build()
        party = built.find_child("Party")
        address = party.find_child("PostalAddress")
        assert address.find_child("StreetName").value == "123 Main St"
        assert address.find_child("CityName").value == "Boston"
        country = address.find_child("Country")
        assert country.find_child("IdentificationCode").value == "US"

    def test_contact(self):
        parent = ElementBuilder(tag="AccountingSupplierParty", namespace=Namespace.CAC.value)
        PartyBuilder(parent).contact(
            name="John Doe",
            phone="+1-555-1234",
            email="john@example.com",
        )
        built = parent.build()
        party = built.find_child("Party")
        contact = party.find_child("Contact")
        assert contact.find_child("Name").value == "John Doe"
        assert contact.find_child("Telephone").value == "+1-555-1234"
        assert contact.find_child("ElectronicMail").value == "john@example.com"

    def test_fluent_chaining(self):
        parent = ElementBuilder(tag="AccountingSupplierParty", namespace=Namespace.CAC.value)
        (
            PartyBuilder(parent)
            .name("Test Corp")
            .postal_address(city="Boston")
            .contact(email="test@example.com")
        )
        built = parent.build()
        party = built.find_child("Party")
        assert party.find_child("PartyName") is not None
        assert party.find_child("PostalAddress") is not None
        assert party.find_child("Contact") is not None


class TestXMLSerializer:
    """Tests for XMLSerializer."""

    def test_basic_serialization(self):
        doc = DocumentBuilder("Invoice").id("INV-001").build()
        serializer = XMLSerializer()
        xml = serializer.serialize(doc)

        assert "<?xml" in xml
        assert "Invoice" in xml
        assert "INV-001" in xml

    def test_pretty_print(self):
        doc = DocumentBuilder("Invoice").id("INV-001").build()
        serializer = XMLSerializer(pretty=True)
        xml = serializer.serialize(doc)

        # Should have newlines for pretty printing
        assert "\n" in xml

    def test_compact_output(self):
        doc = DocumentBuilder("Invoice").id("INV-001").build()
        serializer = XMLSerializer(pretty=False)
        xml = serializer.serialize(doc)

        # Should not have pretty print newlines
        lines = [l for l in xml.split("\n") if l.strip()]
        # With compact, should be mostly on one line (except declaration)
        assert len(lines) <= 2

    def test_no_xml_declaration(self):
        doc = DocumentBuilder("Invoice").id("INV-001").build()
        serializer = XMLSerializer(xml_declaration=False)
        xml = serializer.serialize(doc)

        assert "<?xml" not in xml

    def test_serialize_bytes(self):
        doc = DocumentBuilder("Invoice").id("INV-001").build()
        serializer = XMLSerializer()
        xml_bytes = serializer.serialize_bytes(doc)

        assert isinstance(xml_bytes, bytes)
        assert b"Invoice" in xml_bytes

    def test_serialize_to_file(self):
        doc = DocumentBuilder("Invoice").id("INV-001").build()
        serializer = XMLSerializer()

        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
            path = f.name

        try:
            serializer.serialize_to_file(doc, path)
            content = Path(path).read_text()
            assert "Invoice" in content
            assert "INV-001" in content
        finally:
            Path(path).unlink()

    def test_namespace_handling(self):
        doc = (
            DocumentBuilder("Invoice")
            .id("INV-001")
            .accounting_supplier_party(lambda p: p.add_element("ID", "SUPP"))
            .build()
        )
        serializer = XMLSerializer()
        xml = serializer.serialize(doc)

        # Should have namespace declarations
        assert "xmlns" in xml
        assert "cbc:" in xml or "cac:" in xml or Namespace.CBC.value in xml

    def test_serialize_element(self):
        elem = (
            ElementBuilder(tag="Amount", namespace=Namespace.CBC.value)
            .set_value("100.00")
            .add_attribute("currencyID", "USD")
            .build()
        )
        serializer = XMLSerializer()
        xml = serializer.serialize_element(elem)

        assert "100.00" in xml
        assert "currencyID" in xml
        assert "USD" in xml


class TestSerializeFunctions:
    """Tests for serialize convenience functions."""

    def test_serialize_function(self):
        doc = DocumentBuilder("Invoice").id("INV-001").build()
        xml = serialize(doc)

        assert "<?xml" in xml
        assert "Invoice" in xml

    def test_serialize_function_options(self):
        doc = DocumentBuilder("Invoice").id("INV-001").build()
        xml = serialize(doc, pretty=False, xml_declaration=False)

        assert "<?xml" not in xml

    def test_serialize_to_file_function(self):
        doc = DocumentBuilder("Invoice").id("INV-001").build()

        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
            path = f.name

        try:
            serialize_to_file(doc, path)
            content = Path(path).read_text()
            assert "Invoice" in content
        finally:
            Path(path).unlink()


class TestIntegration:
    """Integration tests for document building and serialization."""

    def test_complete_invoice(self):
        """Test building a complete invoice."""
        doc = (
            DocumentBuilder("Invoice")
            .ubl_version_id("2.5")
            .id("INV-2024-001")
            .issue_date("2024-01-15")
            .document_currency_code("USD")
            .note("Test invoice")
            .accounting_supplier_party(lambda p: (
                party(p)
                .name("Supplier Corp")
                .postal_address(
                    street="123 Main St",
                    city="Boston",
                    postal_zone="02101",
                    country="US",
                )
                .contact(email="supplier@example.com")
            ))
            .accounting_customer_party(lambda p: (
                party(p)
                .name("Customer Inc")
                .postal_address(city="New York", country="US")
            ))
            .legal_monetary_total(lambda t: (
                t.add_element("PayableAmount", "1000.00",
                             namespace=Namespace.CBC.value,
                             currencyID="USD")
            ))
            .invoice_line(lambda l: (
                l.add_element("ID", "1", namespace=Namespace.CBC.value)
                .add_element("LineExtensionAmount", "1000.00",
                           namespace=Namespace.CBC.value,
                           currencyID="USD")
            ))
            .build()
        )

        xml = serialize(doc)

        # Verify key elements
        assert "INV-2024-001" in xml
        assert "2024-01-15" in xml
        assert "USD" in xml
        assert "Supplier Corp" in xml
        assert "Customer Inc" in xml
        assert "1000.00" in xml

    def test_roundtrip(self):
        """Test that built documents can be parsed back."""
        from edi_schema.ubl.parser import parse

        doc = (
            DocumentBuilder("Invoice")
            .id("INV-001")
            .issue_date("2024-01-15")
            .build()
        )

        xml = serialize(doc)
        result = parse(xml)

        assert result.is_valid
        assert result.document.document_type == "Invoice"
        assert result.document.root.find_child("ID").value == "INV-001"
