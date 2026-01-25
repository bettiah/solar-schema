"""
X12 Document Parser.

High-level parsing API with optional schema binding.

This module provides a clean, one-shot API for parsing X12 documents,
similar to the UBL parser. It integrates the tokenizer, envelope parser,
and transaction parser into a unified flow.

Usage:
    from edi_schema.x12.parser import parse_file
    from edi_schema.x12.schemas import GeneratedX12SchemaLoader

    # Parse without schema
    result = parse_file(Path("invoice.x12"))

    # Parse with schema binding
    loader = GeneratedX12SchemaLoader(version="005010")
    result = parse_file(Path("invoice.x12"), schema_loader=loader)

    # Access parsed content
    for group in result.interchange.groups:
        for txn in group.transactions:
            for item in txn.content:
                if isinstance(item, LoopInstance):
                    print(f"Loop: {item.loop_id}")
"""

from pathlib import Path
from typing import IO, Protocol, runtime_checkable

from edi_schema.x12.ast import (
    LoopInstance,
    ParsedSegment,
    ParseResult,
    RawSegment,
)
from edi_schema.x12.parser.envelope import EnvelopeParser
from edi_schema.x12.parser.tokenizer import X12Tokenizer
from edi_schema.x12.parser.transaction import TransactionParser
from edi_schema.x12.schema import X12Schema


@runtime_checkable
class SchemaLoader(Protocol):
    """
    Protocol for X12 schema loaders.

    Both X12SchemaLoader (runtime file parsing) and GeneratedX12SchemaLoader
    (pre-generated modules) implement this interface.
    """

    def load(self, transaction_id: str) -> X12Schema:
        """
        Load a schema by transaction ID.

        Args:
            transaction_id: Transaction set ID (e.g., '850', '837')

        Returns:
            X12Schema instance

        Raises:
            ValueError: If schema not found
        """
        ...

    def exists(self, transaction_id: str) -> bool:
        """Check if a transaction set exists."""
        ...


def parse(
    source: str | bytes | Path | IO[bytes],
    recover: bool = True,
) -> ParseResult:
    """
    Parse an X12 document without schema binding.

    This parses the envelope structure (ISA/IEA, GS/GE, ST/SE) and tokenizes
    segments, but does not interpret transaction content using schemas.
    Transaction content will contain RawSegment instances.

    Args:
        source: X12 content (string, bytes, file path, or file object)
        recover: Whether to attempt recovery from errors (default True)

    Returns:
        ParseResult with the parsed interchange or errors
    """
    # Get content as string
    content = _read_source(source)

    # Tokenize
    tokenizer = X12Tokenizer()
    tokenizer_result = tokenizer.tokenize(content)

    # Parse envelope
    envelope_parser = EnvelopeParser()
    result = envelope_parser.parse(tokenizer_result)

    return result


def parse_with_schema(
    source: str | bytes | Path | IO[bytes],
    schema_loader: SchemaLoader,
    recover: bool = True,
) -> ParseResult:
    """
    Parse an X12 document with schema binding and transaction parsing.

    This parses the document and then uses the schema to interpret
    transaction content, building a proper loop hierarchy with
    ParsedSegment and LoopInstance nodes.

    Args:
        source: X12 content (string, bytes, file path, or file object)
        schema_loader: Schema loader for loading transaction schemas
        recover: Whether to attempt recovery from errors (default True)

    Returns:
        ParseResult with schema-bound interchange or errors
    """
    result = parse(source, recover=recover)
    bind_schemas(result, schema_loader)
    return result


def bind_schemas(
    result: ParseResult,
    schema_loader: SchemaLoader,
) -> ParseResult:
    """
    Bind schemas to an already-parsed document.

    This converts raw segment content in transactions to a proper
    loop hierarchy using the TransactionParser with schema-driven
    loop matching.

    Args:
        result: ParseResult from a previous parse() call
        schema_loader: Schema loader for loading transaction schemas

    Returns:
        The same ParseResult with schema binding applied
    """
    if result.interchange is None:
        return result

    for group in result.interchange.groups:
        for txn in group.transactions:
            # Check if content is still raw segments
            if not txn.content or not isinstance(txn.content[0], RawSegment):
                # Already parsed or empty
                continue

            # Try to load schema for this transaction
            try:
                schema = schema_loader.load(txn.transaction_id)
            except (ValueError, KeyError, FileNotFoundError):
                # Schema not found - leave as raw segments
                continue

            # Parse transaction content using schema
            parser = TransactionParser(schema)
            raw_segments: list[RawSegment] = [
                seg for seg in txn.content if isinstance(seg, RawSegment)
            ]
            parsed_content = parser.parse(raw_segments, txn.transaction_id)

            # Replace content with parsed structure
            txn.content = parsed_content
            txn.schema = schema.transaction_set

            # Add any parser errors to transaction
            txn.errors.extend(parser.errors)

    return result


def parse_file(
    path: Path,
    schema_loader: SchemaLoader | None = None,
    recover: bool = True,
) -> ParseResult:
    """
    Parse an X12 document from a file.

    This is the recommended entry point for parsing X12 documents.
    It handles file reading and optionally binds schemas to produce
    a fully-structured document.

    Args:
        path: Path to the X12 file
        schema_loader: Optional schema loader for schema binding
        recover: Whether to attempt recovery from errors (default True)

    Returns:
        ParseResult with parsed interchange or errors

    Example:
        from edi_schema.x12.parser import parse_file
        from edi_schema.x12.schemas import GeneratedX12SchemaLoader

        loader = GeneratedX12SchemaLoader(version="005010")
        result = parse_file(Path("invoice.x12"), schema_loader=loader)

        if result.interchange:
            for group in result.interchange.groups:
                for txn in group.transactions:
                    print(f"Transaction: {txn.transaction_id}")
    """
    if schema_loader:
        return parse_with_schema(path, schema_loader, recover=recover)
    return parse(path, recover=recover)


def _read_source(source: str | bytes | Path | IO[bytes]) -> str:
    """
    Read source content into a string.

    Args:
        source: X12 content in various formats

    Returns:
        Content as a string
    """
    if isinstance(source, str):
        # Already a string - could be content or a file path
        if len(source) < 260 and not source.startswith("ISA"):
            # Looks like a file path
            path = Path(source)
            if path.exists():
                return path.read_text()
        return source

    if isinstance(source, bytes):
        return source.decode("utf-8")

    if isinstance(source, Path):
        return source.read_text()

    # File-like object
    content = source.read()
    if isinstance(content, bytes):
        return content.decode("utf-8")
    return content
