"""
Semantic Validator (Level 6).

Validates cross-element and cross-segment rules:
- Conditional requirements (if A then B required)
- Mutual exclusion (A or B but not both)
- Cross-element dependencies
- Date consistency checks
- Reference integrity

This validator handles business logic rules that span multiple elements
or segments within a message.

Note: Full semantic validation requires schema-specific rules that are
not typically encoded in standard EDIFACT directories. This module
provides a framework and common validations that can be extended.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from edi_schema.edifact.ast import (
    ErrorCategory,
    ErrorSeverity,
    MessageInstance,
    ParsedSegment,
    ParseError,
    SegmentGroupInstance,
)

if TYPE_CHECKING:
    from edi_schema.edifact.models import ResolvedMessageSpec


@dataclass
class SemanticValidationContext:
    """Context for semantic validation."""

    message_type: str
    message_reference: str | None = None


class SemanticValidator:
    """
    Validates semantic rules across elements and segments.

    Semantic rules include:
    - Conditional requirements based on other element values
    - Mutual exclusion between elements
    - Cross-segment reference integrity
    - Date/time consistency
    - Quantity/amount consistency

    This is a framework for semantic validation. Specific rules can be
    registered for different message types.
    """

    def __init__(
        self,
        schema: "ResolvedMessageSpec | None" = None,
        custom_rules: list | None = None,
    ):
        """
        Initialize the semantic validator.

        Args:
            schema: Message schema (for rule lookup)
            custom_rules: Optional list of custom validation rules
        """
        self.schema = schema
        self.custom_rules = custom_rules or []
        self.errors: list[ParseError] = []

    def validate(
        self,
        message: MessageInstance,
        context: SemanticValidationContext,
    ) -> list[ParseError]:
        """
        Validate semantic rules for a message.

        Args:
            message: The parsed message
            context: Validation context

        Returns:
            List of validation errors
        """
        self.errors = []

        # Common validations
        self.errors.extend(self._validate_reference_integrity(message, context))
        self.errors.extend(self._validate_date_consistency(message, context))

        # Apply custom rules
        for rule in self.custom_rules:
            rule_errors = rule.validate(message, context)
            self.errors.extend(rule_errors)

        return self.errors

    def _validate_reference_integrity(
        self,
        message: MessageInstance,
        context: SemanticValidationContext,
    ) -> list[ParseError]:
        """
        Validate that references within the message are consistent.

        For example:
        - RFF segments should reference valid document types
        - NAD party references should be used consistently
        """
        errors: list[ParseError] = []

        # Collect all segments
        all_segments = self._flatten_content(message.content)

        # Track references
        rff_references: dict[str, list[str]] = {}  # qualifier -> [values]

        for segment in all_segments:
            if segment.tag == "RFF":
                # RFF structure: RFF+qualifier:reference
                if segment.elements and segment.elements[0].components:
                    components = segment.elements[0].components
                    if len(components) >= 2:
                        qualifier = components[0].value if components[0] else None
                        reference = components[1].value if components[1] else None
                        if qualifier and reference:
                            if qualifier not in rff_references:
                                rff_references[qualifier] = []
                            rff_references[qualifier].append(reference)

        # Check for duplicate references (may be intentional, so just warn)
        for qualifier, refs in rff_references.items():
            if len(refs) != len(set(refs)):
                errors.append(
                    ParseError(
                        code="SEM01",
                        message=f"Duplicate {qualifier} reference values found",
                        category=ErrorCategory.SEMANTIC,
                        severity=ErrorSeverity.WARNING,
                    )
                )

        return errors

    def _validate_date_consistency(
        self,
        message: MessageInstance,
        context: SemanticValidationContext,
    ) -> list[ParseError]:
        """
        Validate that dates within the message are logically consistent.

        For example:
        - Delivery date should be after order date
        - Expiry date should be after document date
        """
        errors: list[ParseError] = []

        # Collect all DTM segments
        all_segments = self._flatten_content(message.content)
        dates: dict[str, str] = {}  # qualifier -> date value

        for segment in all_segments:
            if segment.tag == "DTM":
                # DTM structure: DTM+qualifier:date:format
                if segment.elements and segment.elements[0].components:
                    components = segment.elements[0].components
                    if len(components) >= 2:
                        qualifier = components[0].value if components[0] else None
                        date_value = components[1].value if components[1] else None
                        if qualifier and date_value:
                            dates[qualifier] = date_value

        # Check logical date relationships
        # 137 = Document date, 2 = Requested delivery, 35 = Actual delivery

        doc_date = dates.get("137")
        req_delivery = dates.get("2")
        actual_delivery = dates.get("35")

        # Delivery dates should be >= document date
        if doc_date and req_delivery:
            if self._compare_dates(req_delivery, doc_date) < 0:
                errors.append(
                    ParseError(
                        code="SEM02",
                        message="Requested delivery date is before document date",
                        category=ErrorCategory.SEMANTIC,
                        severity=ErrorSeverity.WARNING,
                    )
                )

        if doc_date and actual_delivery:
            if self._compare_dates(actual_delivery, doc_date) < 0:
                errors.append(
                    ParseError(
                        code="SEM03",
                        message="Actual delivery date is before document date",
                        category=ErrorCategory.SEMANTIC,
                        severity=ErrorSeverity.WARNING,
                    )
                )

        return errors

    def _compare_dates(self, date1: str, date2: str) -> int:
        """
        Compare two date strings.

        Returns:
            -1 if date1 < date2
             0 if date1 == date2
             1 if date1 > date2

        Handles common date formats: YYYYMMDD, YYMMDD
        """
        # Normalize to 8-digit format
        d1 = self._normalize_date(date1)
        d2 = self._normalize_date(date2)

        if d1 < d2:
            return -1
        elif d1 > d2:
            return 1
        return 0

    def _normalize_date(self, date: str) -> str:
        """Normalize date to YYYYMMDD format."""
        # Strip non-digits
        digits = "".join(c for c in date if c.isdigit())

        if len(digits) == 6:
            # YYMMDD - assume 20xx for 00-49, 19xx for 50-99
            yy = int(digits[:2])
            prefix = "20" if yy < 50 else "19"
            return prefix + digits
        elif len(digits) == 8:
            return digits
        else:
            # Unknown format, return as-is
            return digits

    def _flatten_content(
        self,
        content: list[ParsedSegment | SegmentGroupInstance],
    ) -> list[ParsedSegment]:
        """Flatten nested content into a list of segments."""
        result: list[ParsedSegment] = []

        for item in content:
            if isinstance(item, ParsedSegment):
                result.append(item)
            elif isinstance(item, SegmentGroupInstance):
                result.extend(item.segments)
                result.extend(self._flatten_content(item.children))

        return result


# Convenience function


def validate_semantics(
    message: MessageInstance,
    schema: "ResolvedMessageSpec | None" = None,
) -> list[ParseError]:
    """
    Convenience function to validate semantic rules.

    Args:
        message: The parsed message
        schema: Optional schema

    Returns:
        List of validation errors
    """
    context = SemanticValidationContext(
        message_type=message.message_type,
        message_reference=message.reference_number,
    )

    validator = SemanticValidator(schema)
    return validator.validate(message, context)
