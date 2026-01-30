"""
FieldMappingHandler - maps a single FieldMapping from segment to builder.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from box import Box

from edi_schema.semantic.mapping.engine import _get_composite_component, _get_element_value
from edi_schema.semantic.mapping.errors import MappingErrorCode
from edi_schema.semantic.mapping.types import EnvelopePath, SegmentPath

from .base import HandlerContext, set_box_path

if TYPE_CHECKING:
    from edi_schema.semantic.mapping.types import FieldMapping
    from edi_schema.x12.ast import ParsedSegment


class FieldMappingHandler:
    """
    Handles a single FieldMapping: extracts a value from a segment,
    applies an optional transform, and writes to the builder.
    """

    def __init__(self, mapping: FieldMapping) -> None:
        self.mapping = mapping

    @property
    def segment_tag(self) -> str:
        """The segment tag this handler responds to."""
        if isinstance(self.mapping.x12, SegmentPath):
            return self.mapping.x12.segment
        return ""

    def handle(
        self,
        segment: ParsedSegment,
        builder: Box,
        ctx: HandlerContext,
    ) -> None:
        """Extract value from segment and set on builder."""
        path = self.mapping.x12
        if not isinstance(path, SegmentPath):
            return

        # Check qualifier match if specified
        if path.qualifier:
            elem_idx, expected_value = path.qualifier
            actual = _get_element_value(segment, elem_idx)
            if actual != expected_value:
                return

        # Extract value
        value: Any = None
        if path.element is not None:
            if path.component:
                value = _get_composite_component(segment, path.element, path.component)
            else:
                value = _get_element_value(segment, path.element)

        if value is None and self.mapping.default is not None:
            value = self.mapping.default
            if ctx.metrics:
                ctx.metrics.fields_defaulted += 1

        if value is None:
            if self.mapping.required and ctx.accumulator:
                ctx.accumulator.add(
                    MappingErrorCode.REQUIRED_FIELD_MISSING,
                    f"Required field {path} is missing",
                    source_path=str(path),
                    target_path=self.mapping.semantic.path,
                )
            if ctx.metrics:
                ctx.metrics.fields_skipped += 1
            return

        # Apply transform
        if self.mapping.to_semantic_transform:
            try:
                value = self.mapping.to_semantic_transform.to_semantic(value)
                if ctx.metrics:
                    ctx.metrics.transforms_applied += 1
            except Exception as e:
                if self.mapping.fallback is not None:
                    value = self.mapping.fallback
                else:
                    ctx.accumulator.add_warning(
                        MappingErrorCode.TRANSFORM_FAILED,
                        f"Transform failed: {e}",
                        source_path=str(path),
                        target_path=self.mapping.semantic.path,
                        value=value,
                    )
                    if ctx.metrics:
                        ctx.metrics.fields_skipped += 1
                    return

        # Write to builder
        set_box_path(builder, self.mapping.semantic.path, value, ctx)
        if ctx.metrics:
            ctx.metrics.fields_mapped += 1
        if ctx.trace:
            ctx.trace.add_field(str(path), self.mapping.semantic.path, value)


def handle_field_in_loop(
    mapping: FieldMapping,
    segment: ParsedSegment,
    builder: Box,
    ctx: HandlerContext,
    prefix: str,
) -> None:
    """
    Handle a field mapping within a loop context.

    The semantic path is prefixed with the loop item path, e.g.
    prefix="order_lines[0]" + mapping.semantic.path="id" -> "order_lines[0].id"
    """
    path = mapping.x12
    if not isinstance(path, SegmentPath):
        return

    # Check qualifier match if specified
    if path.qualifier:
        elem_idx, expected_value = path.qualifier
        actual = _get_element_value(segment, elem_idx)
        if actual != expected_value:
            return

    # Extract value
    value: Any = None
    if path.element is not None:
        if path.component:
            value = _get_composite_component(segment, path.element, path.component)
        else:
            value = _get_element_value(segment, path.element)

    if value is None and mapping.default is not None:
        value = mapping.default
        if ctx.metrics:
            ctx.metrics.fields_defaulted += 1

    if value is None:
        if ctx.metrics:
            ctx.metrics.fields_skipped += 1
        return

    # Apply transform
    if mapping.to_semantic_transform:
        try:
            value = mapping.to_semantic_transform.to_semantic(value)
            if ctx.metrics:
                ctx.metrics.transforms_applied += 1
        except Exception:
            if mapping.fallback is not None:
                value = mapping.fallback
            else:
                if ctx.metrics:
                    ctx.metrics.fields_skipped += 1
                return

    # Write to builder with prefix
    full_path = f"{prefix}.{mapping.semantic.path}" if prefix else mapping.semantic.path
    set_box_path(builder, full_path, value, ctx)
    if ctx.metrics:
        ctx.metrics.fields_mapped += 1
    if ctx.trace:
        ctx.trace.add_field(str(path), full_path, value)
