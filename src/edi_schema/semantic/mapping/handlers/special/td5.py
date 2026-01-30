"""TD5 (Carrier/Shipping) handler."""

from __future__ import annotations

from typing import TYPE_CHECKING

from box import Box

from edi_schema.semantic.mapping.segment_utils import get_element_value as _get_element_value
from edi_schema.semantic.mapping.handlers.base import HandlerContext, ensure_list, set_box_path

if TYPE_CHECKING:
    from edi_schema.x12.ast import ParsedSegment


class TD5Handler:
    """
    Handles TD5 segment: maps carrier/shipping info to delivery[0].shipment.

    TD5*02/03 -> carrier_party identification
    TD5*04 -> transport_mode_code
    TD5*05 -> transit_direction_code
    TD5*12 -> shipping_priority_level_code
    """

    def handle(
        self,
        segment: ParsedSegment,
        builder: Box,
        ctx: HandlerContext,
    ) -> None:
        id_qual = _get_element_value(segment, 2)
        carrier_id = _get_element_value(segment, 3)
        transport_mode = _get_element_value(segment, 4)
        routing = _get_element_value(segment, 5)
        service_level = _get_element_value(segment, 12)

        if not any([id_qual, carrier_id, transport_mode, routing, service_level]):
            return

        # Ensure delivery[0] exists
        delivery_list = ensure_list(builder, "delivery")
        if not delivery_list:
            delivery_list.append(Box(default_box=True))

        base = "delivery[0].shipment"

        if carrier_id:
            scheme_id = id_qual or "SCAC"
            ids_list = ensure_list(builder, f"{base}.carrier_party.party_identifications")
            ids_list.append({"id": {"value": carrier_id, "scheme_id": scheme_id}})
            if ctx.metrics:
                ctx.metrics.fields_mapped += 2
            if ctx.trace:
                ctx.trace.add_field("TD5*02", f"{base}.carrier_party.party_identifications[0].id.scheme_id", scheme_id)
                ctx.trace.add_field("TD5*03", f"{base}.carrier_party.party_identifications[0].id.value", carrier_id)

        if transport_mode:
            stages = ensure_list(builder, f"{base}.shipment_stages")
            if not stages:
                stages.append(Box(default_box=True))
            set_box_path(builder, f"{base}.shipment_stages[0].transport_mode_code", transport_mode, ctx)
            if ctx.metrics:
                ctx.metrics.fields_mapped += 1
            if ctx.trace:
                ctx.trace.add_field("TD5*04", f"{base}.shipment_stages[0].transport_mode_code", transport_mode)

        if routing:
            stages = ensure_list(builder, f"{base}.shipment_stages")
            if not stages:
                stages.append(Box(default_box=True))
            set_box_path(builder, f"{base}.shipment_stages[0].transit_direction_code", routing, ctx)
            if ctx.metrics:
                ctx.metrics.fields_mapped += 1
            if ctx.trace:
                ctx.trace.add_field("TD5*05", f"{base}.shipment_stages[0].transit_direction_code", routing)

        if service_level:
            set_box_path(builder, f"{base}.shipping_priority_level_code", service_level, ctx)
            if ctx.metrics:
                ctx.metrics.fields_mapped += 1
            if ctx.trace:
                ctx.trace.add_field("TD5*12", f"{base}.shipping_priority_level_code", service_level)
