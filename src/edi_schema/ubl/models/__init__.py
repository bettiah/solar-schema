"""
UBL Schema Models.

This package contains dataclass definitions for UBL schema components:
- Data types (UDT, QDT)
- Components (ABIE, BBIE, ASBIE)
- Documents (DocumentType, UBLSchema)
- Code lists (CodeList, CodeValue)
"""

from .code_list import STANDARD_CODE_LISTS, CodeList, CodeListColumn, CodeValue
from .component import ABIE, ASBIE, BBIE, CACElement, CBCElement
from .data_type import (
    STANDARD_QDT_TYPES,
    STANDARD_UDT_TYPES,
    Attribute,
    QualifiedDataType,
    UnqualifiedDataType,
)
from .document import UBL_DOCUMENT_TYPES, DocumentType, UBLSchema
from .loader import SchemaLoader

__all__ = [
    # Data types
    "Attribute",
    "UnqualifiedDataType",
    "QualifiedDataType",
    "STANDARD_UDT_TYPES",
    "STANDARD_QDT_TYPES",
    # Components
    "ABIE",
    "BBIE",
    "ASBIE",
    "CBCElement",
    "CACElement",
    # Documents
    "DocumentType",
    "UBLSchema",
    "UBL_DOCUMENT_TYPES",
    # Code lists
    "CodeList",
    "CodeListColumn",
    "CodeValue",
    "STANDARD_CODE_LISTS",
    # Loader protocol
    "SchemaLoader",
]
