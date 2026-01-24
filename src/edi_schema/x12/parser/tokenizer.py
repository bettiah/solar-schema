"""
X12 Tokenizer / Lexer.

Tokenizes raw X12 EDI documents into segments and elements with full
error recovery support.

The ISA segment is special - it's exactly 106 characters with fixed-width
fields. Delimiters are extracted from:
- Position 3: Element separator (character after "ISA")
- Position 82: Repetition separator (ISA11 in version 5010+)
- Position 104: Component separator (ISA16)
- Position 105: Segment terminator
"""

from dataclasses import dataclass, field

from edi_schema.x12.ast import (
    Delimiters,
    ErrorCategory,
    ErrorSeverity,
    ParseError,
    RawComposite,
    RawElement,
    RawSegment,
    RecoveryPoint,
    SourcePosition,
)


@dataclass
class TokenizerResult:
    """Result of tokenizing an X12 document."""

    segments: list[RawSegment] = field(default_factory=list)
    delimiters: Delimiters = field(default_factory=Delimiters)
    errors: list[ParseError] = field(default_factory=list)

    # Statistics
    total_characters: int = 0
    segments_parsed: int = 0
    segments_skipped: int = 0
    recovery_count: int = 0

    def is_valid(self) -> bool:
        """Check if tokenization completed without errors."""
        return len(self.errors) == 0

    def has_fatal_errors(self) -> bool:
        """Check if there are fatal errors that prevent further processing."""
        return any(e.severity == ErrorSeverity.FATAL for e in self.errors)


