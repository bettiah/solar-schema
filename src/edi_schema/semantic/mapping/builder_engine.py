"""
Builder Mapping Engine - Single-pass mapping using Box dict accumulator.

Replaces the multi-phase MappingEngine with a single forward pass through
content, dispatching each segment/loop to registered handlers. The Pydantic
model is built once at the end via model_validate(dict).
"""

from __future__ import annotations

import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, TypeVar

from box import Box

from .context import MessageContext
from .diagnostics import AggregateMetrics, MappingLogger, MappingMetrics, MappingTrace
from .engine import (
    _get_element_value,
    find_all_loops,
)
from .errors import (
    ErrorAccumulator,
    ErrorHandlingMode,
    MappingError,
    MappingErrorCode,
    MappingErrorSeverity,
    MappingException,
)
from .handlers.base import (
    HandlerContext,
    ensure_list,
    set_box_path,
    strip_empty_boxes,
)
from .handlers.field import FieldMappingHandler
from .handlers.loop import LoopItemHandler
from .handlers.party import PartyLoopHandler
from .handlers.qualified import QualifiedMappingHandler
from .handlers.registry import HANDLER_REGISTRY, LINE_HANDLER_REGISTRY
from .result import MappingResult
from .types import (
    ContextPath,
    EnvelopePath,
    FieldMapping,
    SegmentPath,
    TransactionMapping,
)

if TYPE_CHECKING:
    from edi_schema.x12.ast import LoopInstance, ParsedSegment, TransactionSetInstance

T = TypeVar("T")


