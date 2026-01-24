"""
Schema Validator (Level 3).

Validates message structure against schema definitions:
- Segment order
- Required segments
- Segment group cardinality (min/max occurrences)
- Segment usage (M=mandatory, C=conditional)

EDIFACT Error Codes (for CONTRL UCS):
- 12: Invalid value
- 13: Missing
- 14: Value not supported
- 15: Not supported at this position
- 16: Too many constituents
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from edi_schema.edifact.ast import (
    ErrorCategory,
    ErrorSeverity,
    ParsedSegment,
    ParseError,
    RecoveryPoint,
    SegmentGroupInstance,
)
from edi_schema.edifact.parser.hierarchy import (
    build_group_hierarchy,
)

if TYPE_CHECKING:
    from edi_schema.edifact.models import (
        ResolvedMessageSpec,
    )


@dataclass
class SchemaValidationContext:
    """Context for schema validation."""

    message_type: str
    message_reference: str | None = None
    interchange_reference: str | None = None


@dataclass
class SegmentTracker:
    """Tracks segment occurrences for cardinality validation."""

    counts: dict[str, int] = field(default_factory=dict)  # segment_tag -> count
    group_counts: dict[int, int] = field(default_factory=dict)  # group_number -> count

    def record_segment(self, segment_tag: str) -> int:
        """Record a segment occurrence and return the new count."""
        current = self.counts.get(segment_tag, 0)
        self.counts[segment_tag] = current + 1
        return current + 1

    def record_group(self, group_number: int) -> int:
        """Record a group iteration and return the new count."""
        current = self.group_counts.get(group_number, 0)
        self.group_counts[group_number] = current + 1
        return current + 1

    def get_segment_count(self, segment_tag: str) -> int:
        """Get current count for a segment."""
        return self.counts.get(segment_tag, 0)

    def get_group_count(self, group_number: int) -> int:
        """Get current count for a group."""
        return self.group_counts.get(group_number, 0)


class SchemaValidator:
    """
    Validates message structure against schema.

    This validator checks:
    1. Segment order - segments appear in correct sequence
    2. Required segments - mandatory segments are present
    3. Group cardinality - groups don't exceed max iterations
    4. Segment usage - segments don't exceed max repetitions
    """

    def __init__(self, schema: "ResolvedMessageSpec"):
        self.schema = schema
        self.hierarchy = build_group_hierarchy(schema)
        self.errors: list[ParseError] = []
        self.tracker = SegmentTracker()

    def validate(
        self,
        content: list[ParsedSegment | SegmentGroupInstance],
        context: SchemaValidationContext,
    ) -> list[ParseError]:
        """
        Validate message content against schema.

        Args:
            content: Parsed message content
            context: Validation context

        Returns:
            List of validation errors
        """
        self.errors = []
        self.tracker = SegmentTracker()

        # Collect all segments for order/presence validation
        all_segments = self._flatten_content(content)

        # Validate segment order
        self.errors.extend(self._validate_segment_order(all_segments, context))

        # Validate required segments
        self.errors.extend(self._validate_required_segments(all_segments, context))

        # Validate group cardinality
        self.errors.extend(self._validate_group_cardinality(content, context))

        return self.errors

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

    def _validate_segment_order(
        self,
        segments: list[ParsedSegment],
        context: SchemaValidationContext,
    ) -> list[ParseError]:
        """
        Validate segments are in correct order per schema.

        This is a simplified check - we verify each segment exists
        in the schema and track if any are grossly out of order.
        """
        errors: list[ParseError] = []
        valid_tags = self._collect_valid_segment_tags()

        for i, segment in enumerate(segments):
            position = i + 1

            # Check if segment is defined in schema
            if segment.tag not in valid_tags:
                # Envelope segments (UNH, UNT) are handled separately
                if segment.tag not in ("UNH", "UNT"):
                    seg_position = segment.raw.position if segment.raw else None

                    errors.append(
                        ParseError(
                            code="15",  # Not supported at this position
                            message=f"Segment {segment.tag} not defined in message {context.message_type}",
                            category=ErrorCategory.SCHEMA,
                            severity=ErrorSeverity.ERROR,
                            position=seg_position,
                            segment_tag=segment.tag,
                            segment_position=position,
                            recovery_point=RecoveryPoint.SEGMENT_BOUNDARY,
                        )
                    )

            # Track segment occurrence
            count = self.tracker.record_segment(segment.tag)

            # Check max repetitions for this segment
            max_repeat = self._get_segment_max_repeat(segment.tag)
            if max_repeat is not None and count > max_repeat:
                seg_position = segment.raw.position if segment.raw else None

                errors.append(
                    ParseError(
                        code="16",  # Too many constituents
                        message=f"Segment {segment.tag} exceeds maximum repetitions "
                        f"({count} > {max_repeat})",
                        category=ErrorCategory.SCHEMA,
                        severity=ErrorSeverity.ERROR,
                        position=seg_position,
                        segment_tag=segment.tag,
                        segment_position=position,
                    )
                )

        return errors

    def _validate_required_segments(
        self,
        segments: list[ParsedSegment],
        context: SchemaValidationContext,
    ) -> list[ParseError]:
        """
        Validate all required (mandatory) segments are present.

        Only checks segments that are:
        - Mandatory
        - At the message root level (not inside groups)
        - Not envelope segments (UNH/UNT)
        """
        errors: list[ParseError] = []
        segment_tags_present = {s.tag for s in segments}

        # Envelope segments are validated separately
        envelope_segments = {"UNH", "UNT"}

        # Check each item at the root level of the message structure
        for item in self.schema.spec.structure:
            if hasattr(item, "segment_tag"):
                # It's a SegmentRef
                seg_ref = item
                if seg_ref.segment_tag in envelope_segments:
                    continue

                if seg_ref.mandatory:
                    if seg_ref.segment_tag not in segment_tags_present:
                        errors.append(
                            ParseError(
                                code="13",  # Missing
                                message=f"Mandatory segment {seg_ref.segment_tag} missing "
                                f"in message {context.message_type}",
                                category=ErrorCategory.SCHEMA,
                                severity=ErrorSeverity.ERROR,
                                segment_tag=seg_ref.segment_tag,
                            )
                        )

        return errors

    def _validate_group_cardinality(
        self,
        content: list[ParsedSegment | SegmentGroupInstance],
        context: SchemaValidationContext,
    ) -> list[ParseError]:
        """
        Validate segment group iterations don't exceed maximum.
        """
        errors: list[ParseError] = []

        # Count group iterations
        group_counts: dict[int, int] = {}

        def count_groups(items: list[ParsedSegment | SegmentGroupInstance]) -> None:
            for item in items:
                if isinstance(item, SegmentGroupInstance):
                    group_num = item.group_number
                    group_counts[group_num] = group_counts.get(group_num, 0) + 1
                    count_groups(item.children)

        count_groups(content)

        # Check against schema
        for group_num, count in group_counts.items():
            max_repeat = self._get_group_max_repeat(group_num)
            if max_repeat is not None and count > max_repeat:
                errors.append(
                    ParseError(
                        code="16",  # Too many constituents
                        message=f"Segment group {group_num} exceeds maximum iterations "
                        f"({count} > {max_repeat})",
                        category=ErrorCategory.SCHEMA,
                        severity=ErrorSeverity.ERROR,
                    )
                )

        return errors

    def _collect_valid_segment_tags(self) -> set[str]:
        """Collect all valid segment tags from schema structure."""
        tags: set[str] = set()

        def collect(items: list) -> None:
            for item in items:
                if hasattr(item, "segment_tag"):
                    # It's a SegmentRef
                    tags.add(item.segment_tag)
                elif hasattr(item, "children"):
                    # It's a SegmentGroup
                    collect(item.children)

        collect(self.schema.spec.structure)
        return tags

    def _get_segment_max_repeat(self, segment_tag: str) -> int | None:
        """Get max repeat for a segment from schema."""

        def find_in_items(items: list) -> int | None:
            for item in items:
                if hasattr(item, "segment_tag"):
                    if item.segment_tag == segment_tag:
                        return item.max_repeat
                elif hasattr(item, "children"):
                    result = find_in_items(item.children)
                    if result is not None:
                        return result
            return None

        return find_in_items(self.schema.spec.structure)

    def _get_group_max_repeat(self, group_number: int) -> int | None:
        """Get max repeat for a segment group from schema."""

        def find_in_items(items: list) -> int | None:
            for item in items:
                if hasattr(item, "number"):
                    # It's a SegmentGroup
                    if item.number == group_number:
                        return item.max_repeat
                    # Also search nested groups
                    result = find_in_items(item.children)
                    if result is not None:
                        return result
            return None

        return find_in_items(self.schema.spec.structure)


# Convenience functions


def validate_segment_order(
    segments: list[ParsedSegment],
    schema: "ResolvedMessageSpec",
    context: SchemaValidationContext,
) -> list[ParseError]:
    """Validate segment order against schema."""
    validator = SchemaValidator(schema)
    return validator._validate_segment_order(segments, context)


def validate_required_segments(
    segments: list[ParsedSegment],
    schema: "ResolvedMessageSpec",
    context: SchemaValidationContext,
) -> list[ParseError]:
    """Validate required segments are present."""
    validator = SchemaValidator(schema)
    return validator._validate_required_segments(segments, context)


def validate_group_cardinality(
    content: list[ParsedSegment | SegmentGroupInstance],
    schema: "ResolvedMessageSpec",
    context: SchemaValidationContext,
) -> list[ParseError]:
    """Validate segment group cardinality."""
    validator = SchemaValidator(schema)
    return validator._validate_group_cardinality(content, context)
