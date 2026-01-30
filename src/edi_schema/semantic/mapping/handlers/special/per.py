"""PER (Header-level Contact) handler."""

from __future__ import annotations

from typing import TYPE_CHECKING

from box import Box

from edi_schema.semantic.mapping.segment_utils import get_element_value as _get_element_value
from edi_schema.semantic.mapping.handlers.base import HandlerContext, set_box_path

if TYPE_CHECKING:
    from edi_schema.x12.ast import ParsedSegment


class HeaderPERHandler:
    """
    Handles header-level PER segments (outside N1 loops).

    Maps contact info based on qualifier:
    - PER*OC / PER*BD -> buyer_customer_party.buyer_contact
    - PER*IC -> accounting_customer_party.party.contact
    """

    def handle(
        self,
        segment: ParsedSegment,
        builder: Box,
        ctx: HandlerContext,
    ) -> None:
        qualifier = _get_element_value(segment, 1)
        name = _get_element_value(segment, 2)

        if not name:
            return

        # Build contact dict
        contact: dict = {"name": name}
        for i in range(3, 9, 2):
            qual = _get_element_value(segment, i)
            val = _get_element_value(segment, i + 1)
            if qual and val:
                if qual == "TE":
                    contact["telephone"] = val
                elif qual == "EM":
                    contact["electronic_mail"] = val
                elif qual == "FX":
                    contact["telefax"] = val

        if ctx.metrics:
            ctx.metrics.fields_mapped += 1

        # Map to appropriate model field based on qualifier
        if qualifier in ("OC", "BD"):
            _set_contact_dict(builder, "buyer_customer_party.buyer_contact", contact, ctx)
            if ctx.trace:
                ctx.trace.add_field(
                    f"PER*{qualifier}",
                    "buyer_customer_party.buyer_contact",
                    name,
                )
        elif qualifier == "IC":
            _set_contact_dict(builder, "accounting_customer_party.party.contact", contact, ctx)
            if ctx.trace:
                ctx.trace.add_field(
                    f"PER*{qualifier}",
                    "accounting_customer_party.party.contact",
                    name,
                )
        else:
            # Unknown qualifier - map to buyer party contact if not already set
            _set_contact_dict(builder, "buyer_customer_party.party.contact", contact, ctx)
            if ctx.trace:
                ctx.trace.add_field(
                    f"PER*{qualifier}",
                    "buyer_customer_party.party.contact",
                    name,
                )


def _set_contact_dict(builder: Box, path: str, contact: dict, ctx: HandlerContext) -> None:
    """Set contact fields at the given path."""
    for key, val in contact.items():
        set_box_path(builder, f"{path}.{key}", val, ctx)
