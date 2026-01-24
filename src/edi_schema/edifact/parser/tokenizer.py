"""
EDIFACT Tokenizer / Lexer.

Tokenizes raw EDIFACT documents into segments and elements with full
error recovery support.

EDIFACT uses the UNA segment (optional) to define delimiters:
    UNA:+.? '
       ││││└─ segment terminator (position 8)
       │││└── reserved (position 7, usually space)
       ││└─── release/escape character (position 6)
       │└──── decimal notation (position 5)
       └───── element separator (position 4)
    position 3 is component separator

If UNA is absent, default UNOA/UNOB delimiters are used:
- Component separator: :
- Element separator: +
- Decimal notation: .
- Release character: ?
- Segment terminator: '

The release character (?) escapes the next character:
- ?+ → literal +
- ?: → literal :
- ?' → literal '
- ?? → literal ?
"""

from dataclasses import dataclass, field

from edi_schema.edifact.ast import (
    Delimiters,
    ErrorCategory,
    ErrorSeverity,
    ParseError,
    RawComponent,
    RawElement,
    RawSegment,
    RecoveryPoint,
    SourcePosition,
)


@dataclass
class TokenizerResult:
    """Result of tokenizing an EDIFACT document."""

    segments: list[RawSegment] = field(default_factory=list)
    delimiters: Delimiters = field(default_factory=Delimiters)
    errors: list[ParseError] = field(default_factory=list)
    has_una: bool = False

    # Statistics
    total_bytes: int = 0
    segment_count: int = 0
    element_count: int = 0
    component_count: int = 0
    segments_skipped: int = 0
    recovery_count: int = 0

    def is_valid(self) -> bool:
        """Check if tokenization completed without errors."""
        return len(self.errors) == 0

    def has_fatal_errors(self) -> bool:
        """Check if there are fatal errors that prevent further processing."""
        return any(e.severity == ErrorSeverity.FATAL for e in self.errors)


