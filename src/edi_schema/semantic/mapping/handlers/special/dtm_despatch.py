"""DTM Despatch dates handler."""

from __future__ import annotations

from datetime import date as date_type
from typing import TYPE_CHECKING

from box import Box

from edi_schema.semantic.mapping.engine import _get_element_value
from edi_schema.semantic.mapping.handlers.base import HandlerContext, ensure_list, set_box_path

if TYPE_CHECKING:
    from edi_schema.x12.ast import ParsedSegment


class DTMDespatchHandler:
    """
    Handles despatch-related DTM qualifiers.

    DTM*010 -> delivery[0].despatch.requested_despatch_date
    DTM*037 -> delivery[0].despatch.earliest_despatch_date
    """

    _QUALIFIER_FIELD_MAP = {
        "010": "requested_despatch_date",
        "037": "earliest_despatch_date",
    }

    def handle(
        self,
        segment: ParsedSegment,
        builder: Box,
        ctx: HandlerContext,
    ) -> None:
        qualifier = _get_element_value(segment, 1)
        date_str = _get_element_value(segment, 2)

        if not qualifier or not date_str:
            return

        field_name = self._QUALIFIER_FIELD_MAP.get(qualifier)
        if not field_name:
            return

        # Ensure delivery[0] exists
        delivery_list = ensure_list(builder, "delivery")
        if not delivery_list:
            delivery_list.append(Box(default_box=True))

        # Parse CCYYMMDD format
        try:
            parsed_date = date_type(
                year=int(date_str[0:4]),
                month=int(date_str[4:6]),
                day=int(date_str[6:8]),
            )
        except (ValueError, IndexError):
            return

        set_box_path(
            builder,
            f"delivery[0].despatch.{field_name}",
            parsed_date.isoformat(),
            ctx,
        )

        if ctx.metrics:
            ctx.metrics.fields_mapped += 1
        if ctx.trace:
            ctx.trace.add_field(
                f"DTM*{qualifier}*02",
                f"delivery[0].despatch.{field_name}",
                str(parsed_date),
            )
