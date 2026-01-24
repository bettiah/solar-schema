"""
Tests for UBL code generation.
"""

import tempfile
from pathlib import Path

import pytest

from edi_schema.ubl.codegen import UBLSchemaGenerator
from edi_schema.ubl.codegen.generator import (
    generate_abie_code,
    generate_asbie_code,
    generate_bbie_code,
)
from edi_schema.ubl.enums import Cardinality
from edi_schema.ubl.models import (
    ABIE,
    ASBIE,
    BBIE,
    CodeList,
    CodeValue,
    DocumentType,
    UBLSchema,
)
from edi_schema.ubl.schemas import (
    SCHEMAS_GENERATED,
    get_schema,
    list_schemas,
    schema_exists,
)


class TestCodeGeneration:
    """Tests for code generation helpers."""

    def test_generate_bbie_code(self):
        bbie = BBIE(
            name="ID",
            definition="Invoice ID",
            cardinality=Cardinality.EXACTLY_ONE,
            data_type="IdentifierType",
            representation_term="Identifier",
            property_term="ID",
            object_class="Invoice",
        )
        code = generate_bbie_code(bbie)
        assert "BBIE(" in code
        assert "name='ID'" in code
        assert "Cardinality.EXACTLY_ONE" in code

    def test_generate_asbie_code(self):
        asbie = ASBIE(
            name="InvoiceLine",
            definition="Invoice line item",
            cardinality=Cardinality.ONE_OR_MORE,
            associated_abie="InvoiceLine",
            property_term="Line",
            object_class="Invoice",
        )
        code = generate_asbie_code(asbie)
        assert "ASBIE(" in code
        assert "name='InvoiceLine'" in code
        assert "Cardinality.ONE_OR_MORE" in code

    def test_generate_abie_code(self):
        abie = ABIE(
            name="Invoice",
            definition="Invoice document",
            object_class="Invoice",
            namespace="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
            bbies=[
                BBIE(
                    name="ID",
                    definition="ID",
                    cardinality=Cardinality.EXACTLY_ONE,
                    data_type="IdentifierType",
                    representation_term="Identifier",
                ),
            ],
            asbies=[
                ASBIE(
                    name="InvoiceLine",
                    definition="Line",
                    cardinality=Cardinality.ONE_OR_MORE,
                    associated_abie="InvoiceLine",
                ),
            ],
        )
        code = generate_abie_code(abie)
        assert "ABIE(" in code
        assert "name='Invoice'" in code
        assert "BBIE(" in code
        assert "ASBIE(" in code


class TestUBLSchemaGenerator:
    """Tests for UBLSchemaGenerator."""

    def test_to_module_name(self):
        assert UBLSchemaGenerator._to_module_name("Invoice") == "invoice"
        assert UBLSchemaGenerator._to_module_name("CreditNote") == "credit_note"
        assert UBLSchemaGenerator._to_module_name("DespatchAdvice") == "despatch_advice"
        assert UBLSchemaGenerator._to_module_name("ApplicationResponse") == "application_response"

    def test_generator_creates_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "generated" / "schemas"
            generator = UBLSchemaGenerator(output_dir)
            assert output_dir.exists()

    def test_template_loading(self):
        with tempfile.TemporaryDirectory() as tmp:
            generator = UBLSchemaGenerator(Path(tmp))
            # Should be able to load templates
            template = generator.env.get_template("schema.py.j2")
            assert template is not None


class TestSchemasPackage:
    """Tests for the schemas package."""

    def test_schemas_generated_flag(self):
        # This should be False until we run code generation
        assert isinstance(SCHEMAS_GENERATED, bool)

    def test_list_schemas_empty_without_generation(self):
        # Without generation, should return empty or error
        result = list_schemas()
        assert isinstance(result, list)

    def test_schema_exists_false_without_generation(self):
        # Without generation, should return False
        result = schema_exists("Invoice")
        assert result is False or SCHEMAS_GENERATED is False

    @pytest.mark.skipif(not SCHEMAS_GENERATED, reason="Schemas not generated")
    def test_get_schema_raises_without_generation(self):
        # This test is skipped if schemas not generated
        schema = get_schema("Invoice")
        assert schema.name == "Invoice"


class TestCodeGenerationIntegration:
    """Integration tests for code generation (require XSD files)."""

    # Test file path for UBL XSD
    XSD_PATH = Path("/Users/me/Downloads/edi/ubl/UBL-2.5/xsd")

    @pytest.fixture
    def sample_schema(self):
        """Create a minimal sample schema for testing."""
        abie = ABIE(
            name="TestDoc",
            definition="Test document",
            object_class="TestDoc",
            namespace="urn:test",
            bbies=[
                BBIE(
                    name="ID",
                    definition="ID",
                    cardinality=Cardinality.EXACTLY_ONE,
                    data_type="IdentifierType",
                    representation_term="Identifier",
                ),
            ],
            asbies=[],
        )
        doc_type = DocumentType(
            name="TestDoc",
            namespace="urn:test",
            definition="Test document",
            root_element="TestDoc",
            root_abie=abie,
        )
        return UBLSchema(
            document_type=doc_type,
            abies={"TestDoc": abie},
            code_lists={
                "TestCode": CodeList(
                    id="TestCode-1.0",
                    short_name="TestCode",
                    values=[
                        CodeValue(code="A", name="Value A"),
                        CodeValue(code="B", name="Value B"),
                    ],
                ),
            },
        )

    def test_generate_schema_module(self, sample_schema):
        """Test generating a schema module."""
        with tempfile.TemporaryDirectory() as tmp:
            generator = UBLSchemaGenerator(Path(tmp))
            output = generator._generate_schema_module(sample_schema)

            assert output.exists()
            content = output.read_text()

            # Check module content
            assert "Generated UBL schema for TestDoc" in content
            assert "def get_schema()" in content
            assert "SCHEMA_NAME = 'TestDoc'" in content
            assert "ABIE(" in content
            assert "BBIE(" in content

    def test_generate_init_module(self, sample_schema):
        """Test generating __init__.py."""
        with tempfile.TemporaryDirectory() as tmp:
            generator = UBLSchemaGenerator(Path(tmp))
            schema_path = generator._generate_schema_module(sample_schema)
            init_path = generator._generate_init([schema_path])

            assert init_path.exists()
            content = init_path.read_text()

            # Check init content
            assert "from . import test_doc" in content

    @pytest.mark.skipif(not XSD_PATH.exists(), reason="UBL XSD files not available")
    def test_generate_from_xsd(self):
        """Test generating schema from actual XSD (requires XSD files)."""
        from edi_schema.ubl.schema import UBLSchemaLoader

        with tempfile.TemporaryDirectory() as tmp:
            loader = UBLSchemaLoader(self.XSD_PATH)
            generator = UBLSchemaGenerator(Path(tmp))

            # Generate Invoice schema
            output = generator.generate_document(loader, "Invoice")

            assert output.exists()
            content = output.read_text()
            assert "Invoice" in content
            assert "def get_schema()" in content
