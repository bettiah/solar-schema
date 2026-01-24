"""
UBL Schema Code Generation.

This package provides code generation for UBL schemas:
- Generate Python modules from XSD schemas
- Jinja2 templates for code generation
- Registry generation for schema lookup
"""

from .generator import UBLSchemaGenerator

__all__ = [
    "UBLSchemaGenerator",
]
