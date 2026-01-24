"""
Tests for UBL schema parsers.

These tests require the UBL 2.5 schema files to be present at the expected location.
"""

import pytest
from pathlib import Path

# Schema file paths
UBL_XSD_PATH = Path("/Users/me/Downloads/edi/ubl/UBL-2.5/xsd")
UBL_COMMON_PATH = UBL_XSD_PATH / "common"
UBL_MAINDOC_PATH = UBL_XSD_PATH / "maindoc"
UBL_CODE_LIST_PATH = UBL_XSD_PATH.parent / "cl" / "gc" / "default"

# Skip all tests if schema files are not available
pytestmark = pytest.mark.skipif(
    not UBL_XSD_PATH.exists(),
    reason="UBL schema files not available"
)


class TestUDTParser:
    """Tests for UDT parser."""

    def test_parse_udt(self):
        from edi_schema.ubl.schema_parsers import parse_udt

        udt_file = UBL_COMMON_PATH / "BDNDR-UnqualifiedDataTypes-1.1.xsd"
        if not udt_file.exists():
            pytest.skip("UDT file not found")

        result = parse_udt(udt_file)

        assert "Amount" in result
        assert "Code" in result
        assert "Date" in result
        assert "Text" in result
        assert "Identifier" in result

    def test_amount_type_attributes(self):
        from edi_schema.ubl.schema_parsers import parse_udt

        udt_file = UBL_COMMON_PATH / "BDNDR-UnqualifiedDataTypes-1.1.xsd"
        if not udt_file.exists():
            pytest.skip("UDT file not found")

        result = parse_udt(udt_file)
        amount = result.get("Amount")

        assert amount is not None
        assert amount.representation_term == "Amount"
        # Amount should have currencyID attribute
        attr_names = [attr.name for attr in amount.attributes]
        assert "currencyID" in attr_names


class TestQDTParser:
    """Tests for QDT parser."""

    def test_parse_qdt(self):
        from edi_schema.ubl.schema_parsers import parse_qdt

        qdt_file = UBL_COMMON_PATH / "UBL-QualifiedDataTypes-2.5.xsd"
        if not qdt_file.exists():
            pytest.skip("QDT file not found")

        result = parse_qdt(qdt_file)

        assert "CurrencyCode" in result
        assert "CountryIdentificationCode" in result
        assert "LanguageCode" in result

    def test_currency_code_type(self):
        from edi_schema.ubl.schema_parsers import parse_qdt

        qdt_file = UBL_COMMON_PATH / "UBL-QualifiedDataTypes-2.5.xsd"
        if not qdt_file.exists():
            pytest.skip("QDT file not found")

        result = parse_qdt(qdt_file)
        currency = result.get("CurrencyCode")

        assert currency is not None
        assert currency.base_type == "Code"
        assert currency.code_list_id == "CurrencyCode-2.4"


class TestCBCParser:
    """Tests for CBC parser."""

    def test_parse_cbc_elements(self):
        from edi_schema.ubl.schema_parsers import parse_cbc_elements

        cbc_file = UBL_COMMON_PATH / "UBL-CommonBasicComponents-2.5.xsd"
        if not cbc_file.exists():
            pytest.skip("CBC file not found")

        result = parse_cbc_elements(cbc_file)

        assert "ID" in result
        assert "IssueDate" in result
        assert "Amount" in result
        assert "Note" in result

    def test_cbc_element_types(self):
        from edi_schema.ubl.schema_parsers import parse_cbc_elements

        cbc_file = UBL_COMMON_PATH / "UBL-CommonBasicComponents-2.5.xsd"
        if not cbc_file.exists():
            pytest.skip("CBC file not found")

        result = parse_cbc_elements(cbc_file)

        assert result["ID"].type_name == "IDType"
        assert result["IssueDate"].type_name == "IssueDateType"


class TestCACParser:
    """Tests for CAC parser."""

    def test_parse_cac_elements(self):
        from edi_schema.ubl.schema_parsers import parse_cac_elements

        cac_file = UBL_COMMON_PATH / "UBL-CommonAggregateComponents-2.5.xsd"
        if not cac_file.exists():
            pytest.skip("CAC file not found")

        result = parse_cac_elements(cac_file)

        assert "AccountingSupplierParty" in result
        assert "AccountingCustomerParty" in result
        assert "Address" in result
        assert "Party" in result

    def test_parse_cac_types(self):
        from edi_schema.ubl.schema_parsers import parse_cac_types

        cac_file = UBL_COMMON_PATH / "UBL-CommonAggregateComponents-2.5.xsd"
        if not cac_file.exists():
            pytest.skip("CAC file not found")

        result = parse_cac_types(cac_file)

        assert "Party" in result
        assert "Address" in result
        assert "Contact" in result

    def test_party_type_structure(self):
        from edi_schema.ubl.schema_parsers import parse_cac_types

        cac_file = UBL_COMMON_PATH / "UBL-CommonAggregateComponents-2.5.xsd"
        if not cac_file.exists():
            pytest.skip("CAC file not found")

        result = parse_cac_types(cac_file)
        party = result.get("Party")

        assert party is not None
        # Party should have child elements
        assert len(party.bbies) > 0 or len(party.asbies) > 0


