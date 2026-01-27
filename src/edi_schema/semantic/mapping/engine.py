"""
Mapping Engine - Core declarative mapping implementation.

Executes TransactionMapping definitions to convert between X12 and semantic models.
"""

import time
from typing import TYPE_CHECKING, Any, TypeVar

from .context import MessageContext
from .diagnostics import AggregateMetrics, MappingLogger, MappingMetrics, MappingTrace
from .errors import (
    ErrorAccumulator,
    ErrorContext,
    ErrorHandlingMode,
    MappingError,
    MappingErrorCode,
    MappingErrorSeverity,
    MappingException,
)
from .result import MappingResult
from .types import (
    ContextPath,
    EnvelopePath,
    FieldMapping,
    LoopMapping,
    PartyLoopMapping,
    QualifiedMapping,
    SegmentPath,
    SemanticPath,
    SourcePath,
    TransactionMapping,
)

if TYPE_CHECKING:
    from edi_schema.x12.ast import LoopInstance, ParsedSegment, TransactionSetInstance

T = TypeVar("T")


# =============================================================================
# Utility Functions for X12 Content Access
# =============================================================================


def find_segment(
    content: list["ParsedSegment | LoopInstance"],
    tag: str,
    *,
    qualifier: tuple[int, str] | None = None,
) -> "ParsedSegment | None":
    """Find a segment in content by tag and optional qualifier."""
    from edi_schema.x12.ast import LoopInstance, ParsedSegment, RawSegment

    for item in content:
        # Check if it's a segment (either ParsedSegment or RawSegment)
        if isinstance(item, (ParsedSegment, RawSegment)) and item.tag == tag:
            if qualifier is None:
                return item
            # Check qualifier
            elem_idx, expected_value = qualifier
            actual_value = _get_element_value(item, elem_idx)
            if actual_value == expected_value:
                return item
        elif isinstance(item, LoopInstance):
            # Search in loop segments
            for seg in item.segments:
                if seg.tag == tag:
                    if qualifier is None:
                        return seg
                    elem_idx, expected_value = qualifier
                    actual_value = _get_element_value(seg, elem_idx)
                    if actual_value == expected_value:
                        return seg
    return None


def find_all_segments(
    content: list["ParsedSegment | LoopInstance"],
    tag: str,
    *,
    qualifier: tuple[int, str] | None = None,
) -> list["ParsedSegment"]:
    """Find all segments with given tag and optional qualifier."""
    from edi_schema.x12.ast import LoopInstance, ParsedSegment, RawSegment

    results: list["ParsedSegment"] = []

    for item in content:
        # Check if it's a segment (either ParsedSegment or RawSegment)
        if isinstance(item, (ParsedSegment, RawSegment)) and item.tag == tag:
            if qualifier is None:
                results.append(item)
            else:
                elem_idx, expected_value = qualifier
                actual_value = _get_element_value(item, elem_idx)
                if actual_value == expected_value:
                    results.append(item)
        elif isinstance(item, LoopInstance):
            for seg in item.segments:
                if seg.tag == tag:
                    if qualifier is None:
                        results.append(seg)
                    else:
                        elem_idx, expected_value = qualifier
                        actual_value = _get_element_value(seg, elem_idx)
                        if actual_value == expected_value:
                            results.append(seg)

    return results


def find_all_loops(
    content: list["ParsedSegment | LoopInstance"],
    loop_id: str,
) -> list["LoopInstance"]:
    """
    Find all loops with the given ID, including implicit loops.

    Handles both proper LoopInstance objects and "implicit loops"
    where consecutive segments form a logical loop.
    """
    from edi_schema.x12.ast import LoopInstance, ParsedSegment, RawSegment

    # Known child segments for common loop types
    LOOP_CHILD_SEGMENTS = {
        "N1": {"N1", "N2", "N3", "N4", "PER", "REF"},
        "PO1": {"PO1", "PID", "SAC", "DTM", "MEA", "CTP", "PAM", "PO3", "PO4", "REF", "MSG"},
        "IT1": {"IT1", "PID", "SAC", "DTM", "MEA", "CTP", "REF", "SLN"},
        "ITD": {"ITD"},
    }

    results: list["LoopInstance"] = []
    child_segments = LOOP_CHILD_SEGMENTS.get(loop_id, {loop_id})

    i = 0
    while i < len(content):
        item = content[i]

        if isinstance(item, LoopInstance) and item.loop_id == loop_id:
            results.append(item)
            i += 1
        elif isinstance(item, (ParsedSegment, RawSegment)) and item.tag == loop_id:
            # Found a standalone segment that should start a loop
            # Collect consecutive segments that belong to this implicit loop
            segments = [item]
            j = i + 1
            while j < len(content):
                next_item = content[j]
                if isinstance(next_item, (ParsedSegment, RawSegment)) and next_item.tag in child_segments:
                    if next_item.tag == loop_id:
                        # New loop trigger - stop here
                        break
                    segments.append(next_item)
                    j += 1
                elif isinstance(next_item, LoopInstance):
                    break
                else:
                    break

            # Create synthetic LoopInstance
            implicit_loop = LoopInstance(
                loop_id=loop_id,
                segments=segments,
                children=[],
            )
            results.append(implicit_loop)
            i = j
        else:
            i += 1

    return results


def _get_element_value(segment: "ParsedSegment", index: int) -> str | None:
    """Get element value from segment by 1-indexed position."""
    # RawSegment has get_element_value directly
    if hasattr(segment, "get_element_value"):
        return segment.get_element_value(index)
    # ParsedSegment may have raw attribute
    if hasattr(segment, "raw") and hasattr(segment.raw, "get_element_value"):
        return segment.raw.get_element_value(index)
    return None


