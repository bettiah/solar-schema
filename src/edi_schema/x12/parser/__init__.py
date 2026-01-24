"""
X12 Document Parser.

This module provides parsers for X12 EDI documents with full error recovery.
"""

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
