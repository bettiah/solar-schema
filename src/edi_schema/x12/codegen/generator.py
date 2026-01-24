"""
X12 Schema Code Generator.

Generates Python schema modules from X12 text definition files using Jinja2 templates.
"""

from dataclasses import dataclass
from pathlib import Path

import jinja2
from edi_schema.x12.schema import X12SchemaLoader

# Path to templates directory
TEMPLATES_DIR = Path(__file__).parent / "templates"


@dataclass
class GeneratorConfig:
    """Configuration for schema generation."""

    source_path: Path
    output_path: Path
    version: str
    include_code_values: bool = True
    include_freeform: bool = True


class SchemaGenerator:
    """
    Generates Python schema modules from X12 text definition files.

    Usage:
        generator = SchemaGenerator(
            source_path=Path("/path/to/005010"),
            output_path=Path("src/edi_schema/x12/schemas/v005010"),
            version="005010",
        )
        generator.generate()
    """

    def __init__(
        self,
        source_path: Path,
        output_path: Path,
        version: str,
        include_code_values: bool = True,
        include_freeform: bool = True,
    ):
        self.config = GeneratorConfig(
            source_path=source_path,
            output_path=output_path,
            version=version,
            include_code_values=include_code_values,
            include_freeform=include_freeform,
        )
        self._loader: X12SchemaLoader | None = None
        self._env = self._create_jinja_env()

    def _create_jinja_env(self) -> jinja2.Environment:
        """Create Jinja2 environment with custom filters."""
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(TEMPLATES_DIR),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        env.filters["safe_id"] = self._safe_id
        env.filters["repr"] = repr  # Python's built-in repr for safe string escaping
        return env

    @property
    def loader(self) -> X12SchemaLoader:
        """Lazy-load the schema loader."""
        if self._loader is None:
            self._loader = X12SchemaLoader(self.config.source_path)
        return self._loader

    def generate(self) -> None:
        """Generate all schema modules."""
        self.config.output_path.mkdir(parents=True, exist_ok=True)

        # Generate modules
        self._generate_init()
        self._generate_data_elements()
        self._generate_composites()
        self._generate_segments()
        self._generate_transaction_sets()
        self._generate_lookups()

        print(f"Generated schemas in {self.config.output_path}")

    def _generate_init(self) -> None:
        """Generate __init__.py for the version package."""
        template = self._env.get_template("__init__.py.j2")
        content = template.render(version=self.config.version)
        self._write_file("__init__.py", content)

    def _generate_data_elements(self) -> None:
        """Generate data_elements.py."""
        elements = self.loader.get_all_elements()
        sorted_elements = sorted(
            elements.values(), key=lambda x: int(x.id) if x.id.isdigit() else 0
        )

        template = self._env.get_template("data_elements.py.j2")
        content = template.render(
            version=self.config.version,
            elements=sorted_elements,
            include_code_values=self.config.include_code_values,
            include_freeform=self.config.include_freeform,
        )
        self._write_file("data_elements.py", content)
        print(f"  Generated {len(elements)} data elements")

    def _generate_composites(self) -> None:
        """Generate composites.py."""
        composites = self.loader.get_all_composites()
        sorted_composites = sorted(composites.values(), key=lambda x: x.id)

        template = self._env.get_template("composites.py.j2")
        content = template.render(
            version=self.config.version,
            composites=sorted_composites,
            include_freeform=self.config.include_freeform,
        )
        self._write_file("composites.py", content)
        print(f"  Generated {len(composites)} composites")

    def _generate_segments(self) -> None:
        """Generate segments.py."""
        segments = self.loader.get_all_segments()
        sorted_segments = sorted(segments.values(), key=lambda x: x.id)

        template = self._env.get_template("segments.py.j2")
        content = template.render(
            version=self.config.version,
            segments=sorted_segments,
            include_freeform=self.config.include_freeform,
        )
        self._write_file("segments.py", content)
        print(f"  Generated {len(segments)} segments")

    def _generate_transaction_sets(self) -> None:
        """Generate transaction_sets.py."""
        transaction_ids = self.loader.list_schemas()
        transactions = []
        for txn_id in sorted(transaction_ids):
            schema = self.loader.load(txn_id)
            transactions.append(schema.transaction_set)

        template = self._env.get_template("transaction_sets.py.j2")
        content = template.render(
            version=self.config.version,
            transactions=transactions,
            include_freeform=self.config.include_freeform,
        )
        self._write_file("transaction_sets.py", content)
        print(f"  Generated {len(transactions)} transaction sets")

    def _generate_lookups(self) -> None:
        """Generate lookups.py with fast lookup tables."""
        elements = self.loader.get_all_elements()
        segments = self.loader.get_all_segments()

        sorted_elements = sorted(
            elements.values(), key=lambda x: int(x.id) if x.id.isdigit() else 0
        )
        sorted_segments = sorted(segments.values(), key=lambda x: x.id)

        template = self._env.get_template("lookups.py.j2")
        content = template.render(
            version=self.config.version,
            elements=sorted_elements,
            segments=sorted_segments,
        )
        self._write_file("lookups.py", content)
        print("  Generated lookup tables")

    def _write_file(self, filename: str, content: str) -> None:
        """Write content to a file in the output directory."""
        path = self.config.output_path / filename
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    @staticmethod
    def _safe_id(id_str: str) -> str:
        """Convert an ID to a valid Python identifier."""
        return id_str.replace("-", "_").replace(" ", "_").replace(".", "_")


def main():
    """Command-line interface for schema generation."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate X12 schema modules")
    parser.add_argument("--source", required=True, help="Path to schema source files")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--version", required=True, help="Schema version (e.g., 005010)")
    parser.add_argument("--no-code-values", action="store_true", help="Exclude code values")
    parser.add_argument("--no-freeform", action="store_true", help="Exclude freeform text")

    args = parser.parse_args()

    generator = SchemaGenerator(
        source_path=Path(args.source),
        output_path=Path(args.output),
        version=args.version,
        include_code_values=not args.no_code_values,
        include_freeform=not args.no_freeform,
    )
    generator.generate()


if __name__ == "__main__":
    main()
