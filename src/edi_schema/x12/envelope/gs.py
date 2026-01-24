"""
GS/GE Functional Group and ST/SE Transaction Set Envelope Definitions.

Unlike ISA which is fixed-width, GS/GE and ST/SE use standard
delimiter-separated parsing.
"""

from dataclasses import dataclass

from edi_schema.x12.ast import (
    ErrorCategory,
    ErrorSeverity,
    ParseError,
    SourcePosition,
)

# =============================================================================
# GS/GE Functional Group
# =============================================================================


@dataclass
class GSSegmentDef:
    """Definition of the GS (Functional Group Header) segment."""

    id: str = "GS"
    name: str = "Functional Group Header"
    element_count: int = 8

    # GS01: Functional Identifier Code (ID, 2 chars) - e.g., "PO", "IN", "HC"
    # GS02: Application Sender's Code (AN, 2-15 chars)
    # GS03: Application Receiver's Code (AN, 2-15 chars)
    # GS04: Date (DT, 8 chars) - CCYYMMDD
    # GS05: Time (TM, 4-8 chars) - HHMM or HHMMSS or HHMMSSDD
    # GS06: Group Control Number (N0, 1-9 chars)
    # GS07: Responsible Agency Code (ID, 1-2 chars) - usually "X"
    # GS08: Version/Release/Industry Identifier Code (AN, 1-12 chars)


@dataclass
class GESegmentDef:
    """Definition of the GE (Functional Group Trailer) segment."""

    id: str = "GE"
    name: str = "Functional Group Trailer"
    element_count: int = 2

    # GE01: Number of Transaction Sets Included (N0, 1-6 chars)
    # GE02: Group Control Number (N0, 1-9 chars) - must match GS06


# Singleton instances
GS_SEGMENT = GSSegmentDef()
GE_SEGMENT = GESegmentDef()


@dataclass
class ParsedGS:
    """Parsed GS segment data."""

    functional_id: str  # GS01
    sender_id: str  # GS02
    receiver_id: str  # GS03
    date: str  # GS04
    time: str  # GS05
    control_number: str  # GS06
    responsible_agency: str  # GS07
    version: str  # GS08
    errors: list[ParseError]


