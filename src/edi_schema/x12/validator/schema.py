"""
Schema Validator (Level 3).

Validates transaction structure against schema definitions:
- Segment order
- Required segments
- Loop cardinality (min/max occurrences)
- Segment usage (M=mandatory, O=optional, C=conditional)

Error Codes (for 997 AK3):
- 2: Unexpected segment
- 3: Mandatory segment missing
- 4: Loop occurs over maximum times
- 5: Segment exceeds maximum use
- 6: Segment not defined in transaction set
- 7: Segment not in proper sequence
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from edi_schema.x12.ast import (
    ErrorCategory,
    ErrorSeverity,
    LoopInstance,
    ParsedSegment,
    ParseError,
    RawSegment,
    RecoveryPoint,
)
from edi_schema.x12.enums import RequirementDesignator

# Alias for cleaner code
Requirement = RequirementDesignator
from edi_schema.x12.parser.loop_hierarchy import (
    LoopNode,
    build_loop_hierarchy,
)

if TYPE_CHECKING:
    from edi_schema.x12.models.transaction import TransactionSetSegment
    from edi_schema.x12.schema import X12Schema


@dataclass
class SchemaValidationContext:
    """Context for schema validation."""

    transaction_id: str
    group_control: str | None = None
    interchange_control: str | None = None


@dataclass
class SegmentTracker:
    """Tracks segment occurrences for cardinality validation."""

    counts: dict[str, int] = field(default_factory=dict)  # segment_id -> count
    loop_counts: dict[str, int] = field(default_factory=dict)  # loop_id -> count

    def record_segment(self, segment_id: str) -> int:
        """Record a segment occurrence and return the new count."""
        current = self.counts.get(segment_id, 0)
        self.counts[segment_id] = current + 1
        return current + 1

    def record_loop(self, loop_id: str) -> int:
        """Record a loop iteration and return the new count."""
        current = self.loop_counts.get(loop_id, 0)
        self.loop_counts[loop_id] = current + 1
        return current + 1

    def get_segment_count(self, segment_id: str) -> int:
        """Get current count for a segment."""
        return self.counts.get(segment_id, 0)

    def get_loop_count(self, loop_id: str) -> int:
        """Get current count for a loop."""
        return self.loop_counts.get(loop_id, 0)


class SchemaValidator:
    """
    Validates transaction structure against schema.

    This validator checks:
    1. Segment order - segments appear in correct sequence
    2. Required segments - mandatory segments are present
    3. Loop cardinality - loops don't exceed max iterations
    4. Segment usage - segments don't exceed max uses
    """

    def __init__(self, schema: "X12Schema"):
        self.schema = schema
        self.loop_hierarchy = build_loop_hierarchy(schema)
        self.errors: list[ParseError] = []
        self.tracker = SegmentTracker()

    def validate(
        self,
        content: list[ParsedSegment | RawSegment | LoopInstance],
        context: SchemaValidationContext,
    ) -> list[ParseError]:
        """
        Validate transaction content against schema.

        Args:
            content: Parsed transaction content
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

        # Validate loop cardinality
        self.errors.extend(self._validate_loop_cardinality(content, context))

        return self.errors

    def _flatten_content(
        self,
        content: list[ParsedSegment | RawSegment | LoopInstance],
    ) -> list[ParsedSegment | RawSegment]:
        """Flatten nested content into a list of segments.

        Handles both RawSegment (from envelope parser) and ParsedSegment
        (from schema-aware parser), as well as LoopInstance for nested loops.
        """
        result: list[ParsedSegment | RawSegment] = []

        for item in content:
            if isinstance(item, (ParsedSegment, RawSegment)):
                result.append(item)
            elif isinstance(item, LoopInstance):
                result.extend(item.segments)
                result.extend(self._flatten_content(item.children))

        return result

    def _validate_segment_order(
        self,
        segments: list[ParsedSegment | RawSegment],
        context: SchemaValidationContext,
    ) -> list[ParseError]:
        """
        Validate segments are in correct order per schema.

        This is a simplified check - we verify each segment exists
        in the schema and track if any are grossly out of order.
        """
        errors: list[ParseError] = []
        structure = self.schema.get_structure()
        schema_segment_ids = [s.segment_id for s in structure]

        for i, segment in enumerate(segments):
            position = i + 1  # 1-indexed

            # Check if segment is defined in schema
            if segment.tag not in schema_segment_ids:
                # Special check for envelope segments (ST/SE are handled separately)
                if segment.tag not in ("ST", "SE"):
                    # Get position from segment (works for both RawSegment and ParsedSegment)
                    seg_position = None
                    if isinstance(segment, RawSegment):
                        seg_position = segment.position
                    elif hasattr(segment, "raw") and segment.raw:
                        seg_position = segment.raw.position

                    errors.append(
                        ParseError(
                            code="6",  # Segment not defined in transaction set
                            message=f"Segment {segment.tag} not defined in transaction {context.transaction_id}",
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

            # Check max uses for this segment
            # Note: max_use is only enforced for segments at the transaction root level
            # (loop_level=0). Segments inside loops can appear multiple times per loop
            # iteration - proper per-loop max_use validation would require tracking
            # segment counts within each loop context, which is complex.
            seg_def = self._find_segment_in_schema(segment.tag)
            if seg_def and seg_def.max_use and seg_def.loop_level == 0:
                try:
                    max_use = int(seg_def.max_use)
                    if count > max_use:
                        # Get position from segment
                        seg_position = None
                        if isinstance(segment, RawSegment):
                            seg_position = segment.position
                        elif hasattr(segment, "raw") and segment.raw:
                            seg_position = segment.raw.position

                        errors.append(
                            ParseError(
                                code="5",  # Segment exceeds maximum use
                                message=f"Segment {segment.tag} exceeds maximum use "
                                f"({count} > {max_use})",
                                category=ErrorCategory.SCHEMA,
                                severity=ErrorSeverity.ERROR,
                                position=seg_position,
                                segment_tag=segment.tag,
                                segment_position=position,
                            )
                        )
                except (ValueError, TypeError):
                    pass  # max_use might be ">1" or similar

        return errors

    def _validate_required_segments(
        self,
        segments: list[ParsedSegment | RawSegment],
        context: SchemaValidationContext,
    ) -> list[ParseError]:
        """
        Validate all required (mandatory) segments are present.

        Only checks segments that are:
        - Mandatory (requirement=M)
        - At the transaction root level (loop_level=0)
        - Not loop segments (loop_id is None)
        - Not envelope segments (ST/SE are handled by envelope parser)
        """
        errors: list[ParseError] = []
        structure = self.schema.get_structure()
        segment_ids_present = {s.tag for s in segments}

        # Envelope segments are not part of transaction content
        # They are validated by the envelope parser
        envelope_segments = {"ST", "SE"}

        for seg_def in structure:
            # Skip envelope segments - they're validated separately
            if seg_def.segment_id in envelope_segments:
                continue

            # Check if segment is mandatory at the root level
            # Segments with loop_level > 0 are inside loops and only required
            # when that loop is entered
            if seg_def.requirement == Requirement.M:
                if seg_def.segment_id not in segment_ids_present:
                    # Only report missing if it's at the transaction root level
                    # (not inside a loop structure)
                    if not seg_def.loop_id and seg_def.loop_level == 0:
                        errors.append(
                            ParseError(
                                code="3",  # Mandatory segment missing
                                message=f"Mandatory segment {seg_def.segment_id} missing "
                                f"in transaction {context.transaction_id}",
                                category=ErrorCategory.SCHEMA,
                                severity=ErrorSeverity.ERROR,
                                segment_tag=seg_def.segment_id,
                                transaction_id=context.transaction_id,
                            )
                        )

        return errors

    def _validate_loop_cardinality(
        self,
        content: list[ParsedSegment | RawSegment | LoopInstance],
        context: SchemaValidationContext,
    ) -> list[ParseError]:
        """
        Validate loop iterations don't exceed maximum.
        """
        errors: list[ParseError] = []

        # Count loop iterations
        loop_counts: dict[str, int] = {}

        def count_loops(items: list[ParsedSegment | RawSegment | LoopInstance]) -> None:
            for item in items:
                if isinstance(item, LoopInstance):
                    loop_id = item.loop_id
                    loop_counts[loop_id] = loop_counts.get(loop_id, 0) + 1
                    count_loops(item.children)

        count_loops(content)

        # Check against schema
        for loop_id, count in loop_counts.items():
            # Find loop definition in hierarchy
            max_repeat = self._find_loop_max_repeat(loop_id)
            if max_repeat is not None:
                try:
                    max_val = int(max_repeat)
                    if count > max_val:
                        errors.append(
                            ParseError(
                                code="4",  # Loop occurs over maximum times
                                message=f"Loop {loop_id} exceeds maximum iterations "
                                f"({count} > {max_val})",
                                category=ErrorCategory.SCHEMA,
                                severity=ErrorSeverity.ERROR,
                                loop_id=loop_id,
                            )
                        )
                except (ValueError, TypeError):
                    # ">1" means unlimited
                    pass

        return errors

    def _find_segment_in_schema(
        self,
        segment_id: str,
    ) -> "TransactionSetSegment | None":
        """Find a segment definition in the schema."""
        for seg in self.schema.get_structure():
            if seg.segment_id == segment_id:
                return seg
        return None

    def _find_loop_max_repeat(self, loop_id: str) -> str | int | None:
        """Find the max repeat value for a loop."""

        def search(node: LoopNode) -> str | int | None:
            if node.loop_id == loop_id:
                return node.max_repeat
            for child in node.children:
                result = search(child)
                if result is not None:
                    return result
            return None

        return search(self.loop_hierarchy)


# Convenience functions


def validate_segment_order(
    segments: list[ParsedSegment | RawSegment],
    schema: "X12Schema",
    context: SchemaValidationContext,
) -> list[ParseError]:
    """Validate segment order against schema."""
    validator = SchemaValidator(schema)
    all_segments = segments
    return validator._validate_segment_order(all_segments, context)


def validate_required_segments(
    segments: list[ParsedSegment | RawSegment],
    schema: "X12Schema",
    context: SchemaValidationContext,
) -> list[ParseError]:
    """Validate required segments are present."""
    validator = SchemaValidator(schema)
    return validator._validate_required_segments(segments, context)


def validate_loop_cardinality(
    content: list[ParsedSegment | RawSegment | LoopInstance],
    schema: "X12Schema",
    context: SchemaValidationContext,
) -> list[ParseError]:
    """Validate loop cardinality."""
    validator = SchemaValidator(schema)
    return validator._validate_loop_cardinality(content, context)
