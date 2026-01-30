"""TXI (Tax) handler."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from box import Box

from edi_schema.semantic.mapping.segment_utils import get_element_value as _get_element_value
from edi_schema.semantic.mapping.handlers.base import HandlerContext, ensure_list

if TYPE_CHECKING:
    from edi_schema.x12.ast import ParsedSegment


class TXIHandler:
    """
    Handles TXI segments at both header and line level.

    Collects tax subtotals. At header level, multiple TXI segments are
    accumulated into a single TaxTotal. This handler processes one segment
    at a time and appends to the tax_total list.
    """

    def handle(
        self,
        segment: ParsedSegment,
        builder: Box,
        ctx: HandlerContext,
        *,
        item_prefix: str = "",
    ) -> None:
        tax_type = _get_element_value(segment, 1)
        amount_str = _get_element_value(segment, 2)
        if not amount_str:
            return

        try:
            amount = Decimal(amount_str)
        except Exception:
            return

        percent_str = _get_element_value(segment, 3)
        percent = None
        if percent_str:
            try:
                percent = Decimal(percent_str)
            except Exception:
                pass

        subtotal: dict = {
            "tax_amount": {"value": str(amount), "currency": "USD"},
        }
        if percent is not None:
            subtotal["percent"] = str(percent)
        if tax_type:
            subtotal["tax_category"] = {"id": tax_type}

        # We accumulate into a special key and resolve in post-processing
        path = f"{item_prefix}._txi_subtotals" if item_prefix else "_txi_subtotals"
        subtotals_list = ensure_list(builder, path)
        subtotals_list.append(subtotal)

        if ctx.metrics:
            ctx.metrics.fields_mapped += 1
