"""
Tests for UBL schema models.
"""

from edi_schema.ubl.enums import Cardinality, ComponentType, Namespace, RepresentationTerm
from edi_schema.ubl.models import (
    ABIE,
    ASBIE,
    BBIE,
    Attribute,
    CodeList,
    CodeValue,
    DocumentType,
    QualifiedDataType,
    UBLSchema,
    UnqualifiedDataType,
)


class TestCardinality:
    """Tests for Cardinality enum."""

    def test_cardinality_values(self):
        assert Cardinality.ZERO_OR_ONE.value == "0..1"
        assert Cardinality.EXACTLY_ONE.value == "1"
        assert Cardinality.ZERO_OR_MORE.value == "0..n"
        assert Cardinality.ONE_OR_MORE.value == "1..n"

    def test_is_required(self):
        assert not Cardinality.ZERO_OR_ONE.is_required
        assert Cardinality.EXACTLY_ONE.is_required
        assert not Cardinality.ZERO_OR_MORE.is_required
        assert Cardinality.ONE_OR_MORE.is_required

    def test_is_multiple(self):
        assert not Cardinality.ZERO_OR_ONE.is_multiple
        assert not Cardinality.EXACTLY_ONE.is_multiple
        assert Cardinality.ZERO_OR_MORE.is_multiple
        assert Cardinality.ONE_OR_MORE.is_multiple

    def test_from_min_max(self):
        assert Cardinality.from_min_max(0, 1) == Cardinality.ZERO_OR_ONE
        assert Cardinality.from_min_max(1, 1) == Cardinality.EXACTLY_ONE
        assert Cardinality.from_min_max(0, None) == Cardinality.ZERO_OR_MORE
        assert Cardinality.from_min_max(0, "unbounded") == Cardinality.ZERO_OR_MORE
        assert Cardinality.from_min_max(1, None) == Cardinality.ONE_OR_MORE
        assert Cardinality.from_min_max(1, "unbounded") == Cardinality.ONE_OR_MORE


class TestComponentType:
    """Tests for ComponentType enum."""

    def test_component_types(self):
        assert ComponentType.ABIE.value == "ABIE"
        assert ComponentType.BBIE.value == "BBIE"
        assert ComponentType.ASBIE.value == "ASBIE"

    def test_description(self):
        assert "Aggregate" in ComponentType.ABIE.description
        assert "Basic" in ComponentType.BBIE.description
        assert "Association" in ComponentType.ASBIE.description


class TestRepresentationTerm:
    """Tests for RepresentationTerm enum."""

    def test_representation_terms(self):
        assert RepresentationTerm.AMOUNT.value == "Amount"
        assert RepresentationTerm.CODE.value == "Code"
        assert RepresentationTerm.DATE.value == "Date"
        assert RepresentationTerm.TEXT.value == "Text"

    def test_xsd_base_type(self):
        assert RepresentationTerm.AMOUNT.xsd_base_type == "xsd:decimal"
        assert RepresentationTerm.DATE.xsd_base_type == "xsd:date"
        assert RepresentationTerm.TEXT.xsd_base_type == "xsd:string"

    def test_is_numeric(self):
        assert RepresentationTerm.AMOUNT.is_numeric
        assert RepresentationTerm.QUANTITY.is_numeric
        assert not RepresentationTerm.TEXT.is_numeric
        assert not RepresentationTerm.DATE.is_numeric


class TestNamespace:
    """Tests for Namespace enum."""

    def test_namespaces(self):
        assert "CommonAggregateComponents" in Namespace.CAC.value
        assert "CommonBasicComponents" in Namespace.CBC.value

    def test_prefix(self):
        assert Namespace.CAC.prefix == "cac"
        assert Namespace.CBC.prefix == "cbc"
        assert Namespace.EXT.prefix == "ext"

    def test_from_prefix(self):
        assert Namespace.from_prefix("cac") == Namespace.CAC
        assert Namespace.from_prefix("cbc") == Namespace.CBC
        assert Namespace.from_prefix("unknown") is None

    def test_document_namespace(self):
        ns = Namespace.document_namespace("Invoice")
        assert "Invoice-2" in ns


class TestUnqualifiedDataType:
    """Tests for UnqualifiedDataType model."""

    def test_basic_creation(self):
        udt = UnqualifiedDataType(
            name="Amount",
            definition="A monetary value",
            representation_term="Amount",
            primitive_type="decimal",
            xsd_base="ccts-cct:AmountType",
        )
        assert udt.name == "Amount"
        assert udt.id == "Amount"
        assert udt.type_name == "AmountType"

    def test_with_attributes(self):
        attr = Attribute(
            name="currencyID",
            xsd_type="xsd:normalizedString",
            required=True,
            definition="Currency code",
        )
        udt = UnqualifiedDataType(
            name="Amount",
            definition="A monetary value",
            representation_term="Amount",
            primitive_type="decimal",
            xsd_base="ccts-cct:AmountType",
            attributes=[attr],
        )
        assert len(udt.attributes) == 1
        assert udt.get_required_attributes() == [attr]
        assert udt.get_optional_attributes() == []


