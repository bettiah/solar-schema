"""MSG (Notes) handler."""

from __future__ import annotations

from typing import TYPE_CHECKING

from box import Box

from edi_schema.semantic.mapping.segment_utils import get_element_value as _get_element_value
from edi_schema.semantic.mapping.handlers.base import HandlerContext, ensure_list

if TYPE_CHECKING:
    from edi_schema.x12.ast import ParsedSegment


class MSGHandler:
    """Handles MSG segments: appends note text to model.note list."""

    def handle(
        self,
        segment: ParsedSegment,
        builder: Box,
        ctx: HandlerContext,
    ) -> None:
        note_text = _get_element_value(segment, 1)
        if not note_text:
            return

        notes_list = ensure_list(builder, "note")
        notes_list.append(note_text)
        if ctx.metrics:
            ctx.metrics.fields_mapped += 1
        if ctx.trace:
            ctx.trace.add_field("MSG*01", f"note[{len(notes_list) - 1}]", note_text)
