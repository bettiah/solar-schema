"""
UBL Document Writer.

This package provides document construction and XML serialization:
- DocumentBuilder: Fluent API for building UBL documents
- XMLSerializer: XML output with namespace handling
"""

from .builder import (
    DocumentBuilder,
    ElementBuilder,
    PartyBuilder,
    party,
)
from .serializer import (
    XMLSerializer,
    serialize,
    serialize_to_file,
)

__all__ = [
    # Builder
    "DocumentBuilder",
    "ElementBuilder",
    "PartyBuilder",
    "party",
    # Serializer
    "serialize",
    "serialize_to_file",
    "XMLSerializer",
]
