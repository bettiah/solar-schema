"""
QualifiedMappingHandler - maps qualified segments (DTM, REF) by qualifier value.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from box import Box

from edi_schema.semantic.mapping.segment_utils import get_element_value as _get_element_value
from edi_schema.semantic.mapping.errors import MappingErrorCode

from .base import HandlerContext, set_box_path
from .field import handle_field_in_loop

if TYPE_CHECKING:
    from edi_schema.semantic.mapping.types import QualifiedMapping, SegmentPath
    from edi_schema.x12.ast import ParsedSegment


class QualifiedMappingHandler:
    """
    Handles a QualifiedMapping: reads a qualifier element from a segment,
    looks up sub-mappings, and applies each.
    """

    def __init__(self, mapping: QualifiedMapping) -> None:
        self.mapping = mapping

    @property
    def segment_tag(self) -> str:
        return self.mapping.qualifier_path.segment

    def handle(
        self,
        segment: ParsedSegment,
        builder: Box,
        ctx: HandlerContext,
    ) -> None:
        """Process a qualified segment at header level."""
        self._apply(segment, builder, ctx, prefix="")

    def handle_in_loop(
        self,
        segment: ParsedSegment,
        builder: Box,
        ctx: HandlerContext,
        prefix: str,
    ) -> None:
        """Process a qualified segment within a loop item context."""
        self._apply(segment, builder, ctx, prefix=prefix)

    def _apply(
        self,
        segment: ParsedSegment,
        builder: Box,
        ctx: HandlerContext,
        prefix: str,
    ) -> None:
        qualifier_path = self.mapping.qualifier_path
        qualifier_elem = qualifier_path.element or 1
        qualifier_value = _get_element_value(segment, qualifier_elem)

        if qualifier_value is None:
            return

        if qualifier_value not in self.mapping.mappings:
            # Track unmapped qualifiers
            if ctx.metrics:
                ctx.metrics.record_unmapped_qualifier(qualifier_path.segment, qualifier_value)
            return

        # Apply each field mapping for this qualifier
        field_mappings = self.mapping.mappings[qualifier_value]
        for fm in field_mappings:
            from edi_schema.semantic.mapping.types import SegmentPath

            if not isinstance(fm.x12, SegmentPath):
                continue

            path = fm.x12
            value = None
            if path.element:
                value = _get_element_value(segment, path.element)

            if value is None:
                if ctx.metrics:
                    ctx.metrics.fields_skipped += 1
                continue

            # Apply transform
            if fm.to_semantic_transform:
                try:
                    value = fm.to_semantic_transform.to_semantic(value)
                    if ctx.metrics:
                        ctx.metrics.transforms_applied += 1
                except Exception as e:
                    ctx.accumulator.add_warning(
                        MappingErrorCode.TRANSFORM_FAILED,
                        f"Transform failed: {e}",
                        source_path=str(path),
                        target_path=fm.semantic.path,
                        value=value,
                    )
                    continue

            # Write to builder
            full_path = f"{prefix}.{fm.semantic.path}" if prefix else fm.semantic.path
            set_box_path(builder, full_path, value, ctx)
            if ctx.metrics:
                ctx.metrics.fields_mapped += 1
            if ctx.trace:
                source = f"{path.segment}[{qualifier_value}]*{path.element}"
                ctx.trace.add_field(source, full_path, value)