class BuilderMappingEngine:
    """
    Single-pass mapping engine using Box dict accumulator.

    Builds a plain dict via Box auto-vivification, then calls
    model_validate(dict) once at the end to produce the Pydantic model.
    """

    def __init__(
        self,
        mapping: TransactionMapping,
        error_mode: ErrorHandlingMode = ErrorHandlingMode.LENIENT,
        collect_metrics: bool = True,
        debug_mode: bool = False,
        warn_on_unmapped: bool = True,
    ) -> None:
        self.mapping = mapping
        self.error_mode = error_mode
        self.collect_metrics = collect_metrics
        self.debug_mode = debug_mode
        self.warn_on_unmapped = warn_on_unmapped
        self.logger = MappingLogger()

        # Metrics collector
        self.aggregate_metrics = AggregateMetrics() if collect_metrics else None

        # Build dispatch tables once
        self._segment_dispatch = self._build_segment_dispatch()
        self._loop_dispatch = self._build_loop_dispatch()

    # =========================================================================
    # Dispatch table construction
    # =========================================================================

    def _build_segment_dispatch(self) -> dict[str, list]:
        """
        Build dispatch table for top-level segments.

        Maps segment tag -> list of handlers (FieldMappingHandler, QualifiedMappingHandler,
        or special handlers from the registry).
        """
        table: dict[str, list] = {}

        # Field mappings -> FieldMappingHandler per segment tag
        for fm in self.mapping.field_mappings:
            if isinstance(fm.x12, SegmentPath):
                tag = fm.x12.segment
                handler = FieldMappingHandler(fm)
                table.setdefault(tag, []).append(handler)

        # Qualified mappings -> QualifiedMappingHandler per segment tag
        for qm in self.mapping.qualified_mappings:
            tag = qm.qualifier_path.segment
            handler = QualifiedMappingHandler(qm)
            table.setdefault(tag, []).append(handler)

        # Special handlers from registry
        special = HANDLER_REGISTRY.get(self.mapping.transaction_id, {})
        for tag, handlers in special.items():
            table.setdefault(tag, []).extend(handlers)

        return table

    def _build_loop_dispatch(self) -> dict[str, list]:
        """
        Build dispatch table for loops.

        Maps loop_id -> list of handlers (LoopItemHandler, PartyLoopHandler).
        """
        table: dict[str, list] = {}

        # Loop mappings -> LoopItemHandler
        line_handlers = LINE_HANDLER_REGISTRY.get(self.mapping.transaction_id, {})
        for lm in self.mapping.loop_mappings:
            special = line_handlers.get(lm.loop_id, {})
            handler = LoopItemHandler(lm, line_special_handlers=special)
            table.setdefault(lm.loop_id, []).append(handler)

        # Party loop mappings -> PartyLoopHandler
        for pm in self.mapping.party_mappings:
            handler = PartyLoopHandler(pm)
            table.setdefault(pm.loop_id, []).append(handler)

        return table

    # =========================================================================
    # Content normalization
    # =========================================================================

    def _normalize_content(
        self,
        content: list[ParsedSegment | LoopInstance],
    ) -> list[ParsedSegment | LoopInstance]:
        """
        Pre-normalize content: convert implicit loops into explicit LoopInstances.

        This runs once before the main pass, O(n) in content size.
        Segments that are loop triggers (PO1, IT1, N1) but appear as bare
        segments get wrapped into synthetic LoopInstance objects.
        """
        from edi_schema.x12.ast import LoopInstance as LI
        from edi_schema.x12.ast import ParsedSegment as PS
        from edi_schema.x12.ast import RawSegment as RS

        # Collect all loop IDs we care about
        loop_ids = set()
        for lm in self.mapping.loop_mappings:
            loop_ids.add(lm.loop_id)
        for pm in self.mapping.party_mappings:
            loop_ids.add(pm.loop_id)

        if not loop_ids:
            return content

        # Known child segments for common loop types
        LOOP_CHILD_SEGMENTS = {
            "N1": {"N1", "N2", "N3", "N4", "PER", "REF"},
            "PO1": {"PO1", "PID", "SAC", "DTM", "MEA", "CTP", "PAM", "PO3", "PO4", "REF", "MSG", "SCH", "TXI"},
            "IT1": {"IT1", "PID", "SAC", "DTM", "MEA", "CTP", "REF", "SLN", "TXI"},
            "ITD": {"ITD"},
        }

        normalized: list = []
        i = 0
        while i < len(content):
            item = content[i]

            if isinstance(item, LI):
                # Already a proper loop instance
                normalized.append(item)
                i += 1
            elif isinstance(item, (PS, RS)) and item.tag in loop_ids:
                # Bare segment that should start a loop - collect siblings
                child_segments = LOOP_CHILD_SEGMENTS.get(item.tag, {item.tag})
                segments = [item]
                j = i + 1
                while j < len(content):
                    next_item = content[j]
                    if isinstance(next_item, (PS, RS)) and next_item.tag in child_segments:
                        if next_item.tag == item.tag:
                            break  # New loop trigger
                        segments.append(next_item)
                        j += 1
                    elif isinstance(next_item, LI):
                        break
                    else:
                        break

                implicit_loop = LI(
                    loop_id=item.tag,
                    segments=segments,
                    children=[],
                )
                normalized.append(implicit_loop)
                i = j
            else:
                normalized.append(item)
                i += 1

        return normalized

    # =========================================================================
    # Main mapping method
    # =========================================================================

    def to_semantic(
        self,
        transaction: TransactionSetInstance,
        context: MessageContext | None = None,
    ) -> MappingResult[T]:
        """
        Convert an X12 transaction to a semantic model using single-pass mapping.

        Args:
            transaction: Parsed X12 transaction (from parser)
            context: Optional context with envelope data and external metadata

        Returns:
            MappingResult containing the mapped model and any errors
        """
        metrics = MappingMetrics() if self.collect_metrics else None
        trace = (
            MappingTrace(
                transaction_id=self.mapping.transaction_id,
                control_number=transaction.control_number,
                context=context,
            )
            if self.debug_mode
            else None
        )

        if metrics:
            metrics.start_time = time.perf_counter()

        accumulator = ErrorAccumulator(mode=self.error_mode)

        try:
            # Validate transaction type
            if transaction.transaction_id != self.mapping.transaction_id:
                accumulator.add_fatal(
                    MappingErrorCode.INVALID_VALUE,
                    f"Expected transaction {self.mapping.transaction_id}, "
                    f"got {transaction.transaction_id}",
                )

            builder = Box(default_box=True)
            ctx = HandlerContext(
                metrics=metrics,
                trace=trace,
                accumulator=accumulator,
                transaction_id=self.mapping.transaction_id,
            )

            # Pre-pass: envelope + context fields
            if context and self.mapping.envelope_mappings:
                self._map_envelope(builder, context, ctx)

            if context and self.mapping.context_mappings:
                self._map_context(builder, context, ctx)

            # Normalize implicit loops
            content = self._normalize_content(transaction.content)

            # Collect segment tags for unmapped tracking
            if metrics:
                all_tags = self._collect_segment_tags(content)
                metrics.total_segments_in_document = sum(all_tags.values())

            # Track processed loop IDs to avoid double-dispatching
            processed_loop_ids: set[str] = set()

            # Track which segment tags were seen (for default application)
            seen_tags: set[str] = set()

            # Single forward pass
            for item in content:
                if self._is_loop(item):
                    loop_id = item.loop_id
                    # Dispatch to loop handlers
                    for handler in self._loop_dispatch.get(loop_id, []):
                        handler.handle(item, builder, ctx)
                    # Also dispatch child segments within loops to special handlers
                    # (for segments like MSG inside N9 loops - not line-item loops)
                    if loop_id not in ("PO1", "IT1", "SLN", "N1"):
                        self._dispatch_loop_children(item, builder, ctx)
                else:
                    # Top-level segment
                    tag = item.tag
                    seen_tags.add(tag)
                    for handler in self._segment_dispatch.get(tag, []):
                        handler.handle(item, builder, ctx)

            # Apply defaults for field mappings whose segments were never seen
            self._apply_unseen_defaults(builder, ctx, seen_tags)

            # Post-processing
            self._resolve_txi_subtotals(builder)
            self._merge_delivery_entries(builder)
            self._copy_delivery_locations(builder)
            self._ensure_party_wrappers(builder)
            self._ensure_price_currency(builder)
            self._ensure_amount_currencies(builder)

            # Build Pydantic model from builder dict
            model_dict = strip_empty_boxes(builder.to_dict())
            if model_dict is None:
                model_dict = {}

            # Restore required empty objects that strip_empty_boxes removed
            self._restore_required_empty_objects(model_dict)

            model = self._build_model(model_dict, accumulator)

            # Validation rules
            validation_errors: list[MappingError] = []
            if self.mapping.validate_on_map and self.mapping.validation_rules:
                validation_start = time.perf_counter()
                for rule in self.mapping.validation_rules:
                    errors = rule.validate(model, context)
                    validation_errors.extend(errors)
                    if metrics:
                        metrics.validation_rules_run += 1
                if metrics:
                    metrics.validation_time = time.perf_counter() - validation_start

            # Build result
            all_errors = accumulator.errors + validation_errors
            success = not any(
                e.severity in (MappingErrorSeverity.ERROR, MappingErrorSeverity.FATAL)
                for e in all_errors
            )

            if metrics:
                metrics.end_time = time.perf_counter()
                for error in all_errors:
                    metrics.record_error(error)

            if trace:
                trace.success = success
                trace.error_count = len(all_errors)
                trace.metrics = metrics

            if self.aggregate_metrics and metrics:
                self.aggregate_metrics.add(
                    self.mapping.transaction_id,
                    metrics,
                    success,
                )

            return MappingResult(
                success=success,
                model=model,
                errors=all_errors,
                trace=trace,
                metrics=metrics,
            )

        except MappingException as e:
            if metrics:
                metrics.end_time = time.perf_counter()
                metrics.record_error(e.error)

            return MappingResult(
                success=False,
                model=None,
                errors=accumulator.errors + [e.error],
                trace=trace,
                metrics=metrics,
            )

    # =========================================================================
    # Defaults for unseen segments
    # =========================================================================

    def _apply_unseen_defaults(
        self,
        builder: Box,
        ctx: HandlerContext,
        seen_tags: set[str],
    ) -> None:
        """
        Apply default values for field mappings whose segments never appeared.

        In the old engine, each mapping scans all content and falls back to
        defaults when a segment isn't found. In single-pass mode, we must
        apply defaults after the pass for segments that were never seen.
        """
        for fm in self.mapping.field_mappings:
            if not isinstance(fm.x12, SegmentPath):
                continue
            if fm.default is None:
                continue
            if fm.x12.segment in seen_tags:
                continue  # Handler already processed this segment

            # Check if the value is already set in the builder
            raw = builder.to_dict()
            path_parts = fm.semantic.path.split(".")
            current = raw
            exists = True
            for part in path_parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    exists = False
                    break

            if not exists:
                value = fm.default
                if fm.to_semantic_transform:
                    try:
                        value = fm.to_semantic_transform.to_semantic(value)
                    except Exception:
                        pass
                set_box_path(builder, fm.semantic.path, value, ctx)
                if ctx.metrics:
                    ctx.metrics.fields_defaulted += 1
                    ctx.metrics.fields_mapped += 1

    # =========================================================================
    # Envelope & context mapping
    # =========================================================================

    def _map_envelope(
        self,
        builder: Box,
        context: MessageContext,
        ctx: HandlerContext,
    ) -> None:
        """Map ISA/GS envelope fields to builder."""
        for fm in self.mapping.envelope_mappings:
            if not isinstance(fm.x12, EnvelopePath):
                continue

            path = fm.x12
            value = context.get_envelope_value(path.segment, path.element)

            if value is None and fm.default is not None:
                value = fm.default
                if ctx.metrics:
                    ctx.metrics.fields_defaulted += 1

            if value is None:
                if fm.required:
                    ctx.accumulator.add(
                        MappingErrorCode.REQUIRED_FIELD_MISSING,
                        f"Required envelope field {path} is missing",
                        source_path=str(path),
                        target_path=fm.semantic.path,
                    )
                if ctx.metrics:
                    ctx.metrics.fields_skipped += 1
                continue

            if fm.to_semantic_transform:
                try:
                    value = fm.to_semantic_transform.to_semantic(value)
                    if ctx.metrics:
                        ctx.metrics.transforms_applied += 1
                except Exception as e:
                    ctx.accumulator.add_warning(
                        MappingErrorCode.TRANSFORM_FAILED,
                        f"Transform failed: {e}",
                        source_path=str(path),
                        target_path=fm.semantic.path,
                        value=value,
                    )
                    if fm.fallback is not None:
                        value = fm.fallback
                    else:
                        continue

            set_box_path(builder, fm.semantic.path, value, ctx)
            if ctx.metrics:
                ctx.metrics.fields_mapped += 1
            if ctx.trace:
                ctx.trace.add_field(str(path), fm.semantic.path, value)

    def _map_context(
        self,
        builder: Box,
        context: MessageContext,
        ctx: HandlerContext,
    ) -> None:
        """Map external context metadata to builder."""
        for fm in self.mapping.context_mappings:
            if not isinstance(fm.x12, ContextPath):
                continue

            path = fm.x12
            value = context.get_context_value(path.key)

            if value is None and fm.default is not None:
                value = fm.default
                if ctx.metrics:
                    ctx.metrics.fields_defaulted += 1

            if value is None:
                if ctx.metrics:
                    ctx.metrics.fields_skipped += 1
                continue

            if fm.to_semantic_transform:
                try:
                    value = fm.to_semantic_transform.to_semantic(value)
                    if ctx.metrics:
                        ctx.metrics.transforms_applied += 1
                except Exception:
                    continue

            set_box_path(builder, fm.semantic.path, value, ctx)
            if ctx.metrics:
                ctx.metrics.fields_mapped += 1
            if ctx.trace:
                ctx.trace.add_field(str(path), fm.semantic.path, value)

    # =========================================================================
    # Loop child dispatching (for segments inside non-line-item loops)
    # =========================================================================

    def _dispatch_loop_children(
        self,
        loop: LoopInstance,
        builder: Box,
        ctx: HandlerContext,
    ) -> None:
        """Dispatch segments inside a non-line-item loop to special handlers."""
        for seg in loop.segments:
            tag = seg.tag
            # Only dispatch to special handlers (not field/qualified - those
            # are handled by the loop's own handler)
            special = HANDLER_REGISTRY.get(self.mapping.transaction_id, {})
            if tag in special:
                for handler in special[tag]:
                    handler.handle(seg, builder, ctx)

    # =========================================================================
    # Post-processing
    # =========================================================================

    def _resolve_txi_subtotals(self, builder: Box) -> None:
        """
        Convert accumulated _txi_subtotals into proper tax_total entries.

        TXI segments accumulate into _txi_subtotals during the pass.
        This converts them into TaxTotal objects with summed amounts.
        """
        subtotals = builder.pop("_txi_subtotals", None)
        if subtotals and isinstance(subtotals, list):
            total_tax = Decimal("0")
            for st in subtotals:
                if isinstance(st, dict) and "tax_amount" in st:
                    try:
                        total_tax += Decimal(st["tax_amount"]["value"])
                    except Exception:
                        pass

            tax_total = {
                "tax_amount": {"value": str(total_tax), "currency": "USD"},
                "tax_subtotals": subtotals,
            }
            tax_list = ensure_list(builder, "tax_total")
            tax_list.append(tax_total)

    def _merge_delivery_entries(self, builder: Box) -> None:
        """
        Merge delivery list entries that were created by different handlers.

        FOB/TD5/DTM-despatch create delivery[0] with terms/shipment/despatch.
        Party handler appends delivery entries with delivery_party.
        This merges them into a single entry when possible.
        """
        delivery_list = builder.get("delivery")
        if not isinstance(delivery_list, list) or len(delivery_list) <= 1:
            return

        # Strategy: merge all entries into a single delivery entry
        merged = Box(default_box=True) if not isinstance(delivery_list[0], Box) else delivery_list[0]
        if not isinstance(merged, Box):
            merged = Box(delivery_list[0] if isinstance(delivery_list[0], dict) else {}, default_box=True)

        for entry in delivery_list[1:]:
            if isinstance(entry, (dict, Box)):
                for key, value in entry.items():
                    if key not in merged or isinstance(merged[key], Box) and not dict(merged[key]):
                        merged[key] = value

        builder["delivery"] = [merged]

    def _copy_delivery_locations(self, builder: Box) -> None:
        """Copy delivery_party.postal_address to delivery_location for each delivery."""
        delivery_list = builder.get("delivery")
        if not isinstance(delivery_list, list):
            return

        for delivery_item in delivery_list:
            if not isinstance(delivery_item, (dict, Box)):
                continue
            party = delivery_item.get("delivery_party")
            if isinstance(party, (dict, Box)):
                postal = party.get("postal_address")
                if postal and isinstance(postal, (dict, Box)):
                    delivery_item["delivery_location"] = dict(postal) if isinstance(postal, Box) else postal

    def _ensure_party_wrappers(self, builder: Box) -> None:
        """
        Ensure CustomerParty/SupplierParty wrappers have the required 'party' field.

        When a PER handler creates buyer_contact without a party, we need to
        ensure party is present for Pydantic validation.
        """
        party_wrapper_fields = [
            "buyer_customer_party",
            "seller_supplier_party",
            "accounting_customer_party",
            "originator_customer_party",
            "accounting_supplier_party",
        ]

        raw = builder.to_dict()
        for field_name in party_wrapper_fields:
            wrapper = raw.get(field_name)
            if isinstance(wrapper, dict) and wrapper:
                # Check if 'party' key exists and has content
                party = wrapper.get("party")
                if not party or (isinstance(party, dict) and not party):
                    wrapper["party"] = {}
                    builder[field_name] = wrapper

    def _ensure_price_currency(self, builder: Box) -> None:
        """Ensure price amounts have a currency set (default USD)."""
        currency = builder.get("document_currency_code", "USD")
        if isinstance(currency, Box):
            currency = "USD"

        # Check order_lines / invoice_lines
        for list_key in ("order_lines", "invoice_lines"):
            lines = builder.get(list_key)
            if not isinstance(lines, list):
                continue
            for line in lines:
                if not isinstance(line, (dict, Box)):
                    continue
                price = line.get("price")
                if isinstance(price, (dict, Box)):
                    amount = price.get("price_amount")
                    if isinstance(amount, (dict, Box)):
                        if "currency" not in amount or isinstance(amount.get("currency"), Box):
                            amount["currency"] = currency

    def _ensure_amount_currencies(self, builder: Box) -> None:
        """Ensure Amount objects in monetary totals have currency set."""
        raw = builder.to_dict()
        currency = raw.get("document_currency_code", "USD")
        if not isinstance(currency, str):
            currency = "USD"

        # Check monetary totals - only modify amounts that already have a "value"
        for total_key in (
            "anticipated_monetary_total",
            "legal_monetary_total",
        ):
            total = raw.get(total_key)
            if not isinstance(total, dict):
                continue
            for amount_key in ("payable_amount", "allowance_total_amount", "tax_inclusive_amount"):
                amount = total.get(amount_key)
                if isinstance(amount, dict) and "value" in amount:
                    if "currency" not in amount:
                        amount["currency"] = currency
            # Write back
            builder[total_key] = total

    # =========================================================================
    # Model building
    # =========================================================================

    def _restore_required_empty_objects(self, model_dict: dict) -> None:
        """
        Restore required empty objects that strip_empty_boxes removed.

        CustomerParty and SupplierParty require a 'party' field even if empty.
        """
        party_wrapper_fields = [
            "buyer_customer_party",
            "seller_supplier_party",
            "accounting_customer_party",
            "originator_customer_party",
            "accounting_supplier_party",
        ]

        for field_name in party_wrapper_fields:
            wrapper = model_dict.get(field_name)
            if isinstance(wrapper, dict) and "party" not in wrapper:
                wrapper["party"] = {}

    def _build_model(self, model_dict: dict, accumulator: ErrorAccumulator) -> Any:
        """Build the Pydantic model from the accumulated dict."""
        try:
            return self.mapping.semantic_type.model_validate(model_dict)
        except Exception as e:
            # Try with minimal defaults for required fields
            try:
                self._add_required_defaults(model_dict)
                return self.mapping.semantic_type.model_validate(model_dict)
            except Exception as e2:
                raise MappingException(
                    MappingError(
                        code=MappingErrorCode.TYPE_MISMATCH,
                        severity=MappingErrorSeverity.FATAL,
                        message=f"Cannot create {self.mapping.semantic_type.__name__}: {e2}",
                    )
                )

    def _add_required_defaults(self, model_dict: dict) -> None:
        """Add defaults for required fields that are missing."""
        from datetime import date

        semantic_type = self.mapping.semantic_type
        if not hasattr(semantic_type, "model_fields"):
            return

        for name, field_info in semantic_type.model_fields.items():
            if field_info.is_required() and name not in model_dict:
                annotation = field_info.annotation
                if annotation == str:
                    model_dict[name] = ""
                elif annotation == date:
                    model_dict[name] = date.today()
                elif annotation == int:
                    model_dict[name] = 0

    # =========================================================================
    # Utilities
    # =========================================================================

    @staticmethod
    def _is_loop(item: Any) -> bool:
        """Check if an item is a LoopInstance."""
        return hasattr(item, "loop_id") and hasattr(item, "segments")

    def _collect_segment_tags(
        self,
        content: list,
    ) -> dict[str, int]:
        """Collect counts of all segment tags in the document."""
        counts: dict[str, int] = {}

        def collect(items: list) -> None:
            for item in items:
                if hasattr(item, "tag"):
                    tag = item.tag
                    counts[tag] = counts.get(tag, 0) + 1
                if hasattr(item, "segments"):
                    collect(item.segments)
                if hasattr(item, "children"):
                    for child in item.children:
                        collect([child])

        collect(content)
        return counts

    def get_metrics(self) -> AggregateMetrics | None:
        """Get aggregate metrics across all mappings."""
        return self.aggregate_metrics

    def reset_metrics(self) -> None:
        """Reset aggregate metrics."""
        if self.aggregate_metrics:
            self.aggregate_metrics.reset()
