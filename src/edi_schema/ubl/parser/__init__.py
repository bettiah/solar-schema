"""
UBL Document Parser.

This package provides parsing for UBL XML documents:
- XML parsing with namespace handling
- Schema-driven element binding
- Error collection and recovery
"""

from .document import parse, parse_with_schema
from .xml_parser import XMLParseError, parse_xml

__all__ = [
    "parse_xml",
    "XMLParseError",
    "parse",
    "parse_with_schema",
]
