"""
EDIFACT Envelope Parser.

Parses the EDIFACT envelope structure (UNB/UNZ, UNG/UNE, UNH/UNT) from
tokenized segments with full error recovery support.

Structure:
    UNA (optional) - Service String Advice (delimiters)
    UNB (Interchange Header)
      UNG (Functional Group Header) - OPTIONAL
        UNH (Message Header)
          ... content segments ...
        UNT (Message Trailer)
      UNE (Functional Group Trailer) - OPTIONAL
    UNZ (Interchange Trailer)

Key differences from X12:
- UNG/UNE functional groups are optional (most EDIFACT skips them)
- Control references are variable length (not fixed 9 digits)
- UNB contains composite elements for sender/recipient/datetime
- Support for syntax versions 1-4 (different date formats)

Error Recovery:
- Missing UNZ: Synthesize closure at end of input
- Missing UNE: Close group at next UNG/UNZ
- Missing UNT: Close message at next UNH/UNE/UNZ
- Count mismatches: Log error, use actual count
- Control reference mismatches: Log error, continue
"""

from dataclasses import dataclass

from edi_schema.edifact.ast import (
    Delimiters,
    ErrorCategory,
    ErrorSeverity,
    FunctionalGroupInstance,
    InterchangeInstance,
    MessageInstance,
    ParseError,
    ParseResult,
    ParseStatistics,
    RawSegment,
    RecoveryPoint,
)
from edi_schema.edifact.parser.tokenizer import TokenizerResult


@dataclass
class EnvelopeParserState:
    """Track envelope parsing state for validation and error recovery."""

    in_interchange: bool = False
    in_group: bool = False
    in_message: bool = False

    # Control references for matching headers to trailers
    interchange_reference: str = ""
    group_reference: str = ""
    message_reference: str = ""

    # Counts for trailer validation
    segment_count: int = 0  # Within current message (includes UNH, UNT)
    message_count: int = 0  # Within current group/interchange
    group_count: int = 0  # Within interchange

    # Track what content interchange has
    interchange_has_groups: bool = False


