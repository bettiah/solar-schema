"""TDS (Total Monetary Value Summary) handler - 810 specific."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from box import Box

from edi_schema.semantic.mapping.segment_utils import get_element_value as _get_element_value
from edi_schema.semantic.mapping.handlers.base import HandlerContext, set_box_path

if TYPE_CHECKING:
    from edi_schema.x12.ast import ParsedSegment


class TDSHandler:
    """
    Handles TDS segment: maps total monetary values to legal_monetary_total.

    TDS amounts are in cents (2 implied decimal places), so we divide by 100.
    """

    def handle(
        self,
        segment: ParsedSegment,
        builder: Box,
        ctx: HandlerContext,
    ) -> None:
        total_str = _get_element_value(segment, 1)
        if not total_str:
            return

        try:
            total_value = Decimal(total_str) / Decimal("100")
        except Exception:
            return

        currency = builder.get("document_currency_code", "USD")
        if isinstance(currency, Box):
            currency = "USD"

        set_box_path(
            builder,
            "legal_monetary_total.payable_amount.value",
            str(total_value),
            ctx,
        )
        set_box_path(
            builder,
            "legal_monetary_total.payable_amount.currency",
            currency,
            ctx,
        )

        if ctx.metrics:
            ctx.metrics.fields_mapped += 1
        if ctx.trace:
            ctx.trace.add_field("TDS*01", "legal_monetary_total.payable_amount", str(total_value))

        # TDS*02 = Amount Subject to Terms Discount (optional)
        discount_str = _get_element_value(segment, 2)
        if discount_str:
            try:
                discount_value = Decimal(discount_str) / Decimal("100")
                set_box_path(
                    builder,
                    "legal_monetary_total.allowance_total_amount.value",
                    str(discount_value),
                    ctx,
                )
                set_box_path(
                    builder,
                    "legal_monetary_total.allowance_total_amount.currency",
                    currency,
                    ctx,
                )
                if ctx.metrics:
                    ctx.metrics.fields_mapped += 1
            except Exception:
                pass
