"""
X12 Schema Parser and Models.

This module provides parsing and schema generation for ANSI ASC X12 EDI format,
the primary standard for North American electronic data interchange.

Components:
- enums: X12-specific enumerations (data types, requirements, etc.)
- models: Dataclass models for elements, segments, composites, transactions
- parsers: Parsers for X12 schema definition files
- schema: Schema loader that builds complete transaction set schemas
"""

from edi_schema.x12.enums import (
    FUNCTIONAL_GROUP_CODES,
    DataElementType,
    FreeformTextType,
    NoteType,
    RequirementDesignator,
    TransactionSetArea,
    UsageIndicator,
)
from edi_schema.x12.models import (
    CodeSource,
    Composite,
    CompositeElement,
    DataElement,
    LoopDefinition,
    Segment,
    SegmentElement,
    SegmentNote,
    TransactionSet,
    TransactionSetSegment,
)
from edi_schema.x12.schema import X12Schema, X12SchemaLoader
from edi_schema.x12.schemas import GeneratedX12SchemaLoader

__all__ = [
    # Enums
    "DataElementType",
    "RequirementDesignator",
    "TransactionSetArea",
    "FreeformTextType",
    "NoteType",
    "UsageIndicator",
    "FUNCTIONAL_GROUP_CODES",
    # Models
    "DataElement",
    "CompositeElement",
    "Composite",
    "SegmentElement",
    "SegmentNote",
    "Segment",
    "TransactionSetSegment",
    "LoopDefinition",
    "TransactionSet",
    "CodeSource",
    # Schema
    "X12Schema",
    "X12SchemaLoader",
    "GeneratedX12SchemaLoader",
]
