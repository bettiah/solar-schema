"""
Core components shared across EDI formats.

This module provides:
- Protocol definitions for common interfaces
- Schema repository for loading and caching schemas
- Common types and enumerations
"""

from edi_schema.core.repository import SchemaRepository
from edi_schema.core.types import (
    CompositeLike,
    ElementLike,
    RequirementDesignator,
    SchemaLike,
    SegmentLike,
)

__all__ = [
    "ElementLike",
    "SegmentLike",
    "CompositeLike",
    "SchemaLike",
    "RequirementDesignator",
    "SchemaRepository",
]
