"""SAC (Allowance/Charge) handler."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from box import Box

from edi_schema.semantic.mapping.segment_utils import get_element_value as _get_element_value
from edi_schema.semantic.mapping.handlers.base import HandlerContext, ensure_list

if TYPE_CHECKING:
    from edi_schema.x12.ast import ParsedSegment


class SACHandler:
    """Handles SAC segments at both header and line level."""

    def handle(
        self,
        segment: ParsedSegment,
        builder: Box,
        ctx: HandlerContext,
        *,
        item_prefix: str = "",
    ) -> None:
        indicator = _get_element_value(segment, 1)
        if indicator not in ("A", "C"):
            return

        code = _get_element_value(segment, 2)
        amount_str = _get_element_value(segment, 5)
        if not amount_str:
            return

        try:
            amount_value = Decimal(amount_str)
        except Exception:
            return

        description = _get_element_value(segment, 12)
        percent_str = _get_element_value(segment, 15)
        percent = None
        if percent_str:
            try:
                percent = Decimal(percent_str)
            except Exception:
                pass

        charge_dict: dict = {
            "charge_indicator": indicator == "C",
            "allowance_charge_reason_code": code,
            "allowance_charge_reason": description,
            "amount": {"value": str(amount_value), "currency": "USD"},
        }
        if percent is not None:
            charge_dict["multiplier_factor_numeric"] = str(percent)

        path = f"{item_prefix}.allowance_charges" if item_prefix else "allowance_charges"
        charges_list = ensure_list(builder, path)
        charges_list.append(charge_dict)

        if ctx.metrics:
            ctx.metrics.fields_mapped += 1
        if ctx.trace:
            label = "SAC (line)" if item_prefix else "SAC"
            ctx.trace.add_field(label, f"{path}[+]", str(charge_dict))
