"""
PartyLoopHandler - maps N1-style party loops to semantic party fields.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from box import Box

from edi_schema.semantic.mapping.engine import _get_element_value

from .base import HandlerContext, ensure_list, set_box_path

if TYPE_CHECKING:
    from edi_schema.semantic.mapping.types import PartyLoopMapping
    from edi_schema.x12.ast import LoopInstance


# N1*03 ID qualifier → scheme name
_ID_QUALIFIER_MAP = {
    "1": "DUNS",
    "9": "DUNS+4",
    "12": "Phone",
    "91": "SellerAssigned",
    "92": "BuyerAssigned",
    "ZZ": "MutuallyDefined",
}


class PartyLoopHandler:
    """
    Handles a PartyLoopMapping: reads N1*01 qualifier, resolves the
    target semantic path, and maps N1/N2/N3/N4/PER fields into the builder.
    """

    def __init__(self, mapping: PartyLoopMapping) -> None:
        self.mapping = mapping

    @property
    def loop_id(self) -> str:
        return self.mapping.loop_id

    def handle(
        self,
        loop: LoopInstance,
        builder: Box,
        ctx: HandlerContext,
    ) -> None:
        """Process one N1-style party loop."""
        # Find the N1 segment (trigger segment)
        n1_seg = None
        for seg in loop.segments:
            if seg.tag == self.mapping.loop_id:
                n1_seg = seg
                break

        if n1_seg is None:
            return

        party_code = _get_element_value(n1_seg, 1)
        if party_code is None or party_code not in self.mapping.party_field_map:
            return

        target_path = self.mapping.party_field_map[party_code]
        path_str = target_path.path

        if ctx.metrics:
            ctx.metrics.loop_iterations += 1

        # Determine the base path for this party
        base_path = self._resolve_party_base_path(path_str, builder, ctx)
        if base_path is None:
            return

        # Build the party data
        self._populate_party(loop, builder, ctx, base_path)

    def _resolve_party_base_path(
        self,
        path_str: str,
        builder: Box,
        ctx: HandlerContext,
    ) -> str | None:
        """Resolve the party target path, handling list append and indexed access."""
        if "[+]" in path_str:
            # e.g. "delivery[+].delivery_party"
            parts = path_str.split("[+]")
            list_path = parts[0]
            rest_path = parts[1].lstrip(".") if len(parts) > 1 else ""

            lst = ensure_list(builder, list_path)
            item = Box(default_box=True)
            lst.append(item)
            idx = len(lst) - 1

            if rest_path:
                return f"{list_path}[{idx}].{rest_path}"
            return f"{list_path}[{idx}]"

        elif "[0]" in path_str:
            # e.g. "delivery[0].despatch.despatch_party"
            # Ensure the list has at least one item
            import re

            match = re.match(r"(\w+)\[(\d+)\](.*)", path_str)
            if not match:
                return path_str

            list_name = match.group(1)
            index = int(match.group(2))
            rest = match.group(3).lstrip(".")

            lst = ensure_list(builder, list_name)
            while len(lst) <= index:
                lst.append(Box(default_box=True))

            if rest:
                return f"{list_name}[{index}].{rest}"
            return f"{list_name}[{index}]"

        else:
            # Direct path like "buyer_customer_party"
            return path_str

    def _populate_party(
        self,
        loop: LoopInstance,
        builder: Box,
        ctx: HandlerContext,
        base_path: str,
    ) -> None:
        """Populate party fields from N1/N2/N3/N4/PER segments."""
        # Determine party path: some paths end with e.g. "delivery_party"
        # which IS the party object. Others like "buyer_customer_party" need ".party"
        party_path = base_path
        if not base_path.endswith("_party") or any(
            k in base_path for k in ("customer_party", "supplier_party")
        ):
            # It's a wrapper (CustomerParty/SupplierParty) - nest under .party
            if "customer_party" in base_path or "supplier_party" in base_path:
                party_path = f"{base_path}.party"

        for seg in loop.segments:
            if seg.tag == "N1":
                self._map_n1(seg, builder, ctx, party_path, base_path)
            elif seg.tag == "N2":
                self._map_n2(seg, builder, ctx, party_path)
            elif seg.tag == "N3":
                self._map_n3(seg, builder, ctx, party_path)
            elif seg.tag == "N4":
                self._map_n4(seg, builder, ctx, party_path)
            elif seg.tag == "PER":
                self._map_per(seg, builder, ctx, party_path, base_path)

    def _map_n1(self, seg, builder, ctx, party_path, base_path):
        """Map N1 segment: name and identification."""
        name = _get_element_value(seg, 2)
        if name:
            names_list = ensure_list(builder, f"{party_path}.party_names")
            names_list.append({"name": name})
            if ctx.metrics:
                ctx.metrics.fields_mapped += 1
            if ctx.trace:
                ctx.trace.add_field("N1*02", f"{party_path}.party_names[+].name", name)

        id_qual = _get_element_value(seg, 3)
        id_val = _get_element_value(seg, 4)
        if id_val:
            scheme = _ID_QUALIFIER_MAP.get(id_qual, id_qual) if id_qual else None
            ids_list = ensure_list(builder, f"{party_path}.party_identifications")
            ids_list.append({"id": {"value": id_val, "scheme_id": scheme}})
            if ctx.metrics:
                ctx.metrics.fields_mapped += 1

    def _map_n2(self, seg, builder, ctx, party_path):
        """Map N2 segment: additional name."""
        name2 = _get_element_value(seg, 1)
        if name2:
            names_list = ensure_list(builder, f"{party_path}.party_names")
            names_list.append({"name": name2})
            if ctx.metrics:
                ctx.metrics.fields_mapped += 1

    def _map_n3(self, seg, builder, ctx, party_path):
        """Map N3 segment: street address."""
        street = _get_element_value(seg, 1)
        if street:
            set_box_path(builder, f"{party_path}.postal_address.street_name", street, ctx)
            if ctx.metrics:
                ctx.metrics.fields_mapped += 1

        street2 = _get_element_value(seg, 2)
        if street2:
            set_box_path(
                builder,
                f"{party_path}.postal_address.additional_street_name",
                street2,
                ctx,
            )
            if ctx.metrics:
                ctx.metrics.fields_mapped += 1

    def _map_n4(self, seg, builder, ctx, party_path):
        """Map N4 segment: city, state, zip, country."""
        city = _get_element_value(seg, 1)
        if city:
            set_box_path(builder, f"{party_path}.postal_address.city_name", city, ctx)
            if ctx.metrics:
                ctx.metrics.fields_mapped += 1

        state = _get_element_value(seg, 2)
        if state:
            set_box_path(builder, f"{party_path}.postal_address.country_subentity", state, ctx)
            if ctx.metrics:
                ctx.metrics.fields_mapped += 1

        postal = _get_element_value(seg, 3)
        if postal:
            set_box_path(builder, f"{party_path}.postal_address.postal_zone", postal, ctx)
            if ctx.metrics:
                ctx.metrics.fields_mapped += 1

        country = _get_element_value(seg, 4)
        if country:
            set_box_path(builder, f"{party_path}.postal_address.country_code", country, ctx)
            if ctx.metrics:
                ctx.metrics.fields_mapped += 1

    def _map_per(self, seg, builder, ctx, party_path, base_path):
        """Map PER segment: contact information."""
        contact_name = _get_element_value(seg, 2)
        if not contact_name:
            return

        contact_path = f"{party_path}.contact"
        set_box_path(builder, f"{contact_path}.name", contact_name, ctx)
        if ctx.metrics:
            ctx.metrics.fields_mapped += 1

        # PER*03-08 are qualifier/value pairs
        for i in range(3, 9, 2):
            qual = _get_element_value(seg, i)
            val = _get_element_value(seg, i + 1)
            if qual and val:
                if qual == "TE":
                    set_box_path(builder, f"{contact_path}.telephone", val, ctx)
                elif qual == "EM":
                    set_box_path(builder, f"{contact_path}.electronic_mail", val, ctx)
                elif qual == "FX":
                    set_box_path(builder, f"{contact_path}.telefax", val, ctx)
                if ctx.metrics:
                    ctx.metrics.fields_mapped += 1

        # Also set buyer_contact/seller_contact on the wrapper
        if "customer_party" in base_path:
            set_box_path(builder, f"{base_path}.buyer_contact.name", contact_name, ctx)
            for i in range(3, 9, 2):
                qual = _get_element_value(seg, i)
                val = _get_element_value(seg, i + 1)
                if qual and val:
                    if qual == "TE":
                        set_box_path(builder, f"{base_path}.buyer_contact.telephone", val, ctx)
                    elif qual == "EM":
                        set_box_path(
                            builder,
                            f"{base_path}.buyer_contact.electronic_mail",
                            val,
                            ctx,
                        )
                    elif qual == "FX":
                        set_box_path(builder, f"{base_path}.buyer_contact.telefax", val, ctx)

        # Copy postal_address to delivery_location for delivery parties
        if base_path.endswith("delivery_party"):
            # The delivery_location is a sibling of delivery_party
            delivery_item_path = base_path.rsplit(".", 1)[0] if "." in base_path else ""
            if delivery_item_path:
                # We'll copy postal_address fields after N3/N4 have been set
                # This is handled in the engine's post-processing
                pass
