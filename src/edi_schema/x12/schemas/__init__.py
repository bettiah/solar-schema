"""
X12 Generated Schema Repository.

Provides fast access to pre-generated X12 schemas for validation and processing.

Usage:
    from edi_schema.x12.schemas import get_schema, get_segment, get_element

    # Load a complete transaction set schema
    schema = get_schema("837", version="005010")

    # Direct lookups
    segment = get_segment("NM1", version="005010")
    element = get_element("98", version="005010")
"""

from edi_schema.x12.schemas.registry import (
    GeneratedX12SchemaLoader,
    get_composite,
    get_element,
    get_schema,
    get_segment,
    get_transaction_set,
    list_transaction_sets,
    list_versions,
)

__all__ = [
    "get_schema",
    "get_segment",
    "get_element",
    "get_composite",
    "get_transaction_set",
    "list_versions",
    "list_transaction_sets",
    "GeneratedX12SchemaLoader",
]
