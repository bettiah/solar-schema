"""
EDIFACT Parser Package.

This package contains the components for parsing EDIFACT documents:
- tokenizer: Lexical analysis (UNA detection, segment splitting)
- envelope: Envelope parsing (UNB/UNZ, UNG/UNE, UNH/UNT)
- message: Schema-driven message content parsing
- hierarchy: Segment group hierarchy building and matching
"""

from edi_schema.edifact.ast import (
    Delimiters,
    ErrorCategory,
    ErrorSeverity,
    ParseError,
    ParseResult,
    RecoveryPoint,
    SourcePosition,
)
from edi_schema.edifact.parser.envelope import (
    EdifactEnvelopeParser,
    EnvelopeParserState,
    parse_envelope,
)
from edi_schema.edifact.parser.message import (
    EdifactMessageParser,
    MessageParseResult,
    parse_message,
)
from edi_schema.edifact.parser.tokenizer import (
    EdifactTokenizer,
    TokenizerResult,
    tokenize,
)

__all__ = [
    # AST types
    "Delimiters",
    "ErrorCategory",
    "ErrorSeverity",
    "ParseError",
    "ParseResult",
    "RecoveryPoint",
    "SourcePosition",
    # Tokenizer
    "EdifactTokenizer",
    "TokenizerResult",
    "tokenize",
    # Envelope Parser
    "EdifactEnvelopeParser",
    "EnvelopeParserState",
    "parse_envelope",
    # Message Parser
    "EdifactMessageParser",
    "MessageParseResult",
    "parse_message",
]
