"""AMT (Monetary Totals) handler."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from box import Box

from edi_schema.semantic.mapping.engine import _get_element_value
from edi_schema.semantic.mapping.handlers.base import HandlerContext, set_box_path

if TYPE_CHECKING:
    from edi_schema.x12.ast import ParsedSegment


class AMTHandler:
    """
    Handles AMT segments: maps AMT*TT to anticipated_monetary_total.payable_amount.
    """

    def handle(
        self,
        segment: ParsedSegment,
        builder: Box,
        ctx: HandlerContext,
    ) -> None:
        qualifier = _get_element_value(segment, 1)
        amount_str = _get_element_value(segment, 2)

        if qualifier != "TT" or not amount_str:
            return

        try:
            amount_value = Decimal(amount_str)
        except Exception:
            return

        # Get currency from builder or default to USD
        currency = builder.get("document_currency_code", "USD")
        if isinstance(currency, Box):
            currency = "USD"

        set_box_path(
            builder,
            "anticipated_monetary_total.payable_amount.value",
            str(amount_value),
            ctx,
        )
        set_box_path(
            builder,
            "anticipated_monetary_total.payable_amount.currency",
            currency,
            ctx,
        )

        if ctx.metrics:
            ctx.metrics.fields_mapped += 1
        if ctx.trace:
            ctx.trace.add_field(
                "AMT*TT*02",
                "anticipated_monetary_total.payable_amount",
                amount_str,
            )