class TestQualifiedDataType:
    """Tests for QualifiedDataType model."""

    def test_basic_creation(self):
        qdt = QualifiedDataType(
            name="CurrencyCode",
            base_type="Code",
            code_list_id="CurrencyCode-2.4",
        )
        assert qdt.name == "CurrencyCode"
        assert qdt.id == "CurrencyCode"
        assert qdt.type_name == "CurrencyCodeType"
        assert qdt.base_type == "Code"


class TestBBIE:
    """Tests for BBIE model."""

    def test_basic_creation(self):
        bbie = BBIE(
            name="ID",
            definition="Document identifier",
            cardinality=Cardinality.EXACTLY_ONE,
            data_type="Identifier",
            representation_term="Identifier",
        )
        assert bbie.name == "ID"
        assert bbie.id == "ID"
        assert bbie.is_required
        assert not bbie.is_multiple
        assert bbie.component_type == ComponentType.BBIE


class TestASBIE:
    """Tests for ASBIE model."""

    def test_basic_creation(self):
        asbie = ASBIE(
            name="AccountingSupplierParty",
            definition="The supplier party",
            cardinality=Cardinality.ZERO_OR_ONE,
            associated_abie="SupplierParty",
        )
        assert asbie.name == "AccountingSupplierParty"
        assert asbie.associated_abie == "SupplierParty"
        assert not asbie.is_required
        assert asbie.component_type == ComponentType.ASBIE


class TestABIE:
    """Tests for ABIE model."""

    def test_basic_creation(self):
        bbie = BBIE(
            name="ID",
            definition="Party ID",
            cardinality=Cardinality.ZERO_OR_ONE,
            data_type="Identifier",
            representation_term="Identifier",
        )
        asbie = ASBIE(
            name="PostalAddress",
            definition="Postal address",
            cardinality=Cardinality.ZERO_OR_ONE,
            associated_abie="Address",
        )
        abie = ABIE(
            name="Party",
            definition="A party",
            bbies=[bbie],
            asbies=[asbie],
        )
        assert abie.name == "Party"
        assert abie.type_name == "PartyType"
        assert len(abie.elements) == 2
        assert abie.get_bbie("ID") == bbie
        assert abie.get_asbie("PostalAddress") == asbie


class TestCodeList:
    """Tests for CodeList model."""

    def test_basic_creation(self):
        values = [
            CodeValue(code="USD", name="US Dollar"),
            CodeValue(code="EUR", name="Euro"),
        ]
        code_list = CodeList(
            id="CurrencyCode-2.4",
            short_name="CurrencyCode",
            values=values,
        )
        assert code_list.id == "CurrencyCode-2.4"
        assert code_list.contains("USD")
        assert code_list.contains("EUR")
        assert not code_list.contains("XXX")

    def test_code_lookup(self):
        values = [
            CodeValue(code="USD", name="US Dollar"),
        ]
        code_list = CodeList(
            id="CurrencyCode-2.4",
            short_name="CurrencyCode",
            values=values,
        )
        assert code_list.get("USD").name == "US Dollar"
        assert code_list.get_name("USD") == "US Dollar"
        assert code_list.get("XXX") is None

    def test_validate(self):
        values = [
            CodeValue(code="USD", name="US Dollar"),
        ]
        code_list = CodeList(
            id="CurrencyCode-2.4",
            short_name="CurrencyCode",
            values=values,
        )
        assert code_list.validate("USD")
        assert not code_list.validate("XXX")


class TestDocumentType:
    """Tests for DocumentType model."""

    def test_basic_creation(self):
        root_abie = ABIE(
            name="Invoice",
            definition="An invoice document",
        )
        doc_type = DocumentType(
            name="Invoice",
            namespace="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
            definition="A document used to request payment",
            root_element="Invoice",
            root_abie=root_abie,
        )
        assert doc_type.name == "Invoice"
        assert doc_type.id == "Invoice"


class TestUBLSchema:
    """Tests for UBLSchema model."""

    def test_basic_creation(self):
        root_abie = ABIE(name="Invoice", definition="")
        doc_type = DocumentType(
            name="Invoice",
            namespace="",
            definition="",
            root_element="Invoice",
            root_abie=root_abie,
        )
        schema = UBLSchema(document_type=doc_type)
        assert schema.name == "Invoice"

    def test_lookups(self):
        root_abie = ABIE(name="Invoice", definition="")
        doc_type = DocumentType(
            name="Invoice",
            namespace="",
            definition="",
            root_element="Invoice",
            root_abie=root_abie,
        )
        party_abie = ABIE(name="Party", definition="")
        udt = UnqualifiedDataType(
            name="Amount",
            definition="",
            representation_term="Amount",
            primitive_type="decimal",
            xsd_base="",
        )

        schema = UBLSchema(
            document_type=doc_type,
            abies={"Party": party_abie},
            udt_types={"Amount": udt},
        )

        assert schema.get_abie("Party") == party_abie
        assert schema.get_abie("Unknown") is None
        assert schema.get_data_type("Amount") == udt
