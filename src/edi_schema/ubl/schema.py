"""
UBL Schema Loader.

Provides runtime loading of UBL schemas from XSD files.
"""

from pathlib import Path
from functools import lru_cache

from .models import (
    ABIE,
    CACElement,
    CBCElement,
    CodeList,
    DocumentType,
    QualifiedDataType,
    UBLSchema,
    UnqualifiedDataType,
)
from .schema_parsers import (
    list_document_schemas,
    parse_all_code_lists,
    parse_cac_elements,
    parse_cac_types,
    parse_cbc_elements,
    parse_cbc_types,
    parse_document_schema,
    parse_qdt,
    parse_udt,
)


class UBLSchemaLoader:
    """
    Runtime loader for UBL schemas from XSD files.

    This loader parses XSD files on demand. For faster loading,
    use the generated schema modules.

    Usage:
        loader = UBLSchemaLoader(Path("/path/to/UBL-2.5/xsd"))
        schema = loader.load("Invoice")
    """

    def __init__(self, xsd_path: Path, code_list_path: Path | None = None):
        """
        Initialize the schema loader.

        Args:
            xsd_path: Path to UBL xsd/ directory
            code_list_path: Path to code list directory (default: xsd/../cl/gc/default)
        """
        self.xsd_path = Path(xsd_path)
        self.common_path = self.xsd_path / "common"
        self.maindoc_path = self.xsd_path / "maindoc"

        if code_list_path:
            self.code_list_path = Path(code_list_path)
        else:
            # Default to cl/gc/default relative to xsd parent
            self.code_list_path = self.xsd_path.parent / "cl" / "gc" / "default"

        # Cache for loaded components
        self._udt_cache: dict[str, UnqualifiedDataType] | None = None
        self._qdt_cache: dict[str, QualifiedDataType] | None = None
        self._cbc_elements_cache: dict[str, CBCElement] | None = None
        self._cac_elements_cache: dict[str, CACElement] | None = None
        self._cac_types_cache: dict[str, ABIE] | None = None
        self._code_lists_cache: dict[str, CodeList] | None = None

    def load(self, document_type: str) -> UBLSchema:
        """
        Load a complete schema for a document type.

        Args:
            document_type: Document name (e.g., 'Invoice', 'Order')

        Returns:
            UBLSchema with all resolved references

        Raises:
            FileNotFoundError: If the document schema doesn't exist
        """
        # Find the document schema file
        schema_file = self.maindoc_path / f"UBL-{document_type}-2.5.xsd"
        if not schema_file.exists():
            raise FileNotFoundError(f"Schema not found: {schema_file}")

        # Parse document schema
        doc_type = parse_document_schema(schema_file)

        # Load common components (cached)
        udt_types = self._load_udt()
        qdt_types = self._load_qdt()
        cbc_elements = self._load_cbc_elements()
        cac_elements = self._load_cac_elements()
        cac_types = self._load_cac_types()
        code_lists = self._load_code_lists()

        # Collect ABIEs referenced by this document
        referenced_abies = self._collect_referenced_abies(doc_type.root_abie, cac_types)

        return UBLSchema(
            document_type=doc_type,
            abies=referenced_abies,
            cbc_elements=cbc_elements,
            cac_elements=cac_elements,
            udt_types=udt_types,
            qdt_types=qdt_types,
            code_lists=code_lists,
        )

    def list_document_types(self) -> list[str]:
        """
        List all available document types.

        Returns:
            List of document type names
        """
        return list_document_schemas(self.maindoc_path)

    def _load_udt(self) -> dict[str, UnqualifiedDataType]:
        """Load and cache UDT types."""
        if self._udt_cache is None:
            udt_file = self.common_path / "BDNDR-UnqualifiedDataTypes-1.1.xsd"
            if udt_file.exists():
                self._udt_cache = parse_udt(udt_file)
            else:
                self._udt_cache = {}
        return self._udt_cache

    def _load_qdt(self) -> dict[str, QualifiedDataType]:
        """Load and cache QDT types."""
        if self._qdt_cache is None:
            qdt_file = self.common_path / "UBL-QualifiedDataTypes-2.5.xsd"
            if qdt_file.exists():
                self._qdt_cache = parse_qdt(qdt_file)
            else:
                self._qdt_cache = {}
        return self._qdt_cache

    def _load_cbc_elements(self) -> dict[str, CBCElement]:
        """Load and cache CBC elements."""
        if self._cbc_elements_cache is None:
            cbc_file = self.common_path / "UBL-CommonBasicComponents-2.5.xsd"
            if cbc_file.exists():
                self._cbc_elements_cache = parse_cbc_elements(cbc_file)
            else:
                self._cbc_elements_cache = {}
        return self._cbc_elements_cache

    def _load_cac_elements(self) -> dict[str, CACElement]:
        """Load and cache CAC elements."""
        if self._cac_elements_cache is None:
            cac_file = self.common_path / "UBL-CommonAggregateComponents-2.5.xsd"
            if cac_file.exists():
                self._cac_elements_cache = parse_cac_elements(cac_file)
            else:
                self._cac_elements_cache = {}
        return self._cac_elements_cache

    def _load_cac_types(self) -> dict[str, ABIE]:
        """Load and cache CAC types (ABIEs)."""
        if self._cac_types_cache is None:
            cac_file = self.common_path / "UBL-CommonAggregateComponents-2.5.xsd"
            if cac_file.exists():
                self._cac_types_cache = parse_cac_types(cac_file)
            else:
                self._cac_types_cache = {}
        return self._cac_types_cache

    def _load_code_lists(self) -> dict[str, CodeList]:
        """Load and cache code lists."""
        if self._code_lists_cache is None:
            if self.code_list_path.exists():
                self._code_lists_cache = parse_all_code_lists(self.code_list_path)
            else:
                self._code_lists_cache = {}
        return self._code_lists_cache

    def _collect_referenced_abies(
        self,
        root_abie: ABIE,
        all_abies: dict[str, ABIE],
        collected: dict[str, ABIE] | None = None,
    ) -> dict[str, ABIE]:
        """
        Recursively collect all ABIEs referenced by a document.

        Args:
            root_abie: The root ABIE to start from
            all_abies: All available ABIEs
            collected: Already collected ABIEs (for recursion)

        Returns:
            Dictionary of all referenced ABIEs
        """
        if collected is None:
            collected = {}

        # Add root ABIE
        collected[root_abie.name] = root_abie

        # Follow ASBIE references
        for asbie in root_abie.asbies:
            abie_name = asbie.associated_abie
            if abie_name in collected:
                continue  # Already processed

            if abie_name in all_abies:
                referenced_abie = all_abies[abie_name]
                self._collect_referenced_abies(referenced_abie, all_abies, collected)

        return collected


@lru_cache(maxsize=128)
def get_schema(document_type: str, xsd_path: str) -> UBLSchema:
    """
    Convenience function to load a schema with caching.

    Args:
        document_type: Document name (e.g., 'Invoice')
        xsd_path: Path to UBL xsd/ directory

    Returns:
        UBLSchema for the document type
    """
    loader = UBLSchemaLoader(Path(xsd_path))
    return loader.load(document_type)
