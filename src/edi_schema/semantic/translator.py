"""
Translation Service for Cross-Format Document Conversion.

Provides a unified API for translating documents between X12, UBL, and EDIFACT formats
using the semantic model layer as an intermediate representation.

Usage:
    service = TranslationService()

    # X12 850 → UBL Order
    x12_doc = x12_parser.parse(raw_x12)
    order = service.to_semantic(x12_doc, Format.X12, DocumentType.ORDER)
    ubl_doc = service.from_semantic(order, Format.UBL)

    # Or directly
    ubl_doc = service.translate(x12_doc, Format.X12, Format.UBL, DocumentType.ORDER)
"""

from enum import Enum
from typing import Any, TypeVar

from .mappers.base import Format, SemanticMapper
from .mappers.edifact import (
    EdifactCreditNoteMapper,
    EdifactDespatchAdviceMapper,
    EdifactInvoiceMapper,
    EdifactOrderMapper,
    EdifactOrderResponseMapper,
    EdifactQuotationMapper,
    EdifactReceiptAdviceMapper,
    EdifactRemittanceAdviceMapper,
)
from .mappers.ubl import (
    UBLCreditNoteMapper,
    UBLDespatchAdviceMapper,
    UBLInvoiceMapper,
    UBLOrderMapper,
    UBLOrderResponseMapper,
    UBLQuotationMapper,
    UBLReceiptAdviceMapper,
    UBLRemittanceAdviceMapper,
)
from .mappers.x12 import (
    X12CreditNoteMapper,
    X12DespatchAdviceMapper,
    X12InvoiceMapper,
    X12OrderMapper,
    X12OrderResponseMapper,
    X12QuotationMapper,
    X12ReceiptAdviceMapper,
    X12RemittanceAdviceMapper,
)
from .models import (
    CreditNote,
    DespatchAdvice,
    Invoice,
    Order,
    OrderResponse,
    Quotation,
    ReceiptAdvice,
    RemittanceAdvice,
    SemanticModel,
)


class DocumentType(Enum):
    """Supported document types for translation."""

    ORDER = "order"
    ORDER_RESPONSE = "order_response"
    QUOTATION = "quotation"
    INVOICE = "invoice"
    CREDIT_NOTE = "credit_note"
    REMITTANCE_ADVICE = "remittance_advice"
    DESPATCH_ADVICE = "despatch_advice"
    RECEIPT_ADVICE = "receipt_advice"


T = TypeVar("T", bound=SemanticModel)


