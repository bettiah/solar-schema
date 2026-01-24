"""
997 Functional Acknowledgment Generator.

Generates 997 Functional Acknowledgment transaction sets from validation results.

997 Structure:
    ST*997*{control}~
    AK1*{func_id}*{group_control}~
      AK2*{txn_id}*{txn_control}~          # For each transaction
        AK3*{seg_id}*{pos}*{loop}*{err}~   # For each segment error
          AK4*{elem_pos}*{elem_ref}*{err}~ # For each element error
        AK5*{status}*{err1}*...~           # Transaction status
    AK9*{status}*{inc}*{rcvd}*{accp}~      # Group summary
    SE*{count}*{control}~

Error Codes:
    AK3 Segment Error Codes (element 4):
        1 = Unrecognized segment ID
        2 = Unexpected segment
        3 = Mandatory segment missing
        4 = Loop occurs over maximum times
        5 = Segment exceeds maximum use
        6 = Segment not in defined transaction set
        7 = Segment not in proper sequence
        8 = Segment has data element errors

    AK4 Element Error Codes (element 3):
        1 = Mandatory data element missing
        2 = Conditional required data element missing
        3 = Too many data elements
        4 = Data element too short
        5 = Data element too long
        6 = Invalid character in data element
        7 = Invalid code value
        8 = Invalid date
        9 = Invalid time
        10 = Exclusion condition violated

    AK5 Transaction Status Codes (element 1):
        A = Accepted
        E = Accepted But Errors Were Noted
        M = Rejected, Message Authentication Code (MAC) Failed
        P = Partially Accepted, At Least One Transaction Set Was Rejected
        R = Rejected
        W = Rejected, Assurance Failed Validity Tests
        X = Rejected, Content After Decryption Could Not Be Analyzed

    AK9 Group Status Codes (element 1):
        A = Accepted
        E = Accepted, But Errors Were Noted
        M = Rejected, Message Authentication Code (MAC) Failed
        P = Partially Accepted, At Least One Transaction Set Was Rejected
        R = Rejected
        W = Rejected, Assurance Failed Validity Tests
        X = Rejected, Content After Decryption Could Not Be Analyzed
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from edi_schema.x12.ast import (
    ErrorCategory,
    ErrorSeverity,
    FunctionalGroupInstance,
    ParseError,
    TransactionSetInstance,
)

if TYPE_CHECKING:
    from edi_schema.x12.validator.core import ValidationResult


@dataclass
class AK1Data:
    """AK1 - Functional Group Response Header."""

    functional_id: str  # AK101 - Functional identifier code (e.g., "PO", "HC")
    group_control: str  # AK102 - Group control number


@dataclass
class AK2Data:
    """AK2 - Transaction Set Response Header."""

    transaction_id: str  # AK201 - Transaction set identifier code
    control_number: str  # AK202 - Transaction set control number
    implementation_reference: str | None = None  # AK203 (optional)


@dataclass
class AK3Data:
    """AK3 - Data Segment Note."""

    segment_id: str  # AK301 - Segment ID code
    segment_position: int  # AK302 - Segment position in transaction set
    loop_identifier: str | None = None  # AK303 - Bound loop identifier code
    error_code: str | None = None  # AK304 - Segment syntax error code


@dataclass
class AK4Data:
    """AK4 - Data Element Note."""

    element_position: int  # AK401 - Position in segment
    error_code: str  # AK403 - Data element syntax error code
    element_reference: str | None = None  # AK402 - Data element reference number
    copy_of_bad_element: str | None = None  # AK404 - Copy of bad data element


@dataclass
class AK5Data:
    """AK5 - Transaction Set Response Trailer."""

    status_code: str  # AK501 - Transaction set acknowledgment code (A/E/R)
    error_codes: list[str] = field(default_factory=list)  # AK502-AK506 (up to 5)


@dataclass
class AK9Data:
    """AK9 - Functional Group Response Trailer."""

    status_code: str  # AK901 - Functional group acknowledge code (A/E/R)
    included_count: int  # AK902 - Number of transaction sets included
    received_count: int  # AK903 - Number of received transaction sets
    accepted_count: int  # AK904 - Number of accepted transaction sets
    error_codes: list[str] = field(default_factory=list)  # AK905-AK909 (up to 5)


class FA997Generator:
    """
    Generates 997 Functional Acknowledgment transaction sets.

    Usage:
        generator = FA997Generator()
        ack_content = generator.generate(
            group=original_group,
            validation_result=result,
            control_number="0001",
        )
    """

    def __init__(
        self,
        element_separator: str = "*",
        segment_terminator: str = "~",
    ):
        """
        Initialize the generator.

        Args:
            element_separator: Element separator character
            segment_terminator: Segment terminator character
        """
        self.element_sep = element_separator
        self.segment_term = segment_terminator

    def generate(
        self,
        group: FunctionalGroupInstance,
        validation_result: "ValidationResult | None" = None,
        control_number: str = "0001",
        errors_by_transaction: dict[str, list[ParseError]] | None = None,
    ) -> str:
        """
        Generate a 997 acknowledgment for a functional group.

        Args:
            group: The original functional group being acknowledged
            validation_result: Optional validation result with errors
            control_number: Control number for the 997
            errors_by_transaction: Optional dict mapping txn control numbers to errors

        Returns:
            The generated 997 content as a string
        """
        segments: list[str] = []

        # Collect errors by transaction if not provided
        if errors_by_transaction is None:
            errors_by_transaction = self._collect_errors_by_transaction(group, validation_result)

        # ST - Transaction Set Header
        segments.append(self._generate_st(control_number))

        # AK1 - Functional Group Response Header
        ak1 = AK1Data(
            functional_id=group.functional_id,
            group_control=group.control_number,
        )
        segments.append(self._generate_ak1(ak1))

        # Process each transaction
        accepted_count = 0
        for txn in group.transactions:
            txn_errors = errors_by_transaction.get(txn.control_number, [])
            txn_segments, is_accepted = self._generate_transaction_response(txn, txn_errors)
            segments.extend(txn_segments)
            if is_accepted:
                accepted_count += 1

        # AK9 - Functional Group Response Trailer
        status = self._determine_group_status(len(group.transactions), accepted_count)
        ak9 = AK9Data(
            status_code=status,
            included_count=len(group.transactions),
            received_count=len(group.transactions),
            accepted_count=accepted_count,
        )
        segments.append(self._generate_ak9(ak9))

        # SE - Transaction Set Trailer
        segment_count = len(segments) + 1  # +1 for SE itself
        segments.append(self._generate_se(segment_count, control_number))

        return self.segment_term.join(segments) + self.segment_term

    def _generate_st(self, control_number: str) -> str:
        """Generate ST segment."""
        return f"ST{self.element_sep}997{self.element_sep}{control_number}"

    def _generate_se(self, segment_count: int, control_number: str) -> str:
        """Generate SE segment."""
        return f"SE{self.element_sep}{segment_count}{self.element_sep}{control_number}"

    def _generate_ak1(self, data: AK1Data) -> str:
        """Generate AK1 segment."""
        return f"AK1{self.element_sep}{data.functional_id}{self.element_sep}{data.group_control}"

    def _generate_ak2(self, data: AK2Data) -> str:
        """Generate AK2 segment."""
        seg = f"AK2{self.element_sep}{data.transaction_id}{self.element_sep}{data.control_number}"
        if data.implementation_reference:
            seg += f"{self.element_sep}{data.implementation_reference}"
        return seg

    def _generate_ak3(self, data: AK3Data) -> str:
        """Generate AK3 segment."""
        seg = f"AK3{self.element_sep}{data.segment_id}{self.element_sep}{data.segment_position}"
        if data.loop_identifier:
            seg += f"{self.element_sep}{data.loop_identifier}"
        else:
            seg += f"{self.element_sep}"
        if data.error_code:
            seg += f"{self.element_sep}{data.error_code}"
        return seg

    def _generate_ak4(self, data: AK4Data) -> str:
        """Generate AK4 segment."""
        seg = f"AK4{self.element_sep}{data.element_position}"
        # AK402 - element reference (optional)
        if data.element_reference:
            seg += f"{self.element_sep}{data.element_reference}"
        else:
            seg += f"{self.element_sep}"
        # AK403 - error code
        seg += f"{self.element_sep}{data.error_code}"
        # AK404 - copy of bad element (optional)
        if data.copy_of_bad_element:
            seg += f"{self.element_sep}{data.copy_of_bad_element}"
        return seg

    def _generate_ak5(self, data: AK5Data) -> str:
        """Generate AK5 segment."""
        seg = f"AK5{self.element_sep}{data.status_code}"
        for code in data.error_codes[:5]:  # Max 5 error codes
            seg += f"{self.element_sep}{code}"
        return seg

    def _generate_ak9(self, data: AK9Data) -> str:
        """Generate AK9 segment."""
        seg = (
            f"AK9{self.element_sep}{data.status_code}"
            f"{self.element_sep}{data.included_count}"
            f"{self.element_sep}{data.received_count}"
            f"{self.element_sep}{data.accepted_count}"
        )
        for code in data.error_codes[:5]:  # Max 5 error codes
            seg += f"{self.element_sep}{code}"
        return seg

    def _generate_transaction_response(
        self,
        txn: TransactionSetInstance,
        errors: list[ParseError],
    ) -> tuple[list[str], bool]:
        """
        Generate AK2 loop for a transaction.

        Returns:
            Tuple of (segments, is_accepted)
        """
        segments: list[str] = []

        # AK2 - Transaction Set Response Header
        ak2 = AK2Data(
            transaction_id=txn.transaction_id,
            control_number=txn.control_number,
            implementation_reference=txn.implementation_reference,
        )
        segments.append(self._generate_ak2(ak2))

        # Group errors by segment
        segment_errors: dict[tuple[str, int], list[ParseError]] = {}
        transaction_level_errors: list[ParseError] = []

        for error in errors:
            if error.segment_tag and error.segment_position:
                key = (error.segment_tag, error.segment_position)
                if key not in segment_errors:
                    segment_errors[key] = []
                segment_errors[key].append(error)
            else:
                transaction_level_errors.append(error)

        # Generate AK3/AK4 for each segment with errors
        for (seg_id, seg_pos), seg_errors in sorted(segment_errors.items(), key=lambda x: x[0][1]):
            # Determine segment error code
            seg_error_code = self._determine_segment_error_code(seg_errors)

            # If there are element errors, use code 8
            element_errors = [e for e in seg_errors if e.element_position]
            if element_errors:
                seg_error_code = "8"  # Segment has data element errors

            # Find loop identifier from first error with loop_id
            loop_id = None
            for err in seg_errors:
                if err.loop_id:
                    loop_id = err.loop_id
                    break

            ak3 = AK3Data(
                segment_id=seg_id,
                segment_position=seg_pos,
                loop_identifier=loop_id,
                error_code=seg_error_code,
            )
            segments.append(self._generate_ak3(ak3))

            # Generate AK4 for each element error
            for error in element_errors:
                if error.element_position:
                    ak4 = AK4Data(
                        element_position=error.element_position,
                        element_reference=None,  # TODO: Get element reference
                        error_code=error.code,
                        copy_of_bad_element=error.actual[:20] if error.actual else None,
                    )
                    segments.append(self._generate_ak4(ak4))

        # Determine transaction status
        has_errors = len(errors) > 0
        fatal_errors = any(e.severity == ErrorSeverity.FATAL for e in errors)
        non_warning_errors = [e for e in errors if e.severity != ErrorSeverity.WARNING]

        if fatal_errors or non_warning_errors:
            status = "R"  # Rejected
        elif has_errors:
            status = "E"  # Accepted with errors
        else:
            status = "A"  # Accepted

        # Collect unique error codes for AK5
        error_codes = list(set(e.code for e in non_warning_errors))[:5]

        # AK5 - Transaction Set Response Trailer
        ak5 = AK5Data(
            status_code=status,
            error_codes=error_codes,
        )
        segments.append(self._generate_ak5(ak5))

        is_accepted = status in ("A", "E")
        return segments, is_accepted

    def _determine_segment_error_code(
        self,
        errors: list[ParseError],
    ) -> str:
        """Determine the AK3 segment error code from errors."""
        # Map error categories to AK3 codes
        for error in errors:
            code = error.code
            # If the error code is already an AK3 segment code, use it
            if code in ("1", "2", "3", "4", "5", "6", "7"):
                return code

        # Check error categories
        for error in errors:
            if error.category == ErrorCategory.SCHEMA:
                if "not defined" in error.message.lower():
                    return "6"  # Not in defined transaction set
                if "unexpected" in error.message.lower():
                    return "2"  # Unexpected segment
                if "missing" in error.message.lower():
                    return "3"  # Mandatory segment missing
                if "sequence" in error.message.lower():
                    return "7"  # Not in proper sequence
                if "maximum" in error.message.lower() and "loop" in error.message.lower():
                    return "4"  # Loop over maximum times
                if "maximum" in error.message.lower():
                    return "5"  # Segment exceeds maximum use

        # Default to segment not defined
        return "6"

    def _determine_group_status(
        self,
        total_count: int,
        accepted_count: int,
    ) -> str:
        """Determine the AK9 group status code."""
        if accepted_count == total_count:
            return "A"  # All accepted
        elif accepted_count > 0:
            return "P"  # Partially accepted
        else:
            return "R"  # All rejected

    def _collect_errors_by_transaction(
        self,
        group: FunctionalGroupInstance,
        validation_result: "ValidationResult | None",
    ) -> dict[str, list[ParseError]]:
        """Collect errors grouped by transaction control number."""
        errors_by_txn: dict[str, list[ParseError]] = {}

        # Initialize with empty lists for each transaction
        for txn in group.transactions:
            errors_by_txn[txn.control_number] = []

        # Add transaction-level errors
        for txn in group.transactions:
            errors_by_txn[txn.control_number].extend(txn.errors)

        # Add validation result errors if available
        if validation_result:
            for error in validation_result.errors:
                # Try to match to a transaction
                # Errors may have transaction_id but not control_number
                matched = False
                for txn in group.transactions:
                    if error.transaction_id == txn.transaction_id:
                        errors_by_txn[txn.control_number].append(error)
                        matched = True
                        break

                # If not matched, add to first transaction or skip
                if not matched and error.segment_tag:
                    # Try to find by segment position
                    # This is a fallback - ideally errors have transaction context
                    if group.transactions:
                        first_txn = group.transactions[0]
                        errors_by_txn[first_txn.control_number].append(error)

        return errors_by_txn


def generate_997(
    group: FunctionalGroupInstance,
    control_number: str = "0001",
    validation_result: "ValidationResult | None" = None,
    element_separator: str = "*",
    segment_terminator: str = "~",
) -> str:
    """
    Convenience function to generate a 997 acknowledgment.

    Args:
        group: The functional group to acknowledge
        control_number: Control number for the 997
        validation_result: Optional validation result
        element_separator: Element separator character
        segment_terminator: Segment terminator character

    Returns:
        The generated 997 content
    """
    generator = FA997Generator(
        element_separator=element_separator,
        segment_terminator=segment_terminator,
    )
    return generator.generate(
        group=group,
        control_number=control_number,
        validation_result=validation_result,
    )
