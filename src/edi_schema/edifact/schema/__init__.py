"""
EDIFACT Schema Loading and Resolution.

Components for loading and building complete message schemas:
- registry: Holds all parsed components
- resolver: Cross-reference linking between components
- loader: Runtime schema loader (parses directory files)

For pre-generated schemas (recommended), use:
    from edi_schema.edifact.schemas import GeneratedEdifactSchemaLoader
"""

from .loader import EdifactSchemaLoader
from .registry import EdifactRegistry
from .resolver import EdifactResolver, collect_segment_tags

__all__ = [
    "EdifactRegistry",
    "EdifactResolver",
    "EdifactSchemaLoader",
    "collect_segment_tags",
]
