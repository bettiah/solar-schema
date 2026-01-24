"""
X12 Data Models.

Dataclass definitions for X12 schema components:
- DataElement: Simple data elements with type and length constraints
- Composite: Composite elements containing multiple simple elements
- Segment: Named groups of elements
- TransactionSet: Complete transaction definitions with structure
- CodeSource: External code list references
"""

from edi_schema.x12.models.codesource import CodeSource
from edi_schema.x12.models.element import (
    Composite,
    CompositeElement,
    DataElement,
)
from edi_schema.x12.models.segment import (
    Segment,
    SegmentElement,
    SegmentNote,
)
from edi_schema.x12.models.transaction import (
    LoopDefinition,
    TransactionSet,
    TransactionSetSegment,
)

__all__ = [
    # Element models
    "DataElement",
    "CompositeElement",
    "Composite",
    # Segment models
    "SegmentElement",
    "SegmentNote",
    "Segment",
    # Transaction models
    "TransactionSetSegment",
    "LoopDefinition",
    "TransactionSet",
    # Code source model
    "CodeSource",
]
