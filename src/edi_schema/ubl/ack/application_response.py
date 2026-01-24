"""
UBL ApplicationResponse Generator.

Generates ApplicationResponse documents from validation results.
UBL's equivalent of X12 997 / EDIFACT CONTRL.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Callable
from uuid import uuid4

from ..ast import ParsedDocument, ParseError
from ..enums import Namespace
from ..validator import ValidationResult
from ..writer import DocumentBuilder, ElementBuilder, serialize


class ResponseCode(str, Enum):
    """
    UBL ApplicationResponse codes.

    Standard codes for document acceptance/rejection status.
    """

    ACCEPTED = "AP"  # Accepted
    REJECTED = "RE"  # Rejected
    ACKNOWLEDGED = "AB"  # Message acknowledged
    CONDITIONALLY_ACCEPTED = "CA"  # Conditionally accepted
    IN_PROCESS = "IP"  # In process
    PENDING = "PD"  # Pending
    RECEIVED = "RD"  # Received


@dataclass
class LineError:
    """
    Error associated with a specific line in the document.

    Attributes:
        line_id: Line identifier (e.g., InvoiceLine ID)
        response_code: Response code for this line
        description: Error description
    """

    line_id: str
    response_code: ResponseCode = ResponseCode.REJECTED
    description: str = ""


@dataclass
class DocumentError:
    """
    Document-level error.

    Attributes:
        response_code: Overall response code
        description: Error description
        line_errors: Errors specific to document lines
    """

    response_code: ResponseCode = ResponseCode.REJECTED
    description: str = ""
    line_errors: list[LineError] = field(default_factory=list)


class ApplicationResponseBuilder:
    """
    Builder for UBL ApplicationResponse documents.

    Creates acknowledgment responses from validation results or manually.

    Usage:
        # From validation result
        response = ApplicationResponseBuilder.from_validation(
            validation_result,
            original_document,
            sender_party=...,
        )

        # Manual construction
        response = (
            ApplicationResponseBuilder()
            .id("AR-001")
            .issue_date("2024-01-15")
            .response_code(ResponseCode.ACCEPTED)
            .document_reference("INV-001", "Invoice")
            .build()
        )
    """

    def __init__(self):
        """Initialize the builder."""
        self._builder = DocumentBuilder("ApplicationResponse")
        self._response_code = ResponseCode.ACCEPTED
        self._description = ""
        self._document_errors: list[DocumentError] = []

    @classmethod
    def from_validation(
        cls,
        result: ValidationResult,
        original_document: ParsedDocument,
        response_id: str | None = None,
        issue_date: str | None = None,
        sender_party: Callable[[ElementBuilder], None] | None = None,
        receiver_party: Callable[[ElementBuilder], None] | None = None,
    ) -> "ApplicationResponseBuilder":
        """
        Create an ApplicationResponse from a validation result.

        Args:
            result: Validation result to base response on
            original_document: The document that was validated
            response_id: Response document ID (auto-generated if not provided)
            issue_date: Issue date (today if not provided)
            sender_party: Callback to configure sender party
            receiver_party: Callback to configure receiver party

        Returns:
            Configured ApplicationResponseBuilder
        """
        builder = cls()

        # Set ID
        if response_id is None:
            response_id = f"AR-{uuid4().hex[:8].upper()}"
        builder.id(response_id)

        # Set date
        if issue_date is None:
            issue_date = date.today().isoformat()
        builder.issue_date(issue_date)

        # Determine overall response code
        if result.is_valid:
            builder.response_code(ResponseCode.ACCEPTED)
        else:
            builder.response_code(ResponseCode.REJECTED)
            builder._description = f"Validation failed with {len(result.errors)} error(s)"

        # Add document reference
        doc_id = _get_document_id(original_document)
        builder.document_reference(doc_id, original_document.document_type)

        # Add parties if provided
        if sender_party:
            builder.sender_party(sender_party)
        if receiver_party:
            builder.receiver_party(receiver_party)

        # Convert validation errors to document errors
        if result.errors:
            doc_error = DocumentError(
                response_code=ResponseCode.REJECTED,
                description=builder._description,
            )

            # Group errors by line if possible
            line_errors: dict[str, list[ParseError]] = {}
            other_errors: list[ParseError] = []

            for error in result.errors:
                line_id = _extract_line_id(error)
                if line_id:
                    if line_id not in line_errors:
                        line_errors[line_id] = []
                    line_errors[line_id].append(error)
                else:
                    other_errors.append(error)

            # Create line errors
            for line_id, errors in line_errors.items():
                descriptions = [e.message for e in errors]
                doc_error.line_errors.append(LineError(
                    line_id=line_id,
                    response_code=ResponseCode.REJECTED,
                    description="; ".join(descriptions),
                ))

            # Add document-level error description if there are non-line errors
            if other_errors:
                doc_error.description = "; ".join(e.message for e in other_errors[:5])
                if len(other_errors) > 5:
                    doc_error.description += f" (and {len(other_errors) - 5} more)"

            builder._document_errors.append(doc_error)

        return builder

    def id(self, value: str) -> "ApplicationResponseBuilder":
        """Set the response ID."""
        self._builder.id(value)
        return self

    def uuid(self, value: str) -> "ApplicationResponseBuilder":
        """Set the UUID."""
        self._builder.uuid(value)
        return self

    def issue_date(self, value: str) -> "ApplicationResponseBuilder":
        """Set the issue date."""
        self._builder.issue_date(value)
        return self

    def issue_time(self, value: str) -> "ApplicationResponseBuilder":
        """Set the issue time."""
        self._builder.issue_time(value)
        return self

    def note(self, value: str) -> "ApplicationResponseBuilder":
        """Add a note."""
        self._builder.note(value)
        return self

    def response_code(self, code: ResponseCode) -> "ApplicationResponseBuilder":
        """Set the overall response code."""
        self._response_code = code
        return self

    def sender_party(
        self,
        configure: Callable[[ElementBuilder], None],
    ) -> "ApplicationResponseBuilder":
        """Set the sender party."""
        self._builder.add_cac("SenderParty", configure)
        return self

    def receiver_party(
        self,
        configure: Callable[[ElementBuilder], None],
    ) -> "ApplicationResponseBuilder":
        """Set the receiver party."""
        self._builder.add_cac("ReceiverParty", configure)
        return self

    def document_reference(
        self,
        doc_id: str,
        doc_type: str,
        doc_type_code: str | None = None,
    ) -> "ApplicationResponseBuilder":
        """
        Add a document reference.

        Args:
            doc_id: ID of the referenced document
            doc_type: Document type name
            doc_type_code: Optional document type code
        """
        def configure(ref: ElementBuilder):
            ref.add_element("ID", doc_id, namespace=Namespace.CBC.value)
            if doc_type_code:
                ref.add_element("DocumentTypeCode", doc_type_code, namespace=Namespace.CBC.value)
            ref.add_element("DocumentType", doc_type, namespace=Namespace.CBC.value)

        self._builder.add_cac("DocumentReference", configure)
        return self

    def add_document_error(self, error: DocumentError) -> "ApplicationResponseBuilder":
        """Add a document error."""
        self._document_errors.append(error)
        return self

    def build(self) -> ParsedDocument:
        """
        Build the ApplicationResponse document.

        Returns:
            ParsedDocument ready for serialization
        """
        # Add DocumentResponse elements
        if self._document_errors:
            for doc_error in self._document_errors:
                self._add_document_response(doc_error)
        else:
            # Add simple response if no errors
            self._add_simple_response()

        return self._builder.build()

    def to_xml(self, pretty: bool = True) -> str:
        """
        Build and serialize to XML.

        Args:
            pretty: Whether to format output

        Returns:
            XML string
        """
        doc = self.build()
        return serialize(doc, pretty=pretty)

    def _add_simple_response(self) -> None:
        """Add a simple DocumentResponse element."""
        def configure(dr: ElementBuilder):
            # Response element
            def response(r: ElementBuilder):
                r.add_element("ResponseCode", self._response_code.value, namespace=Namespace.CBC.value)
                if self._description:
                    r.add_element("Description", self._description, namespace=Namespace.CBC.value)

            dr.with_child("Response", response, namespace=Namespace.CAC.value)

        self._builder.add_cac("DocumentResponse", configure)

    def _add_document_response(self, doc_error: DocumentError) -> None:
        """Add a DocumentResponse element for an error."""
        def configure(dr: ElementBuilder):
            # Response element
            def response(r: ElementBuilder):
                r.add_element("ResponseCode", doc_error.response_code.value, namespace=Namespace.CBC.value)
                if doc_error.description:
                    r.add_element("Description", doc_error.description, namespace=Namespace.CBC.value)

            dr.with_child("Response", response, namespace=Namespace.CAC.value)

            # Line responses
            for line_error in doc_error.line_errors:
                def line_response(lr: ElementBuilder):
                    # LineReference
                    def line_ref(lref: ElementBuilder):
                        lref.add_element("LineID", line_error.line_id, namespace=Namespace.CBC.value)

                    lr.with_child("LineReference", line_ref, namespace=Namespace.CAC.value)

                    # Response
                    def resp(r: ElementBuilder):
                        r.add_element("ResponseCode", line_error.response_code.value, namespace=Namespace.CBC.value)
                        if line_error.description:
                            r.add_element("Description", line_error.description, namespace=Namespace.CBC.value)

                    lr.with_child("Response", resp, namespace=Namespace.CAC.value)

                dr.with_child("LineResponse", line_response, namespace=Namespace.CAC.value)

        self._builder.add_cac("DocumentResponse", configure)


def _get_document_id(document: ParsedDocument) -> str:
    """Extract the document ID from a parsed document."""
    id_elem = document.root.find_child("ID")
    if id_elem and id_elem.value:
        return id_elem.value
    return "UNKNOWN"


def _extract_line_id(error: ParseError) -> str | None:
    """
    Extract line ID from an error if it relates to a specific line.

    Looks for patterns like InvoiceLine[1], OrderLine[2], etc.
    """
    if error.xpath:
        # Look for line patterns in xpath
        import re
        match = re.search(r"(Invoice|Order|Credit|Debit|Despatch|Receipt)Line\[(\d+)\]", error.xpath)
        if match:
            return match.group(2)

        # Also check context
        if error.context:
            if "line_id" in error.context:
                return str(error.context["line_id"])

    return None


def generate_application_response(
    validation_result: ValidationResult,
    original_document: ParsedDocument,
    **kwargs,
) -> str:
    """
    Convenience function to generate ApplicationResponse XML.

    Args:
        validation_result: Validation result
        original_document: Original document that was validated
        **kwargs: Additional arguments for ApplicationResponseBuilder

    Returns:
        ApplicationResponse XML string
    """
    builder = ApplicationResponseBuilder.from_validation(
        validation_result,
        original_document,
        **kwargs,
    )
    return builder.to_xml()
