"""
UBL Document Parser.

This package provides parsing for UBL XML documents:
- XML parsing with namespace handling
- Schema-driven element binding
- Error collection and recovery
"""

from .document import bind_schema, parse, parse_file, parse_with_schema
from .xml_parser import XMLParseError, parse_xml

__all__ = [
    "parse_xml",
    "XMLParseError",
    "parse",
    "parse_with_schema",
    "parse_file",
    "bind_schema",
]
