"""
EDI Schema Library

A Python library for parsing and validating Electronic Data Interchange (EDI)
documents using schema definitions.

Supported Formats:
- X12: ANSI ASC X12 (primary standard for North American EDI)
- EDIFACT: UN/EDIFACT (international EDI standard)
"""

from edi_schema.core.repository import SchemaRepository
from edi_schema.core.types import (
    CompositeLike,
    ElementLike,
    RequirementDesignator,
    SchemaLike,
    SegmentLike,
)

__version__ = "0.1.0"

__all__ = [
    "SchemaRepository",
    "ElementLike",
    "SegmentLike",
    "CompositeLike",
    "SchemaLike",
    "RequirementDesignator",
]
