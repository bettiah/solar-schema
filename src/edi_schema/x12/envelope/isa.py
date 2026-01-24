"""
ISA/IEA Interchange Envelope Segment Definitions.

The ISA segment is unique in X12 - it's EXACTLY 106 characters with
fixed-width fields. The delimiters for the entire document are determined
by positions within ISA:
- Position 3: Element separator (character after "ISA")
- Position 82: Repetition separator (ISA11, in version 5010+)
- Position 104: Component separator (ISA16)
- Position 105: Segment terminator (character after ISA16)
"""

from dataclasses import dataclass
from typing import NamedTuple

from edi_schema.x12.ast import (
    Delimiters,
    ErrorCategory,
    ErrorSeverity,
    ParseError,
    SourcePosition,
)


class ISAElementPosition(NamedTuple):
    """Position and length of an ISA element (fixed-width)."""

    start: int  # 0-indexed start position
    length: int  # Fixed length
    name: str  # Element name
    element_id: str  # Element reference (e.g., "I01")


# ISA segment element positions (0-indexed, fixed-width)
# Total ISA length: 106 characters (including segment terminator)
ISA_ELEMENT_POSITIONS = [
    ISAElementPosition(0, 3, "Segment ID", "ISA"),  # "ISA"
    # Position 3 is the element separator
    ISAElementPosition(4, 2, "Authorization Information Qualifier", "I01"),  # ISA01
    ISAElementPosition(7, 10, "Authorization Information", "I02"),  # ISA02
    ISAElementPosition(18, 2, "Security Information Qualifier", "I03"),  # ISA03
    ISAElementPosition(21, 10, "Security Information", "I04"),  # ISA04
    ISAElementPosition(32, 2, "Interchange ID Qualifier", "I05"),  # ISA05
    ISAElementPosition(35, 15, "Interchange Sender ID", "I06"),  # ISA06
    ISAElementPosition(51, 2, "Interchange ID Qualifier", "I07"),  # ISA07
    ISAElementPosition(54, 15, "Interchange Receiver ID", "I08"),  # ISA08
    ISAElementPosition(70, 6, "Interchange Date", "I09"),  # ISA09 YYMMDD
    ISAElementPosition(77, 4, "Interchange Time", "I10"),  # ISA10 HHMM
    ISAElementPosition(82, 1, "Repetition Separator", "I11"),  # ISA11
    ISAElementPosition(84, 5, "Interchange Control Version Number", "I12"),  # ISA12
    ISAElementPosition(90, 9, "Interchange Control Number", "I13"),  # ISA13
    ISAElementPosition(100, 1, "Acknowledgment Requested", "I14"),  # ISA14
    ISAElementPosition(102, 1, "Usage Indicator", "I15"),  # ISA15
    ISAElementPosition(104, 1, "Component Element Separator", "I16"),  # ISA16
    # Position 105 is the segment terminator
]

# ISA must be exactly this many characters (excluding line breaks)
ISA_FIXED_LENGTH = 106


@dataclass
class ISASegmentDef:
    """Definition of the ISA segment structure."""

    id: str = "ISA"
    name: str = "Interchange Control Header"
    element_count: int = 16
    fixed_length: int = ISA_FIXED_LENGTH

    def get_element_position(self, element_num: int) -> ISAElementPosition | None:
        """Get position info for ISA element (1-indexed)."""
        # Element 0 is segment ID, 1-16 are actual elements
        if 1 <= element_num <= 16:
            return ISA_ELEMENT_POSITIONS[element_num]
        return None


@dataclass
class IEASegmentDef:
    """Definition of the IEA segment structure."""

    id: str = "IEA"
    name: str = "Interchange Control Trailer"
    element_count: int = 2

    # IEA01: Number of Included Functional Groups (N0, 1-5 chars)
    # IEA02: Interchange Control Number (N0, 9 chars, must match ISA13)


# Singleton instances
ISA_SEGMENT = ISASegmentDef()
IEA_SEGMENT = IEASegmentDef()


@dataclass
class ParsedISA:
    """Parsed ISA segment data."""

    auth_qualifier: str  # ISA01
    auth_info: str  # ISA02
    security_qualifier: str  # ISA03
    security_info: str  # ISA04
    sender_qualifier: str  # ISA05
    sender_id: str  # ISA06
    receiver_qualifier: str  # ISA07
    receiver_id: str  # ISA08
    date: str  # ISA09
    time: str  # ISA10
    repetition_separator: str  # ISA11
    version: str  # ISA12
    control_number: str  # ISA13
    ack_requested: str  # ISA14
    usage_indicator: str  # ISA15
    component_separator: str  # ISA16
    delimiters: Delimiters
    errors: list[ParseError]