def _get_composite_component(
    segment: "ParsedSegment",
    element_index: int,
    component_index: int,
) -> str | None:
    """Get component from composite element."""
    # RawSegment has get_element directly
    if hasattr(segment, "get_element"):
        elem = segment.get_element(element_index)
    elif hasattr(segment, "raw") and hasattr(segment.raw, "get_element"):
        elem = segment.raw.get_element(element_index)
    else:
        return None

    if elem is None:
        return None
    if hasattr(elem, "components"):
        return elem.get_component(component_index)
    elif hasattr(elem, "value"):
        return elem.value if component_index == 1 else None
    return None


# =============================================================================
# Utility Functions for Setting Nested Attributes
# =============================================================================


def set_nested_attr(obj: Any, path: str, value: Any) -> bool:
    """
    Set a nested attribute value by dot-separated path.

    Supports:
    - Simple paths: "id" -> obj.id = value
    - Nested paths: "buyer.party.name" -> obj.buyer.party.name = value
    - List append: "order_lines[+]" -> obj.order_lines.append(value)
    - List index: "order_lines[0].id" -> obj.order_lines[0].id = value

    Returns True if successful, False otherwise.
    """
    if not path:
        return False

    parts = _parse_path_parts(path)
    current = obj

    for i, part in enumerate(parts[:-1]):
        if part.startswith("[") and part.endswith("]"):
            # List access
            index_str = part[1:-1]
            if index_str == "+":
                # Append creates new item, can't navigate further here
                return False
            try:
                index = int(index_str)
                if isinstance(current, list) and 0 <= index < len(current):
                    current = current[index]
                else:
                    return False
            except ValueError:
                return False
        else:
            # Attribute access
            if hasattr(current, part):
                attr_value = getattr(current, part)
                if attr_value is None:
                    # Try to create the intermediate object
                    # Get type hint to know what to create
                    if not _create_intermediate(current, part):
                        return False
                    attr_value = getattr(current, part)
                current = attr_value
            else:
                return False

    # Set the final value
    final_part = parts[-1]
    if final_part.startswith("[") and final_part.endswith("]"):
        index_str = final_part[1:-1]
        if index_str == "+":
            # Append to list
            if isinstance(current, list):
                current.append(value)
                return True
            return False
        try:
            index = int(index_str)
            if isinstance(current, list) and 0 <= index < len(current):
                current[index] = value
                return True
            return False
        except ValueError:
            return False
    else:
        # Set attribute
        if hasattr(current, final_part):
            try:
                setattr(current, final_part, value)
                return True
            except (AttributeError, TypeError, ValueError):
                return False
        return False


def _parse_path_parts(path: str) -> list[str]:
    """Parse a path into parts, handling brackets."""
    parts: list[str] = []
    current = ""

    i = 0
    while i < len(path):
        char = path[i]
        if char == ".":
            if current:
                parts.append(current)
                current = ""
        elif char == "[":
            if current:
                parts.append(current)
                current = ""
            # Find matching bracket
            j = i + 1
            while j < len(path) and path[j] != "]":
                j += 1
            parts.append(path[i : j + 1])
            i = j
        else:
            current += char
        i += 1

    if current:
        parts.append(current)

    return parts


def _create_intermediate(obj: Any, attr_name: str) -> bool:
    """Try to create an intermediate object for a path."""
    # This is a simplified version - in practice, you'd use type hints
    # to determine what class to instantiate
    try:
        # For Pydantic models, try to get the field type
        if hasattr(obj, "model_fields"):
            field_info = obj.model_fields.get(attr_name)
            if field_info and field_info.annotation:
                annotation = field_info.annotation

                # Handle Optional types
                origin = getattr(annotation, "__origin__", None)
                if origin is type(None):
                    return False

                # Get the actual type (unwrap Optional)
                args = getattr(annotation, "__args__", ())
                actual_type = None
                for arg in args:
                    if arg is not type(None):
                        actual_type = arg
                        break
                if actual_type is None:
                    actual_type = annotation

                # Try to instantiate
                if hasattr(actual_type, "__call__"):
                    try:
                        instance = actual_type()
                        setattr(obj, attr_name, instance)
                        return True
                    except (TypeError, ValueError):
                        pass
    except Exception:
        pass

    return False


def get_nested_attr(obj: Any, path: str) -> Any:
    """Get a nested attribute value by dot-separated path."""
    if not path or obj is None:
        return obj

    parts = _parse_path_parts(path)
    current = obj

    for part in parts:
        if current is None:
            return None

        if part.startswith("[") and part.endswith("]"):
            index_str = part[1:-1]
            if index_str == "":
                # Return the list itself
                return current
            try:
                index = int(index_str)
                if isinstance(current, list) and 0 <= index < len(current):
                    current = current[index]
                else:
                    return None
            except ValueError:
                return None
        else:
            if hasattr(current, part):
                current = getattr(current, part)
            elif isinstance(current, dict):
                current = current.get(part)
            else:
                return None

    return current


# =============================================================================
# Mapping Engine
# =============================================================================