class X12Tokenizer:
    """
    Tokenizes raw X12 documents into segments and elements.

    Features:
    - Extracts delimiters from ISA segment (fixed positions)
    - Handles various line ending styles (CRLF, LF, CR)
    - Supports error recovery (continues after bad data)
    - Tracks source positions for error reporting
    - Handles composite elements (sub-elements)
    - Supports repetition separator (element arrays)

    Usage:
        tokenizer = X12Tokenizer()
        result = tokenizer.tokenize(content)
        if result.has_fatal_errors():
            # Cannot continue
        else:
            for segment in result.segments:
                process(segment)
    """

    # Known segment tags for recovery
    KNOWN_SEGMENT_TAGS = frozenset(
        {
            # Envelope
            "ISA",
            "IEA",
            "GS",
            "GE",
            "ST",
            "SE",
            # Common segments
            "BEG",
            "BHT",
            "BGN",
            "BPR",
            "BSN",
            "CLP",
            "CLM",
            "CTT",
            "CUR",
            "DMG",
            "DTM",
            "DTP",
            "ENT",
            "GS",
            "HL",
            "HI",
            "ISA",
            "LIN",
            "LQ",
            "LX",
            "MEA",
            "MIA",
            "MOA",
            "MSG",
            "N1",
            "N2",
            "N3",
            "N4",
            "NM1",
            "NTE",
            "OTI",
            "PAT",
            "PER",
            "PID",
            "PKG",
            "PO1",
            "PO4",
            "PRF",
            "PWK",
            "QTY",
            "REF",
            "SAC",
            "SBR",
            "SE",
            "SLN",
            "SN1",
            "ST",
            "STC",
            "SV1",
            "SV2",
            "SVC",
            "TAX",
            "TD1",
            "TD3",
            "TD4",
            "TD5",
            "TRN",
            "TS2",
            "TS3",
            # 997/999 specific
            "AK1",
            "AK2",
            "AK3",
            "AK4",
            "AK5",
            "AK9",
            "IK3",
            "IK4",
            "IK5",
            # Healthcare
            "CAS",
            "AMT",
            "QTY",
            "PLB",
        }
    )

    def __init__(self):
        self.content: str = ""
        self.position: int = 0
        self.line: int = 1
        self.column: int = 1
        self.delimiters: Delimiters = Delimiters()
        self.errors: list[ParseError] = []

    def tokenize(self, content: str) -> TokenizerResult:
        """
        Tokenize an X12 document.

        Args:
            content: Raw X12 document content

        Returns:
            TokenizerResult with segments, delimiters, and any errors
        """
        self.content = content
        self.position = 0
        self.line = 1
        self.column = 1
        self.errors = []

        result = TokenizerResult(total_characters=len(content))

        # Step 1: Extract delimiters from ISA
        if not self._extract_delimiters():
            # Fatal error - cannot continue
            result.errors = self.errors
            return result

        result.delimiters = self.delimiters

        # Step 2: Normalize line endings and remove them
        # X12 allows segment terminators to be followed by line breaks
        normalized = self._normalize_content(content)

        # Step 3: Split into segments and parse each
        segments, skipped = self._tokenize_segments(normalized)

        result.segments = segments
        result.errors = self.errors
        result.segments_parsed = len(segments)
        result.segments_skipped = skipped
        result.recovery_count = sum(1 for e in self.errors if e.recovery_point is not None)

        return result

    def _extract_delimiters(self) -> bool:
        """
        Extract delimiters from the ISA segment.

        ISA is exactly 106 characters with fixed positions:
        - Position 3: Element separator
        - Position 82: Repetition separator (or standards ID in older versions)
        - Position 104: Component separator
        - Position 105: Segment terminator

        Returns:
            True if delimiters extracted successfully, False on fatal error
        """
        content = self.content

        # Must start with ISA
        if not content.startswith("ISA"):
            self.errors.append(
                ParseError(
                    code="TOK01",
                    message="Document must start with ISA segment",
                    category=ErrorCategory.STRUCTURAL,
                    severity=ErrorSeverity.FATAL,
                    position=self._current_position(),
                    expected="ISA",
                    actual=content[:3] if len(content) >= 3 else content,
                )
            )
            return False

        # Must have at least 106 characters for ISA
        if len(content) < 106:
            self.errors.append(
                ParseError(
                    code="TOK02",
                    message=f"Document too short for ISA segment: {len(content)} < 106",
                    category=ErrorCategory.STRUCTURAL,
                    severity=ErrorSeverity.FATAL,
                    position=self._current_position(),
                )
            )
            return False

        # Extract delimiters from fixed positions
        element_sep = content[3]
        repetition_sep = content[82]
        component_sep = content[104]
        segment_term = content[105]

        # Validate delimiters are printable and distinct
        delim_chars = {element_sep, component_sep, segment_term}
        if len(delim_chars) < 3:
            self.errors.append(
                ParseError(
                    code="TOK03",
                    message=f"Delimiters must be distinct: element={element_sep!r}, "
                    f"component={component_sep!r}, segment={segment_term!r}",
                    category=ErrorCategory.STRUCTURAL,
                    severity=ErrorSeverity.ERROR,
                    position=self._current_position(),
                )
            )
            # Continue anyway - might still work

        # Check for common delimiter issues
        if element_sep in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
            self.errors.append(
                ParseError(
                    code="TOK04",
                    message=f"Element separator appears to be alphanumeric: {element_sep!r}",
                    category=ErrorCategory.STRUCTURAL,
                    severity=ErrorSeverity.WARNING,
                    position=self._current_position(),
                )
            )

        self.delimiters = Delimiters(
            element=element_sep,
            component=component_sep,
            repetition=repetition_sep,
            segment=segment_term,
        )

        return True

    def _normalize_content(self, content: str) -> str:
        """
        Normalize content by handling line breaks after segment terminators.

        X12 documents may have line breaks (CRLF, LF, CR) after segment
        terminators for readability. These should be removed.
        """
        term = self.delimiters.segment

        # Remove line breaks that follow segment terminators
        # Common patterns: ~\r\n, ~\n, ~\r
        normalized = content.replace(f"{term}\r\n", term)
        normalized = normalized.replace(f"{term}\n", term)
        normalized = normalized.replace(f"{term}\r", term)

        # Also handle case where line breaks are used AS terminators
        # (some systems use \n instead of ~)
        # We detect this if there are very few ~ but many \n
        tilde_count = content.count("~")
        newline_count = content.count("\n")

        if tilde_count < 5 and newline_count > 10:
            self.errors.append(
                ParseError(
                    code="TOK05",
                    message="Document may be using newlines as segment terminators",
                    category=ErrorCategory.STRUCTURAL,
                    severity=ErrorSeverity.WARNING,
                    position=self._current_position(),
                )
            )

        return normalized

    def _tokenize_segments(self, content: str) -> tuple[list[RawSegment], int]:
        """
        Split content into segments and parse each one.

        Returns:
            Tuple of (list of segments, count of skipped segments)
        """
        segments: list[RawSegment] = []
        skipped = 0

        term = self.delimiters.segment

        # Split by segment terminator
        raw_segments = content.split(term)

        offset = 0
        line = 1
        column = 1

        for i, raw in enumerate(raw_segments):
            # Track position
            seg_position = SourcePosition(
                offset=offset,
                line=line,
                column=column,
                length=len(raw),
            )

            # Skip empty segments (trailing terminator)
            raw_stripped = raw.strip()
            if not raw_stripped:
                offset += len(raw) + 1  # +1 for terminator
                continue

            # Parse the segment
            segment = self._parse_segment(raw_stripped, seg_position)

            if segment:
                segments.append(segment)
            else:
                skipped += 1

            # Update position tracking
            offset += len(raw) + 1  # +1 for terminator
            # Count newlines in raw segment for line tracking
            newlines = raw.count("\n")
            if newlines > 0:
                line += newlines
                # Column is position after last newline
                last_nl = raw.rfind("\n")
                column = len(raw) - last_nl
            else:
                column += len(raw) + 1

        return segments, skipped

    def _parse_segment(
        self,
        raw: str,
        position: SourcePosition,
    ) -> RawSegment | None:
        """
        Parse a single segment into tag and elements.

        Args:
            raw: Raw segment text (without terminator)
            position: Source position

        Returns:
            RawSegment or None if segment should be skipped
        """
        elem_sep = self.delimiters.element
        comp_sep = self.delimiters.component
        rep_sep = self.delimiters.repetition

        # Split by element separator
        parts = raw.split(elem_sep)

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
            return None

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
            return None

        if not self._is_valid_tag(tag):
            # Try to recover - maybe there's garbage before a valid tag
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
                # Continue anyway - might be a valid but unknown segment

        # Parse elements
        elements: list[RawElement | RawComposite] = []
        elem_offset = len(tag) + 1  # +1 for element separator after tag

        for i, part in enumerate(parts[1:], start=1):
            elem_position = SourcePosition(
                offset=position.offset + elem_offset,
                line=position.line,
                column=position.column + elem_offset,
                length=len(part),
            )

            # Check for composite (contains component separator)
            if comp_sep in part:
                components = part.split(comp_sep)
                elements.append(
                    RawComposite(
                        components=components,
                        position=elem_position,
                        element_index=i,
                    )
                )
            # Check for repetition (contains repetition separator)
            elif rep_sep in part and rep_sep != "U":
                # Repetition separator - split into array
                # For now, join them back as a single value
                # TODO: Support repeated elements properly
                elements.append(
                    RawElement(
                        value=part,
                        position=elem_position,
                        element_index=i,
                    )
                )
            else:
                # Simple element
                elements.append(
                    RawElement(
                        value=part,
                        position=elem_position,
                        element_index=i,
                    )
                )

            elem_offset += len(part) + 1  # +1 for separator

        return RawSegment(
            tag=tag,
            elements=elements,
            position=position,
            raw_text=raw,
        )

    def _is_valid_tag(self, tag: str) -> bool:
        """
        Check if a segment tag is valid.

        Valid tags are 2-3 uppercase alphanumeric characters.
        """
        if len(tag) < 2 or len(tag) > 3:
            return False

        # Must be uppercase letters and digits
        return all(c.isalnum() and (c.isupper() or c.isdigit()) for c in tag)

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
            if idx > 0 and idx < 10:  # Allow up to 10 chars of garbage
                return tag

        return None

    def _current_position(self) -> SourcePosition:
        """Get current position in the document."""
        return SourcePosition(
            offset=self.position,
            line=self.line,
            column=self.column,
        )


def tokenize(content: str) -> TokenizerResult:
    """
    Convenience function to tokenize an X12 document.

    Args:
        content: Raw X12 document content

    Returns:
        TokenizerResult with segments, delimiters, and any errors
    """
    tokenizer = X12Tokenizer()
    return tokenizer.tokenize(content)
