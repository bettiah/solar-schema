"""
X12 Envelope Parser.

Parses the X12 envelope structure (ISA/IEA, GS/GE, ST/SE) from tokenized
segments with full error recovery support.

Structure:
    ISA (Interchange Header)
      GS (Functional Group Header)
        ST (Transaction Set Header)
          ... content segments ...
        SE (Transaction Set Trailer)
      GE (Functional Group Trailer)
    IEA (Interchange Trailer)

Error Recovery:
- Missing IEA: Synthesize closure, log error
- Missing GE: Close group at next GS/IEA
- Missing SE: Close transaction at next ST/GE
- Count mismatches: Log error, use actual count
- Control number mismatches: Log error, continue
"""

from dataclasses import dataclass

from edi_schema.x12.ast import (
    Delimiters,
    ErrorCategory,
    ErrorSeverity,
    FunctionalGroupInstance,
    InterchangeInstance,
    ParseError,
    ParseResult,
    RawSegment,
    RecoveryPoint,
    TransactionSetInstance,
)
from edi_schema.x12.envelope.gs import (
    parse_ge_segment,
    parse_gs_segment,
    parse_se_segment,
    parse_st_segment,
)
from edi_schema.x12.envelope.isa import parse_iea_segment, parse_isa_segment
from edi_schema.x12.parser.tokenizer import TokenizerResult


@dataclass
class EnvelopeParserState:
    """Tracks parser state for error recovery."""

    in_interchange: bool = False
    in_group: bool = False
    in_transaction: bool = False

    current_isa_control: str = ""
    current_gs_control: str = ""
    current_st_control: str = ""

    group_count: int = 0
    transaction_count: int = 0
    segment_count: int = 0  # Within current transaction (includes ST, SE)


