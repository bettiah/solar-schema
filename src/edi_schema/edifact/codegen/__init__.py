"""
EDIFACT Schema Code Generator.

Generate Python schema modules from EDIFACT directory specification files.
"""

from .generator import EdifactSchemaGenerator, GeneratorConfig

__all__ = [
    "EdifactSchemaGenerator",
    "GeneratorConfig",
]
