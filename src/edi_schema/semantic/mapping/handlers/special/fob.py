"""FOB (Delivery Terms) handler."""

from __future__ import annotations

from typing import TYPE_CHECKING

from box import Box

from edi_schema.semantic.mapping.segment_utils import get_element_value as _get_element_value
from edi_schema.semantic.mapping.handlers.base import HandlerContext, ensure_list, set_box_path

if TYPE_CHECKING:
    from edi_schema.x12.ast import ParsedSegment


class FOBHandler:
    """
    Handles FOB segment: maps delivery terms to delivery[0].

    FOB*02 -> loss_risk_responsibility_code
    FOB*03 -> special_terms
    FOB*05 -> delivery_terms.id (incoterms)
    """

    def handle(
        self,
        segment: ParsedSegment,
        builder: Box,
        ctx: HandlerContext,
    ) -> None:
        # Ensure delivery[0] exists
        delivery_list = ensure_list(builder, "delivery")
        if not delivery_list:
            delivery_list.append(Box(default_box=True))

        base = "delivery[0].delivery_terms"

        location_qual = _get_element_value(segment, 2)
        if location_qual:
            set_box_path(builder, f"{base}.loss_risk_responsibility_code", location_qual, ctx)
            if ctx.metrics:
                ctx.metrics.fields_mapped += 1
            if ctx.trace:
                ctx.trace.add_field("FOB*02", f"{base}.loss_risk_responsibility_code", location_qual)

        description = _get_element_value(segment, 3)
        if description:
            set_box_path(builder, f"{base}.special_terms", description, ctx)
            if ctx.metrics:
                ctx.metrics.fields_mapped += 1
            if ctx.trace:
                ctx.trace.add_field("FOB*03", f"{base}.special_terms", description)

        incoterms = _get_element_value(segment, 5)
        if incoterms:
            set_box_path(builder, f"{base}.id", incoterms, ctx)
            if ctx.metrics:
                ctx.metrics.fields_mapped += 1
            if ctx.trace:
                ctx.trace.add_field("FOB*05", f"{base}.id", incoterms)
