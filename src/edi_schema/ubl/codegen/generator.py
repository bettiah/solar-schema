"""
UBL Schema Code Generator.

Generates Python modules from UBL schema definitions for fast loading.
"""

from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from ..models import (
    ABIE,
    ASBIE,
    BBIE,
    UBLSchema,
)
from ..schema import UBLSchemaLoader


class UBLSchemaGenerator:
    """
    Generates Python code from UBL schemas.

    Converts runtime-parsed schemas into pre-generated Python modules
    for faster loading (~50x improvement).

    Usage:
        loader = UBLSchemaLoader(xsd_path)
        generator = UBLSchemaGenerator(output_path)

        # Generate single document type
        generator.generate_document(loader, "Invoice")

        # Generate all document types
        generator.generate_all(loader)
    """

    def __init__(self, output_dir: Path):
        """
        Initialize the generator.

        Args:
            output_dir: Directory for generated Python modules
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Set up Jinja2 environment
        self.env = Environment(
            loader=PackageLoader("edi_schema.ubl.codegen", "templates"),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def generate_document(
        self,
        loader: UBLSchemaLoader,
        document_type: str,
    ) -> Path:
        """
        Generate a Python module for a single document type.

        Args:
            loader: Schema loader to use
            document_type: Document type name (e.g., 'Invoice')

        Returns:
            Path to the generated module
        """
        schema = loader.load(document_type)
        return self._generate_schema_module(schema)

    def generate_all(
        self,
        loader: UBLSchemaLoader,
        document_types: list[str] | None = None,
    ) -> list[Path]:
        """
        Generate Python modules for multiple document types.

        Args:
            loader: Schema loader to use
            document_types: List of document types, or None for all available

        Returns:
            List of paths to generated modules
        """
        if document_types is None:
            from ..models.document import UBL_DOCUMENT_TYPES

            document_types = UBL_DOCUMENT_TYPES

        generated: list[Path] = []
        for doc_type in document_types:
            try:
                path = self.generate_document(loader, doc_type)
                generated.append(path)
            except Exception as e:
                print(f"Warning: Failed to generate {doc_type}: {e}")

        # Generate __init__.py with imports
        self._generate_init(generated)

        # Generate registry module
        self._generate_registry(document_types)

        return generated

    def _generate_schema_module(self, schema: UBLSchema) -> Path:
        """Generate a Python module for a schema."""
        template = self.env.get_template("schema.py.j2")

        module_name = self._to_module_name(schema.name)
        output_path = self.output_dir / f"{module_name}.py"

        content = template.render(
            schema=schema,
            document_type=schema.document_type,
            abies=schema.abies,
            code_lists=schema.code_lists,
            to_module_name=self._to_module_name,
            repr_str=repr,
        )

        output_path.write_text(content)
        return output_path

    def _generate_init(self, generated: list[Path]) -> Path:
        """Generate __init__.py for the schemas package."""
        template = self.env.get_template("__init__.py.j2")

        modules = [p.stem for p in generated]
        output_path = self.output_dir / "__init__.py"

        content = template.render(modules=modules)
        output_path.write_text(content)
        return output_path

    def _generate_registry(self, document_types: list[str]) -> Path:
        """Generate the registry module."""
        template = self.env.get_template("registry.py.j2")

        output_path = self.output_dir.parent / "registry.py"

        content = template.render(
            document_types=document_types,
            to_module_name=self._to_module_name,
        )
        output_path.write_text(content)
        return output_path

    @staticmethod
    def _to_module_name(document_type: str) -> str:
        """Convert document type name to Python module name."""
        # CamelCase to snake_case
        result = []
        for i, char in enumerate(document_type):
            if char.isupper() and i > 0:
                result.append("_")
            result.append(char.lower())
        return "".join(result)


def generate_bbie_code(bbie: BBIE) -> str:
    """Generate Python code for a BBIE definition."""
    return f"""BBIE(
    name={repr(bbie.name)},
    definition={repr(bbie.definition)},
    cardinality=Cardinality.{bbie.cardinality.name},
    data_type={repr(bbie.data_type)},
    representation_term={repr(bbie.representation_term)},
    property_term={repr(bbie.property_term)},
    object_class={repr(bbie.object_class)},
)"""


def generate_asbie_code(asbie: ASBIE) -> str:
    """Generate Python code for an ASBIE definition."""
    return f"""ASBIE(
    name={repr(asbie.name)},
    definition={repr(asbie.definition)},
    cardinality=Cardinality.{asbie.cardinality.name},
    associated_abie={repr(asbie.associated_abie)},
    property_term={repr(asbie.property_term)},
    object_class={repr(asbie.object_class)},
)"""


def generate_abie_code(abie: ABIE) -> str:
    """Generate Python code for an ABIE definition."""
    bbies_code = ",\n        ".join(generate_bbie_code(b) for b in abie.bbies)
    asbies_code = ",\n        ".join(generate_asbie_code(a) for a in abie.asbies)

    return f"""ABIE(
    name={repr(abie.name)},
    definition={repr(abie.definition)},
    object_class={repr(abie.object_class)},
    namespace={repr(abie.namespace)},
    bbies=[
        {bbies_code}
    ],
    asbies=[
        {asbies_code}
    ],
)"""


def main():
    """Command-line interface for schema generation."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate UBL schema modules")
    parser.add_argument("--source", required=True, help="Path to UBL XSD directory")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--version", default="2.5", help="Version identifier (default: 2.5)")
    parser.add_argument("--documents", nargs="*", help="Specific document types to generate")

    args = parser.parse_args()

    source_path = Path(args.source)
    output_path = Path(args.output)

    if not source_path.exists():
        print(f"Error: Source directory does not exist: {source_path}")
        return

    print(f"UBL Schema Generator v{args.version}")
    print(f"  Source: {source_path}")
    print(f"  Output: {output_path}")

    loader = UBLSchemaLoader(source_path)
    generator = UBLSchemaGenerator(output_path)

    document_types = args.documents if args.documents else None
    generated = generator.generate_all(loader, document_types)

    print(f"\nGenerated {len(generated)} schema modules")


if __name__ == "__main__":
    main()
