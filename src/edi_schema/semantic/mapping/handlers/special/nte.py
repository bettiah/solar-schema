"""NTE (Note/Special Instruction) handler - 810 specific."""

from __future__ import annotations

from typing import TYPE_CHECKING

from box import Box

from edi_schema.semantic.mapping.engine import _get_element_value
from edi_schema.semantic.mapping.handlers.base import HandlerContext, ensure_list

if TYPE_CHECKING:
    from edi_schema.x12.ast import ParsedSegment


class NTEHandler:
    """Handles NTE segments: appends note text to model.note list."""

    def handle(
        self,
        segment: ParsedSegment,
        builder: Box,
        ctx: HandlerContext,
    ) -> None:
        description = _get_element_value(segment, 2)
        if not description:
            return

        notes_list = ensure_list(builder, "note")
        notes_list.append(description)
        if ctx.metrics:
            ctx.metrics.fields_mapped += 1
        if ctx.trace:
            ctx.trace.add_field("NTE*02", "note[+]", description)
