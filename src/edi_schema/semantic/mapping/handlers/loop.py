"""
LoopItemHandler - maps a repeating loop to a list in the builder.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from box import Box

from edi_schema.semantic.mapping.engine import _get_element_value
from edi_schema.semantic.mapping.types import SegmentPath

from .base import HandlerContext, ensure_list, set_box_path
from .field import handle_field_in_loop

if TYPE_CHECKING:
    from edi_schema.semantic.mapping.types import LoopMapping, QualifiedMapping
    from edi_schema.x12.ast import LoopInstance


class LoopItemHandler:
    """
    Handles a LoopMapping: for each loop occurrence, creates a list entry
    in the builder and maps field/qualified/nested loop content into it.
    """

    def __init__(
        self,
        mapping: LoopMapping,
        *,
        line_special_handlers: dict[str, list] | None = None,
    ) -> None:
        self.mapping = mapping
        # Special handlers invoked per line-item (e.g. SAC, TXI within PO1/IT1)
        self.line_special_handlers = line_special_handlers or {}

    @property
    def loop_id(self) -> str:
        return self.mapping.loop_id

    def handle(
        self,
        loop: LoopInstance,
        builder: Box,
        ctx: HandlerContext,
    ) -> None:
        """Process one loop occurrence, adding an item to the target list."""
        list_path = self.mapping.semantic_path.path

        # Ensure the target is a Python list
        target_list = ensure_list(builder, list_path)

        # Create a new Box for this item
        item = Box(default_box=True)
        idx = len(target_list)
        target_list.append(item)

        prefix = f"{list_path}[{idx}]"

        if ctx.metrics:
            ctx.metrics.loop_iterations += 1

        # Map field mappings
        for fm in self.mapping.field_mappings:
            if not isinstance(fm.x12, SegmentPath):
                continue
            seg = _find_segment_in_loop(loop, fm.x12)
            if seg is not None:
                handle_field_in_loop(fm, seg, builder, ctx, prefix)

        # Map qualified mappings
        from .qualified import QualifiedMappingHandler

        for qm in self.mapping.qualified_mappings:
            handler = QualifiedMappingHandler(qm)
            for seg in loop.segments:
                if seg.tag == qm.qualifier_path.segment:
                    handler.handle_in_loop(seg, builder, ctx, prefix)

        # Map nested loops
        for nested_mapping in self.mapping.nested_loops:
            nested_handler = LoopItemHandler(nested_mapping)
            # Find nested loop instances within this loop's children
            for child in getattr(loop, "children", []):
                if hasattr(child, "loop_id") and child.loop_id == nested_mapping.loop_id:
                    nested_handler.handle(child, builder, ctx)

        # Invoke line-level special handlers
        for seg in loop.segments:
            tag = seg.tag
            if tag in self.line_special_handlers:
                for special in self.line_special_handlers[tag]:
                    special.handle(seg, builder, ctx, item_prefix=prefix)

        # Handle product IDs (PO1/IT1 elements 6-25)
        if self.mapping.loop_id in ("PO1", "IT1"):
            _extract_product_ids(loop, builder, ctx, prefix, self.mapping.loop_id)

        # Handle SCH segments (delivery schedule) for PO1 loops
        if self.mapping.loop_id == "PO1":
            _extract_sch_segments(loop, builder, ctx, prefix)


def _find_segment_in_loop(loop: LoopInstance, path: SegmentPath) -> Any:
    """Find a segment in a loop matching a SegmentPath."""
    for seg in loop.segments:
        if seg.tag != path.segment:
            continue
        if path.qualifier:
            elem_idx, expected = path.qualifier
            actual = _get_element_value(seg, elem_idx)
            if actual != expected:
                continue
        return seg
    return None


# =============================================================================
# Product ID extraction (PO1/IT1 elements 6-25)
# =============================================================================

_PRODUCT_ID_QUALIFIER_MAP = {
    "UP": ("standard", "UPC"),
    "EN": ("standard", "EAN"),
    "UK": ("standard", "UCC/EAN-128"),
    "UA": ("standard", "UPC-A"),
    "UI": ("standard", "UPC-I"),
    "VP": ("sellers", None),
    "SK": ("sellers", None),
    "VN": ("sellers", None),
    "BP": ("buyers", None),
    "IN": ("buyers", None),
    "MG": ("manufacturers", None),
    "MN": ("manufacturers", None),
    "SN": ("additional", "Serial"),
    "PN": ("additional", "PartNumber"),
    "CB": ("additional", "BuyerCatalog"),
    "CG": ("additional", "SellerCatalog"),
    "EC": ("additional", "EngineeringChange"),
    "PL": ("additional", "PurchaseOrder"),
    "ZZ": ("additional", "MutuallyDefined"),
}

# Tracks which field_type has been used so we know to append to additional
_SINGULAR_FIELDS = {"standard", "sellers", "buyers", "manufacturers"}


def _extract_product_ids(
    loop: LoopInstance,
    builder: Box,
    ctx: HandlerContext,
    prefix: str,
    trigger_tag: str,
) -> None:
    """Extract product ID pairs from PO1/IT1 elements 6-25."""
    trigger_seg = None
    for seg in loop.segments:
        if seg.tag == trigger_tag:
            trigger_seg = seg
            break

    if trigger_seg is None:
        return

    # Track which singular fields have been set
    used_fields: set[str] = set()

    for i in range(6, 26, 2):
        qualifier = _get_element_value(trigger_seg, i)
        value = _get_element_value(trigger_seg, i + 1)

        if not qualifier or not value:
            continue

        field_type, scheme = _PRODUCT_ID_QUALIFIER_MAP.get(qualifier, ("additional", None))
        scheme_id = scheme or qualifier

        # Determine target path
        if field_type in _SINGULAR_FIELDS and field_type not in used_fields:
            used_fields.add(field_type)
            target = f"{prefix}.item.{field_type}_item_identification"
        else:
            # Append to additional_item_identifications list
            items_list = ensure_list(builder, f"{prefix}.item.additional_item_identifications")
            items_list.append({"id": {"value": value, "scheme_id": scheme_id}})
            if ctx.metrics:
                ctx.metrics.fields_mapped += 1
            continue

        set_box_path(builder, f"{target}.id.value", value, ctx)
        set_box_path(builder, f"{target}.id.scheme_id", scheme_id, ctx)
        if ctx.metrics:
            ctx.metrics.fields_mapped += 1
        if ctx.trace:
            ctx.trace.add_field(
                f"{trigger_tag}*{i:02d}/*{i + 1:02d}",
                f"item.{field_type}_item_identification",
                value,
            )


def _extract_sch_segments(
    loop: LoopInstance,
    builder: Box,
    ctx: HandlerContext,
    prefix: str,
) -> None:
    """Extract SCH (delivery schedule) segments for line items."""
    from datetime import date

    for seg in loop.segments:
        if seg.tag != "SCH":
            continue

        qty_str = _get_element_value(seg, 1)
        if not qty_str:
            continue

        from decimal import Decimal

        try:
            qty_value = Decimal(qty_str)
        except Exception:
            continue

        uom = _get_element_value(seg, 2) or "EA"
        date_str = _get_element_value(seg, 6)

        delivery_list = ensure_list(builder, f"{prefix}.delivery")
        delivery_item: dict[str, Any] = {
            "quantity": {"value": str(qty_value), "unit_code": uom},
        }

        if date_str and len(date_str) >= 8:
            try:
                parsed_date = date(
                    int(date_str[0:4]),
                    int(date_str[4:6]),
                    int(date_str[6:8]),
                )
                delivery_item["requested_delivery_period"] = {
                    "start_date": parsed_date.isoformat(),
                }
            except Exception:
                pass

        delivery_list.append(delivery_item)
        if ctx.metrics:
            ctx.metrics.fields_mapped += 1