def parse_gs_segment(
    elements: list[str],
    position: SourcePosition | None = None,
) -> tuple[ParsedGS, list[ParseError]]:
    """
    Parse GS segment.

    Args:
        elements: List of element values (excluding segment tag)
        position: Source position for error reporting

    Returns:
        Tuple of (parsed GS data, list of errors)
    """
    errors: list[ParseError] = []
    pos = position or SourcePosition(0, 1, 1, 0)

    def get_element(index: int, name: str, required: bool = True) -> str:
        if index < len(elements):
            return elements[index]
        if required:
            errors.append(
                ParseError(
                    code=f"GS{index + 1:02d}",
                    message=f"Missing required element {name} (GS{index + 1:02d})",
                    category=ErrorCategory.ELEMENT,
                    severity=ErrorSeverity.ERROR,
                    position=pos,
                    segment_tag="GS",
                    element_position=index + 1,
                )
            )
        return ""

    parsed = ParsedGS(
        functional_id=get_element(0, "Functional Identifier Code"),
        sender_id=get_element(1, "Application Sender's Code"),
        receiver_id=get_element(2, "Application Receiver's Code"),
        date=get_element(3, "Date"),
        time=get_element(4, "Time"),
        control_number=get_element(5, "Group Control Number"),
        responsible_agency=get_element(6, "Responsible Agency Code"),
        version=get_element(7, "Version/Release/Industry ID"),
        errors=errors,
    )

    # Validate functional identifier code
    valid_functional_ids = {
        "AA",
        "AB",
        "AD",
        "AF",
        "AG",
        "AH",
        "AI",
        "AM",
        "AS",
        "AW",
        "AX",
        "AY",
        "BA",
        "BC",
        "BE",
        "BF",
        "BL",
        "BS",
        "CA",
        "CB",
        "CC",
        "CD",
        "CE",
        "CF",
        "CG",
        "CH",
        "CI",
        "CJ",
        "CK",
        "CM",
        "CN",
        "CO",
        "CP",
        "CQ",
        "CR",
        "CS",
        "D3",
        "D4",
        "D5",
        "DA",
        "DD",
        "DF",
        "DI",
        "DM",
        "DS",
        "DX",
        "E1",
        "EC",
        "ED",
        "EF",
        "EI",
        "ER",
        "ES",
        "EV",
        "EX",
        "FA",
        "FB",
        "FC",
        "FG",
        "FH",
        "FR",
        "FT",
        "GA",
        "GB",
        "GC",
        "GD",
        "GE",
        "GF",
        "GL",
        "GP",
        "GR",
        "GT",
        "HB",
        "HC",
        "HI",
        "HN",
        "HP",
        "HR",
        "HS",
        "IA",
        "IB",
        "IC",
        "ID",
        "IE",
        "IG",
        "II",
        "IJ",
        "IM",
        "IN",
        "IO",
        "IR",
        "IS",
        "JB",
        "KM",
        "LA",
        "LB",
        "LI",
        "LN",
        "LR",
        "LS",
        "LT",
        "MA",
        "MC",
        "MD",
        "ME",
        "MF",
        "MG",
        "MH",
        "MI",
        "MJ",
        "MK",
        "MM",
        "MN",
        "MO",
        "MP",
        "MQ",
        "MR",
        "MS",
        "MT",
        "MV",
        "MW",
        "MX",
        "MY",
        "NC",
        "NL",
        "NP",
        "NR",
        "NT",
        "OC",
        "OG",
        "OR",
        "OW",
        "PA",
        "PB",
        "PC",
        "PD",
        "PE",
        "PF",
        "PG",
        "PH",
        "PI",
        "PJ",
        "PK",
        "PL",
        "PM",
        "PN",
        "PO",
        "PP",
        "PQ",
        "PR",
        "PS",
        "PT",
        "PU",
        "PV",
        "PW",
        "QG",
        "QM",
        "QO",
        "RA",
        "RB",
        "RC",
        "RD",
        "RE",
        "RF",
        "RG",
        "RH",
        "RI",
        "RJ",
        "RK",
        "RL",
        "RM",
        "RN",
        "RO",
        "RP",
        "RQ",
        "RR",
        "RS",
        "RT",
        "RU",
        "RV",
        "RW",
        "RX",
        "RY",
        "RZ",
        "SA",
        "SB",
        "SC",
        "SD",
        "SE",
        "SG",
        "SH",
        "SI",
        "SJ",
        "SL",
        "SM",
        "SN",
        "SO",
        "SP",
        "SQ",
        "SR",
        "SS",
        "ST",
        "SU",
        "SV",
        "SW",
        "TA",
        "TB",
        "TD",
        "TF",
        "TI",
        "TM",
        "TN",
        "TO",
        "TP",
        "TR",
        "TS",
        "TT",
        "TU",
        "TX",
        "UA",
        "UB",
        "UC",
        "UD",
        "UI",
        "UP",
        "UW",
        "VA",
        "VB",
        "VC",
        "VD",
        "VE",
        "VH",
        "VI",
        "VS",
        "WA",
        "WB",
        "WG",
        "WI",
        "WL",
        "WR",
        "WT",
    }
    if parsed.functional_id and parsed.functional_id not in valid_functional_ids:
        errors.append(
            ParseError(
                code="GS10",
                message=f"Unknown Functional Identifier Code: {parsed.functional_id}",
                category=ErrorCategory.CODE,
                severity=ErrorSeverity.WARNING,
                position=pos,
                segment_tag="GS",
                element_position=1,
                actual=parsed.functional_id,
            )
        )

    # Validate responsible agency code
    if parsed.responsible_agency and parsed.responsible_agency not in ("T", "X"):
        errors.append(
            ParseError(
                code="GS11",
                message=f"Unknown Responsible Agency Code: {parsed.responsible_agency}",
                category=ErrorCategory.CODE,
                severity=ErrorSeverity.WARNING,
                position=pos,
                segment_tag="GS",
                element_position=7,
                expected="T or X",
                actual=parsed.responsible_agency,
            )
        )

    return parsed, errors


@dataclass
class ParsedGE:
    """Parsed GE segment data."""

    transaction_count: int  # GE01
    control_number: str  # GE02
    errors: list[ParseError]


