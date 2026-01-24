"""
Schema Repository for loading and caching EDI schemas.

The repository provides a unified interface for loading schemas
from both X12 and EDIFACT formats.

By default, uses pre-generated schemas for better performance.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from edi_schema.core.types import SchemaLike

if TYPE_CHECKING:
    from edi_schema.edifact.schema.loader import EdifactSchemaLoader
    from edi_schema.edifact.schemas import GeneratedEdifactSchemaLoader
    from edi_schema.x12.schema import X12SchemaLoader
    from edi_schema.x12.schemas import GeneratedX12SchemaLoader


class SchemaRepository:
    """
    Repository for loading and caching EDI schemas.

    Provides a unified interface to load schemas from either X12 or EDIFACT
    format directories. By default, uses pre-generated schemas for better
    performance (~50x faster than runtime parsing).

    Example (using pre-generated schemas - recommended):
        >>> repo = SchemaRepository()
        >>> repo.exists("x12", "850")
        True
        >>> schema = repo.load("x12", "850")
        >>> schema.name
        'Purchase Order'
        >>> repo.exists("edifact", "INVOIC")
        True
        >>> schema = repo.load("edifact", "INVOIC")

    Example (using runtime parsing for custom schemas):
        >>> repo = SchemaRepository(
        ...     x12_path="/path/to/x12/005010",
        ...     edifact_path="/path/to/edifact/d23a"
        ... )
    """

    def __init__(
        self,
        x12_path: str | Path | None = None,
        edifact_path: str | Path | None = None,
        *,
        x12_version: str = "005010",
        edifact_version: str = "d23a",
    ):
        """
        Initialize the schema repository.

        When paths are not provided, uses pre-generated schemas (recommended).
        When paths are provided, uses runtime parsing for those formats.

        Args:
            x12_path: Path to X12 schema directory (None = use generated)
            edifact_path: Path to EDIFACT schema directory (None = use generated)
            x12_version: X12 version for generated schemas (e.g., "005010", "004010")
            edifact_version: EDIFACT version for generated schemas (e.g., "d23a", "d96a")
        """
        self._x12_path = Path(x12_path) if x12_path else None
        self._edifact_path = Path(edifact_path) if edifact_path else None
        self._x12_version = x12_version
        self._edifact_version = edifact_version

        # Lazy-loaded schema loaders
        self._x12_loader: "X12SchemaLoader | GeneratedX12SchemaLoader | None" = None
        self._edifact_loader: "EdifactSchemaLoader | GeneratedEdifactSchemaLoader | None" = None

        # Cache for loaded schemas
        self._cache: dict[tuple[str, str, str], SchemaLike] = {}

    def _get_x12_loader(self) -> "X12SchemaLoader | GeneratedX12SchemaLoader":
        """Get or create the X12 schema loader."""
        if self._x12_loader is None:
            if self._x12_path is not None:
                # Use runtime loader for custom schema directories
                from edi_schema.x12.schema import X12SchemaLoader

                self._x12_loader = X12SchemaLoader(self._x12_path)
            else:
                # Default to pre-generated schemas for better performance
                from edi_schema.x12.schemas import GeneratedX12SchemaLoader

                self._x12_loader = GeneratedX12SchemaLoader(version=self._x12_version)
        return self._x12_loader

    def _get_edifact_loader(self) -> "EdifactSchemaLoader | GeneratedEdifactSchemaLoader":
        """Get or create the EDIFACT schema loader."""
        if self._edifact_loader is None:
            if self._edifact_path is not None:
                # Use runtime loader for custom schema directories
                from edi_schema.edifact.schema.loader import EdifactSchemaLoader

                self._edifact_loader = EdifactSchemaLoader(self._edifact_path)
            else:
                # Default to pre-generated schemas for better performance
                from edi_schema.edifact.schemas import GeneratedEdifactSchemaLoader

                self._edifact_loader = GeneratedEdifactSchemaLoader(version=self._edifact_version)
        return self._edifact_loader

    def exists(
        self,
        format: str,
        schema_id: str,
        version: str | None = None,
    ) -> bool:
        """
        Check if a schema exists in the repository.

        Args:
            format: EDI format ('x12' or 'edifact')
            schema_id: Schema identifier (e.g., '850', 'INVOIC')
            version: Optional version (uses default if not specified)

        Returns:
            True if the schema exists, False otherwise
        """
        format_lower = format.lower()

        if format_lower == "x12":
            # GeneratedSchemaLoader works without a path
            return self._get_x12_loader().exists(schema_id)

        elif format_lower == "edifact":
            # Use generated schemas when no path provided
            return self._get_edifact_loader().exists(schema_id)

        else:
            raise ValueError(f"Unknown format: {format}. Use 'x12' or 'edifact'.")

    def load(
        self,
        format: str,
        schema_id: str,
        version: str | None = None,
    ) -> SchemaLike:
        """
        Load a schema from the repository.

        Args:
            format: EDI format ('x12' or 'edifact')
            schema_id: Schema identifier (e.g., '850', 'INVOIC')
            version: Optional version (uses default if not specified)

        Returns:
            Loaded schema object implementing SchemaLike protocol

        Raises:
            ValueError: If format is unknown or schema not found
        """
        format_lower = format.lower()
        version = version or "default"

        # Check cache
        cache_key = (format_lower, schema_id, version)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Load schema
        if format_lower == "x12":
            schema = self._get_x12_loader().load(schema_id)
        elif format_lower == "edifact":
            schema = self._get_edifact_loader().load(schema_id)
        else:
            raise ValueError(f"Unknown format: {format}. Use 'x12' or 'edifact'.")

        # Cache and return
        self._cache[cache_key] = schema
        return schema

    def list_schemas(self, format: str) -> list[str]:
        """
        List all available schema IDs for a format.

        Args:
            format: EDI format ('x12' or 'edifact')

        Returns:
            List of schema identifiers
        """
        format_lower = format.lower()

        if format_lower == "x12":
            return self._get_x12_loader().list_schemas()
        elif format_lower == "edifact":
            return self._get_edifact_loader().list_schemas()
        else:
            raise ValueError(f"Unknown format: {format}. Use 'x12' or 'edifact'.")

    def clear_cache(self) -> None:
        """Clear the schema cache."""
        self._cache.clear()
