"""
EDIFACT Schema Code Generator.

Generates Python schema modules from EDIFACT directory specification files
using Jinja2 templates.
"""

from dataclasses import dataclass
from pathlib import Path

import jinja2

from edi_schema.edifact.models import SegmentGroup, SegmentRef
from edi_schema.edifact.schema.registry import EdifactRegistry

# Path to templates directory
TEMPLATES_DIR = Path(__file__).parent / "templates"


@dataclass
class GeneratorConfig:
    """Configuration for schema generation."""

    source_path: Path
    output_path: Path
    version: str
    include_codes: bool = True
    include_descriptions: bool = True


class EdifactSchemaGenerator:
    """
    Generates Python schema modules from EDIFACT directory files.

    Usage:
        generator = EdifactSchemaGenerator(
            source_path=Path("~/Downloads/edi/schema/edifact/d96a"),
            output_path=Path("src/edi_schema/edifact/schemas/d96a"),
            version="d96a",
        )
        generator.generate()
    """

    def __init__(
        self,
        source_path: Path,
        output_path: Path,
        version: str,
        include_codes: bool = True,
        include_descriptions: bool = True,
    ):
        self.config = GeneratorConfig(
            source_path=Path(source_path).expanduser(),
            output_path=Path(output_path),
            version=version,
            include_codes=include_codes,
            include_descriptions=include_descriptions,
        )
        self._registry: EdifactRegistry | None = None
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
        env.filters["repr"] = repr
        env.filters["structure_repr"] = self._structure_repr
        return env

    @property
    def registry(self) -> EdifactRegistry:
        """Lazy-load the EDIFACT registry."""
        if self._registry is None:
            self._registry = EdifactRegistry()
            self._registry.load_from_directory(self.config.source_path)
        return self._registry

    def generate(self) -> None:
        """Generate all schema modules."""
        self.config.output_path.mkdir(parents=True, exist_ok=True)

        print(f"Generating EDIFACT {self.config.version} schemas...")
        print(f"  Source: {self.config.source_path}")
        print(f"  Output: {self.config.output_path}")

        # Generate modules
        self._generate_init()
        self._generate_data_elements()
        self._generate_composites()
        self._generate_segments()
        self._generate_messages()
        self._generate_lookups()

        print(f"Generated schemas in {self.config.output_path}")

    def _generate_init(self) -> None:
        """Generate __init__.py for the version package."""
        template = self._env.get_template("__init__.py.j2")
        content = template.render(version=self.config.version)
        self._write_file("__init__.py", content)

    def _generate_data_elements(self) -> None:
        """Generate data_elements.py."""
        elements = self.registry.elements
        sorted_elements = sorted(
            elements.values(), key=lambda x: int(x.tag) if x.tag.isdigit() else 0
        )

        template = self._env.get_template("data_elements.py.j2")
        content = template.render(
            version=self.config.version,
            elements=sorted_elements,
            include_codes=self.config.include_codes,
            include_descriptions=self.config.include_descriptions,
        )
        self._write_file("data_elements.py", content)
        print(f"  Generated {len(elements)} data elements")

    def _generate_composites(self) -> None:
        """Generate composites.py."""
        composites = self.registry.composites
        sorted_composites = sorted(composites.values(), key=lambda x: x.tag)

        template = self._env.get_template("composites.py.j2")
        content = template.render(
            version=self.config.version,
            composites=sorted_composites,
            include_descriptions=self.config.include_descriptions,
        )
        self._write_file("composites.py", content)
        print(f"  Generated {len(composites)} composites")

    def _generate_segments(self) -> None:
        """Generate segments.py."""
        segments = self.registry.segments
        sorted_segments = sorted(segments.values(), key=lambda x: x.tag)

        template = self._env.get_template("segments.py.j2")
        content = template.render(
            version=self.config.version,
            segments=sorted_segments,
            include_descriptions=self.config.include_descriptions,
        )
        self._write_file("segments.py", content)
        print(f"  Generated {len(segments)} segments")

    def _generate_messages(self) -> None:
        """Generate messages package with one file per message."""
        message_codes = self.registry.list_available_messages()

        # Create messages directory
        messages_dir = self.config.output_path / "messages"
        messages_dir.mkdir(parents=True, exist_ok=True)

        # Generate individual message files
        single_template = self._env.get_template("message_single.py.j2")
        generated_codes = []

        for code in sorted(message_codes):
            msg = self.registry.load_message(code)
            if msg:
                content = single_template.render(msg=msg)
                filename = f"{code.lower()}.py"
                with open(messages_dir / filename, "w", encoding="utf-8") as f:
                    f.write(content)
                generated_codes.append(code)

        # Generate messages/__init__.py with lazy loading
        init_template = self._env.get_template("messages_init.py.j2")
        init_content = init_template.render(
            version=self.config.version,
            message_codes=generated_codes,
        )
        with open(messages_dir / "__init__.py", "w", encoding="utf-8") as f:
            f.write(init_content)

        print(f"  Generated {len(generated_codes)} messages in messages/")

    def _generate_lookups(self) -> None:
        """Generate lookups.py with fast lookup tables."""
        elements = self.registry.elements
        segments = self.registry.segments
        composites = self.registry.composites

        sorted_elements = sorted(
            elements.values(), key=lambda x: int(x.tag) if x.tag.isdigit() else 0
        )
        sorted_segments = sorted(segments.values(), key=lambda x: x.tag)
        sorted_composites = sorted(composites.values(), key=lambda x: x.tag)

        template = self._env.get_template("lookups.py.j2")
        content = template.render(
            version=self.config.version,
            elements=sorted_elements,
            segments=sorted_segments,
            composites=sorted_composites,
            include_codes=self.config.include_codes,
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

    @staticmethod
    def _structure_repr(structure: list[SegmentRef | SegmentGroup], indent: int = 0) -> str:
        """
        Generate Python code representation of a message structure.

        Handles nested SegmentRef and SegmentGroup objects.
        """
        if not structure:
            return "[]"

        lines = []
        prefix = "    " * indent

        for item in structure:
            if isinstance(item, SegmentRef):
                lines.append(
                    f"{prefix}SegmentRef("
                    f"position={item.position}, "
                    f"segment_tag={item.segment_tag!r}, "
                    f"mandatory={item.mandatory}, "
                    f"max_repeat={item.max_repeat}"
                    f"),"
                )
            elif isinstance(item, SegmentGroup):
                children_repr = EdifactSchemaGenerator._structure_repr(item.children, indent + 1)
                lines.append(
                    f"{prefix}SegmentGroup("
                    f"number={item.number}, "
                    f"mandatory={item.mandatory}, "
                    f"max_repeat={item.max_repeat}, "
                    f"children=[\n{children_repr}\n{prefix}]),"
                )

        return "\n".join(lines)


def main():
    """Command-line interface for schema generation."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate EDIFACT schema modules")
    parser.add_argument("--source", required=True, help="Path to EDIFACT source directory")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--version", required=True, help="Version identifier (e.g., d96a)")
    parser.add_argument("--no-codes", action="store_true", help="Exclude code values")
    parser.add_argument("--no-descriptions", action="store_true", help="Exclude descriptions")

    args = parser.parse_args()

    generator = EdifactSchemaGenerator(
        source_path=Path(args.source),
        output_path=Path(args.output),
        version=args.version,
        include_codes=not args.no_codes,
        include_descriptions=not args.no_descriptions,
    )
    generator.generate()


if __name__ == "__main__":
    main()
