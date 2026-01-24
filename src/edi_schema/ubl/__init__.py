"""
UBL (Universal Business Language) Schema Support.

This package provides tools for working with UBL 2.5 schemas:
- Schema parsing (XSD to Python models)
- Document parsing (XML to AST)
- Validation (structure, types, codes)
- Document generation (Python to XML)

UBL is an OASIS standard for XML-based business documents.
"""

from .ast import (
    ErrorCategory,
    ErrorSeverity,
    ParsedAttribute,
    ParsedDocument,
    ParsedElement,
    ParseError,
    ParseResult,
    ParseStatistics,
    SourcePosition,
)
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
    SchemaLoader,
    UBLSchema,
    UnqualifiedDataType,
)
from .schema import UBLSchemaLoader
from .schemas import (
    SCHEMAS_GENERATED,
    GeneratedUBLSchemaLoader,
    get_schema,
    list_schemas,
    schema_exists,
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
    # Schema loaders
    "SchemaLoader",
    "UBLSchemaLoader",
    "GeneratedUBLSchemaLoader",
    "get_schema",
    "list_schemas",
    "schema_exists",
    "SCHEMAS_GENERATED",
    # AST
    "ErrorCategory",
    "ErrorSeverity",
    "ParsedAttribute",
    "ParsedDocument",
    "ParsedElement",
    "ParseError",
    "ParseResult",
    "ParseStatistics",
    "SourcePosition",
]
