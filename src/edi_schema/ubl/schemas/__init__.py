"""
UBL Generated Schemas.

This package provides pre-generated schemas for fast loading.

Usage:
    from edi_schema.ubl.schemas import get_schema, GeneratedUBLSchemaLoader

    # Get schema directly
    schema = get_schema("Invoice")

    # Or use the loader class
    loader = GeneratedUBLSchemaLoader()
    schema = loader.load("Invoice")

Note: If schemas have not been generated yet, use the runtime loader:
    from edi_schema.ubl.schema import UBLSchemaLoader
    loader = UBLSchemaLoader(xsd_path)
"""

try:
    from .registry import (
        GeneratedUBLSchemaLoader,
        get_schema,
        list_schemas,
        schema_exists,
    )

    SCHEMAS_GENERATED = True
except ImportError:
    # Schemas not yet generated - provide stub functions
    SCHEMAS_GENERATED = False

    def get_schema(name: str, version: str = "2.5"):
        raise ImportError(
            "Generated schemas not available. "
            "Use UBLSchemaLoader for runtime loading or run code generation first."
        )

    def list_schemas(version: str = "2.5") -> list[str]:
        return []

    def schema_exists(name: str, version: str = "2.5") -> bool:
        return False

    class GeneratedUBLSchemaLoader:
        def __init__(self, version: str = "2.5"):
            raise ImportError(
                "Generated schemas not available. "
                "Use UBLSchemaLoader for runtime loading or run code generation first."
            )


__all__ = [
    "GeneratedUBLSchemaLoader",
    "get_schema",
    "list_schemas",
    "schema_exists",
    "SCHEMAS_GENERATED",
]
