"""
UBL Schema Parsers.

This package provides parsers for UBL XSD schema files:
- UDT parser: BDNDR-UnqualifiedDataTypes-1.1.xsd
- QDT parser: UBL-QualifiedDataTypes-2.5.xsd
- CBC parser: UBL-CommonBasicComponents-2.5.xsd
- CAC parser: UBL-CommonAggregateComponents-2.5.xsd
- Document parser: maindoc/*.xsd
- Genericode parser: cl/gc/default/*.gc
"""

from .base import parse_xsd, NSMAP
from .udt import parse_udt
from .qdt import parse_qdt
from .cbc import parse_cbc_elements, parse_cbc_types
from .cac import parse_cac_elements, parse_cac_types
from .maindoc import parse_document_schema, list_document_schemas
from .genericode import parse_genericode, parse_all_code_lists

__all__ = [
    # Base utilities
    "parse_xsd",
    "NSMAP",
    # UDT
    "parse_udt",
    # QDT
    "parse_qdt",
    # CBC
    "parse_cbc_elements",
    "parse_cbc_types",
    # CAC
    "parse_cac_elements",
    "parse_cac_types",
    # Document
    "parse_document_schema",
    "list_document_schemas",
    # Code lists
    "parse_genericode",
    "parse_all_code_lists",
]
