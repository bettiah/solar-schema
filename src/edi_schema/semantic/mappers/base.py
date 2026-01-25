"""
Base Mapper Protocol and Types.

Defines the interface that all format-specific mappers must implement.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Generic, TypeVar

from ..models.base import SemanticModel

T = TypeVar("T", bound=SemanticModel)


class Format(Enum):
    """Supported EDI formats."""

    X12 = "x12"
    UBL = "ubl"
    EDIFACT = "edifact"


class SemanticMapper(ABC, Generic[T]):
    """
    Base class for format-specific mappers.

    Mappers convert between format-specific parsed documents and
    format-agnostic semantic models. Each mapper handles one
    document type (e.g., Order, Invoice) for one format (e.g., X12).

    Type parameter T is the semantic model type this mapper handles.
    """

    @abstractmethod
    def to_semantic(self, source: object) -> T:
        """
        Convert a format-specific parsed document to a semantic model.

        Args:
            source: The format-specific parsed document (e.g., X12
                TransactionSetInstance, UBL ParsedDocument)

        Returns:
            The semantic model representation

        Raises:
            ValueError: If the source document type doesn't match
        """
        ...

    @abstractmethod
    def from_semantic(self, model: T) -> object:
        """
        Convert a semantic model to a format-specific document.

        Args:
            model: The semantic model to convert

        Returns:
            The format-specific document representation

        Raises:
            ValueError: If required fields are missing
        """
        ...

    @property
    @abstractmethod
    def semantic_type(self) -> type[T]:
        """Return the semantic model type this mapper handles."""
        ...

    @property
    @abstractmethod
    def source_format(self) -> Format:
        """Return the source format this mapper handles."""
        ...

    @property
    @abstractmethod
    def transaction_id(self) -> str:
        """Return the transaction set ID (e.g., '850', 'ORDERS')."""
        ...