def parse_isa_segment(
    content: str,
    position: SourcePosition | None = None,
) -> tuple[ParsedISA | None, list[ParseError]]:
    """
    Parse ISA segment using fixed-width positions.

    The ISA segment is special - it's exactly 106 characters with fixed-width
    fields. We use positional parsing, not delimiter-based parsing.

    Args:
        content: Raw content starting with "ISA"
        position: Source position for error reporting

    Returns:
        Tuple of (parsed ISA data, list of errors)
        Returns None for parsed data only if fatal error occurs
    """
    errors: list[ParseError] = []
    pos = position or SourcePosition(0, 1, 1, 0)

    # Validate starts with ISA
    if not content.startswith("ISA"):
        errors.append(
            ParseError(
                code="ISA01",
                message="Document must start with ISA segment",
                category=ErrorCategory.STRUCTURAL,
                severity=ErrorSeverity.FATAL,
                position=pos,
                expected="ISA",
                actual=content[:3] if len(content) >= 3 else content,
            )
        )
        return None, errors

    # Extract element separator (position 3)
    if len(content) < 4:
        errors.append(
            ParseError(
                code="ISA02",
                message="ISA segment too short to determine element separator",
                category=ErrorCategory.STRUCTURAL,
                severity=ErrorSeverity.FATAL,
                position=pos,
            )
        )
        return None, errors

    element_sep = content[3]

    # Find segment terminator - it's at position 105 in a properly formatted ISA
    # But we need to handle cases where it might be different
    if len(content) < 106:
        errors.append(
            ParseError(
                code="ISA03",
                message=f"ISA segment too short: expected 106 characters, got {len(content)}",
                category=ErrorCategory.STRUCTURAL,
                severity=ErrorSeverity.ERROR,
                position=pos,
                expected="106",
                actual=str(len(content)),
            )
        )
        # Try to continue with what we have

    # Extract delimiters
    segment_term = content[105] if len(content) > 105 else "~"
    component_sep = content[104] if len(content) > 104 else ":"
    repetition_sep = content[82] if len(content) > 82 else "^"

    delimiters = Delimiters(
        element=element_sep,
        component=component_sep,
        repetition=repetition_sep,
        segment=segment_term,
    )

    # Extract fixed-width fields
    def extract_field(pos_info: ISAElementPosition) -> str:
        start = pos_info.start
        end = start + pos_info.length
        if len(content) >= end:
            return content[start:end]
        return ""

    # Parse all ISA elements
    try:
        parsed = ParsedISA(
            auth_qualifier=extract_field(ISA_ELEMENT_POSITIONS[1]),
            auth_info=extract_field(ISA_ELEMENT_POSITIONS[2]),
            security_qualifier=extract_field(ISA_ELEMENT_POSITIONS[3]),
            security_info=extract_field(ISA_ELEMENT_POSITIONS[4]),
            sender_qualifier=extract_field(ISA_ELEMENT_POSITIONS[5]),
            sender_id=extract_field(ISA_ELEMENT_POSITIONS[6]),
            receiver_qualifier=extract_field(ISA_ELEMENT_POSITIONS[7]),
            receiver_id=extract_field(ISA_ELEMENT_POSITIONS[8]),
            date=extract_field(ISA_ELEMENT_POSITIONS[9]),
            time=extract_field(ISA_ELEMENT_POSITIONS[10]),
            repetition_separator=extract_field(ISA_ELEMENT_POSITIONS[11]),
            version=extract_field(ISA_ELEMENT_POSITIONS[12]),
            control_number=extract_field(ISA_ELEMENT_POSITIONS[13]),
            ack_requested=extract_field(ISA_ELEMENT_POSITIONS[14]),
            usage_indicator=extract_field(ISA_ELEMENT_POSITIONS[15]),
            component_separator=extract_field(ISA_ELEMENT_POSITIONS[16]),
            delimiters=delimiters,
            errors=errors,
        )
    except (IndexError, ValueError) as e:
        errors.append(
            ParseError(
                code="ISA04",
                message=f"Error parsing ISA segment: {e}",
                category=ErrorCategory.STRUCTURAL,
                severity=ErrorSeverity.FATAL,
                position=pos,
            )
        )
        return None, errors

    # Validate ISA fields
    _validate_isa_fields(parsed, errors, pos)

    return parsed, errors


