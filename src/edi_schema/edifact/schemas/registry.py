"""
EDIFACT Schema Version Registry.

Provides version dispatch and schema loading from generated modules.
"""

from typing import TYPE_CHECKING

from edi_schema.edifact.models import (
    Composite,
    DataElement,
    MessageSpec,
    ResolvedMessageSpec,
    Segment,
    SegmentGroup,
    SegmentRef,
)

if TYPE_CHECKING:
    pass


# Available pre-generated versions
AVAILABLE_VERSIONS = ["d96a", "d23a"]
DEFAULT_VERSION = "d23a"


# Lazy-load version modules to avoid import overhead
_version_modules: dict[str, dict] = {}


def _get_version_module(version: str) -> dict:
    """Get the generated module for a version (lazy-loaded)."""
    version_normalized = version.lower().replace(".", "")

    if version_normalized not in _version_modules:
        if version_normalized == "d96a":
            from edi_schema.edifact.schemas import d96a

            _version_modules[version_normalized] = {
                "data_elements": d96a.DATA_ELEMENTS,
                "composites": d96a.COMPOSITES,
                "segments": d96a.SEGMENTS,
                "messages": d96a.MESSAGES,
                "get_data_element": d96a.get_data_element,
                "get_composite": d96a.get_composite,
                "get_segment": d96a.get_segment,
                "get_message": d96a.get_message,
                "list_messages": d96a.list_messages,
                "element_types": d96a.ELEMENT_TYPES,
                "segment_elements": d96a.SEGMENT_ELEMENTS,
                "composite_components": d96a.COMPOSITE_COMPONENTS,
                "element_codes": d96a.ELEMENT_CODES,
            }
        elif version_normalized == "d23a":
            from edi_schema.edifact.schemas import d23a

            _version_modules[version_normalized] = {
                "data_elements": d23a.DATA_ELEMENTS,
                "composites": d23a.COMPOSITES,
                "segments": d23a.SEGMENTS,
                "messages": d23a.MESSAGES,
                "get_data_element": d23a.get_data_element,
                "get_composite": d23a.get_composite,
                "get_segment": d23a.get_segment,
                "get_message": d23a.get_message,
                "list_messages": d23a.list_messages,
                "element_types": d23a.ELEMENT_TYPES,
                "segment_elements": d23a.SEGMENT_ELEMENTS,
                "composite_components": d23a.COMPOSITE_COMPONENTS,
                "element_codes": d23a.ELEMENT_CODES,
            }
        else:
            raise ValueError(f"Unknown EDIFACT version: {version}")

    return _version_modules[version_normalized]


def list_versions() -> list[str]:
    """List all available EDIFACT versions."""
    return AVAILABLE_VERSIONS.copy()


def list_messages(version: str = DEFAULT_VERSION) -> list[str]:
    """List all message IDs for a version."""
    module = _get_version_module(version)
    return module["list_messages"]()


def get_data_element(
    element_id: str,
    version: str = DEFAULT_VERSION,
) -> DataElement | None:
    """Get a data element definition by ID."""
    module = _get_version_module(version)
    return module["get_data_element"](element_id)


def get_composite(
    composite_id: str,
    version: str = DEFAULT_VERSION,
) -> Composite | None:
    """Get a composite definition by ID."""
    module = _get_version_module(version)
    return module["get_composite"](composite_id)


def get_segment(
    segment_id: str,
    version: str = DEFAULT_VERSION,
) -> Segment | None:
    """Get a segment definition by ID."""
    module = _get_version_module(version)
    return module["get_segment"](segment_id)


def get_message(
    message_id: str,
    version: str = DEFAULT_VERSION,
) -> MessageSpec | None:
    """Get a message specification by ID."""
    module = _get_version_module(version)
    return module["get_message"](message_id)


def get_schema(
    message_id: str,
    version: str = DEFAULT_VERSION,
) -> ResolvedMessageSpec | None:
    """
    Get a fully resolved message schema.

    This builds a ResolvedMessageSpec instance from the generated modules,
    loading all the segments, composites, and elements used by the message.

    Args:
        message_id: The message ID (e.g., "INVOIC", "ORDERS")
        version: The schema version (e.g., "d23a", "d96a")

    Returns:
        ResolvedMessageSpec instance or None if not found
    """
    module = _get_version_module(version)

    # Get message spec
    msg = module["get_message"](message_id)
    if not msg:
        return None

    # Collect all referenced components
    segments: dict[str, Segment] = {}
    composites: dict[str, Composite] = {}
    elements: dict[str, DataElement] = {}

    # Walk the message structure to collect segment tags
    segment_tags = _collect_segment_tags(msg.structure)

    for seg_tag in segment_tags:
        seg = module["get_segment"](seg_tag)
        if seg:
            segments[seg_tag] = seg

            # Collect elements and composites used by this segment
            for seg_elem in seg.elements:
                elem_tag = seg_elem.tag
                if seg_elem.is_composite:
                    comp = module["get_composite"](elem_tag)
                    if comp:
                        composites[elem_tag] = comp
                        # Get elements in composite
                        for comp_elem in comp.components:
                            data_elem = module["get_data_element"](comp_elem.element_tag)
                            if data_elem:
                                elements[comp_elem.element_tag] = data_elem
                else:
                    data_elem = module["get_data_element"](elem_tag)
                    if data_elem:
                        elements[elem_tag] = data_elem

    return ResolvedMessageSpec(
        spec=msg,
        segments=segments,
        composites=composites,
        elements=elements,
    )


def _collect_segment_tags(
    structure: list[SegmentRef | SegmentGroup],
) -> set[str]:
    """Recursively collect all segment tags from a message structure."""
    tags: set[str] = set()

    for item in structure:
        if isinstance(item, SegmentRef):
            tags.add(item.segment_tag)
        elif isinstance(item, SegmentGroup):
            tags.update(_collect_segment_tags(item.children))

    return tags


class GeneratedEdifactSchemaLoader:
    """
    Schema loader using pre-generated EDIFACT schemas.

    This is the recommended loader for production use.
    Much faster than runtime parsing from directory files.

    Usage:
        loader = GeneratedEdifactSchemaLoader(version="d23a")
        schema = loader.load("INVOIC")  # Returns ResolvedMessageSpec
    """

    def __init__(self, version: str = DEFAULT_VERSION):
        """Initialize with a schema version."""
        self.version = version.lower().replace(".", "")
        self._cache: dict[str, ResolvedMessageSpec] = {}

    def exists(self, message_id: str) -> bool:
        """Check if a message exists."""
        try:
            module = _get_version_module(self.version)
            return message_id.upper() in module["messages"]
        except ValueError:
            return False

    def load(self, message_id: str) -> ResolvedMessageSpec:
        """
        Load a message schema.

        Args:
            message_id: The message ID (e.g., "INVOIC")

        Returns:
            ResolvedMessageSpec instance

        Raises:
            ValueError: If message not found
        """
        message_id_upper = message_id.upper()

        if message_id_upper not in self._cache:
            schema = get_schema(message_id_upper, version=self.version)
            if schema is None:
                raise ValueError(f"Message {message_id} not found in version {self.version}")
            self._cache[message_id_upper] = schema

        return self._cache[message_id_upper]

    def list_schemas(self) -> list[str]:
        """List all available message IDs."""
        return list_messages(self.version)

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