class TestDocumentParser:
    """Tests for document schema parser."""

    def test_parse_invoice_schema(self):
        from edi_schema.ubl.schema_parsers import parse_document_schema

        invoice_file = UBL_MAINDOC_PATH / "UBL-Invoice-2.5.xsd"
        if not invoice_file.exists():
            pytest.skip("Invoice schema not found")

        result = parse_document_schema(invoice_file)

        assert result.name == "Invoice"
        assert result.root_element == "Invoice"
        assert "Invoice-2" in result.namespace

    def test_invoice_structure(self):
        from edi_schema.ubl.schema_parsers import parse_document_schema

        invoice_file = UBL_MAINDOC_PATH / "UBL-Invoice-2.5.xsd"
        if not invoice_file.exists():
            pytest.skip("Invoice schema not found")

        result = parse_document_schema(invoice_file)

        # Invoice should have common elements
        bbie_names = [b.name for b in result.root_abie.bbies]
        assert "ID" in bbie_names
        assert "IssueDate" in bbie_names

    def test_list_document_schemas(self):
        from edi_schema.ubl.schema_parsers import list_document_schemas

        if not UBL_MAINDOC_PATH.exists():
            pytest.skip("Maindoc directory not found")

        result = list_document_schemas(UBL_MAINDOC_PATH)

        assert "Invoice" in result
        assert "Order" in result
        assert "CreditNote" in result
        assert len(result) > 50  # UBL 2.5 has 101 document types


class TestGenericodeParser:
    """Tests for Genericode parser."""

    def test_parse_currency_code_list(self):
        from edi_schema.ubl.schema_parsers import parse_genericode

        currency_file = UBL_CODE_LIST_PATH / "CurrencyCode-2.4.gc"
        if not currency_file.exists():
            pytest.skip("Currency code list not found")

        result = parse_genericode(currency_file)

        assert result.short_name == "CurrencyCode"
        assert result.contains("USD")
        assert result.contains("EUR")
        assert result.get_name("USD") == "US Dollar"

    def test_parse_country_code_list(self):
        from edi_schema.ubl.schema_parsers import parse_genericode

        country_file = UBL_CODE_LIST_PATH / "CountryIdentificationCode-2.4.gc"
        if not country_file.exists():
            pytest.skip("Country code list not found")

        result = parse_genericode(country_file)

        assert result.contains("US")
        assert result.contains("GB")
        assert result.contains("DE")

    def test_parse_all_code_lists(self):
        from edi_schema.ubl.schema_parsers import parse_all_code_lists

        if not UBL_CODE_LIST_PATH.exists():
            pytest.skip("Code list directory not found")

        result = parse_all_code_lists(UBL_CODE_LIST_PATH)

        assert "CurrencyCode-2.4" in result
        assert "CountryIdentificationCode-2.4" in result
        assert len(result) > 5


class TestUBLSchemaLoader:
    """Tests for UBLSchemaLoader."""

    def test_load_invoice_schema(self):
        from edi_schema.ubl.schema import UBLSchemaLoader

        if not UBL_XSD_PATH.exists():
            pytest.skip("UBL schema directory not found")

        loader = UBLSchemaLoader(UBL_XSD_PATH)
        schema = loader.load("Invoice")

        assert schema.name == "Invoice"
        assert len(schema.abies) > 0
        assert len(schema.cbc_elements) > 0
        assert len(schema.cac_elements) > 0

    def test_list_document_types(self):
        from edi_schema.ubl.schema import UBLSchemaLoader

        if not UBL_XSD_PATH.exists():
            pytest.skip("UBL schema directory not found")

        loader = UBLSchemaLoader(UBL_XSD_PATH)
        doc_types = loader.list_document_types()

        assert "Invoice" in doc_types
        assert "Order" in doc_types
        assert len(doc_types) > 50

    def test_load_nonexistent_schema(self):
        from edi_schema.ubl.schema import UBLSchemaLoader

        if not UBL_XSD_PATH.exists():
            pytest.skip("UBL schema directory not found")

        loader = UBLSchemaLoader(UBL_XSD_PATH)

        with pytest.raises(FileNotFoundError):
            loader.load("NonExistentDocument")
