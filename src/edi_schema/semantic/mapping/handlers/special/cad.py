"""CAD (Carrier Detail) handler - 810 specific."""

from __future__ import annotations

from typing import TYPE_CHECKING

from box import Box

from edi_schema.semantic.mapping.segment_utils import get_element_value as _get_element_value
from edi_schema.semantic.mapping.handlers.base import HandlerContext, ensure_list, set_box_path

if TYPE_CHECKING:
    from edi_schema.x12.ast import ParsedSegment


class CADHandler:
    """
    Handles CAD segment: maps carrier details to delivery[0].shipment.

    CAD*01 -> transport_mode_code
    CAD*04 -> carrier SCAC
    CAD*05 -> routing
    CAD*07/08 -> Bill of Lading reference
    CAD*09 -> service_level_code
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

        base = "delivery[0].shipment"

        transport_method = _get_element_value(segment, 1)
        if transport_method:
            stages = ensure_list(builder, f"{base}.shipment_stages")
            if not stages:
                stages.append(Box(default_box=True))
            set_box_path(builder, f"{base}.shipment_stages[0].transport_mode_code", transport_method, ctx)
            if ctx.metrics:
                ctx.metrics.fields_mapped += 1
            if ctx.trace:
                ctx.trace.add_field("CAD*01", f"{base}.shipment_stages[0].transport_mode_code", transport_method)

        scac = _get_element_value(segment, 4)
        if scac:
            ids_list = ensure_list(builder, f"{base}.carrier_party.party_identifications")
            ids_list.append({"id": {"value": scac, "scheme_id": "SCAC"}})
            if ctx.metrics:
                ctx.metrics.fields_mapped += 1
            if ctx.trace:
                ctx.trace.add_field("CAD*04", f"{base}.carrier_party", scac)

        routing = _get_element_value(segment, 5)
        if routing:
            stages = ensure_list(builder, f"{base}.shipment_stages")
            if not stages:
                stages.append(Box(default_box=True))
            set_box_path(builder, f"{base}.shipment_stages[0].transit_direction_code", routing, ctx)
            if ctx.metrics:
                ctx.metrics.fields_mapped += 1

        # CAD*07/08 = Reference qualifier/ID (Bill of Lading)
        ref_qual = _get_element_value(segment, 7)
        ref_id = _get_element_value(segment, 8)
        if ref_id and ref_qual == "BM":
            set_box_path(builder, "despatch_document_reference.id", ref_id, ctx)
            if ctx.metrics:
                ctx.metrics.fields_mapped += 1
            if ctx.trace:
                ctx.trace.add_field("CAD*08", "despatch_document_reference.id", ref_id)

        service_level = _get_element_value(segment, 9)
        if service_level:
            set_box_path(builder, f"{base}.shipping_priority_level_code", service_level, ctx)
            if ctx.metrics:
                ctx.metrics.fields_mapped += 1
