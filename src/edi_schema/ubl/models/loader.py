"""
Schema Loader Protocol.

Defines the interface for UBL schema loaders.
"""

from typing import Protocol

from .document import UBLSchema


class SchemaLoader(Protocol):
    """
    Protocol for UBL schema loaders.

    Both UBLSchemaLoader (runtime XSD parsing) and GeneratedUBLSchemaLoader
    (pre-generated modules) implement this interface.
    """

    def load(self, document_type: str) -> UBLSchema:
        """
        Load a schema by document type.

        Args:
            document_type: Document type name (e.g., 'Invoice')

        Returns:
            UBLSchema instance

        Raises:
            FileNotFoundError: If schema not found (UBLSchemaLoader)
            ValueError: If schema not found (GeneratedUBLSchemaLoader)
        """
        ...