def _validate_isa_fields(
    isa: ParsedISA,
    errors: list[ParseError],
    pos: SourcePosition,
) -> None:
    """Validate ISA field values."""
    # ISA01 must be 00 or valid auth qualifier
    if isa.auth_qualifier not in ("00", "01", "02", "03", "04", "05", "06"):
        errors.append(
            ParseError(
                code="ISA05",
                message=f"Invalid Authorization Information Qualifier: {isa.auth_qualifier}",
                category=ErrorCategory.CODE,
                severity=ErrorSeverity.WARNING,
                position=pos,
                segment_tag="ISA",
                element_position=1,
                actual=isa.auth_qualifier,
            )
        )

    # ISA03 must be 00 or valid security qualifier
    if isa.security_qualifier not in ("00", "01"):
        errors.append(
            ParseError(
                code="ISA06",
                message=f"Invalid Security Information Qualifier: {isa.security_qualifier}",
                category=ErrorCategory.CODE,
                severity=ErrorSeverity.WARNING,
                position=pos,
                segment_tag="ISA",
                element_position=3,
                actual=isa.security_qualifier,
            )
        )

    # ISA15 must be P, T, or I
    if isa.usage_indicator not in ("P", "T", "I"):
        errors.append(
            ParseError(
                code="ISA07",
                message=f"Invalid Usage Indicator: {isa.usage_indicator}. Expected P, T, or I",
                category=ErrorCategory.CODE,
                severity=ErrorSeverity.ERROR,
                position=pos,
                segment_tag="ISA",
                element_position=15,
                expected="P, T, or I",
                actual=isa.usage_indicator,
            )
        )

    # ISA14 must be 0 or 1
    if isa.ack_requested not in ("0", "1"):
        errors.append(
            ParseError(
                code="ISA08",
                message=f"Invalid Acknowledgment Requested: {isa.ack_requested}. Expected 0 or 1",
                category=ErrorCategory.CODE,
                severity=ErrorSeverity.WARNING,
                position=pos,
                segment_tag="ISA",
                element_position=14,
                expected="0 or 1",
                actual=isa.ack_requested,
            )
        )


@dataclass
class ParsedIEA:
    """Parsed IEA segment data."""

    group_count: int  # IEA01
    control_number: str  # IEA02
    errors: list[ParseError]


def parse_iea_segment(
    elements: list[str],
    expected_control: str,
    expected_count: int,
    position: SourcePosition | None = None,
) -> tuple[ParsedIEA, list[ParseError]]:
    """
    Parse IEA segment and validate against ISA.

    Args:
        elements: List of element values (excluding segment tag)
        expected_control: Control number from ISA13 (must match)
        expected_count: Expected functional group count
        position: Source position for error reporting

    Returns:
        Tuple of (parsed IEA data, list of errors)
    """
    errors: list[ParseError] = []
    pos = position or SourcePosition(0, 1, 1, 0)

    # IEA01: Number of functional groups
    group_count = 0
    if len(elements) >= 1:
        try:
            group_count = int(elements[0])
        except ValueError:
            errors.append(
                ParseError(
                    code="IEA01",
                    message=f"Invalid group count in IEA01: {elements[0]}",
                    category=ErrorCategory.ELEMENT,
                    severity=ErrorSeverity.ERROR,
                    position=pos,
                    segment_tag="IEA",
                    element_position=1,
                    actual=elements[0],
                )
            )
    else:
        errors.append(
            ParseError(
                code="IEA02",
                message="Missing group count in IEA01",
                category=ErrorCategory.ELEMENT,
                severity=ErrorSeverity.ERROR,
                position=pos,
                segment_tag="IEA",
                element_position=1,
            )
        )

    # Validate group count
    if group_count != expected_count:
        errors.append(
            ParseError(
                code="IEA03",
                message=f"Group count mismatch: IEA01={group_count}, actual={expected_count}",
                category=ErrorCategory.ENVELOPE,
                severity=ErrorSeverity.ERROR,
                position=pos,
                segment_tag="IEA",
                element_position=1,
                expected=str(expected_count),
                actual=str(group_count),
            )
        )

    # IEA02: Control number (must match ISA13)
    control_number = ""
    if len(elements) >= 2:
        control_number = elements[1]
    else:
        errors.append(
            ParseError(
                code="IEA04",
                message="Missing control number in IEA02",
                category=ErrorCategory.ELEMENT,
                severity=ErrorSeverity.ERROR,
                position=pos,
                segment_tag="IEA",
                element_position=2,
            )
        )

    # Validate control number match
    if control_number != expected_control:
        errors.append(
            ParseError(
                code="IEA05",
                message=f"Control number mismatch: ISA13={expected_control}, IEA02={control_number}",
                category=ErrorCategory.ENVELOPE,
                severity=ErrorSeverity.ERROR,
                position=pos,
                segment_tag="IEA",
                element_position=2,
                expected=expected_control,
                actual=control_number,
            )
        )

    return ParsedIEA(
        group_count=group_count,
        control_number=control_number,
        errors=errors,
    ), errors