def parse_ge_segment(
    elements: list[str],
    expected_control: str,
    expected_count: int,
    position: SourcePosition | None = None,
) -> tuple[ParsedGE, list[ParseError]]:
    """
    Parse GE segment and validate against GS.

    Args:
        elements: List of element values (excluding segment tag)
        expected_control: Control number from GS06 (must match)
        expected_count: Expected transaction set count
        position: Source position for error reporting

    Returns:
        Tuple of (parsed GE data, list of errors)
    """
    errors: list[ParseError] = []
    pos = position or SourcePosition(0, 1, 1, 0)

    # GE01: Number of transaction sets
    transaction_count = 0
    if len(elements) >= 1:
        try:
            transaction_count = int(elements[0])
        except ValueError:
            errors.append(
                ParseError(
                    code="GE01",
                    message=f"Invalid transaction count in GE01: {elements[0]}",
                    category=ErrorCategory.ELEMENT,
                    severity=ErrorSeverity.ERROR,
                    position=pos,
                    segment_tag="GE",
                    element_position=1,
                    actual=elements[0],
                )
            )
    else:
        errors.append(
            ParseError(
                code="GE02",
                message="Missing transaction count in GE01",
                category=ErrorCategory.ELEMENT,
                severity=ErrorSeverity.ERROR,
                position=pos,
                segment_tag="GE",
                element_position=1,
            )
        )

    # Validate transaction count
    if transaction_count != expected_count:
        errors.append(
            ParseError(
                code="GE03",
                message=f"Transaction count mismatch: GE01={transaction_count}, actual={expected_count}",
                category=ErrorCategory.ENVELOPE,
                severity=ErrorSeverity.ERROR,
                position=pos,
                segment_tag="GE",
                element_position=1,
                expected=str(expected_count),
                actual=str(transaction_count),
            )
        )

    # GE02: Control number (must match GS06)
    control_number = ""
    if len(elements) >= 2:
        control_number = elements[1]
    else:
        errors.append(
            ParseError(
                code="GE04",
                message="Missing control number in GE02",
                category=ErrorCategory.ELEMENT,
                severity=ErrorSeverity.ERROR,
                position=pos,
                segment_tag="GE",
                element_position=2,
            )
        )

    # Validate control number match
    if control_number != expected_control:
        errors.append(
            ParseError(
                code="GE05",
                message=f"Control number mismatch: GS06={expected_control}, GE02={control_number}",
                category=ErrorCategory.ENVELOPE,
                severity=ErrorSeverity.ERROR,
                position=pos,
                segment_tag="GE",
                element_position=2,
                expected=expected_control,
                actual=control_number,
            )
        )

    return ParsedGE(
        transaction_count=transaction_count,
        control_number=control_number,
        errors=errors,
    ), errors


# =============================================================================
# ST/SE Transaction Set
# =============================================================================


@dataclass
class STSegmentDef:
    """Definition of the ST (Transaction Set Header) segment."""

    id: str = "ST"
    name: str = "Transaction Set Header"
    element_count: int = 3  # ST03 is optional

    # ST01: Transaction Set Identifier Code (ID, 3 chars) - e.g., "850", "810", "837"
    # ST02: Transaction Set Control Number (AN, 4-9 chars)
    # ST03: Implementation Convention Reference (AN, 1-35 chars) - optional


@dataclass
class SESegmentDef:
    """Definition of the SE (Transaction Set Trailer) segment."""

    id: str = "SE"
    name: str = "Transaction Set Trailer"
    element_count: int = 2

    # SE01: Number of Included Segments (N0, 1-10 chars) - includes ST and SE
    # SE02: Transaction Set Control Number (AN, 4-9 chars) - must match ST02


# Singleton instances
ST_SEGMENT = STSegmentDef()
SE_SEGMENT = SESegmentDef()


@dataclass
class ParsedST:
    """Parsed ST segment data."""

    transaction_id: str  # ST01
    control_number: str  # ST02
    implementation_reference: str | None  # ST03
    errors: list[ParseError]


