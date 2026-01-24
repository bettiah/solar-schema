"""
EDIFACT Pre-Generated Schemas.

Provides fast access to pre-generated EDIFACT schema definitions.
Much faster than runtime parsing from directory files.

Usage:
    from edi_schema.edifact.schemas import GeneratedEdifactSchemaLoader

    loader = GeneratedEdifactSchemaLoader(version="d23a")
    schema = loader.load("INVOIC")

    # Or use convenience functions
    from edi_schema.edifact.schemas import get_schema, get_segment

    schema = get_schema("INVOIC", version="d23a")
    segment = get_segment("NAD", version="d96a")

Available versions:
    - d23a: UN/EDIFACT D.23A (199 messages)
    - d96a: UN/EDIFACT D.96A (125 messages)
"""

from .registry import (
    AVAILABLE_VERSIONS,
    DEFAULT_VERSION,
    GeneratedEdifactSchemaLoader,
    get_composite,
    get_data_element,
    get_message,
    get_schema,
    get_segment,
    list_messages,
    list_versions,
)

__all__ = [
    # Loader class
    "GeneratedEdifactSchemaLoader",
    # Version info
    "list_versions",
    "list_messages",
    "AVAILABLE_VERSIONS",
    "DEFAULT_VERSION",
    # Convenience functions
    "get_data_element",
    "get_composite",
    "get_segment",
    "get_message",
    "get_schema",
]