class EdifactTokenizer:
    """
    Tokenizes raw EDIFACT documents into segments and elements.

    Features:
    - Detects UNA segment and extracts custom delimiters
    - Falls back to default UNOA/UNOB delimiters if no UNA
    - Handles release character escaping (?+, ?:, ?', ??)
    - Handles various line ending styles (CRLF, LF, CR)
    - Supports error recovery (continues after bad data)
    - Tracks source positions for error reporting
    - Handles composite elements (sub-elements)

    Usage:
        tokenizer = EdifactTokenizer()
        result = tokenizer.tokenize(content)
        if result.has_fatal_errors():
            # Cannot continue
        else:
            for segment in result.segments:
                process(segment)
    """

    # Known EDIFACT segment tags for recovery and validation
    KNOWN_SEGMENT_TAGS = frozenset(
        {
            # Service segments (envelope)
            "UNA",
            "UNB",
            "UNZ",
            "UNG",
            "UNE",
            "UNH",
            "UNT",
            # Common message segments
            "ADR",
            "AGR",
            "AJT",
            "ALC",
            "ALI",
            "APR",
            "ARD",
            "AUT",
            "BGM",
            "BII",
            "BUS",
            "CAV",
            "CCI",
            "CDI",
            "CDS",
            "CDV",
            "CED",
            "CIN",
            "CLI",
            "CMP",
            "CNI",
            "CNT",
            "COD",
            "COM",
            "COT",
            "CPI",
            "CPS",
            "CPT",
            "CST",
            "CTA",
            "CUX",
            "DAM",
            "DFN",
            "DGS",
            "DII",
            "DIM",
            "DLI",
            "DLM",
            "DMS",
            "DOC",
            "DRD",
            "DSG",
            "DSI",
            "DTM",
            "EFI",
            "ELM",
            "ELU",
            "EMP",
            "EQA",
            "EQD",
            "EQN",
            "ERC",
            "ERP",
            "EVE",
            "FCA",
            "FII",
            "FNS",
            "FNT",
            "FOR",
            "FSQ",
            "FTX",
            "GDS",
            "GEI",
            "GID",
            "GIN",
            "GIR",
            "GOR",
            "GPO",
            "GRU",
            "HAN",
            "HYN",
            "ICD",
            "IDE",
            "IFD",
            "IHC",
            "IMD",
            "IND",
            "INP",
            "INV",
            "IRQ",
            "LAN",
            "LIN",
            "LOC",
            "MEA",
            "MEM",
            "MKS",
            "MOA",
            "MSG",
            "MTD",
            "NAD",
            "NAT",
            "PAC",
            "PAI",
            "PAS",
            "PCC",
            "PCD",
            "PCI",
            "PDI",
            "PER",
            "PGI",
            "PIA",
            "PNA",
            "POC",
            "PRC",
            "PRI",
            "PRV",
            "PSD",
            "PTY",
            "QRS",
            "QTY",
            "QUA",
            "QVR",
            "RCS",
            "REL",
            "RFF",
            "RJL",
            "RNG",
            "ROD",
            "RSL",
            "RTE",
            "SAL",
            "SCC",
            "SCD",
            "SEG",
            "SEL",
            "SEQ",
            "SFI",
            "SGP",
            "SGU",
            "SPR",
            "SPS",
            "STA",
            "STC",
            "STG",
            "STS",
            "TAX",
            "TCC",
            "TDT",
            "TEM",
            "TMD",
            "TMP",
            "TOD",
            "TPL",
            "TRU",
            "TSR",
            "UCD",
            "UCF",
            "UCI",
            "UCM",
            "UCS",
            "UGH",
            "UGT",
            "UIB",
            "UIH",
            "UIT",
            "UIZ",
            "UNO",
            "UNP",
            "UNS",
            "USA",
            "USB",
            "USC",
            "USD",
            "USE",
            "USF",
            "USH",
            "USL",
            "USR",
            "USS",
            "UST",
            "USU",
            "USX",
            "USY",
            "VLI",
        }
    )

    def __init__(self) -> None:
        self.content: str = ""
        self.position: int = 0
        self.line: int = 1
        self.column: int = 1
        self.delimiters: Delimiters = Delimiters()
        self.errors: list[ParseError] = []

    def tokenize(self, content: str | bytes) -> TokenizerResult:
        """
        Tokenize an EDIFACT document.

        Args:
            content: Raw EDIFACT document content (str or bytes)

        Returns:
            TokenizerResult with segments, delimiters, and any errors
        """
        # Handle bytes input
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")

        self.content = content
        self.position = 0
        self.line = 1
        self.column = 1
        self.errors = []

        result = TokenizerResult(total_bytes=len(content))

        if not content.strip():
            self.errors.append(
                ParseError(
                    code="TOK01",
                    message="Empty document",
                    category=ErrorCategory.STRUCTURAL,
                    severity=ErrorSeverity.FATAL,
                    position=self._current_position(),
                )
            )
            result.errors = self.errors
            return result

        # Step 1: Detect UNA and extract delimiters
        has_una, start_offset = self._detect_una()
        result.has_una = has_una

        if has_una:
            result.delimiters = self.delimiters
        else:
            self.delimiters = Delimiters.defaults()
            result.delimiters = self.delimiters

        # Step 2: Validate document starts with UNB after UNA (if any)
        remaining = content[start_offset:].lstrip()
        if not remaining.startswith("UNB"):
            self.errors.append(
                ParseError(
                    code="TOK02",
                    message="Document must start with UNB segment (after optional UNA)",
                    category=ErrorCategory.STRUCTURAL,
                    severity=ErrorSeverity.FATAL,
                    position=SourcePosition(start_offset, self.line, self.column),
                    expected="UNB",
                    actual=remaining[:3] if len(remaining) >= 3 else remaining,
                )
            )
            result.errors = self.errors
            return result

        # Step 3: Normalize line endings
        normalized = self._normalize_content(content[start_offset:])

        # Step 4: Split into segments and parse each
        segments, stats = self._tokenize_segments(normalized, start_offset)

        result.segments = segments
        result.errors = self.errors
        result.segment_count = len(segments)
        result.element_count = stats["elements"]
        result.component_count = stats["components"]
        result.segments_skipped = stats["skipped"]
        result.recovery_count = sum(1 for e in self.errors if e.recovery_point is not None)

        return result

    def _detect_una(self) -> tuple[bool, int]:
        """
        Detect UNA segment and extract delimiters.

        UNA is exactly 9 bytes: "UNA" + 6 delimiter characters.
        Position 3: component separator
        Position 4: element separator
        Position 5: decimal notation
        Position 6: release character
        Position 7: reserved (usually space)
        Position 8: segment terminator

        Returns:
            Tuple of (has_una, start_offset for content after UNA)
        """
        content = self.content

        # Check for UNA prefix
        if not content.startswith("UNA"):
            return False, 0

        # UNA must be exactly 9 characters
        if len(content) < 9:
            self.errors.append(
                ParseError(
                    code="TOK03",
                    message=f"UNA segment too short: {len(content)} < 9 bytes",
                    category=ErrorCategory.STRUCTURAL,
                    severity=ErrorSeverity.ERROR,
                    position=self._current_position(),
                )
            )
            # Try to continue with defaults
            return False, 0

        # Extract delimiters from UNA
        try:
            self.delimiters = Delimiters.from_una(content[:9])
        except ValueError as e:
            self.errors.append(
                ParseError(
                    code="TOK04",
                    message=f"Invalid UNA segment: {e}",
                    category=ErrorCategory.STRUCTURAL,
                    severity=ErrorSeverity.ERROR,
                    position=self._current_position(),
                )
            )
            # Use defaults
            self.delimiters = Delimiters.defaults()
            return False, 0

        # Validate delimiters are printable and distinct
        delim_chars = {
            self.delimiters.component,
            self.delimiters.element,
            self.delimiters.segment,
        }
        if len(delim_chars) < 3:
            self.errors.append(
                ParseError(
                    code="TOK05",
                    message=f"Delimiters must be distinct: component={self.delimiters.component!r}, "
                    f"element={self.delimiters.element!r}, segment={self.delimiters.segment!r}",
                    category=ErrorCategory.STRUCTURAL,
                    severity=ErrorSeverity.WARNING,
                    position=self._current_position(),
                )
            )

        return True, 9

    def _normalize_content(self, content: str) -> str:
        """
        Normalize content by handling line breaks after segment terminators.

        EDIFACT documents may have line breaks (CRLF, LF, CR) after segment
        terminators for readability. These should be removed.
        """
        term = self.delimiters.segment

        # Remove line breaks that follow segment terminators
        normalized = content.replace(f"{term}\r\n", term)
        normalized = normalized.replace(f"{term}\n", term)
        normalized = normalized.replace(f"{term}\r", term)

        return normalized

    def _tokenize_segments(
        self,
        content: str,
        base_offset: int,
    ) -> tuple[list[RawSegment], dict]:
        """
        Split content into segments and parse each one.

        This handles the release character when splitting - we can't just
        split on the segment terminator because it might be escaped.

        Returns:
            Tuple of (list of segments, statistics dict)
        """
        segments: list[RawSegment] = []
        stats = {"elements": 0, "components": 0, "skipped": 0}

        term = self.delimiters.segment
        release = self.delimiters.release

        # Split segments handling release character
        raw_segments = self._split_with_release(content, term, release)

        offset = base_offset
        line = self.line
        column = self.column

        for raw in raw_segments:
            # Track position
            seg_position = SourcePosition(
                offset=offset,
                line=line,
                column=column,
                length=len(raw),
            )

            # Skip empty segments
            raw_stripped = raw.strip()
            if not raw_stripped:
                offset += len(raw) + 1  # +1 for terminator
                continue

            # Parse the segment
            segment, seg_stats = self._parse_segment(raw_stripped, seg_position)

            if segment:
                segments.append(segment)
                stats["elements"] += seg_stats.get("elements", 0)
                stats["components"] += seg_stats.get("components", 0)
            else:
                stats["skipped"] += 1

            # Update position tracking
            offset += len(raw) + 1  # +1 for terminator
            newlines = raw.count("\n")
            if newlines > 0:
                line += newlines
                last_nl = raw.rfind("\n")
                column = len(raw) - last_nl
            else:
                column += len(raw) + 1

        return segments, stats

    def _split_with_release(
        self,
        content: str,
        separator: str,
        release: str,
    ) -> list[str]:
        """
        Split content by separator, respecting release character escaping.

        The release character escapes the next character, so:
        - ?'  → literal ' (not a segment terminator)
        - ??  → literal ? (not a release character)

        Args:
            content: Content to split
            separator: The separator character
            release: The release/escape character

        Returns:
            List of segments
        """
        if not content:
            return []

        result: list[str] = []
        current = []
        i = 0

        while i < len(content):
            char = content[i]

            if char == release and i + 1 < len(content):
                # Release character - include the next character literally
                current.append(char)
                current.append(content[i + 1])
                i += 2
            elif char == separator:
                # Unescaped separator - end of segment
                result.append("".join(current))
                current = []
                i += 1
            else:
                current.append(char)
                i += 1

        # Add final segment if any
        if current:
            result.append("".join(current))

        return result

    def _parse_segment(
        self,
        raw: str,
        position: SourcePosition,
    ) -> tuple[RawSegment | None, dict]:
        """
        Parse a single segment into tag and elements.

        Args:
            raw: Raw segment text (without terminator)
            position: Source position

        Returns:
            Tuple of (RawSegment or None, statistics dict)
        """
        stats = {"elements": 0, "components": 0}

        elem_sep = self.delimiters.element
        comp_sep = self.delimiters.component
        release = self.delimiters.release

        # Split by element separator (respecting release character)
        parts = self._split_with_release(raw, elem_sep, release)

        if not parts:
            self.errors.append(
                ParseError(
                    code="TOK10",
                    message="Empty segment",
                    category=ErrorCategory.STRUCTURAL,
                    severity=ErrorSeverity.WARNING,
                    position=position,
                    recovery_point=RecoveryPoint.SEGMENT_BOUNDARY,
                )
            )
            return None, stats

        # First part is the segment tag
        tag = parts[0].strip()

        # Validate tag
        if not tag:
            self.errors.append(
                ParseError(
                    code="TOK11",
                    message="Segment has no tag",
                    category=ErrorCategory.STRUCTURAL,
                    severity=ErrorSeverity.ERROR,
                    position=position,
                    recovery_point=RecoveryPoint.SEGMENT_BOUNDARY,
                )
            )
            return None, stats

        if not self._is_valid_tag(tag):
            recovered_tag = self._try_recover_tag(raw)
            if recovered_tag:
                self.errors.append(
                    ParseError(
                        code="TOK12",
                        message=f"Invalid segment tag '{tag}', recovered to '{recovered_tag}'",
                        category=ErrorCategory.STRUCTURAL,
                        severity=ErrorSeverity.WARNING,
                        position=position,
                        recovery_point=RecoveryPoint.SEGMENT_BOUNDARY,
                        actual=tag,
                        suggested_fix=recovered_tag,
                    )
                )
                tag = recovered_tag
            else:
                self.errors.append(
                    ParseError(
                        code="TOK13",
                        message=f"Invalid segment tag: '{tag}'",
                        category=ErrorCategory.STRUCTURAL,
                        severity=ErrorSeverity.WARNING,
                        position=position,
                        recovery_point=RecoveryPoint.SEGMENT_BOUNDARY,
                        actual=tag,
                    )
                )
                # Continue anyway - might be valid but unknown segment

        # Parse elements
        elements: list[RawElement] = []
        elem_offset = len(tag) + 1  # +1 for element separator after tag

        for i, part in enumerate(parts[1:], start=1):
            elem_position = SourcePosition(
                offset=position.offset + elem_offset,
                line=position.line,
                column=position.column + elem_offset,
                length=len(part),
            )

            # Check for composite (contains component separator)
            if self._contains_unescaped(part, comp_sep, release):
                components = self._split_with_release(part, comp_sep, release)
                raw_components = []
                comp_offset = 0

                for j, comp_value in enumerate(components, start=1):
                    # Unescape the component value
                    unescaped = self._unescape(comp_value, release)
                    comp_position = SourcePosition(
                        offset=elem_position.offset + comp_offset,
                        line=elem_position.line,
                        column=elem_position.column + comp_offset,
                        length=len(comp_value),
                    )
                    raw_components.append(
                        RawComponent(
                            value=unescaped,
                            position=comp_position,
                            component_index=j,
                        )
                    )
                    comp_offset += len(comp_value) + 1
                    stats["components"] += 1

                elements.append(
                    RawElement(
                        value=None,
                        position=elem_position,
                        element_index=i,
                        components=raw_components,
                    )
                )
            else:
                # Simple element - unescape the value
                unescaped = self._unescape(part, release)
                elements.append(
                    RawElement(
                        value=unescaped,
                        position=elem_position,
                        element_index=i,
                    )
                )

            stats["elements"] += 1
            elem_offset += len(part) + 1

        return RawSegment(
            tag=tag,
            elements=elements,
            position=position,
            raw_text=raw,
        ), stats

    def _contains_unescaped(self, text: str, char: str, release: str) -> bool:
        """Check if text contains an unescaped occurrence of char."""
        i = 0
        while i < len(text):
            if text[i] == release and i + 1 < len(text):
                # Skip escaped character
                i += 2
            elif text[i] == char:
                return True
            else:
                i += 1
        return False

    def _unescape(self, text: str, release: str) -> str:
        """
        Remove release character escaping from text.

        ?+ → +
        ?: → :
        ?' → '
        ?? → ?
        """
        if release not in text:
            return text

        result = []
        i = 0
        while i < len(text):
            if text[i] == release and i + 1 < len(text):
                # Release character - include next char literally
                result.append(text[i + 1])
                i += 2
            else:
                result.append(text[i])
                i += 1

        return "".join(result)

    def _is_valid_tag(self, tag: str) -> bool:
        """
        Check if a segment tag is valid.

        Valid EDIFACT tags are 3 uppercase letters (e.g., NAD, DTM, UNB).
        """
        if len(tag) != 3:
            return False

        # Must be uppercase letters
        return tag.isalpha() and tag.isupper()

    def _try_recover_tag(self, raw: str) -> str | None:
        """
        Try to find a valid segment tag in corrupted data.

        Looks for known segment tags in the raw content.
        """
        # Look for known tags at the start
        for tag in self.KNOWN_SEGMENT_TAGS:
            if raw.startswith(tag):
                return tag

        # Look for known tags anywhere (might have garbage prefix)
        for tag in self.KNOWN_SEGMENT_TAGS:
            idx = raw.find(tag)
            if 0 < idx < 10:  # Allow up to 10 chars of garbage
                return tag

        return None

    def _current_position(self) -> SourcePosition:
        """Get current position in the document."""
        return SourcePosition(
            offset=self.position,
            line=self.line,
            column=self.column,
        )


def tokenize(content: str | bytes) -> TokenizerResult:
    """
    Convenience function to tokenize an EDIFACT document.

    Args:
        content: Raw EDIFACT document content (str or bytes)

    Returns:
        TokenizerResult with segments, delimiters, and any errors
    """
    tokenizer = EdifactTokenizer()
    return tokenizer.tokenize(content)