class EnvelopeParser:
    """
    Parses X12 envelope structure from tokenized segments.

    Features:
    - Builds nested InterchangeInstance hierarchy
    - Validates control numbers and counts
    - Recovers from missing trailers
    - Collects all errors for reporting

    Usage:
        parser = EnvelopeParser()
        result = parser.parse(tokenizer_result)
    """

    def __init__(self):
        self.segments: list[RawSegment] = []
        self.delimiters: Delimiters = Delimiters()
        self.index: int = 0
        self.errors: list[ParseError] = []
        self.state: EnvelopeParserState = EnvelopeParserState()

    def parse(self, tokenizer_result: TokenizerResult) -> ParseResult:
        """
        Parse envelope structure from tokenizer result.

        Args:
            tokenizer_result: Result from X12Tokenizer

        Returns:
            ParseResult with interchange and all errors
        """
        # Initialize
        self.segments = tokenizer_result.segments
        self.delimiters = tokenizer_result.delimiters
        self.index = 0
        self.errors = list(tokenizer_result.errors)  # Start with tokenizer errors
        self.state = EnvelopeParserState()

        result = ParseResult()

        # Check for empty input
        if not self.segments:
            self.errors.append(
                ParseError(
                    code="ENV01",
                    message="No segments to parse",
                    category=ErrorCategory.STRUCTURAL,
                    severity=ErrorSeverity.FATAL,
                )
            )
            result.errors = self.errors
            return result

        # Parse interchange
        try:
            interchange = self._parse_interchange()
            result.interchange = interchange
        except Exception as e:
            self.errors.append(
                ParseError(
                    code="ENV02",
                    message=f"Unexpected error parsing envelope: {e}",
                    category=ErrorCategory.STRUCTURAL,
                    severity=ErrorSeverity.FATAL,
                )
            )

        result.errors = [e for e in self.errors if e.severity != ErrorSeverity.WARNING]
        result.warnings = [e for e in self.errors if e.severity == ErrorSeverity.WARNING]
        result.segments_parsed = self.index

        return result

    def _parse_interchange(self) -> InterchangeInstance | None:
        """Parse ISA...IEA interchange envelope."""
        # Must start with ISA
        if not self._peek_tag() == "ISA":
            self.errors.append(
                ParseError(
                    code="ENV10",
                    message=f"Expected ISA, found {self._peek_tag()}",
                    category=ErrorCategory.ENVELOPE,
                    severity=ErrorSeverity.FATAL,
                    recovery_point=RecoveryPoint.INTERCHANGE_END,
                )
            )
            return None

        # Parse ISA
        isa_segment = self._next_segment()
        isa_data, isa_errors = parse_isa_segment(
            isa_segment.raw_text + self.delimiters.segment,
            isa_segment.position,
        )
        self.errors.extend(isa_errors)

        if isa_data is None:
            return None

        self.state.in_interchange = True
        self.state.current_isa_control = isa_data.control_number

        # Parse functional groups
        groups: list[FunctionalGroupInstance] = []

        while self._has_more() and self._peek_tag() not in ("IEA", None):
            if self._peek_tag() == "GS":
                group = self._parse_functional_group()
                if group:
                    groups.append(group)
                    self.state.group_count += 1
            else:
                # Unexpected segment at interchange level
                seg = self._next_segment()
                self.errors.append(
                    ParseError(
                        code="ENV11",
                        message=f"Unexpected segment at interchange level: {seg.tag}",
                        category=ErrorCategory.ENVELOPE,
                        severity=ErrorSeverity.WARNING,
                        position=seg.position,
                        segment_tag=seg.tag,
                        recovery_point=RecoveryPoint.GROUP_START,
                    )
                )

        # Parse IEA (or synthesize if missing)
        iea_errors: list[ParseError] = []
        if self._peek_tag() == "IEA":
            iea_segment = self._next_segment()
            elements = [e.value if hasattr(e, "value") else str(e) for e in iea_segment.elements]
            _, iea_errors = parse_iea_segment(
                elements,
                expected_control=self.state.current_isa_control,
                expected_count=self.state.group_count,
                position=iea_segment.position,
            )
            self.errors.extend(iea_errors)
        else:
            # Missing IEA - synthesize closure
            self.errors.append(
                ParseError(
                    code="ENV12",
                    message="Missing IEA segment - interchange not properly closed",
                    category=ErrorCategory.ENVELOPE,
                    severity=ErrorSeverity.ERROR,
                    recovery_point=RecoveryPoint.INTERCHANGE_END,
                )
            )

        self.state.in_interchange = False

        return InterchangeInstance(
            auth_qualifier=isa_data.auth_qualifier,
            auth_info=isa_data.auth_info,
            security_qualifier=isa_data.security_qualifier,
            security_info=isa_data.security_info,
            sender_qualifier=isa_data.sender_qualifier,
            sender_id=isa_data.sender_id.strip(),
            receiver_qualifier=isa_data.receiver_qualifier,
            receiver_id=isa_data.receiver_id.strip(),
            date=isa_data.date,
            time=isa_data.time,
            repetition_separator=isa_data.repetition_separator,
            version=isa_data.version,
            control_number=isa_data.control_number,
            ack_requested=isa_data.ack_requested,
            usage_indicator=isa_data.usage_indicator,
            component_separator=isa_data.component_separator,
            delimiters=self.delimiters,
            groups=groups,
            group_count=self.state.group_count,
            errors=[e for e in isa_errors + iea_errors if e.severity == ErrorSeverity.ERROR],
        )

    def _parse_functional_group(self) -> FunctionalGroupInstance | None:
        """Parse GS...GE functional group envelope."""
        # Parse GS
        gs_segment = self._next_segment()
        elements = self._extract_elements(gs_segment)
        gs_data, gs_errors = parse_gs_segment(elements, gs_segment.position)
        self.errors.extend(gs_errors)

        self.state.in_group = True
        self.state.current_gs_control = gs_data.control_number
        self.state.transaction_count = 0

        # Parse transaction sets
        transactions: list[TransactionSetInstance] = []

        while self._has_more() and self._peek_tag() not in ("GE", "GS", "IEA", None):
            if self._peek_tag() == "ST":
                txn = self._parse_transaction_set()
                if txn:
                    transactions.append(txn)
                    self.state.transaction_count += 1
            else:
                # Unexpected segment at group level
                seg = self._next_segment()
                self.errors.append(
                    ParseError(
                        code="ENV20",
                        message=f"Unexpected segment at group level: {seg.tag}",
                        category=ErrorCategory.ENVELOPE,
                        severity=ErrorSeverity.WARNING,
                        position=seg.position,
                        segment_tag=seg.tag,
                        group_control=self.state.current_gs_control,
                        recovery_point=RecoveryPoint.TRANSACTION_START,
                    )
                )

        # Parse GE (or synthesize if missing)
        ge_errors: list[ParseError] = []
        if self._peek_tag() == "GE":
            ge_segment = self._next_segment()
            elements = self._extract_elements(ge_segment)
            _, ge_errors = parse_ge_segment(
                elements,
                expected_control=self.state.current_gs_control,
                expected_count=self.state.transaction_count,
                position=ge_segment.position,
            )
            self.errors.extend(ge_errors)
        else:
            # Missing GE - synthesize closure
            self.errors.append(
                ParseError(
                    code="ENV21",
                    message=f"Missing GE segment for group {self.state.current_gs_control}",
                    category=ErrorCategory.ENVELOPE,
                    severity=ErrorSeverity.ERROR,
                    group_control=self.state.current_gs_control,
                    recovery_point=RecoveryPoint.GROUP_END,
                )
            )

        self.state.in_group = False

        return FunctionalGroupInstance(
            functional_id=gs_data.functional_id,
            sender_id=gs_data.sender_id,
            receiver_id=gs_data.receiver_id,
            date=gs_data.date,
            time=gs_data.time,
            control_number=gs_data.control_number,
            responsible_agency=gs_data.responsible_agency,
            version=gs_data.version,
            transactions=transactions,
            transaction_count=self.state.transaction_count,
            errors=[e for e in gs_errors + ge_errors if e.severity == ErrorSeverity.ERROR],
        )

    def _parse_transaction_set(self) -> TransactionSetInstance | None:
        """Parse ST...SE transaction set envelope."""
        # Parse ST
        st_segment = self._next_segment()
        elements = self._extract_elements(st_segment)
        st_data, st_errors = parse_st_segment(elements, st_segment.position)
        self.errors.extend(st_errors)

        self.state.in_transaction = True
        self.state.current_st_control = st_data.control_number
        self.state.segment_count = 1  # ST counts as 1

        # Collect content segments (everything between ST and SE)
        content_segments: list[RawSegment] = []

        while self._has_more() and self._peek_tag() not in ("SE", "ST", "GE", "GS", "IEA", None):
            seg = self._next_segment()
            content_segments.append(seg)
            self.state.segment_count += 1

        # Parse SE (or synthesize if missing)
        se_errors: list[ParseError] = []
        expected_count = self.state.segment_count + 1  # +1 for SE itself

        if self._peek_tag() == "SE":
            se_segment = self._next_segment()
            elements = self._extract_elements(se_segment)
            se_data, se_errors = parse_se_segment(
                elements,
                expected_control=self.state.current_st_control,
                expected_count=expected_count,
                position=se_segment.position,
            )
            self.errors.extend(se_errors)
            actual_count = se_data.segment_count
        else:
            # Missing SE - synthesize closure
            self.errors.append(
                ParseError(
                    code="ENV30",
                    message=f"Missing SE segment for transaction {self.state.current_st_control}",
                    category=ErrorCategory.ENVELOPE,
                    severity=ErrorSeverity.ERROR,
                    transaction_id=st_data.transaction_id,
                    group_control=self.state.current_gs_control,
                    recovery_point=RecoveryPoint.TRANSACTION_END,
                )
            )
            actual_count = expected_count

        self.state.in_transaction = False

        return TransactionSetInstance(
            transaction_id=st_data.transaction_id,
            control_number=st_data.control_number,
            implementation_reference=st_data.implementation_reference,
            content=content_segments,  # Raw segments for now
            segment_count=actual_count,
            actual_segment_count=expected_count,
            errors=[e for e in st_errors + se_errors if e.severity == ErrorSeverity.ERROR],
        )

    def _peek_tag(self) -> str | None:
        """Peek at the next segment's tag without consuming it."""
        if self.index < len(self.segments):
            return self.segments[self.index].tag
        return None

    def _next_segment(self) -> RawSegment:
        """Consume and return the next segment."""
        seg = self.segments[self.index]
        self.index += 1
        return seg

    def _has_more(self) -> bool:
        """Check if there are more segments to process."""
        return self.index < len(self.segments)

    def _extract_elements(self, segment: RawSegment) -> list[str]:
        """Extract element values from a raw segment."""
        result = []
        for elem in segment.elements:
            if hasattr(elem, "value"):
                result.append(elem.value)
            elif hasattr(elem, "components"):
                # For composites, join with component separator
                result.append(self.delimiters.component.join(elem.components))
            else:
                result.append(str(elem))
        return result


def parse_envelope(tokenizer_result: TokenizerResult) -> ParseResult:
    """
    Convenience function to parse envelope structure.

    Args:
        tokenizer_result: Result from X12Tokenizer

    Returns:
        ParseResult with interchange and all errors
    """
    parser = EnvelopeParser()
    return parser.parse(tokenizer_result)
