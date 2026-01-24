"""
EDIFACT Message Parser.

Schema-driven message content parser that:
1. Loads schema based on message type/version/release from UNH S009
2. Builds segment group hierarchy from schema
3. Matches segments to correct group positions
4. Attaches segment/element/composite definitions
5. Falls back to flat parsing when no schema available

Usage:
    from edi_schema.edifact.parser.message import EdifactMessageParser
    from edi_schema.edifact.schema import EdifactSchemaLoader

    schema_loader = EdifactSchemaLoader("/path/to/d23a")
    parser = EdifactMessageParser(schema_loader)

    # Parse a message with schema
    parsed_message = parser.parse(message_instance)
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from edi_schema.edifact.ast import (
    ErrorCategory,
    ErrorSeverity,
    MessageInstance,
    ParsedComponent,
    ParsedElement,
    ParsedSegment,
    ParseError,
    RawSegment,
    SegmentGroupInstance,
)
from edi_schema.edifact.parser.hierarchy import (
    GroupMatcher,
    MatchAction,
    build_group_hierarchy,
)

if TYPE_CHECKING:
    from edi_schema.edifact.models import (
        Composite,
        ResolvedMessageSpec,
        Segment,
    )
    from edi_schema.edifact.schema import EdifactSchemaLoader
    from edi_schema.edifact.schemas import GeneratedEdifactSchemaLoader


@dataclass
class MessageParseResult:
    """Result of parsing a message with schema."""

    message: MessageInstance
    schema_applied: bool = False
    schema_id: str | None = None
    errors: list[ParseError] = field(default_factory=list)


class EdifactMessageParser:
    """
    Schema-driven message content parser.

    Takes a MessageInstance from the envelope parser and applies
    schema information to:
    - Organize segments into segment groups
    - Attach segment definitions
    - Attach element/composite definitions
    - Validate structure against schema

    If no schema is available for the message type, falls back to
    flat parsing (no segment groups, no definitions).
    """

    def __init__(
        self, schema_loader: "EdifactSchemaLoader | GeneratedEdifactSchemaLoader | None" = None
    ) -> None:
        """
        Initialize the message parser.

        Args:
            schema_loader: Schema loader for loading message schemas.
                           If None, all messages will use fallback parsing.
        """
        self.schema_loader = schema_loader

    def parse(self, message: MessageInstance) -> MessageInstance:
        """
        Parse message content with schema if available.

        Args:
            message: MessageInstance from envelope parser

        Returns:
            Updated MessageInstance with schema information attached
        """
        # Try to load schema
        schema = self._load_schema(message)

        if schema is None:
            # No schema available - use fallback parsing
            return self._fallback_parse(message)

        # Parse with schema
        return self._parse_with_schema(message, schema)

    def _load_schema(self, message: MessageInstance) -> "ResolvedMessageSpec | None":
        """
        Load schema for a message based on UNH S009 identifier.

        Args:
            message: MessageInstance with message_type, version, release

        Returns:
            ResolvedMessageSpec if found, None otherwise
        """
        if self.schema_loader is None:
            return None

        # Try exact message type (e.g., "INVOIC")
        try:
            if self.schema_loader.exists(message.message_type):
                return self.schema_loader.load(message.message_type)
        except Exception:
            pass

        return None

    def _parse_with_schema(
        self,
        message: MessageInstance,
        schema: "ResolvedMessageSpec",
    ) -> MessageInstance:
        """
        Parse message content using schema.

        This method:
        1. Builds group hierarchy from schema
        2. Creates GroupMatcher for segment matching
        3. Iterates through segments, organizing into groups
        4. Attaches schema definitions to segments/elements

        Args:
            message: MessageInstance with raw content
            schema: Resolved message schema

        Returns:
            Updated MessageInstance with organized content
        """
        # Build group hierarchy
        hierarchy = build_group_hierarchy(schema)
        matcher = GroupMatcher(hierarchy)

        # Collect all raw segments from content
        raw_segments = self._collect_raw_segments(message)

        # Track segment position for error reporting
        segment_position = 0

        # Build organized content with segment groups
        organized_content: list[ParsedSegment | SegmentGroupInstance] = []
        errors: list[ParseError] = []

        # Stack of active segment group instances
        # Each entry is (group_number, SegmentGroupInstance)
        group_stack: list[tuple[int | None, SegmentGroupInstance | None]] = []

        # Current group being populated (None = root level)
        current_group: SegmentGroupInstance | None = None

        for raw_seg in raw_segments:
            segment_position += 1

            # Match segment against schema
            match_result = matcher.match_segment(raw_seg.tag)

            # Create parsed segment with schema definition
            parsed_segment = self._attach_segment_definition(raw_seg, schema, segment_position)

            # Handle match result
            if match_result.action == MatchAction.ACCEPT:
                # Normal acceptance - add to current location
                matcher.advance_to(match_result)
                self._add_segment_to_current(parsed_segment, current_group, organized_content)

            elif match_result.action == MatchAction.ENTER_CHILD_GROUP:
                # Start a new child group
                matcher.advance_to(match_result)

                # Create new group instance
                new_group = SegmentGroupInstance(
                    group_number=match_result.group.group_number or 0,
                    iteration=1,
                )

                # Push current group onto stack
                if current_group is not None:
                    group_stack.append((current_group.group_number, current_group))
                else:
                    group_stack.append((None, None))

                # Add new group to appropriate parent
                if current_group is not None:
                    current_group.children.append(new_group)
                else:
                    organized_content.append(new_group)

                current_group = new_group

                # Add trigger segment to new group
                current_group.segments.append(parsed_segment)

            elif match_result.action == MatchAction.NEW_ITERATION:
                # Start new iteration of current group
                matcher.advance_to(match_result)

                if current_group is not None:
                    # Create new iteration
                    new_iteration = SegmentGroupInstance(
                        group_number=current_group.group_number,
                        iteration=current_group.iteration + 1,
                    )

                    # Add as sibling to current group
                    if group_stack:
                        parent_num, parent_group = group_stack[-1]
                        if parent_group is not None:
                            parent_group.children.append(new_iteration)
                        else:
                            organized_content.append(new_iteration)
                    else:
                        organized_content.append(new_iteration)

                    current_group = new_iteration
                    current_group.segments.append(parsed_segment)

            elif match_result.action == MatchAction.ACCEPT_OUT_OF_ORDER:
                # Segment in wrong order - accept with warning
                errors.append(
                    ParseError(
                        code="MSG01",
                        message=f"Segment {raw_seg.tag} out of expected order",
                        category=ErrorCategory.SCHEMA,
                        severity=ErrorSeverity.WARNING,
                        position=raw_seg.position,
                        segment_tag=raw_seg.tag,
                        segment_position=segment_position,
                    )
                )
                self._add_segment_to_current(parsed_segment, current_group, organized_content)

            elif match_result.action == MatchAction.POP_TO_PARENT:
                # Current group ended, return to parent
                matcher.advance_to(match_result)

                # Pop back up the stack
                for _ in range(match_result.levels_popped):
                    if group_stack:
                        _, parent_group = group_stack.pop()
                        current_group = parent_group

                # Add segment to new current location
                self._add_segment_to_current(parsed_segment, current_group, organized_content)

            elif match_result.action == MatchAction.ENTER_SIBLING_GROUP:
                # Pop current and enter sibling
                matcher.advance_to(match_result)

                # Pop back
                for _ in range(match_result.levels_popped):
                    if group_stack:
                        _, parent_group = group_stack.pop()
                        current_group = parent_group

                # Create new sibling group
                new_group = SegmentGroupInstance(
                    group_number=match_result.group.group_number or 0,
                    iteration=1,
                )

                # Push current onto stack
                if current_group is not None:
                    group_stack.append((current_group.group_number, current_group))
                    current_group.children.append(new_group)
                else:
                    group_stack.append((None, None))
                    organized_content.append(new_group)

                current_group = new_group
                current_group.segments.append(parsed_segment)

            elif match_result.action == MatchAction.UNKNOWN_SEGMENT:
                # Unknown segment - add with error
                errors.append(
                    ParseError(
                        code="MSG02",
                        message=f"Unexpected segment {raw_seg.tag}",
                        category=ErrorCategory.SCHEMA,
                        severity=ErrorSeverity.WARNING,
                        position=raw_seg.position,
                        segment_tag=raw_seg.tag,
                        segment_position=segment_position,
                        expected=", ".join(match_result.expected or []),
                    )
                )
                self._add_segment_to_current(parsed_segment, current_group, organized_content)

        # Update message with organized content
        message.content = organized_content
        message.errors.extend(errors)

        return message

    def _fallback_parse(self, message: MessageInstance) -> MessageInstance:
        """
        Parse message without schema (flat segment list).

        Simply converts existing parsed content to ensure consistent format.
        No segment groups are created, no schema definitions attached.

        Args:
            message: MessageInstance to parse

        Returns:
            MessageInstance with flat content (no segment groups)
        """
        # Content should already be ParsedSegments from envelope parser
        # Just ensure they're properly formatted
        flat_content: list[ParsedSegment | SegmentGroupInstance] = []

        for item in message.content:
            if isinstance(item, ParsedSegment):
                flat_content.append(item)
            elif isinstance(item, SegmentGroupInstance):
                # Flatten any groups (shouldn't happen from envelope parser)
                flat_content.extend(item.all_segments())

        message.content = flat_content
        return message

    def _collect_raw_segments(self, message: MessageInstance) -> list[RawSegment]:
        """
        Collect all raw segments from message content.

        Args:
            message: MessageInstance with content

        Returns:
            List of RawSegment objects
        """
        raw_segments: list[RawSegment] = []

        for item in message.content:
            if isinstance(item, ParsedSegment):
                raw_segments.append(item.raw)
            elif isinstance(item, SegmentGroupInstance):
                # Shouldn't happen from envelope parser, but handle it
                for seg in item.all_segments():
                    raw_segments.append(seg.raw)

        return raw_segments

    def _attach_segment_definition(
        self,
        raw_segment: RawSegment,
        schema: "ResolvedMessageSpec",
        position: int,
    ) -> ParsedSegment:
        """
        Create ParsedSegment with schema definition attached.

        Args:
            raw_segment: Raw segment from tokenizer
            schema: Resolved message schema
            position: Segment position in message

        Returns:
            ParsedSegment with definition and elements
        """
        # Get segment definition
        segment_def = schema.get_segment(raw_segment.tag)

        # Create parsed elements with definitions
        parsed_elements = self._attach_element_definitions(raw_segment, segment_def, schema)

        return ParsedSegment(
            tag=raw_segment.tag,
            elements=parsed_elements,
            raw=raw_segment,
            definition=segment_def,
            position_in_message=position,
        )

    def _attach_element_definitions(
        self,
        raw_segment: RawSegment,
        segment_def: "Segment | None",
        schema: "ResolvedMessageSpec",
    ) -> list[ParsedElement]:
        """
        Create ParsedElements with schema definitions attached.

        Args:
            raw_segment: Raw segment with elements
            segment_def: Segment definition (may be None)
            schema: Resolved message schema

        Returns:
            List of ParsedElement objects
        """
        parsed_elements: list[ParsedElement] = []

        for i, raw_elem in enumerate(raw_segment.elements):
            # Try to get element definition from segment
            elem_def = None
            element_definition = None
            composite_definition = None

            if segment_def is not None and i < len(segment_def.elements):
                elem_def = segment_def.elements[i]

                # Check if it's a composite or simple element
                # SegmentElement has: tag, is_composite, resolved
                if elem_def.is_composite:
                    # Use resolved if available, otherwise lookup by tag
                    if elem_def.resolved is not None:
                        composite_definition = elem_def.resolved
                    else:
                        composite_definition = schema.composites.get(elem_def.tag)
                else:
                    # Simple element
                    if elem_def.resolved is not None:
                        element_definition = elem_def.resolved
                    else:
                        element_definition = schema.elements.get(elem_def.tag)

            # Create parsed components if composite
            parsed_components = None
            if raw_elem.components:
                parsed_components = self._attach_component_definitions(
                    raw_elem.components,
                    composite_definition,
                    schema,
                )

            parsed_elements.append(
                ParsedElement(
                    raw=raw_elem,
                    definition=elem_def,
                    element_definition=element_definition,
                    composite_definition=composite_definition,
                    components=parsed_components,
                )
            )

        return parsed_elements

    def _attach_component_definitions(
        self,
        components: list,
        composite_def: "Composite | None",
        schema: "ResolvedMessageSpec",
    ) -> list[ParsedComponent]:
        """
        Create ParsedComponents with definitions attached.

        Args:
            components: List of RawComponent objects
            composite_def: Composite definition (may be None)
            schema: Resolved message schema

        Returns:
            List of ParsedComponent objects
        """
        parsed_components: list[ParsedComponent] = []

        for i, raw_comp in enumerate(components):
            comp_def = None
            element_def = None

            if composite_def is not None and i < len(composite_def.components):
                comp_def = composite_def.components[i]
                # Component has: element_tag, element (resolved)
                if comp_def.element is not None:
                    element_def = comp_def.element
                elif comp_def.element_tag:
                    element_def = schema.elements.get(comp_def.element_tag)

            parsed_components.append(
                ParsedComponent(
                    value=raw_comp.value,
                    raw=raw_comp,
                    definition=comp_def,
                    element_definition=element_def,
                )
            )

        return parsed_components

    def _add_segment_to_current(
        self,
        segment: ParsedSegment,
        current_group: SegmentGroupInstance | None,
        root_content: list[ParsedSegment | SegmentGroupInstance],
    ) -> None:
        """
        Add a parsed segment to the current location.

        Args:
            segment: Parsed segment to add
            current_group: Current segment group (None = root level)
            root_content: Root level content list
        """
        if current_group is not None:
            current_group.segments.append(segment)
        else:
            root_content.append(segment)


def parse_message(
    message: MessageInstance,
    schema_loader: "EdifactSchemaLoader | GeneratedEdifactSchemaLoader | None" = None,
) -> MessageInstance:
    """
    Convenience function to parse a message with schema.

    Args:
        message: MessageInstance from envelope parser
        schema_loader: Schema loader for loading schemas

    Returns:
        Updated MessageInstance with schema information
    """
    parser = EdifactMessageParser(schema_loader)
    return parser.parse(message)
