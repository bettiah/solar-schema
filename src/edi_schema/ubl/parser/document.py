"""
Document Parser for UBL Documents.

High-level parsing with optional schema binding.
"""

from pathlib import Path
from typing import IO

from ..ast import (
    ErrorCategory,
    ErrorSeverity,
    ParsedDocument,
    ParsedElement,
    ParseError,
    ParseResult,
    SourcePosition,
)
from ..models import ABIE, ASBIE, BBIE, UBLSchema
from ..schema import UBLSchemaLoader
from .xml_parser import XMLParseError, get_document_type, get_ubl_version, parse_xml


def parse(
    source: str | bytes | Path | IO[bytes],
    recover: bool = True,
) -> ParseResult:
    """
    Parse a UBL XML document without schema binding.

    Args:
        source: XML content (string, bytes, file path, or file object)
        recover: Whether to attempt recovery from errors

    Returns:
        ParseResult with the parsed document or errors
    """
    result = ParseResult()

    try:
        root, nsmap = parse_xml(source, recover=recover)
    except XMLParseError as e:
        result.add_error(
            ParseError(
                code="XML_PARSE_ERROR",
                message=str(e),
                severity=ErrorSeverity.FATAL,
                category=ErrorCategory.STRUCTURAL,
                position=SourcePosition(line=e.line, column=e.column),
            )
        )
        return result

    # Create document
    doc_type = get_document_type(root)
    version = get_ubl_version(root)

    result.document = ParsedDocument(
        document_type=doc_type,
        version=version,
        root=root,
        namespaces=nsmap,
    )

    return result


def parse_with_schema(
    source: str | bytes | Path | IO[bytes],
    schema: UBLSchema,
    recover: bool = True,
) -> ParseResult:
    """
    Parse a UBL XML document with schema binding.

    Binds parsed elements to their corresponding schema components
    (ABIE, BBIE, ASBIE).

    Args:
        source: XML content
        schema: UBL schema for the document type
        recover: Whether to attempt recovery from errors

    Returns:
        ParseResult with schema-bound document or errors
    """
    # First, parse without schema
    result = parse(source, recover=recover)

    if result.document is None:
        return result

    # Verify document type matches schema
    if result.document.document_type != schema.name:
        result.add_error(
            ParseError(
                code="DOCUMENT_TYPE_MISMATCH",
                message=f"Expected {schema.name}, got {result.document.document_type}",
                severity=ErrorSeverity.ERROR,
                category=ErrorCategory.SCHEMA,
                expected=schema.name,
                actual=result.document.document_type,
            )
        )
        return result

    # Bind schema to elements
    _bind_schema(result.document.root, schema, result)

    return result


def _bind_schema(
    element: ParsedElement,
    schema: UBLSchema,
    result: ParseResult,
    parent_abie: ABIE | None = None,
) -> None:
    """
    Recursively bind schema components to parsed elements.

    Args:
        element: The parsed element to bind
        schema: The UBL schema
        result: ParseResult to add errors to
        parent_abie: The parent ABIE context (for looking up children)
    """
    # Determine the context ABIE
    if parent_abie is None:
        # Root element - use document's root ABIE
        abie = schema.document_type.root_abie
        element.schema_component = abie
        parent_abie = abie
    else:
        # Look up this element in the parent's context
        component = _find_component(element.tag, parent_abie, schema)
        element.schema_component = component

        # If this is an ASBIE, update parent context
        if isinstance(component, ASBIE):
            abie = schema.get_abie(component.associated_abie)
            if abie:
                parent_abie = abie

    # Recursively bind children
    for child in element.children:
        _bind_schema(child, schema, result, parent_abie)


def _find_component(
    tag: str,
    parent_abie: ABIE,
    schema: UBLSchema,
) -> BBIE | ASBIE | ABIE | None:
    """
    Find the schema component for an element within a parent ABIE.

    Args:
        tag: Element tag name
        parent_abie: Parent ABIE context
        schema: The UBL schema

    Returns:
        The matching component, or None if not found
    """
    # Check BBIEs first
    for bbie in parent_abie.bbies:
        if bbie.name == tag:
            return bbie

    # Check ASBIEs
    for asbie in parent_abie.asbies:
        if asbie.name == tag:
            return asbie

    # Check CAC elements (for reference resolution)
    cac_elem = schema.get_cac_element(tag)
    if cac_elem:
        abie = schema.get_abie(cac_elem.abie_name)
        if abie:
            return abie

    return None


def parse_file(
    path: Path,
    schema_loader: UBLSchemaLoader | None = None,
) -> ParseResult:
    """
    Parse a UBL document from a file.

    Args:
        path: Path to the XML file
        schema_loader: Optional schema loader for schema binding

    Returns:
        ParseResult with parsed document or errors
    """
    # Parse without schema first
    result = parse(path)

    if result.document is None:
        return result

    # Load schema if loader provided
    if schema_loader:
        try:
            schema = schema_loader.load(result.document.document_type)
            # Re-parse with schema binding
            return parse_with_schema(path, schema)
        except FileNotFoundError:
            result.add_error(
                ParseError(
                    code="SCHEMA_NOT_FOUND",
                    message=f"Schema not found for {result.document.document_type}",
                    severity=ErrorSeverity.WARNING,
                    category=ErrorCategory.SCHEMA,
                )
            )

    return result
