"""
X12 Document Parser.

This module provides parsers for X12 EDI documents with full error recovery.

High-Level API:
    parse_file - One-shot file parsing with optional schema binding
    parse - Parse without schema binding
    parse_with_schema - Parse with schema binding
    bind_schemas - Bind schemas to already-parsed document

Lower-Level Components:
    EnvelopeParser - Parses ISA/IEA, GS/GE, ST/SE envelope structure
    TransactionParser - Parses transaction content using loop hierarchy
    X12Tokenizer - Tokenizes raw X12 text into segments
"""

from .document import (
    SchemaLoader,
    bind_schemas,
    parse,
    parse_file,
    parse_with_schema,
)
from .envelope import (
    EnvelopeParser,
    EnvelopeParserState,
    parse_envelope,
)
from .loop_hierarchy import (
    LoopHierarchyBuilder,
    LoopMatcher,
    LoopNode,
    LoopPosition,
    MatchAction,
    MatchResult,
    build_loop_hierarchy,
)
from .tokenizer import (
    TokenizerResult,
    X12Tokenizer,
    tokenize,
)
from .transaction import (
    HLNode,
    HLParser,
    TransactionParser,
    TransactionParserState,
    parse_transaction,
)

__all__ = [
    # High-level API
    "parse",
    "parse_file",
    "parse_with_schema",
    "bind_schemas",
    "SchemaLoader",
    # Loop hierarchy
    "LoopNode",
    "LoopHierarchyBuilder",
    "build_loop_hierarchy",
    "LoopPosition",
    "LoopMatcher",
    "MatchAction",
    "MatchResult",
    # Tokenizer
    "X12Tokenizer",
    "TokenizerResult",
    "tokenize",
    # Envelope parser
    "EnvelopeParser",
    "EnvelopeParserState",
    "parse_envelope",
    # Transaction parser
    "TransactionParser",
    "TransactionParserState",
    "HLParser",
    "HLNode",
    "parse_transaction",
]