def parse_st_segment(
    elements: list[str],
    position: SourcePosition | None = None,
) -> tuple[ParsedST, list[ParseError]]:
    """
    Parse ST segment.

    Args:
        elements: List of element values (excluding segment tag)
        position: Source position for error reporting

    Returns:
        Tuple of (parsed ST data, list of errors)
    """
    errors: list[ParseError] = []
    pos = position or SourcePosition(0, 1, 1, 0)

    # ST01: Transaction Set Identifier Code (required)
    transaction_id = ""
    if len(elements) >= 1:
        transaction_id = elements[0]
        if len(transaction_id) != 3:
            errors.append(
                ParseError(
                    code="ST01",
                    message=f"Transaction Set ID must be 3 characters: {transaction_id}",
                    category=ErrorCategory.ELEMENT,
                    severity=ErrorSeverity.WARNING,
                    position=pos,
                    segment_tag="ST",
                    element_position=1,
                    actual=transaction_id,
                )
            )
    else:
        errors.append(
            ParseError(
                code="ST02",
                message="Missing Transaction Set Identifier Code (ST01)",
                category=ErrorCategory.ELEMENT,
                severity=ErrorSeverity.ERROR,
                position=pos,
                segment_tag="ST",
                element_position=1,
            )
        )

    # ST02: Transaction Set Control Number (required)
    control_number = ""
    if len(elements) >= 2:
        control_number = elements[1]
        if not (4 <= len(control_number) <= 9):
            errors.append(
                ParseError(
                    code="ST03",
                    message=f"Transaction Set Control Number must be 4-9 characters: {control_number}",
                    category=ErrorCategory.ELEMENT,
                    severity=ErrorSeverity.WARNING,
                    position=pos,
                    segment_tag="ST",
                    element_position=2,
                    actual=control_number,
                )
            )
    else:
        errors.append(
            ParseError(
                code="ST04",
                message="Missing Transaction Set Control Number (ST02)",
                category=ErrorCategory.ELEMENT,
                severity=ErrorSeverity.ERROR,
                position=pos,
                segment_tag="ST",
                element_position=2,
            )
        )

    # ST03: Implementation Convention Reference (optional)
    implementation_reference = None
    if len(elements) >= 3 and elements[2]:
        implementation_reference = elements[2]

    return ParsedST(
        transaction_id=transaction_id,
        control_number=control_number,
        implementation_reference=implementation_reference,
        errors=errors,
    ), errors


@dataclass
class ParsedSE:
    """Parsed SE segment data."""

    segment_count: int  # SE01
    control_number: str  # SE02
    errors: list[ParseError]


def parse_se_segment(
    elements: list[str],
    expected_control: str,
    expected_count: int,
    position: SourcePosition | None = None,
) -> tuple[ParsedSE, list[ParseError]]:
    """
    Parse SE segment and validate against ST.

    Args:
        elements: List of element values (excluding segment tag)
        expected_control: Control number from ST02 (must match)
        expected_count: Expected segment count (including ST and SE)
        position: Source position for error reporting

    Returns:
        Tuple of (parsed SE data, list of errors)
    """
    errors: list[ParseError] = []
    pos = position or SourcePosition(0, 1, 1, 0)

    # SE01: Number of included segments
    segment_count = 0
    if len(elements) >= 1:
        try:
            segment_count = int(elements[0])
        except ValueError:
            errors.append(
                ParseError(
                    code="SE01",
                    message=f"Invalid segment count in SE01: {elements[0]}",
                    category=ErrorCategory.ELEMENT,
                    severity=ErrorSeverity.ERROR,
                    position=pos,
                    segment_tag="SE",
                    element_position=1,
                    actual=elements[0],
                )
            )
    else:
        errors.append(
            ParseError(
                code="SE02",
                message="Missing segment count in SE01",
                category=ErrorCategory.ELEMENT,
                severity=ErrorSeverity.ERROR,
                position=pos,
                segment_tag="SE",
                element_position=1,
            )
        )

    # Validate segment count
    if segment_count != expected_count:
        errors.append(
            ParseError(
                code="SE03",
                message=f"Segment count mismatch: SE01={segment_count}, actual={expected_count}",
                category=ErrorCategory.ENVELOPE,
                severity=ErrorSeverity.ERROR,
                position=pos,
                segment_tag="SE",
                element_position=1,
                expected=str(expected_count),
                actual=str(segment_count),
            )
        )

    # SE02: Control number (must match ST02)
    control_number = ""
    if len(elements) >= 2:
        control_number = elements[1]
    else:
        errors.append(
            ParseError(
                code="SE04",
                message="Missing control number in SE02",
                category=ErrorCategory.ELEMENT,
                severity=ErrorSeverity.ERROR,
                position=pos,
                segment_tag="SE",
                element_position=2,
            )
        )

    # Validate control number match
    if control_number != expected_control:
        errors.append(
            ParseError(
                code="SE05",
                message=f"Control number mismatch: ST02={expected_control}, SE02={control_number}",
                category=ErrorCategory.ENVELOPE,
                severity=ErrorSeverity.ERROR,
                position=pos,
                segment_tag="SE",
                element_position=2,
                expected=expected_control,
                actual=control_number,
            )
        )

    return ParsedSE(
        segment_count=segment_count,
        control_number=control_number,
        errors=errors,
    ), errors