class TranslationService:
    """
    Translate documents between X12, UBL, and EDIFACT formats.

    The service uses semantic models as an intermediate representation,
    allowing translation between any supported formats.

    Example:
        >>> service = TranslationService()
        >>>
        >>> # Convert X12 850 to semantic Order
        >>> order = service.to_semantic(x12_doc, Format.X12, DocumentType.ORDER)
        >>>
        >>> # Convert semantic Order to UBL
        >>> ubl_doc = service.from_semantic(order, Format.UBL)
        >>>
        >>> # Or translate directly
        >>> ubl_doc = service.translate(
        ...     x12_doc, Format.X12, Format.UBL, DocumentType.ORDER
        ... )
    """

    def __init__(self):
        """Initialize the translation service with registered mappers."""
        self._mappers: dict[tuple[Format, DocumentType], SemanticMapper] = {
            # X12 mappers
            (Format.X12, DocumentType.ORDER): X12OrderMapper(),
            (Format.X12, DocumentType.ORDER_RESPONSE): X12OrderResponseMapper(),
            (Format.X12, DocumentType.QUOTATION): X12QuotationMapper(),
            (Format.X12, DocumentType.INVOICE): X12InvoiceMapper(),
            (Format.X12, DocumentType.CREDIT_NOTE): X12CreditNoteMapper(),
            (Format.X12, DocumentType.REMITTANCE_ADVICE): X12RemittanceAdviceMapper(),
            (Format.X12, DocumentType.DESPATCH_ADVICE): X12DespatchAdviceMapper(),
            (Format.X12, DocumentType.RECEIPT_ADVICE): X12ReceiptAdviceMapper(),
            # UBL mappers
            (Format.UBL, DocumentType.ORDER): UBLOrderMapper(),
            (Format.UBL, DocumentType.ORDER_RESPONSE): UBLOrderResponseMapper(),
            (Format.UBL, DocumentType.QUOTATION): UBLQuotationMapper(),
            (Format.UBL, DocumentType.INVOICE): UBLInvoiceMapper(),
            (Format.UBL, DocumentType.CREDIT_NOTE): UBLCreditNoteMapper(),
            (Format.UBL, DocumentType.REMITTANCE_ADVICE): UBLRemittanceAdviceMapper(),
            (Format.UBL, DocumentType.DESPATCH_ADVICE): UBLDespatchAdviceMapper(),
            (Format.UBL, DocumentType.RECEIPT_ADVICE): UBLReceiptAdviceMapper(),
            # EDIFACT mappers
            (Format.EDIFACT, DocumentType.ORDER): EdifactOrderMapper(),
            (Format.EDIFACT, DocumentType.ORDER_RESPONSE): EdifactOrderResponseMapper(),
            (Format.EDIFACT, DocumentType.QUOTATION): EdifactQuotationMapper(),
            (Format.EDIFACT, DocumentType.INVOICE): EdifactInvoiceMapper(),
            (Format.EDIFACT, DocumentType.CREDIT_NOTE): EdifactCreditNoteMapper(),
            (Format.EDIFACT, DocumentType.REMITTANCE_ADVICE): EdifactRemittanceAdviceMapper(),
            (Format.EDIFACT, DocumentType.DESPATCH_ADVICE): EdifactDespatchAdviceMapper(),
            (Format.EDIFACT, DocumentType.RECEIPT_ADVICE): EdifactReceiptAdviceMapper(),
        }

        # Map model types to document types
        self._model_to_doc_type: dict[type, DocumentType] = {
            Order: DocumentType.ORDER,
            OrderResponse: DocumentType.ORDER_RESPONSE,
            Quotation: DocumentType.QUOTATION,
            Invoice: DocumentType.INVOICE,
            CreditNote: DocumentType.CREDIT_NOTE,
            RemittanceAdvice: DocumentType.REMITTANCE_ADVICE,
            DespatchAdvice: DocumentType.DESPATCH_ADVICE,
            ReceiptAdvice: DocumentType.RECEIPT_ADVICE,
        }

    def to_semantic(
        self,
        source: Any,
        source_format: Format,
        doc_type: DocumentType,
    ) -> SemanticModel:
        """
        Convert a format-specific document to a semantic model.

        Args:
            source: The format-specific document (e.g., TransactionSetInstance,
                    ParsedDocument, MessageInstance)
            source_format: The source format (X12, UBL, or EDIFACT)
            doc_type: The document type (ORDER, INVOICE, or DESPATCH_ADVICE)

        Returns:
            Semantic model (Order, Invoice, or DespatchAdvice)

        Raises:
            ValueError: If no mapper exists for the format/document type combination
        """
        mapper = self._get_mapper(source_format, doc_type)
        return mapper.to_semantic(source)

    def from_semantic(
        self,
        model: SemanticModel,
        target_format: Format,
    ) -> Any:
        """
        Convert a semantic model to a format-specific document.

        Args:
            model: The semantic model (Order, Invoice, or DespatchAdvice)
            target_format: The target format (X12, UBL, or EDIFACT)

        Returns:
            Format-specific document structure

        Raises:
            ValueError: If no mapper exists for the format/document type combination
        """
        doc_type = self._infer_doc_type(model)
        mapper = self._get_mapper(target_format, doc_type)
        return mapper.from_semantic(model)

    def translate(
        self,
        source: Any,
        source_format: Format,
        target_format: Format,
        doc_type: DocumentType,
    ) -> Any:
        """
        Translate a document from one format to another.

        This is a convenience method that combines to_semantic() and from_semantic().

        Args:
            source: The format-specific document
            source_format: The source format (X12, UBL, or EDIFACT)
            target_format: The target format (X12, UBL, or EDIFACT)
            doc_type: The document type (ORDER, INVOICE, or DESPATCH_ADVICE)

        Returns:
            Format-specific document in the target format

        Example:
            >>> # Convert X12 850 to EDIFACT ORDERS
            >>> edifact_doc = service.translate(
            ...     x12_doc, Format.X12, Format.EDIFACT, DocumentType.ORDER
            ... )
        """
        semantic = self.to_semantic(source, source_format, doc_type)
        return self.from_semantic(semantic, target_format)

    def get_supported_formats(self) -> list[Format]:
        """Return list of supported formats."""
        return list(Format)

    def get_supported_document_types(self) -> list[DocumentType]:
        """Return list of supported document types."""
        return list(DocumentType)

    def is_supported(self, fmt: Format, doc_type: DocumentType) -> bool:
        """Check if a format/document type combination is supported."""
        return (fmt, doc_type) in self._mappers

    def get_mapper(self, fmt: Format, doc_type: DocumentType) -> SemanticMapper | None:
        """Get the mapper for a format/document type combination."""
        return self._mappers.get((fmt, doc_type))

    def _get_mapper(self, fmt: Format, doc_type: DocumentType) -> SemanticMapper:
        """Get mapper or raise error if not found."""
        mapper = self._mappers.get((fmt, doc_type))
        if not mapper:
            raise ValueError(
                f"No mapper for {fmt.value}/{doc_type.value}. "
                f"Supported combinations: {self._list_supported()}"
            )
        return mapper

    def _infer_doc_type(self, model: SemanticModel) -> DocumentType:
        """Infer document type from semantic model class."""
        doc_type = self._model_to_doc_type.get(type(model))
        if not doc_type:
            raise ValueError(
                f"Unknown model type: {type(model).__name__}. "
                f"Supported types: {list(self._model_to_doc_type.keys())}"
            )
        return doc_type

    def _list_supported(self) -> str:
        """List supported format/document type combinations."""
        return ", ".join(f"{fmt.value}/{dt.value}" for fmt, dt in self._mappers.keys())


# Convenience functions for direct access
_default_service: TranslationService | None = None


def get_translation_service() -> TranslationService:
    """Get the default translation service instance."""
    global _default_service
    if _default_service is None:
        _default_service = TranslationService()
    return _default_service


def to_semantic(
    source: Any,
    source_format: Format,
    doc_type: DocumentType,
) -> SemanticModel:
    """
    Convert a format-specific document to a semantic model.

    Convenience function using the default translation service.
    """
    return get_translation_service().to_semantic(source, source_format, doc_type)


def from_semantic(model: SemanticModel, target_format: Format) -> Any:
    """
    Convert a semantic model to a format-specific document.

    Convenience function using the default translation service.
    """
    return get_translation_service().from_semantic(model, target_format)


def translate(
    source: Any,
    source_format: Format,
    target_format: Format,
    doc_type: DocumentType,
) -> Any:
    """
    Translate a document from one format to another.

    Convenience function using the default translation service.
    """
    return get_translation_service().translate(source, source_format, target_format, doc_type)
