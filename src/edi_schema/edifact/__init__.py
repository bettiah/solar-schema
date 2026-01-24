"""
EDIFACT Schema Parser and Models.

This module provides parsing and schema generation for UN/EDIFACT format,
the international standard for electronic data interchange.

Components:
- models: Dataclass models for elements, composites, segments, messages
- parsers: Parsers for EDIFACT directory files (UNCL, EDED, EDCD, EDSD, EDMD)
- schema: Schema loader with reference resolution

Example usage (runtime parsing):
    >>> from edi_schema.edifact import EdifactSchemaLoader
    >>> loader = EdifactSchemaLoader("/path/to/d23a")
    >>> schema = loader.load("INVOIC")
    >>> print(schema.spec.name)
    'Invoice message'

Example usage (pre-generated schemas - recommended):
    >>> from edi_schema.edifact.schemas import GeneratedEdifactSchemaLoader
    >>> loader = GeneratedEdifactSchemaLoader(version="d23a")
    >>> schema = loader.load("INVOIC")
"""

from .models import (
    Component,
    Composite,
    DataElement,
    MessageSpec,
    ResolvedMessageSpec,
    Segment,
    SegmentElement,
    SegmentGroup,
    SegmentRef,
)
from .schema import EdifactRegistry, EdifactResolver, EdifactSchemaLoader

__all__ = [
    # Models
    "DataElement",
    "Composite",
    "Component",
    "Segment",
    "SegmentElement",
    "SegmentRef",
    "SegmentGroup",
    "MessageSpec",
    "ResolvedMessageSpec",
    # Schema loading
    "EdifactSchemaLoader",
    "EdifactRegistry",
    "EdifactResolver",
]