class MappingEngine:
    """
    Executes declarative mappings to convert between X12 and semantic models.

    The engine interprets TransactionMapping definitions and handles:
    - Field mappings (simple segment element to semantic field)
    - Qualified mappings (DTM, REF where qualifier determines target)
    - Loop mappings (repeating structures like PO1)
    - Party loop mappings (N1 loops with party qualifiers)
    - Envelope mappings (ISA/GS data)
    - Context mappings (external metadata)
    - Validation rules
    """

    def __init__(
        self,
        mapping: TransactionMapping,
        error_mode: ErrorHandlingMode = ErrorHandlingMode.LENIENT,
        collect_metrics: bool = True,
        debug_mode: bool = False,
    ) -> None:
        self.mapping = mapping
        self.error_mode = error_mode
        self.collect_metrics = collect_metrics
        self.debug_mode = debug_mode
        self.logger = MappingLogger()

        # Metrics collector
        self.aggregate_metrics = AggregateMetrics() if collect_metrics else None

    def to_semantic(
        self,
        transaction: "TransactionSetInstance",
        context: MessageContext | None = None,
    ) -> MappingResult[T]:
        """
        Convert an X12 transaction to a semantic model.

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
                    f"Expected transaction {self.mapping.transaction_id}, got {transaction.transaction_id}",
                )

            content = transaction.content

            # Phase 1: Extract required fields first to build base model
            model_data: dict[str, Any] = {}
            field_start = time.perf_counter()
            self._extract_required_fields(content, model_data, accumulator, metrics, trace)
            if metrics:
                metrics.field_mapping_time += time.perf_counter() - field_start

            # Create the model with required fields
            try:
                model = self.mapping.semantic_type(**model_data)
            except Exception as e:
                accumulator.add(
                    MappingErrorCode.TYPE_MISMATCH,
                    f"Failed to create model: {e}",
                )
                # Try with defaults
                try:
                    model = self._create_model_with_defaults(model_data)
                except Exception:
                    raise MappingException(
                        MappingError(
                            code=MappingErrorCode.TYPE_MISMATCH,
                            severity=MappingErrorSeverity.FATAL,
                            message=f"Cannot create {self.mapping.semantic_type.__name__}: {e}",
                        )
                    )

            # Phase 2: Map envelope fields (ISA/GS)
            if context and self.mapping.envelope_mappings:
                field_start = time.perf_counter()
                self._map_envelope_fields(model, context, accumulator, metrics, trace)
                if metrics:
                    metrics.field_mapping_time += time.perf_counter() - field_start

            # Phase 3: Map context fields (external metadata)
            if context and self.mapping.context_mappings:
                field_start = time.perf_counter()
                self._map_context_fields(model, context, accumulator, metrics, trace)
                if metrics:
                    metrics.field_mapping_time += time.perf_counter() - field_start

            # Phase 4: Map optional header-level fields
            field_start = time.perf_counter()
            self._map_optional_field_mappings(
                model,
                content,
                self.mapping.field_mappings,
                accumulator,
                metrics,
                trace,
            )
            if metrics:
                metrics.field_mapping_time += time.perf_counter() - field_start

            # Phase 5: Map qualified segments (DTM, REF, etc.)
            for qualified_mapping in self.mapping.qualified_mappings:
                self._map_qualified_segments(
                    model,
                    content,
                    qualified_mapping,
                    accumulator,
                    metrics,
                    trace,
                )

            # Phase 6: Map party loops (N1)
            for party_mapping in self.mapping.party_mappings:
                self._map_party_loops(
                    model,
                    content,
                    party_mapping,
                    accumulator,
                    metrics,
                    trace,
                )

            # Phase 7: Map item loops (PO1, IT1, etc.)
            loop_start = time.perf_counter()
            for loop_mapping in self.mapping.loop_mappings:
                self._map_loop(
                    model,
                    content,
                    loop_mapping,
                    accumulator,
                    metrics,
                    trace,
                )
            if metrics:
                metrics.loop_mapping_time = time.perf_counter() - loop_start

            # Phase 8: Run validation rules
            validation_errors: list[MappingError] = []
            if self.mapping.validate_on_map and self.mapping.validation_rules:
                validation_start = time.perf_counter()
                for rule in self.mapping.validation_rules:
                    errors = rule.validate(model, context)
                    validation_errors.extend(errors)
                    if metrics:
                        metrics.validation_rules_run += 1
                    if trace:
                        trace.add_step(
                            type("MappingStep", (), {
                                "step_type": "validation",
                                "source_path": rule.name,
                                "error": errors[0] if errors else None,
                            })()
                        )
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

            # Update aggregate metrics
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

    def _extract_required_fields(
        self,
        content: list["ParsedSegment | LoopInstance"],
        model_data: dict[str, Any],
        accumulator: ErrorAccumulator,
        metrics: MappingMetrics | None,
        trace: MappingTrace | None,
    ) -> None:
        """Extract required fields to build the initial model."""
        # Get the model's required fields
        model_required_fields: set[str] = set()
        if hasattr(self.mapping.semantic_type, "model_fields"):
            for name, field_info in self.mapping.semantic_type.model_fields.items():
                if field_info.is_required():
                    model_required_fields.add(name)

        for field_mapping in self.mapping.field_mappings:
            if not isinstance(field_mapping.x12, SegmentPath):
                continue

            # Get semantic path
            semantic_path = field_mapping.semantic.path

            # Only process top-level fields that are model-required or mapping-required
            if "." in semantic_path or "[" in semantic_path:
                continue

            is_model_required = semantic_path in model_required_fields
            is_mapping_required = field_mapping.required

            if not is_model_required and not is_mapping_required:
                continue

            path = field_mapping.x12
            value = self._resolve_segment_path(content, path)

            if value is None and field_mapping.default is not None:
                value = field_mapping.default
                if metrics:
                    metrics.fields_defaulted += 1

            if value is None:
                if is_mapping_required or is_model_required:
                    accumulator.add(
                        MappingErrorCode.REQUIRED_FIELD_MISSING,
                        f"Required field {path} is missing",
                        source_path=str(path),
                        target_path=semantic_path,
                    )
                if metrics:
                    metrics.fields_skipped += 1
                continue

            # Apply transform
            if field_mapping.to_semantic_transform:
                try:
                    value = field_mapping.to_semantic_transform.to_semantic(value)
                    if metrics:
                        metrics.transforms_applied += 1
                except Exception as e:
                    accumulator.add(
                        MappingErrorCode.TRANSFORM_FAILED,
                        f"Transform failed: {e}",
                        source_path=str(path),
                        target_path=semantic_path,
                        value=value,
                    )
                    continue

            # Set in model_data
            model_data[semantic_path] = value
            if metrics:
                metrics.fields_mapped += 1
            if trace:
                trace.add_field(str(path), semantic_path, value)

    def _create_model_with_defaults(self, model_data: dict[str, Any]) -> Any:
        """Create model with defaults for required fields that are missing."""
        from datetime import date

        semantic_type = self.mapping.semantic_type

        # Get required fields from the model
        if hasattr(semantic_type, "model_fields"):
            for name, field_info in semantic_type.model_fields.items():
                if field_info.is_required() and name not in model_data:
                    # Add defaults for common required field types
                    annotation = field_info.annotation
                    if annotation == str:
                        model_data[name] = ""
                    elif annotation == date:
                        model_data[name] = date.today()
                    elif annotation == int:
                        model_data[name] = 0

        return semantic_type(**model_data)

    def _map_optional_field_mappings(
        self,
        model: Any,
        content: list["ParsedSegment | LoopInstance"],
        field_mappings: list[FieldMapping],
        accumulator: ErrorAccumulator,
        metrics: MappingMetrics | None,
        trace: MappingTrace | None,
    ) -> None:
        """Map optional (non-required) fields to the model."""
        for field_mapping in field_mappings:
            # Skip required fields (already processed)
            if field_mapping.required:
                continue

            if not isinstance(field_mapping.x12, SegmentPath):
                continue

            path = field_mapping.x12
            value = self._resolve_segment_path(content, path)

            if value is None and field_mapping.default is not None:
                value = field_mapping.default
                if metrics:
                    metrics.fields_defaulted += 1

            if value is None:
                if metrics:
                    metrics.fields_skipped += 1
                continue

            # Apply transform
            if field_mapping.to_semantic_transform:
                try:
                    value = field_mapping.to_semantic_transform.to_semantic(value)
                    if metrics:
                        metrics.transforms_applied += 1
                except Exception as e:
                    accumulator.add_warning(
                        MappingErrorCode.TRANSFORM_FAILED,
                        f"Transform failed: {e}",
                        source_path=str(path),
                        target_path=field_mapping.semantic.path,
                        value=value,
                    )
                    continue

            # Set the value
            if set_nested_attr(model, field_mapping.semantic.path, value):
                if metrics:
                    metrics.fields_mapped += 1
                if trace:
                    trace.add_field(str(path), field_mapping.semantic.path, value)
            else:
                if metrics:
                    metrics.fields_skipped += 1

    def _map_envelope_fields(
        self,
        model: Any,
        context: MessageContext,
        accumulator: ErrorAccumulator,
        metrics: MappingMetrics | None,
        trace: MappingTrace | None,
    ) -> None:
        """Map ISA/GS envelope fields to semantic model."""
        for field_mapping in self.mapping.envelope_mappings:
            if not isinstance(field_mapping.x12, EnvelopePath):
                continue

            path = field_mapping.x12
            value = context.get_envelope_value(path.segment, path.element)

            if value is None and field_mapping.default is not None:
                value = field_mapping.default
                if metrics:
                    metrics.fields_defaulted += 1

            if value is None:
                if field_mapping.required:
                    accumulator.add(
                        MappingErrorCode.REQUIRED_FIELD_MISSING,
                        f"Required envelope field {path} is missing",
                        source_path=str(path),
                        target_path=field_mapping.semantic.path,
                    )
                if metrics:
                    metrics.fields_skipped += 1
                continue

            # Apply transform
            if field_mapping.to_semantic_transform:
                try:
                    value = field_mapping.to_semantic_transform.to_semantic(value)
                    if metrics:
                        metrics.transforms_applied += 1
                except Exception as e:
                    accumulator.add(
                        MappingErrorCode.TRANSFORM_FAILED,
                        f"Transform failed: {e}",
                        source_path=str(path),
                        target_path=field_mapping.semantic.path,
                        value=value,
                    )
                    if field_mapping.fallback is not None:
                        value = field_mapping.fallback

            # Set the value
            if set_nested_attr(model, field_mapping.semantic.path, value):
                if metrics:
                    metrics.fields_mapped += 1
                if trace:
                    trace.add_field(str(path), field_mapping.semantic.path, value)
            else:
                if metrics:
                    metrics.fields_skipped += 1
                accumulator.add_warning(
                    MappingErrorCode.CANNOT_SET_FIELD,
                    f"Could not set field {field_mapping.semantic.path}",
                    source_path=str(path),
                    target_path=field_mapping.semantic.path,
                    value=value,
                )

    def _map_context_fields(
        self,
        model: Any,
        context: MessageContext,
        accumulator: ErrorAccumulator,
        metrics: MappingMetrics | None,
        trace: MappingTrace | None,
    ) -> None:
        """Map external context metadata to semantic model."""
        for field_mapping in self.mapping.context_mappings:
            if not isinstance(field_mapping.x12, ContextPath):
                continue

            path = field_mapping.x12
            value = context.get_context_value(path.key)

            if value is None and field_mapping.default is not None:
                value = field_mapping.default
                if metrics:
                    metrics.fields_defaulted += 1

            if value is None:
                if metrics:
                    metrics.fields_skipped += 1
                continue

            # Apply transform
            if field_mapping.to_semantic_transform:
                try:
                    value = field_mapping.to_semantic_transform.to_semantic(value)
                    if metrics:
                        metrics.transforms_applied += 1
                except Exception as e:
                    accumulator.add_warning(
                        MappingErrorCode.TRANSFORM_FAILED,
                        f"Transform failed: {e}",
                        source_path=str(path),
                        target_path=field_mapping.semantic.path,
                        value=value,
                    )
                    continue

            # Set the value
            if set_nested_attr(model, field_mapping.semantic.path, value):
                if metrics:
                    metrics.fields_mapped += 1
                if trace:
                    trace.add_field(str(path), field_mapping.semantic.path, value)
            else:
                if metrics:
                    metrics.fields_skipped += 1

    def _resolve_segment_path(
        self,
        content: list["ParsedSegment | LoopInstance"],
        path: SegmentPath,
    ) -> str | None:
        """Resolve a SegmentPath to a value from content."""
        segment = find_segment(content, path.segment, qualifier=path.qualifier)

        if segment is None:
            return None

        if path.element is None:
            # Return segment tag (unusual but allowed)
            return segment.tag

        if path.component:
            return _get_composite_component(segment, path.element, path.component)
        else:
            return _get_element_value(segment, path.element)

    def _map_qualified_segments(
        self,
        model: Any,
        content: list["ParsedSegment | LoopInstance"],
        qualified_mapping: QualifiedMapping,
        accumulator: ErrorAccumulator,
        metrics: MappingMetrics | None,
        trace: MappingTrace | None,
    ) -> None:
        """Map qualified segments (DTM, REF, etc.) based on qualifier value."""
        qualifier_path = qualified_mapping.qualifier_path

        # Find all segments of this type
        segments = find_all_segments(content, qualifier_path.segment)

        for segment in segments:
            # Get the qualifier value
            qualifier_elem = qualifier_path.element or 1
            qualifier_value = _get_element_value(segment, qualifier_elem)

            if qualifier_value is None:
                continue

            # Check if we have mappings for this qualifier
            if qualifier_value not in qualified_mapping.mappings:
                continue

            # Apply the mappings for this qualifier
            field_mappings = qualified_mapping.mappings[qualifier_value]
            for field_mapping in field_mappings:
                if not isinstance(field_mapping.x12, SegmentPath):
                    continue

                path = field_mapping.x12
                if path.element:
                    value = _get_element_value(segment, path.element)
                else:
                    value = None

                if value is None:
                    if metrics:
                        metrics.fields_skipped += 1
                    continue

                # Apply transform
                if field_mapping.to_semantic_transform:
                    try:
                        value = field_mapping.to_semantic_transform.to_semantic(value)
                        if metrics:
                            metrics.transforms_applied += 1
                    except Exception as e:
                        accumulator.add_warning(
                            MappingErrorCode.TRANSFORM_FAILED,
                            f"Transform failed: {e}",
                            source_path=str(path),
                            target_path=field_mapping.semantic.path,
                            value=value,
                        )
                        continue

                # Set the value
                if set_nested_attr(model, field_mapping.semantic.path, value):
                    if metrics:
                        metrics.fields_mapped += 1
                    if trace:
                        trace.add_field(
                            f"{path.segment}[{qualifier_value}]*{path.element}",
                            field_mapping.semantic.path,
                            value,
                        )
                else:
                    if metrics:
                        metrics.fields_skipped += 1

    def _map_party_loops(
        self,
        model: Any,
        content: list["ParsedSegment | LoopInstance"],
        party_mapping: PartyLoopMapping,
        accumulator: ErrorAccumulator,
        metrics: MappingMetrics | None,
        trace: MappingTrace | None,
    ) -> None:
        """Map N1-style party loops based on party qualifier."""
        loops = find_all_loops(content, party_mapping.loop_id)

        if metrics:
            metrics.loops_processed += 1

        for i, loop in enumerate(loops):
            if metrics:
                metrics.loop_iterations += 1

            # Get the party qualifier (N1*01)
            n1_seg = None
            for seg in loop.segments:
                if seg.tag == party_mapping.loop_id:
                    n1_seg = seg
                    break

            if n1_seg is None:
                continue

            party_code = _get_element_value(n1_seg, 1)
            if party_code is None or party_code not in party_mapping.party_field_map:
                continue

            # Get the target path for this party type
            target_path = party_mapping.party_field_map[party_code]

            with ErrorContext(accumulator, loop=party_mapping.loop_id, party=party_code):
                # Create or get the party object
                # For paths like "buyer_customer_party", we need to create CustomerParty
                # For paths like "delivery[+].delivery_party", we need to append to list

                self._map_party_to_model(
                    model,
                    loop,
                    target_path,
                    party_mapping,
                    accumulator,
                    metrics,
                    trace,
                )

    def _map_party_to_model(
        self,
        model: Any,
        loop: "LoopInstance",
        target_path: SemanticPath,
        party_mapping: PartyLoopMapping,
        accumulator: ErrorAccumulator,
        metrics: MappingMetrics | None,
        trace: MappingTrace | None,
    ) -> None:
        """Map a single party loop to the model at the given path."""
        # This is complex because the target can be:
        # - Direct: "buyer_customer_party" -> CustomerParty
        # - Nested: "buyer_customer_party.party" -> Party
        # - List append: "delivery[+].delivery_party" -> append Delivery with party

        path_str = target_path.path

        # Handle list append syntax
        if "[+]" in path_str:
            # e.g., "delivery[+].delivery_party"
            parts = path_str.split("[+]")
            list_path = parts[0]
            rest_path = parts[1].lstrip(".") if len(parts) > 1 else ""

            # Get or create the list
            list_obj = get_nested_attr(model, list_path)
            if not isinstance(list_obj, list):
                if metrics:
                    metrics.fields_skipped += 1
                return

            # Create a new item for this party
            # We need to determine what type to create
            # For now, handle common cases
            if list_path == "delivery":
                from edi_schema.semantic.models import Delivery

                new_item = Delivery()
                list_obj.append(new_item)

                if rest_path:
                    self._populate_party(new_item, loop, rest_path, party_mapping, accumulator, metrics, trace)
                else:
                    # Map party to the item itself
                    self._populate_party_fields(new_item, loop, party_mapping, accumulator, metrics, trace)
        else:
            # Direct path like "buyer_customer_party" or "accounting_customer_party"
            # Create the party wrapper if needed
            existing = get_nested_attr(model, path_str)

            if existing is None:
                # Create appropriate party wrapper with required Party
                from edi_schema.semantic.models import CustomerParty, SupplierParty, Party

                inner_party = Party()

                if "customer_party" in path_str:
                    wrapper = CustomerParty(party=inner_party)
                elif "supplier_party" in path_str:
                    wrapper = SupplierParty(party=inner_party)
                else:
                    wrapper = inner_party

                if not set_nested_attr(model, path_str, wrapper):
                    if metrics:
                        metrics.fields_skipped += 1
                    return
                existing = wrapper

            # Populate the party
            self._populate_party_fields(existing, loop, party_mapping, accumulator, metrics, trace)

    def _populate_party(
        self,
        obj: Any,
        loop: "LoopInstance",
        rest_path: str,
        party_mapping: PartyLoopMapping,
        accumulator: ErrorAccumulator,
        metrics: MappingMetrics | None,
        trace: MappingTrace | None,
    ) -> None:
        """Populate party at a nested path."""
        from edi_schema.semantic.models import Party

        party = Party()
        self._populate_party_fields(party, loop, party_mapping, accumulator, metrics, trace)

        if rest_path.endswith("delivery_party"):
            set_nested_attr(obj, "delivery_party", party)
            # Also set delivery_location from postal_address
            if party.postal_address:
                set_nested_attr(obj, "delivery_location", party.postal_address)

    def _populate_party_fields(
        self,
        party_obj: Any,
        loop: "LoopInstance",
        party_mapping: PartyLoopMapping,
        accumulator: ErrorAccumulator,
        metrics: MappingMetrics | None,
        trace: MappingTrace | None,
    ) -> None:
        """Populate party fields from N1 loop segments."""
        from edi_schema.semantic.models import Address, Contact, Identifier, PartyIdentification, PartyName, Party

        # Get or create the inner party object
        party: Party | None = None
        if hasattr(party_obj, "party"):
            party = party_obj.party
            if party is None:
                party = Party()
                party_obj.party = party
        elif isinstance(party_obj, Party):
            party = party_obj

        if party is None:
            return

        # Process each segment in the loop
        for seg in loop.segments:
            if seg.tag == "N1":
                # N1*02 = Name
                name = _get_element_value(seg, 2)
                if name:
                    party.party_names.append(PartyName(name=name))
                    if metrics:
                        metrics.fields_mapped += 1
                    if trace:
                        trace.add_field("N1*02", "party.party_names[+].name", name)

                # N1*03/*04 = ID qualifier/value
                id_qual = _get_element_value(seg, 3)
                id_val = _get_element_value(seg, 4)
                if id_val:
                    scheme = self._map_id_qualifier(id_qual) if id_qual else None
                    party.party_identifications.append(
                        PartyIdentification(id=Identifier(value=id_val, scheme_id=scheme))
                    )
                    if metrics:
                        metrics.fields_mapped += 1

            elif seg.tag == "N2":
                # N2*01 = Additional name
                name2 = _get_element_value(seg, 1)
                if name2:
                    party.party_names.append(PartyName(name=name2))
                    if metrics:
                        metrics.fields_mapped += 1

            elif seg.tag == "N3":
                # N3 = Address lines
                if party.postal_address is None:
                    party.postal_address = Address()

                street = _get_element_value(seg, 1)
                if street:
                    party.postal_address.street_name = street
                    if metrics:
                        metrics.fields_mapped += 1

                street2 = _get_element_value(seg, 2)
                if street2:
                    party.postal_address.additional_street_name = street2
                    if metrics:
                        metrics.fields_mapped += 1

            elif seg.tag == "N4":
                # N4 = City, state, zip, country
                if party.postal_address is None:
                    party.postal_address = Address()

                city = _get_element_value(seg, 1)
                if city:
                    party.postal_address.city_name = city
                    if metrics:
                        metrics.fields_mapped += 1

                state = _get_element_value(seg, 2)
                if state:
                    party.postal_address.country_subentity = state
                    if metrics:
                        metrics.fields_mapped += 1

                postal = _get_element_value(seg, 3)
                if postal:
                    party.postal_address.postal_zone = postal
                    if metrics:
                        metrics.fields_mapped += 1

                country = _get_element_value(seg, 4)
                if country:
                    party.postal_address.country_code = country
                    if metrics:
                        metrics.fields_mapped += 1

            elif seg.tag == "PER":
                # PER = Contact information
                contact = Contact()
                contact.name = _get_element_value(seg, 2)
                if metrics and contact.name:
                    metrics.fields_mapped += 1

                # PER03-08 are qualifier/value pairs
                for i in range(3, 9, 2):
                    qual = _get_element_value(seg, i)
                    val = _get_element_value(seg, i + 1)
                    if qual and val:
                        if qual == "TE":
                            contact.telephone = val
                        elif qual == "EM":
                            contact.electronic_mail = val
                        elif qual == "FX":
                            contact.telefax = val
                        if metrics:
                            metrics.fields_mapped += 1

                if party.contact is None:
                    party.contact = contact
                # Also set buyer_contact/seller_contact if appropriate
                if hasattr(party_obj, "buyer_contact") and party_obj.buyer_contact is None:
                    party_obj.buyer_contact = contact
                elif hasattr(party_obj, "seller_contact") and party_obj.seller_contact is None:
                    party_obj.seller_contact = contact

    def _map_id_qualifier(self, qualifier: str | None) -> str | None:
        """Map X12 N1*03 ID qualifier to scheme name."""
        if not qualifier:
            return None
        qual_map = {
            "1": "DUNS",
            "9": "DUNS+4",
            "12": "Phone",
            "91": "SellerAssigned",
            "92": "BuyerAssigned",
            "ZZ": "MutuallyDefined",
        }
        return qual_map.get(qualifier, qualifier)

    def _map_loop(
        self,
        model: Any,
        content: list["ParsedSegment | LoopInstance"],
        loop_mapping: LoopMapping,
        accumulator: ErrorAccumulator,
        metrics: MappingMetrics | None,
        trace: MappingTrace | None,
    ) -> None:
        """Map a repeating loop to a list in the semantic model."""
        loops = find_all_loops(content, loop_mapping.loop_id)

        if metrics:
            metrics.loops_processed += 1

        # Get or create the target list
        target_list = get_nested_attr(model, loop_mapping.semantic_path.path)
        if not isinstance(target_list, list):
            accumulator.add_warning(
                MappingErrorCode.TARGET_PATH_INVALID,
                f"Target path {loop_mapping.semantic_path.path} is not a list",
                target_path=loop_mapping.semantic_path.path,
            )
            return

        for i, loop in enumerate(loops, 1):
            if metrics:
                metrics.loop_iterations += 1

            with ErrorContext(accumulator, loop=loop_mapping.loop_id, iteration=i):
                # Extract required fields first to build the item
                item_data = self._extract_loop_item_required_fields(
                    loop,
                    loop_mapping,
                    accumulator,
                    metrics,
                    trace,
                )

                # Create a new item with required fields
                try:
                    item = loop_mapping.item_type(**item_data)
                except (TypeError, ValueError) as e:
                    accumulator.add(
                        MappingErrorCode.TYPE_MISMATCH,
                        f"Could not create item of type {loop_mapping.item_type}: {e}",
                    )
                    continue

                # Map optional fields within the loop
                self._map_loop_item_optional_fields(
                    item,
                    loop,
                    loop_mapping,
                    accumulator,
                    metrics,
                    trace,
                )

                # Add to the list
                target_list.append(item)

    def _extract_loop_item_required_fields(
        self,
        loop: "LoopInstance",
        loop_mapping: LoopMapping,
        accumulator: ErrorAccumulator,
        metrics: MappingMetrics | None,
        trace: MappingTrace | None,
    ) -> dict[str, Any]:
        """Extract required fields from loop to build the item."""
        from decimal import Decimal
        from edi_schema.semantic.models import Item, Quantity

        item_data: dict[str, Any] = {}
        item_type = loop_mapping.item_type

        # Get the item type's required fields
        model_required_fields: set[str] = set()
        if hasattr(item_type, "model_fields"):
            for name, field_info in item_type.model_fields.items():
                if field_info.is_required():
                    model_required_fields.add(name)

        # Collect values for required fields from the mapping
        for field_mapping in loop_mapping.field_mappings:
            if not isinstance(field_mapping.x12, SegmentPath):
                continue

            semantic_path = field_mapping.semantic.path

            # Get the top-level field name (before any dot)
            top_level_field = semantic_path.split(".")[0].split("[")[0]

            # Check if this maps to a required field (or part of it)
            is_for_required = top_level_field in model_required_fields

            if not is_for_required:
                continue

            # Extract the value
            path = field_mapping.x12
            value = self._resolve_loop_segment_path(loop, path)

            if value is None and field_mapping.default is not None:
                value = field_mapping.default
                if metrics:
                    metrics.fields_defaulted += 1

            if value is None:
                continue

            # Apply transform
            if field_mapping.to_semantic_transform:
                try:
                    value = field_mapping.to_semantic_transform.to_semantic(value)
                    if metrics:
                        metrics.transforms_applied += 1
                except Exception as e:
                    accumulator.add(
                        MappingErrorCode.TRANSFORM_FAILED,
                        f"Transform failed: {e}",
                        source_path=str(path),
                        target_path=semantic_path,
                        value=value,
                    )
                    continue

            # Handle nested paths for required fields
            if "." in semantic_path:
                # e.g., "quantity.value" or "item.description"
                parts = semantic_path.split(".")
                top_field = parts[0].split("[")[0]
                rest_path = ".".join(parts[1:])

                if top_field not in item_data:
                    # Initialize the nested object
                    if top_field == "quantity":
                        # Will be completed below
                        item_data[top_field] = {"value": None, "unit_code": None}
                    elif top_field == "item":
                        # Store as dict, convert to Item later
                        item_data[top_field] = {}

                if top_field == "quantity":
                    # Store in dict for later Quantity construction
                    if rest_path == "value":
                        item_data[top_field]["value"] = value
                    elif rest_path == "unit_code":
                        item_data[top_field]["unit_code"] = value
                elif top_field == "item":
                    # Store in nested dict for later Item construction
                    self._set_nested_dict_value(item_data[top_field], rest_path, value)

                if metrics:
                    metrics.fields_mapped += 1
                if trace:
                    trace.add_field(str(path), semantic_path, value)
            else:
                # Simple top-level field like "id"
                item_data[semantic_path] = value
                if metrics:
                    metrics.fields_mapped += 1
                if trace:
                    trace.add_field(str(path), semantic_path, value)

        # Convert quantity dict to Quantity object if present
        if "quantity" in item_data and isinstance(item_data["quantity"], dict):
            qty_dict = item_data["quantity"]
            if qty_dict.get("value") is not None:
                qty_value = qty_dict["value"]
                qty_unit = qty_dict.get("unit_code") or "EA"
                item_data["quantity"] = Quantity(value=qty_value, unit_code=qty_unit)
            else:
                # Need a default quantity
                item_data["quantity"] = Quantity(value=Decimal("0"), unit_code="EA")

        # Convert item dict to Item object if present
        if "item" in item_data and isinstance(item_data["item"], dict):
            item_dict = item_data["item"]
            if item_dict:
                # Pydantic will handle nested dict conversion
                item_data["item"] = Item(**item_dict)
            else:
                item_data["item"] = Item()

        # Ensure required fields have values
        for required_field in model_required_fields:
            if required_field not in item_data:
                # Provide defaults for common required fields
                if required_field == "id":
                    item_data["id"] = ""
                elif required_field == "quantity":
                    item_data["quantity"] = Quantity(value=Decimal("0"), unit_code="EA")
                elif required_field == "item":
                    item_data["item"] = Item()

        return item_data

    def _map_loop_item_optional_fields(
        self,
        item: Any,
        loop: "LoopInstance",
        loop_mapping: LoopMapping,
        accumulator: ErrorAccumulator,
        metrics: MappingMetrics | None,
        trace: MappingTrace | None,
    ) -> None:
        """Map optional fields within a single loop iteration."""
        item_type = loop_mapping.item_type

        # Get the item type's required fields to skip them
        model_required_fields: set[str] = set()
        if hasattr(item_type, "model_fields"):
            for name, field_info in item_type.model_fields.items():
                if field_info.is_required():
                    model_required_fields.add(name)

        # Map direct field mappings (skip required ones, already processed)
        for field_mapping in loop_mapping.field_mappings:
            if not isinstance(field_mapping.x12, SegmentPath):
                continue

            # Skip fields that contribute to required model fields (already processed)
            semantic_path = field_mapping.semantic.path
            top_level_field = semantic_path.split(".")[0].split("[")[0]
            if top_level_field in model_required_fields:
                continue

            path = field_mapping.x12

            # Find segment within loop
            value = self._resolve_loop_segment_path(loop, path)

            if value is None and field_mapping.default is not None:
                value = field_mapping.default
                if metrics:
                    metrics.fields_defaulted += 1

            if value is None:
                if field_mapping.required:
                    accumulator.add(
                        MappingErrorCode.REQUIRED_FIELD_MISSING,
                        f"Required field {path} is missing in loop",
                        source_path=str(path),
                        target_path=field_mapping.semantic.path,
                    )
                if metrics:
                    metrics.fields_skipped += 1
                continue

            # Apply transform
            if field_mapping.to_semantic_transform:
                try:
                    value = field_mapping.to_semantic_transform.to_semantic(value)
                    if metrics:
                        metrics.transforms_applied += 1
                except Exception as e:
                    accumulator.add(
                        MappingErrorCode.TRANSFORM_FAILED,
                        f"Transform failed: {e}",
                        source_path=str(path),
                        target_path=field_mapping.semantic.path,
                        value=value,
                    )
                    if field_mapping.fallback is not None:
                        value = field_mapping.fallback
                    else:
                        if metrics:
                            metrics.fields_skipped += 1
                        continue

            # Set the value - handle nested paths that need object construction
            if self._set_nested_value_with_construction(item, semantic_path, value):
                if metrics:
                    metrics.fields_mapped += 1
                if trace:
                    trace.add_field(str(path), semantic_path, value)
            else:
                if metrics:
                    metrics.fields_skipped += 1

        # Map qualified segments within loop
        for qualified_mapping in loop_mapping.qualified_mappings:
            self._map_qualified_segments_in_loop(
                item,
                loop,
                qualified_mapping,
                accumulator,
                metrics,
                trace,
            )

    def _set_nested_value_with_construction(
        self,
        obj: Any,
        path: str,
        value: Any,
    ) -> bool:
        """
        Set a nested value, constructing intermediate objects if needed.

        Handles paths like 'price.price_amount.value' by creating
        Price and Amount objects as needed.
        """
        from edi_schema.semantic.models import Amount, Price

        # First try simple set
        if set_nested_attr(obj, path, value):
            return True

        # If simple set failed, try to construct intermediate objects
        parts = path.split(".")
        if len(parts) < 2:
            return False

        # Handle known patterns
        if parts[0] == "price":
            # Create Price -> Amount chain
            if obj.price is None:
                # Need to construct the full chain
                if len(parts) >= 3 and parts[1] == "price_amount" and parts[2] == "value":
                    # Create Amount with the value and default currency
                    amount = Amount(value=value, currency="USD")
                    price = Price(price_amount=amount)
                    obj.price = price
                    return True

        return False

    def _set_nested_dict_value(self, data: dict, path: str, value: Any) -> None:
        """
        Set a value in a nested dict using dot notation path.

        Creates intermediate dicts as needed.
        Example: _set_nested_dict_value({}, "sellers_item_identification.id.value", "123")
        Results in: {"sellers_item_identification": {"id": {"value": "123"}}}
        """
        parts = path.split(".")
        current = data

        for i, part in enumerate(parts[:-1]):
            if part not in current:
                current[part] = {}
            current = current[part]

        # Set the final value
        current[parts[-1]] = value

    def _resolve_loop_segment_path(
        self,
        loop: "LoopInstance",
        path: SegmentPath,
    ) -> str | None:
        """Resolve a SegmentPath within a loop."""
        # Find segment in loop
        for seg in loop.segments:
            if seg.tag == path.segment:
                # Check qualifier if specified
                if path.qualifier:
                    elem_idx, expected = path.qualifier
                    actual = _get_element_value(seg, elem_idx)
                    if actual != expected:
                        continue

                if path.element is None:
                    return seg.tag

                if path.component:
                    return _get_composite_component(seg, path.element, path.component)
                else:
                    return _get_element_value(seg, path.element)

        return None

    def _map_qualified_segments_in_loop(
        self,
        item: Any,
        loop: "LoopInstance",
        qualified_mapping: QualifiedMapping,
        accumulator: ErrorAccumulator,
        metrics: MappingMetrics | None,
        trace: MappingTrace | None,
    ) -> None:
        """Map qualified segments within a loop."""
        qualifier_path = qualified_mapping.qualifier_path

        for seg in loop.segments:
            if seg.tag != qualifier_path.segment:
                continue

            qualifier_elem = qualifier_path.element or 1
            qualifier_value = _get_element_value(seg, qualifier_elem)

            if qualifier_value is None or qualifier_value not in qualified_mapping.mappings:
                continue

            field_mappings = qualified_mapping.mappings[qualifier_value]
            for field_mapping in field_mappings:
                if not isinstance(field_mapping.x12, SegmentPath):
                    continue

                path = field_mapping.x12
                if path.element:
                    value = _get_element_value(seg, path.element)
                else:
                    value = None

                if value is None:
                    if metrics:
                        metrics.fields_skipped += 1
                    continue

                if field_mapping.to_semantic_transform:
                    try:
                        value = field_mapping.to_semantic_transform.to_semantic(value)
                        if metrics:
                            metrics.transforms_applied += 1
                    except Exception:
                        if metrics:
                            metrics.fields_skipped += 1
                        continue

                if set_nested_attr(item, field_mapping.semantic.path, value):
                    if metrics:
                        metrics.fields_mapped += 1
                else:
                    if metrics:
                        metrics.fields_skipped += 1

    def get_metrics(self) -> AggregateMetrics | None:
        """Get aggregate metrics across all mappings."""
        return self.aggregate_metrics

    def reset_metrics(self) -> None:
        """Reset aggregate metrics."""
        if self.aggregate_metrics:
            self.aggregate_metrics.reset()
