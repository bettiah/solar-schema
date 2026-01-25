"""
X12 Schema Version Registry.

Provides version dispatch and schema loading from generated modules.
"""

from typing import TYPE_CHECKING

from edi_schema.x12.models import (
    Composite,
    DataElement,
    Segment,
    TransactionSet,
)
from edi_schema.x12.parser.loop_hierarchy import LoopNode, build_loop_hierarchy

if TYPE_CHECKING:
    from edi_schema.x12.schema import X12Schema


# Lazy-load version modules to avoid import overhead
_version_modules: dict[str, dict] = {}


def _get_version_module(version: str) -> dict:
    """Get the generated module for a version (lazy-loaded)."""
    if version not in _version_modules:
        if version == "005010":
            from edi_schema.x12.schemas import v005010

            _version_modules[version] = {
                "transaction_sets": v005010.TRANSACTION_SETS,
                "segments": v005010.SEGMENTS,
                "data_elements": v005010.DATA_ELEMENTS,
                "composites": v005010.COMPOSITES,
                "element_types": v005010.ELEMENT_TYPES,
                "segment_elements": v005010.SEGMENT_ELEMENTS,
                "get_transaction_set": v005010.get_transaction_set,
                "get_segment": v005010.get_segment,
                "get_data_element": v005010.get_data_element,
                "get_composite": v005010.get_composite,
            }
        elif version == "004010":
            from edi_schema.x12.schemas import v004010

            _version_modules[version] = {
                "transaction_sets": v004010.TRANSACTION_SETS,
                "segments": v004010.SEGMENTS,
                "data_elements": v004010.DATA_ELEMENTS,
                "composites": v004010.COMPOSITES,
                "element_types": v004010.ELEMENT_TYPES,
                "segment_elements": v004010.SEGMENT_ELEMENTS,
                "get_transaction_set": v004010.get_transaction_set,
                "get_segment": v004010.get_segment,
                "get_data_element": v004010.get_data_element,
                "get_composite": v004010.get_composite,
            }
        else:
            raise ValueError(f"Unknown schema version: {version}")
    return _version_modules[version]


def list_versions() -> list[str]:
    """List all available schema versions."""
    return ["004010", "005010"]


def list_transaction_sets(version: str = "005010") -> list[str]:
    """List all transaction set IDs for a version."""
    module = _get_version_module(version)
    return sorted(module["transaction_sets"].keys())


def get_transaction_set(
    transaction_id: str,
    version: str = "005010",
) -> TransactionSet | None:
    """Get a transaction set definition by ID."""
    module = _get_version_module(version)
    return module["get_transaction_set"](transaction_id)


def get_segment(
    segment_id: str,
    version: str = "005010",
) -> Segment | None:
    """Get a segment definition by ID."""
    module = _get_version_module(version)
    return module["get_segment"](segment_id)


def get_element(
    element_id: str,
    version: str = "005010",
) -> DataElement | None:
    """Get a data element definition by ID."""
    module = _get_version_module(version)
    return module["get_data_element"](element_id)


def get_composite(
    composite_id: str,
    version: str = "005010",
) -> Composite | None:
    """Get a composite definition by ID."""
    module = _get_version_module(version)
    return module["get_composite"](composite_id)


def get_schema(
    transaction_id: str,
    version: str = "005010",
) -> "X12Schema | None":
    """
    Get a complete schema for a transaction set.

    This builds an X12Schema instance from the generated modules,
    loading only the segments and elements used by the transaction set.

    Args:
        transaction_id: The transaction set ID (e.g., "837")
        version: The schema version (e.g., "005010")

    Returns:
        X12Schema instance or None if not found
    """
    from edi_schema.x12.schema import X12Schema

    module = _get_version_module(version)

    # Get transaction set
    txn = module["get_transaction_set"](transaction_id)
    if not txn:
        return None

    # Collect segments used by this transaction
    segments: dict[str, Segment] = {}
    elements: dict[str, DataElement] = {}
    composites: dict[str, Composite] = {}

    segment_ids = {seg.segment_id for seg in txn.structure}
    for seg_id in segment_ids:
        seg = module["get_segment"](seg_id)
        if seg:
            segments[seg_id] = seg

            # Collect elements and composites used by this segment
            for elem in seg.elements:
                elem_id = elem.element_id
                if elem_id.startswith("C"):
                    # Composite
                    comp = module["get_composite"](elem_id)
                    if comp:
                        composites[elem_id] = comp
                        # Get elements in composite
                        for comp_elem in comp.elements:
                            data_elem = module["get_data_element"](comp_elem.element_id)
                            if data_elem:
                                elements[comp_elem.element_id] = data_elem
                else:
                    # Simple element
                    data_elem = module["get_data_element"](elem_id)
                    if data_elem:
                        elements[elem_id] = data_elem

    schema = X12Schema(
        transaction_set=txn,
        segments=segments,
        elements=elements,
        composites=composites,
        version=version,
    )

    # Build loop hierarchy once and cache it on the schema
    schema.loop_hierarchy = build_loop_hierarchy(schema)

    return schema


class GeneratedX12SchemaLoader:
    """
    Schema loader compatible with X12SchemaLoader API.

    Uses pre-generated schemas instead of parsing text files at runtime.

    Usage:
        loader = GeneratedSchemaLoader(version="005010")
        schema = loader.load("837")  # Returns X12Schema
    """

    def __init__(self, version: str = "005010"):
        """Initialize with a schema version."""
        self.version = version
        self._cache: dict[str, "X12Schema"] = {}

    def exists(self, transaction_id: str) -> bool:
        """Check if a transaction set exists."""
        try:
            module = _get_version_module(self.version)
            return transaction_id in module["transaction_sets"]
        except ValueError:
            return False

    def load(self, transaction_id: str) -> "X12Schema":
        """
        Load a transaction set schema.

        Args:
            transaction_id: The transaction set ID

        Returns:
            X12Schema instance

        Raises:
            ValueError: If transaction set not found
        """
        if transaction_id not in self._cache:
            schema = get_schema(transaction_id, version=self.version)
            if schema is None:
                raise ValueError(
                    f"Transaction set {transaction_id} not found in version {self.version}"
                )
            self._cache[transaction_id] = schema

        return self._cache[transaction_id]

    def list_schemas(self) -> list[str]:
        """List all available transaction set IDs."""
        return list_transaction_sets(self.version)

    def get_all_elements(self) -> dict[str, DataElement]:
        """Get all data elements."""
        module = _get_version_module(self.version)
        return {elem_id: module["get_data_element"](elem_id) for elem_id in module["data_elements"]}

    def get_all_segments(self) -> dict[str, Segment]:
        """Get all segments."""
        module = _get_version_module(self.version)
        return {seg_id: module["get_segment"](seg_id) for seg_id in module["segments"]}

    def get_all_composites(self) -> dict[str, Composite]:
        """Get all composites."""
        module = _get_version_module(self.version)
        return {comp_id: module["get_composite"](comp_id) for comp_id in module["composites"]}
