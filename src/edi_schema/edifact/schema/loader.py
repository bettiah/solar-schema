"""
EDIFACT Schema Loader.

Runtime schema loader that parses EDIFACT directory files.
Implements the same interface as GeneratedEdifactSchemaLoader.

For better performance, use GeneratedEdifactSchemaLoader with pre-generated schemas.
"""

from pathlib import Path

from ..models import Composite, DataElement, ResolvedMessageSpec, Segment
from .registry import EdifactRegistry
from .resolver import EdifactResolver


class EdifactSchemaLoader:
    """
    Loader for EDIFACT schemas from directory files.

    Parses schema files at runtime. For better performance (~50x faster),
    use GeneratedEdifactSchemaLoader with pre-generated schemas.

    Implements the same interface as GeneratedEdifactSchemaLoader:
    - exists(schema_id) - Check if a message schema exists
    - load(schema_id) - Load and resolve a message schema
    - list_schemas() - List all available message schemas
    - get_segment(segment_id) - Get segment definition
    - get_element(element_id) - Get element definition
    - get_composite(composite_id) - Get composite definition

    Example:
        >>> loader = EdifactSchemaLoader("/path/to/d23a")
        >>> loader.exists("INVOIC")
        True
        >>> schema = loader.load("INVOIC")
        >>> schema.spec.code
        'INVOIC'
    """

    def __init__(self, schema_path: str | Path) -> None:
        """
        Initialize the schema loader.

        Args:
            schema_path: Path to EDIFACT version directory (e.g., d23a/, d96a/)
        """
        self._base_path = Path(schema_path)
        self._registry: EdifactRegistry | None = None
        self._resolver: EdifactResolver | None = None
        self._loaded = False
        self._cache: dict[str, ResolvedMessageSpec] = {}

    def _ensure_loaded(self) -> None:
        """Lazy-load the registry and resolver."""
        if self._loaded:
            return

        self._registry = EdifactRegistry()
        self._registry.load_from_directory(self._base_path)

        self._resolver = EdifactResolver(self._registry)
        self._resolver.resolve_all()

        self._loaded = True

    @property
    def registry(self) -> EdifactRegistry:
        """Get the underlying registry (loads if needed)."""
        self._ensure_loaded()
        assert self._registry is not None
        return self._registry

    @property
    def resolver(self) -> EdifactResolver:
        """Get the resolver (loads registry if needed)."""
        self._ensure_loaded()
        assert self._resolver is not None
        return self._resolver

    def exists(self, schema_id: str) -> bool:
        """
        Check if a message schema exists.

        Args:
            schema_id: Message code (e.g., 'INVOIC', 'ORDERS')

        Returns:
            True if the message schema exists
        """
        self._ensure_loaded()
        return self.registry.message_exists(schema_id)

    def load(self, schema_id: str) -> ResolvedMessageSpec:
        """
        Load and resolve a message schema.

        Args:
            schema_id: Message code (e.g., 'INVOIC', 'ORDERS')

        Returns:
            Fully resolved message specification

        Raises:
            ValueError: If message schema not found
        """
        cache_key = schema_id.upper()
        if cache_key in self._cache:
            return self._cache[cache_key]

        self._ensure_loaded()

        message = self.registry.load_message(schema_id)
        if message is None:
            raise ValueError(f"Message schema not found: {schema_id}")

        resolved = self.resolver.resolve_message(message)
        self._cache[cache_key] = resolved

        return resolved

    def list_schemas(self) -> list[str]:
        """
        List all available message schema IDs.

        Returns:
            List of message codes (e.g., ['INVOIC', 'ORDERS', 'DESADV', ...])
        """
        self._ensure_loaded()
        return self.registry.list_available_messages()

    def get_segment(self, segment_id: str) -> Segment | None:
        """
        Get a segment definition by ID.

        Args:
            segment_id: Segment tag (e.g., 'NAD', 'DTM')

        Returns:
            Segment or None if not found
        """
        self._ensure_loaded()
        return self.registry.get_segment(segment_id)

    def get_element(self, element_id: str) -> DataElement | None:
        """
        Get a data element definition by ID.

        Args:
            element_id: Element tag (e.g., '1001', '3039')

        Returns:
            DataElement or None if not found
        """
        self._ensure_loaded()
        return self.registry.get_element(element_id)

    def get_composite(self, composite_id: str) -> Composite | None:
        """
        Get a composite definition by ID.

        Args:
            composite_id: Composite tag (e.g., 'C082', 'C507')

        Returns:
            Composite or None if not found
        """
        self._ensure_loaded()
        return self.registry.get_composite(composite_id)

    def clear_cache(self) -> None:
        """Clear the resolved message cache."""
        self._cache.clear()

    @property
    def stats(self) -> dict[str, int]:
        """Get statistics about loaded components."""
        self._ensure_loaded()
        stats = self.registry.stats
        stats["messages_cached"] = len(self._cache)
        return stats
