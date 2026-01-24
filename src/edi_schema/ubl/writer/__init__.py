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
    serialize,
    serialize_to_file,
    XMLSerializer,
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