class EdifactEnvelopeParser:
    """
    Parse EDIFACT envelope structure from tokenized segments.

    Features:
    - Builds nested InterchangeInstance hierarchy
    - Handles optional UNG/UNE functional groups
    - Validates control references match between headers/trailers
    - Validates segment/message/group counts
    - Recovers from missing trailers with appropriate errors

    Usage:
        parser = EdifactEnvelopeParser()
        result = parser.parse(tokenizer_result)
    """

    def __init__(self) -> None:
        self.segments: list[RawSegment] = []
        self.delimiters: Delimiters = Delimiters()
        self.index: int = 0
        self.errors: list[ParseError] = []
        self.state: EnvelopeParserState = EnvelopeParserState()

    def parse(self, tokenizer_result: TokenizerResult) -> ParseResult:
        """
        Parse envelope structure from tokenizer result.

        Args:
            tokenizer_result: Result from EdifactTokenizer

        Returns:
            ParseResult with interchange(s) and all errors
        """
        # Initialize
        self.segments = tokenizer_result.segments
        self.delimiters = tokenizer_result.delimiters
        self.index = 0
        self.errors = list(tokenizer_result.errors)  # Start with tokenizer errors
        self.state = EnvelopeParserState()

        result = ParseResult(
            delimiters=self.delimiters,
            statistics=ParseStatistics(
                total_bytes=tokenizer_result.total_bytes,
                una_present=tokenizer_result.has_una,
            ),
        )

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

        # Parse interchange(s)
        interchanges: list[InterchangeInstance] = []
        try:
            while self._has_more():
                if self._peek_tag() == "UNB":
                    interchange = self._parse_interchange()
                    if interchange:
                        interchanges.append(interchange)
                        result.statistics.interchange_count += 1
                else:
                    # Unexpected segment before UNB
                    seg = self._next_segment()
                    self.errors.append(
                        ParseError(
                            code="ENV02",
                            message=f"Expected UNB, found {seg.tag}",
                            category=ErrorCategory.ENVELOPE,
                            severity=ErrorSeverity.ERROR,
                            position=seg.position,
                            segment_tag=seg.tag,
                            recovery_point=RecoveryPoint.INTERCHANGE_END,
                        )
                    )
        except Exception as e:
            self.errors.append(
                ParseError(
                    code="ENV03",
                    message=f"Unexpected error parsing envelope: {e}",
                    category=ErrorCategory.STRUCTURAL,
                    severity=ErrorSeverity.FATAL,
                )
            )

        result.interchanges = interchanges
        result.errors = [e for e in self.errors if e.severity != ErrorSeverity.WARNING]
        result.warnings = [e for e in self.errors if e.severity == ErrorSeverity.WARNING]
        result.segments_parsed = self.index
        result.statistics.segment_count = self.index

        return result

    def _parse_interchange(self) -> InterchangeInstance | None:
        """Parse UNB...UNZ interchange envelope."""
        # Must be at UNB
        if self._peek_tag() != "UNB":
            return None

        # Parse UNB header
        unb_segment = self._next_segment()
        unb_data, unb_errors = self._parse_unb_segment(unb_segment)
        self.errors.extend(unb_errors)

        self.state.in_interchange = True
        self.state.interchange_reference = unb_data.get("control_reference", "")
        self.state.group_count = 0
        self.state.message_count = 0
        self.state.interchange_has_groups = False

        # Parse content: UNG groups or direct UNH messages
        groups: list[FunctionalGroupInstance] = []
        messages: list[MessageInstance] = []

        while self._has_more() and self._peek_tag() not in ("UNZ", None):
            tag = self._peek_tag()

            if tag == "UNG":
                # Functional group
                self.state.interchange_has_groups = True
                group = self._parse_functional_group()
                if group:
                    groups.append(group)
                    self.state.group_count += 1

            elif tag == "UNH":
                # Direct message (no functional group wrapper)
                if self.state.interchange_has_groups:
                    # Error: mixing groups and direct messages
                    self.errors.append(
                        ParseError(
                            code="ENV10",
                            message="Found UNH outside of functional group after UNG was used",
                            category=ErrorCategory.ENVELOPE,
                            severity=ErrorSeverity.WARNING,
                            position=self.segments[self.index].position,
                            interchange_reference=self.state.interchange_reference,
                        )
                    )
                message = self._parse_message()
                if message:
                    messages.append(message)
                    self.state.message_count += 1

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
                        interchange_reference=self.state.interchange_reference,
                        recovery_point=RecoveryPoint.MESSAGE_START,
                    )
                )

        # Parse UNZ trailer
        unz_errors: list[ParseError] = []
        unz_segment: RawSegment | None = None
        declared_count: int | None = None

        if self._peek_tag() == "UNZ":
            unz_segment = self._next_segment()
            declared_count, unz_errors = self._parse_unz_segment(
                unz_segment,
                expected_reference=self.state.interchange_reference,
                expected_count=(
                    self.state.group_count
                    if self.state.interchange_has_groups
                    else self.state.message_count
                ),
            )
            self.errors.extend(unz_errors)
        else:
            # Missing UNZ
            self.errors.append(
                ParseError(
                    code="ENV12",
                    message="Missing UNZ segment - interchange not properly closed",
                    category=ErrorCategory.ENVELOPE,
                    severity=ErrorSeverity.ERROR,
                    interchange_reference=self.state.interchange_reference,
                    recovery_point=RecoveryPoint.INTERCHANGE_END,
                )
            )

        self.state.in_interchange = False

        return InterchangeInstance(
            # Required fields
            syntax_identifier=unb_data.get("syntax_identifier", "UNOA"),
            syntax_version=unb_data.get("syntax_version", "3"),
            sender_id=unb_data.get("sender_id", ""),
            recipient_id=unb_data.get("recipient_id", ""),
            # Optional fields with defaults
            sender_qualifier=unb_data.get("sender_qualifier"),
            recipient_qualifier=unb_data.get("recipient_qualifier"),
            date=unb_data.get("date", ""),
            time=unb_data.get("time", ""),
            control_reference=unb_data.get("control_reference", ""),
            application_reference=unb_data.get("application_reference"),
            processing_priority=unb_data.get("processing_priority"),
            ack_request=unb_data.get("ack_request"),
            agreement_id=unb_data.get("agreement_id"),
            test_indicator=unb_data.get("test_indicator"),
            delimiters=self.delimiters,
            groups=groups,
            messages=messages,
            unb_segment=unb_segment,
            unz_segment=unz_segment,
            count=declared_count,
            errors=[e for e in unb_errors + unz_errors if e.severity == ErrorSeverity.ERROR],
        )

    def _parse_functional_group(self) -> FunctionalGroupInstance | None:
        """Parse UNG...UNE functional group envelope."""
        if self._peek_tag() != "UNG":
            return None

        # Parse UNG header
        ung_segment = self._next_segment()
        ung_data, ung_errors = self._parse_ung_segment(ung_segment)
        self.errors.extend(ung_errors)

        self.state.in_group = True
        self.state.group_reference = ung_data.get("reference_number", "")
        self.state.message_count = 0

        # Parse messages within group
        messages: list[MessageInstance] = []

        while self._has_more() and self._peek_tag() not in ("UNE", "UNG", "UNZ", None):
            if self._peek_tag() == "UNH":
                message = self._parse_message()
                if message:
                    messages.append(message)
                    self.state.message_count += 1
            else:
                # Unexpected segment at group level
                seg = self._next_segment()
                self.errors.append(
                    ParseError(
                        code="ENV20",
                        message=f"Unexpected segment at functional group level: {seg.tag}",
                        category=ErrorCategory.ENVELOPE,
                        severity=ErrorSeverity.WARNING,
                        position=seg.position,
                        segment_tag=seg.tag,
                        group_reference=self.state.group_reference,
                        interchange_reference=self.state.interchange_reference,
                        recovery_point=RecoveryPoint.MESSAGE_START,
                    )
                )

        # Parse UNE trailer
        une_errors: list[ParseError] = []
        une_segment: RawSegment | None = None
        declared_count: int | None = None

        if self._peek_tag() == "UNE":
            une_segment = self._next_segment()
            declared_count, une_errors = self._parse_une_segment(
                une_segment,
                expected_reference=self.state.group_reference,
                expected_count=self.state.message_count,
            )
            self.errors.extend(une_errors)
        else:
            # Missing UNE
            self.errors.append(
                ParseError(
                    code="ENV21",
                    message=f"Missing UNE segment for group {self.state.group_reference}",
                    category=ErrorCategory.ENVELOPE,
                    severity=ErrorSeverity.ERROR,
                    group_reference=self.state.group_reference,
                    interchange_reference=self.state.interchange_reference,
                    recovery_point=RecoveryPoint.FUNCTIONAL_GROUP_END,
                )
            )

        self.state.in_group = False

        return FunctionalGroupInstance(
            message_type=ung_data.get("message_type", ""),
            sender_id=ung_data.get("sender_id", ""),
            recipient_id=ung_data.get("recipient_id", ""),
            reference_number=ung_data.get("reference_number", ""),
            date=ung_data.get("date"),
            time=ung_data.get("time"),
            controlling_agency=ung_data.get("controlling_agency", "UN"),
            message_version=ung_data.get("message_version"),
            message_release=ung_data.get("message_release"),
            messages=messages,
            ung_segment=ung_segment,
            une_segment=une_segment,
            message_count=declared_count,
            errors=[e for e in ung_errors + une_errors if e.severity == ErrorSeverity.ERROR],
        )

    def _parse_message(self) -> MessageInstance | None:
        """Parse UNH...UNT message envelope."""
        if self._peek_tag() != "UNH":
            return None

        # Parse UNH header
        unh_segment = self._next_segment()
        unh_data, unh_errors = self._parse_unh_segment(unh_segment)
        self.errors.extend(unh_errors)

        self.state.in_message = True
        self.state.message_reference = unh_data.get("reference_number", "")
        self.state.segment_count = 1  # UNH counts as 1

        # Collect content segments (everything between UNH and UNT)
        content_segments: list[RawSegment] = []

        while self._has_more() and self._peek_tag() not in (
            "UNT",
            "UNH",
            "UNE",
            "UNG",
            "UNZ",
            None,
        ):
            seg = self._next_segment()
            content_segments.append(seg)
            self.state.segment_count += 1

        # Parse UNT trailer
        unt_errors: list[ParseError] = []
        unt_segment: RawSegment | None = None
        declared_count: int | None = None

        expected_count = self.state.segment_count + 1  # +1 for UNT itself

        if self._peek_tag() == "UNT":
            unt_segment = self._next_segment()
            declared_count, unt_errors = self._parse_unt_segment(
                unt_segment,
                expected_reference=self.state.message_reference,
                expected_count=expected_count,
            )
            self.errors.extend(unt_errors)
        else:
            # Missing UNT
            self.errors.append(
                ParseError(
                    code="ENV30",
                    message=f"Missing UNT segment for message {self.state.message_reference}",
                    category=ErrorCategory.ENVELOPE,
                    severity=ErrorSeverity.ERROR,
                    message_reference=self.state.message_reference,
                    group_reference=self.state.group_reference if self.state.in_group else None,
                    interchange_reference=self.state.interchange_reference,
                    recovery_point=RecoveryPoint.MESSAGE_END,
                )
            )

        self.state.in_message = False

        # Convert content to parsed segments (raw for now, message parser will schema-parse)
        # For envelope parsing, we keep them as RawSegment wrapped in a simple structure
        from edi_schema.edifact.ast import ParsedElement, ParsedSegment

        parsed_content: list[ParsedSegment] = []
        for raw_seg in content_segments:
            # Create ParsedElement from each RawElement
            parsed_elements = [ParsedElement(raw=elem) for elem in raw_seg.elements]
            parsed_content.append(
                ParsedSegment(
                    tag=raw_seg.tag,
                    elements=parsed_elements,
                    raw=raw_seg,
                )
            )

        return MessageInstance(
            reference_number=unh_data.get("reference_number", ""),
            message_type=unh_data.get("message_type", ""),
            version=unh_data.get("version", ""),
            release=unh_data.get("release", ""),
            controlling_agency=unh_data.get("controlling_agency", "UN"),
            association_code=unh_data.get("association_code"),
            content=parsed_content,
            unh_segment=unh_segment,
            unt_segment=unt_segment,
            segment_count=declared_count,
            actual_segment_count=expected_count,
            errors=[e for e in unh_errors + unt_errors if e.severity == ErrorSeverity.ERROR],
        )

    # =========================================================================
    # Segment Parsing Helpers
    # =========================================================================

    def _parse_unb_segment(
        self, segment: RawSegment
    ) -> tuple[dict[str, str | None], list[ParseError]]:
        """
        Parse UNB (Interchange Header) segment.

        UNB structure:
            UNB+S001+S002+S003+S004+0020+S005+0026+0029+0031+0032+0035'
                │    │    │    │    │    │    │    │    │    │    └─ Test indicator
                │    │    │    │    │    │    │    │    │    └─ Agreement ID
                │    │    │    │    │    │    │    │    └─ ACK request
                │    │    │    │    │    │    │    └─ Processing priority
                │    │    │    │    │    │    └─ Application reference
                │    │    │    │    │    └─ S005: Recipient reference (rarely used)
                │    │    │    │    └─ 0020: Control reference
                │    │    │    └─ S004: Date/time (YYMMDD:HHMM or CCYYMMDD:HHMM)
                │    │    └─ S003: Recipient (ID:qualifier)
                │    └─ S002: Sender (ID:qualifier)
                └─ S001: Syntax identifier (UNOA:3)

        Returns:
            Tuple of (parsed_data_dict, errors_list)
        """
        errors: list[ParseError] = []
        data: dict[str, str | None] = {}

        elements = segment.elements

        # S001 - Syntax identifier (required)
        if len(elements) >= 1:
            s001 = elements[0]
            data["syntax_identifier"] = s001.get_component(1) or "UNOA"
            data["syntax_version"] = s001.get_component(2) or "3"
        else:
            errors.append(
                ParseError(
                    code="UNB01",
                    message="Missing S001 (syntax identifier) in UNB",
                    category=ErrorCategory.ENVELOPE,
                    severity=ErrorSeverity.ERROR,
                    position=segment.position,
                    segment_tag="UNB",
                    element_position=1,
                )
            )

        # S002 - Interchange sender (required)
        if len(elements) >= 2:
            s002 = elements[1]
            data["sender_id"] = s002.get_component(1) or ""
            data["sender_qualifier"] = s002.get_component(2)
        else:
            errors.append(
                ParseError(
                    code="UNB02",
                    message="Missing S002 (sender) in UNB",
                    category=ErrorCategory.ENVELOPE,
                    severity=ErrorSeverity.ERROR,
                    position=segment.position,
                    segment_tag="UNB",
                    element_position=2,
                )
            )

        # S003 - Interchange recipient (required)
        if len(elements) >= 3:
            s003 = elements[2]
            data["recipient_id"] = s003.get_component(1) or ""
            data["recipient_qualifier"] = s003.get_component(2)
        else:
            errors.append(
                ParseError(
                    code="UNB03",
                    message="Missing S003 (recipient) in UNB",
                    category=ErrorCategory.ENVELOPE,
                    severity=ErrorSeverity.ERROR,
                    position=segment.position,
                    segment_tag="UNB",
                    element_position=3,
                )
            )

        # S004 - Date/time of preparation (required)
        if len(elements) >= 4:
            s004 = elements[3]
            data["date"] = s004.get_component(1) or ""
            data["time"] = s004.get_component(2) or ""
        else:
            errors.append(
                ParseError(
                    code="UNB04",
                    message="Missing S004 (date/time) in UNB",
                    category=ErrorCategory.ENVELOPE,
                    severity=ErrorSeverity.ERROR,
                    position=segment.position,
                    segment_tag="UNB",
                    element_position=4,
                )
            )

        # 0020 - Interchange control reference (required)
        if len(elements) >= 5:
            data["control_reference"] = elements[4].get_simple_value() or ""
        else:
            errors.append(
                ParseError(
                    code="UNB05",
                    message="Missing interchange control reference (0020) in UNB",
                    category=ErrorCategory.ENVELOPE,
                    severity=ErrorSeverity.ERROR,
                    position=segment.position,
                    segment_tag="UNB",
                    element_position=5,
                )
            )

        # S005 - Recipient reference (optional, rarely used)
        if len(elements) >= 6:
            s005 = elements[5]
            data["recipient_reference"] = s005.get_component(1)

        # 0026 - Application reference (optional)
        if len(elements) >= 7:
            data["application_reference"] = elements[6].get_simple_value()

        # 0029 - Processing priority code (optional)
        if len(elements) >= 8:
            data["processing_priority"] = elements[7].get_simple_value()

        # 0031 - Acknowledgment request (optional)
        if len(elements) >= 9:
            data["ack_request"] = elements[8].get_simple_value()

        # 0032 - Communications agreement ID (optional)
        if len(elements) >= 10:
            data["agreement_id"] = elements[9].get_simple_value()

        # 0035 - Test indicator (optional)
        if len(elements) >= 11:
            data["test_indicator"] = elements[10].get_simple_value()

        return data, errors

    def _parse_unz_segment(
        self,
        segment: RawSegment,
        expected_reference: str,
        expected_count: int,
    ) -> tuple[int | None, list[ParseError]]:
        """
        Parse UNZ (Interchange Trailer) segment.

        UNZ structure:
            UNZ+0036+0020'
                │    └─ 0020: Control reference (must match UNB)
                └─ 0036: Interchange control count (messages or groups)

        Returns:
            Tuple of (declared_count, errors_list)
        """
        errors: list[ParseError] = []
        declared_count: int | None = None

        elements = segment.elements

        # 0036 - Interchange control count
        if len(elements) >= 1:
            count_str = elements[0].get_simple_value()
            if count_str:
                try:
                    declared_count = int(count_str)
                    if declared_count != expected_count:
                        errors.append(
                            ParseError(
                                code="UNZ01",
                                message=f"UNZ count mismatch: declared {declared_count}, actual {expected_count}",
                                category=ErrorCategory.ENVELOPE,
                                severity=ErrorSeverity.ERROR,
                                position=segment.position,
                                segment_tag="UNZ",
                                element_position=1,
                                interchange_reference=expected_reference,
                                expected=str(expected_count),
                                actual=str(declared_count),
                            )
                        )
                except ValueError:
                    errors.append(
                        ParseError(
                            code="UNZ02",
                            message=f"Invalid UNZ count: {count_str}",
                            category=ErrorCategory.ENVELOPE,
                            severity=ErrorSeverity.ERROR,
                            position=segment.position,
                            segment_tag="UNZ",
                            element_position=1,
                        )
                    )
        else:
            errors.append(
                ParseError(
                    code="UNZ03",
                    message="Missing interchange control count in UNZ",
                    category=ErrorCategory.ENVELOPE,
                    severity=ErrorSeverity.ERROR,
                    position=segment.position,
                    segment_tag="UNZ",
                    element_position=1,
                )
            )

        # 0020 - Interchange control reference
        if len(elements) >= 2:
            ref = elements[1].get_simple_value()
            if ref and ref != expected_reference:
                errors.append(
                    ParseError(
                        code="UNZ04",
                        message=f"UNZ control reference mismatch: expected {expected_reference}, found {ref}",
                        category=ErrorCategory.ENVELOPE,
                        severity=ErrorSeverity.ERROR,
                        position=segment.position,
                        segment_tag="UNZ",
                        element_position=2,
                        interchange_reference=expected_reference,
                        expected=expected_reference,
                        actual=ref,
                    )
                )
        else:
            errors.append(
                ParseError(
                    code="UNZ05",
                    message="Missing interchange control reference in UNZ",
                    category=ErrorCategory.ENVELOPE,
                    severity=ErrorSeverity.ERROR,
                    position=segment.position,
                    segment_tag="UNZ",
                    element_position=2,
                )
            )

        return declared_count, errors

    def _parse_ung_segment(
        self, segment: RawSegment
    ) -> tuple[dict[str, str | None], list[ParseError]]:
        """
        Parse UNG (Functional Group Header) segment.

        UNG structure:
            UNG+0038+S006+S007+S004+0048+0051+S008'
                │    │    │    │    │    │    └─ S008: Message version (version:release)
                │    │    │    │    │    └─ 0051: Controlling agency
                │    │    │    │    └─ 0048: Group reference number
                │    │    │    └─ S004: Date/time
                │    │    └─ S007: Application recipient
                │    └─ S006: Application sender
                └─ 0038: Message group identification

        Returns:
            Tuple of (parsed_data_dict, errors_list)
        """
        errors: list[ParseError] = []
        data: dict[str, str | None] = {}

        elements = segment.elements

        # 0038 - Message group identification
        if len(elements) >= 1:
            data["message_type"] = elements[0].get_simple_value() or ""
        else:
            errors.append(
                ParseError(
                    code="UNG01",
                    message="Missing message group identification in UNG",
                    category=ErrorCategory.ENVELOPE,
                    severity=ErrorSeverity.ERROR,
                    position=segment.position,
                    segment_tag="UNG",
                    element_position=1,
                )
            )

        # S006 - Application sender's identification
        if len(elements) >= 2:
            s006 = elements[1]
            data["sender_id"] = s006.get_component(1) or ""
        else:
            errors.append(
                ParseError(
                    code="UNG02",
                    message="Missing application sender in UNG",
                    category=ErrorCategory.ENVELOPE,
                    severity=ErrorSeverity.ERROR,
                    position=segment.position,
                    segment_tag="UNG",
                    element_position=2,
                )
            )

        # S007 - Application recipient's identification
        if len(elements) >= 3:
            s007 = elements[2]
            data["recipient_id"] = s007.get_component(1) or ""
        else:
            errors.append(
                ParseError(
                    code="UNG03",
                    message="Missing application recipient in UNG",
                    category=ErrorCategory.ENVELOPE,
                    severity=ErrorSeverity.ERROR,
                    position=segment.position,
                    segment_tag="UNG",
                    element_position=3,
                )
            )

        # S004 - Date and time of preparation
        if len(elements) >= 4:
            s004 = elements[3]
            data["date"] = s004.get_component(1)
            data["time"] = s004.get_component(2)

        # 0048 - Group reference number
        if len(elements) >= 5:
            data["reference_number"] = elements[4].get_simple_value() or ""
        else:
            errors.append(
                ParseError(
                    code="UNG04",
                    message="Missing group reference number in UNG",
                    category=ErrorCategory.ENVELOPE,
                    severity=ErrorSeverity.ERROR,
                    position=segment.position,
                    segment_tag="UNG",
                    element_position=5,
                )
            )

        # 0051 - Controlling agency
        if len(elements) >= 6:
            data["controlling_agency"] = elements[5].get_simple_value() or "UN"

        # S008 - Message version
        if len(elements) >= 7:
            s008 = elements[6]
            data["message_version"] = s008.get_component(1)
            data["message_release"] = s008.get_component(2)

        return data, errors

    def _parse_une_segment(
        self,
        segment: RawSegment,
        expected_reference: str,
        expected_count: int,
    ) -> tuple[int | None, list[ParseError]]:
        """
        Parse UNE (Functional Group Trailer) segment.

        UNE structure:
            UNE+0060+0048'
                │    └─ 0048: Group reference (must match UNG)
                └─ 0060: Number of messages

        Returns:
            Tuple of (declared_count, errors_list)
        """
        errors: list[ParseError] = []
        declared_count: int | None = None

        elements = segment.elements

        # 0060 - Number of messages
        if len(elements) >= 1:
            count_str = elements[0].get_simple_value()
            if count_str:
                try:
                    declared_count = int(count_str)
                    if declared_count != expected_count:
                        errors.append(
                            ParseError(
                                code="UNE01",
                                message=f"UNE message count mismatch: declared {declared_count}, actual {expected_count}",
                                category=ErrorCategory.ENVELOPE,
                                severity=ErrorSeverity.ERROR,
                                position=segment.position,
                                segment_tag="UNE",
                                element_position=1,
                                group_reference=expected_reference,
                                expected=str(expected_count),
                                actual=str(declared_count),
                            )
                        )
                except ValueError:
                    errors.append(
                        ParseError(
                            code="UNE02",
                            message=f"Invalid UNE count: {count_str}",
                            category=ErrorCategory.ENVELOPE,
                            severity=ErrorSeverity.ERROR,
                            position=segment.position,
                            segment_tag="UNE",
                            element_position=1,
                        )
                    )
        else:
            errors.append(
                ParseError(
                    code="UNE03",
                    message="Missing message count in UNE",
                    category=ErrorCategory.ENVELOPE,
                    severity=ErrorSeverity.ERROR,
                    position=segment.position,
                    segment_tag="UNE",
                    element_position=1,
                )
            )

        # 0048 - Group reference number
        if len(elements) >= 2:
            ref = elements[1].get_simple_value()
            if ref and ref != expected_reference:
                errors.append(
                    ParseError(
                        code="UNE04",
                        message=f"UNE group reference mismatch: expected {expected_reference}, found {ref}",
                        category=ErrorCategory.ENVELOPE,
                        severity=ErrorSeverity.ERROR,
                        position=segment.position,
                        segment_tag="UNE",
                        element_position=2,
                        group_reference=expected_reference,
                        expected=expected_reference,
                        actual=ref,
                    )
                )
        else:
            errors.append(
                ParseError(
                    code="UNE05",
                    message="Missing group reference in UNE",
                    category=ErrorCategory.ENVELOPE,
                    severity=ErrorSeverity.ERROR,
                    position=segment.position,
                    segment_tag="UNE",
                    element_position=2,
                )
            )

        return declared_count, errors

    def _parse_unh_segment(
        self, segment: RawSegment
    ) -> tuple[dict[str, str | None], list[ParseError]]:
        """
        Parse UNH (Message Header) segment.

        UNH structure:
            UNH+0062+S009+0068+S010+S016+S017+S018'
                │    │    │    │    │    │    └─ S018 (rarely used)
                │    │    │    │    │    └─ S017 (rarely used)
                │    │    │    │    └─ S016 (rarely used)
                │    │    │    └─ S010: Status of transfer (optional)
                │    │    └─ 0068: Common access reference (optional)
                │    └─ S009: Message identifier (type:version:release:agency[:code])
                └─ 0062: Message reference number

        S009 structure:
            type:version:release:agency:association_code
            e.g., INVOIC:D:23A:UN:EAN008

        Returns:
            Tuple of (parsed_data_dict, errors_list)
        """
        errors: list[ParseError] = []
        data: dict[str, str | None] = {}

        elements = segment.elements

        # 0062 - Message reference number
        if len(elements) >= 1:
            data["reference_number"] = elements[0].get_simple_value() or ""
        else:
            errors.append(
                ParseError(
                    code="UNH01",
                    message="Missing message reference number in UNH",
                    category=ErrorCategory.ENVELOPE,
                    severity=ErrorSeverity.ERROR,
                    position=segment.position,
                    segment_tag="UNH",
                    element_position=1,
                )
            )

        # S009 - Message identifier
        if len(elements) >= 2:
            s009 = elements[1]
            data["message_type"] = s009.get_component(1) or ""  # 0065
            data["version"] = s009.get_component(2) or ""  # 0052
            data["release"] = s009.get_component(3) or ""  # 0054
            data["controlling_agency"] = s009.get_component(4) or "UN"  # 0051
            data["association_code"] = s009.get_component(5)  # 0057 (optional)

            # Validate required S009 components
            if not data.get("message_type"):
                errors.append(
                    ParseError(
                        code="UNH02",
                        message="Missing message type in S009",
                        category=ErrorCategory.ENVELOPE,
                        severity=ErrorSeverity.ERROR,
                        position=segment.position,
                        segment_tag="UNH",
                        element_position=2,
                        component_position=1,
                    )
                )
            if not data.get("version"):
                errors.append(
                    ParseError(
                        code="UNH03",
                        message="Missing version in S009",
                        category=ErrorCategory.ENVELOPE,
                        severity=ErrorSeverity.ERROR,
                        position=segment.position,
                        segment_tag="UNH",
                        element_position=2,
                        component_position=2,
                    )
                )
            if not data.get("release"):
                errors.append(
                    ParseError(
                        code="UNH04",
                        message="Missing release in S009",
                        category=ErrorCategory.ENVELOPE,
                        severity=ErrorSeverity.ERROR,
                        position=segment.position,
                        segment_tag="UNH",
                        element_position=2,
                        component_position=3,
                    )
                )
        else:
            errors.append(
                ParseError(
                    code="UNH05",
                    message="Missing S009 (message identifier) in UNH",
                    category=ErrorCategory.ENVELOPE,
                    severity=ErrorSeverity.ERROR,
                    position=segment.position,
                    segment_tag="UNH",
                    element_position=2,
                )
            )

        # 0068 - Common access reference (optional)
        if len(elements) >= 3:
            data["common_access_reference"] = elements[2].get_simple_value()

        return data, errors

    def _parse_unt_segment(
        self,
        segment: RawSegment,
        expected_reference: str,
        expected_count: int,
    ) -> tuple[int | None, list[ParseError]]:
        """
        Parse UNT (Message Trailer) segment.

        UNT structure:
            UNT+0074+0062'
                │    └─ 0062: Message reference (must match UNH)
                └─ 0074: Number of segments in message

        Returns:
            Tuple of (declared_count, errors_list)
        """
        errors: list[ParseError] = []
        declared_count: int | None = None

        elements = segment.elements

        # 0074 - Number of segments in message
        if len(elements) >= 1:
            count_str = elements[0].get_simple_value()
            if count_str:
                try:
                    declared_count = int(count_str)
                    if declared_count != expected_count:
                        errors.append(
                            ParseError(
                                code="UNT01",
                                message=f"UNT segment count mismatch: declared {declared_count}, actual {expected_count}",
                                category=ErrorCategory.ENVELOPE,
                                severity=ErrorSeverity.ERROR,
                                position=segment.position,
                                segment_tag="UNT",
                                element_position=1,
                                message_reference=expected_reference,
                                expected=str(expected_count),
                                actual=str(declared_count),
                            )
                        )
                except ValueError:
                    errors.append(
                        ParseError(
                            code="UNT02",
                            message=f"Invalid UNT segment count: {count_str}",
                            category=ErrorCategory.ENVELOPE,
                            severity=ErrorSeverity.ERROR,
                            position=segment.position,
                            segment_tag="UNT",
                            element_position=1,
                        )
                    )
        else:
            errors.append(
                ParseError(
                    code="UNT03",
                    message="Missing segment count in UNT",
                    category=ErrorCategory.ENVELOPE,
                    severity=ErrorSeverity.ERROR,
                    position=segment.position,
                    segment_tag="UNT",
                    element_position=1,
                )
            )

        # 0062 - Message reference number
        if len(elements) >= 2:
            ref = elements[1].get_simple_value()
            if ref and ref != expected_reference:
                errors.append(
                    ParseError(
                        code="UNT04",
                        message=f"UNT message reference mismatch: expected {expected_reference}, found {ref}",
                        category=ErrorCategory.ENVELOPE,
                        severity=ErrorSeverity.ERROR,
                        position=segment.position,
                        segment_tag="UNT",
                        element_position=2,
                        message_reference=expected_reference,
                        expected=expected_reference,
                        actual=ref,
                    )
                )
        else:
            errors.append(
                ParseError(
                    code="UNT05",
                    message="Missing message reference in UNT",
                    category=ErrorCategory.ENVELOPE,
                    severity=ErrorSeverity.ERROR,
                    position=segment.position,
                    segment_tag="UNT",
                    element_position=2,
                )
            )

        return declared_count, errors

    # =========================================================================
    # Navigation Helpers
    # =========================================================================

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


def parse_envelope(tokenizer_result: TokenizerResult) -> ParseResult:
    """
    Convenience function to parse envelope structure.

    Args:
        tokenizer_result: Result from EdifactTokenizer

    Returns:
        ParseResult with interchange(s) and all errors
    """
    parser = EdifactEnvelopeParser()
    return parser.parse(tokenizer_result)
