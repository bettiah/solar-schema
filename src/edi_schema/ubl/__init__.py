"""
UBL (Universal Business Language) Schema Support.

This package provides tools for working with UBL 2.5 schemas:
- Schema parsing (XSD to Python models)
- Document parsing (XML to AST)
- Validation (structure, types, codes)
- Document generation (Python to XML)

UBL is an OASIS standard for XML-based business documents.
"""

from .enums import Cardinality, ComponentType, Namespace, RepresentationTerm
from .models import (
    ABIE,
    ASBIE,
    BBIE,
    Attribute,
    CACElement,
    CBCElement,
    CodeList,
    CodeValue,
    DocumentType,
    QualifiedDataType,
    UBLSchema,
    UnqualifiedDataType,
)

__all__ = [
    # Enums
    "Cardinality",
    "ComponentType",
    "Namespace",
    "RepresentationTerm",
    # Data types
    "Attribute",
    "UnqualifiedDataType",
    "QualifiedDataType",
    # Components
    "ABIE",
    "BBIE",
    "ASBIE",
    "CBCElement",
    "CACElement",
    # Documents
    "DocumentType",
    "UBLSchema",
    # Code lists
    "CodeList",
    "CodeValue",
]
