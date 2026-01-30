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
    """Get element value from segment by 1-indexed position.

    Returns None for both missing elements AND empty strings.
    """
    value = None
    # RawSegment has get_element_value directly
    if hasattr(segment, "get_element_value"):
        value = segment.get_element_value(index)
    # ParsedSegment may have raw attribute
    elif hasattr(segment, "raw") and hasattr(segment.raw, "get_element_value"):
        value = segment.raw.get_element_value(index)

    # Treat empty strings as None (no value)
    if value is not None and value.strip() == "":
        return None
    return value


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
    - List append with field: "items[+].id" -> creates new item, sets id, appends

    Returns True if successful, False otherwise.
    """
    if not path:
        return False

    parts = _parse_path_parts(path)
    current = obj
    last_attr_parent: Any = None
    last_attr_name: str | None = None

    for i, part in enumerate(parts[:-1]):
        if part.startswith("[") and part.endswith("]"):
            # List access
            index_str = part[1:-1]
            if index_str == "+":
                # Append with nested field: need to create new item and continue
                # Find the list attribute from the previous part
                remaining_parts = parts[i + 1:]
                return _handle_append_with_nested(current, remaining_parts, value)
            try:
                index = int(index_str)
                if isinstance(current, list):
                    if len(current) <= index:
                        current.extend([None] * (index + 1 - len(current)))

                    if current[index] is None and last_attr_parent is not None and last_attr_name:
                        new_item = _create_list_item_for_parent(
                            last_attr_parent,
                            last_attr_name,
                        )
                        if new_item is not None:
                            current[index] = new_item

                    if current[index] is None:
                        return False

                    current = current[index]
                else:
                    return False
            except ValueError:
                return False
        else:
            # Attribute access
            if hasattr(current, part):
                attr_value = getattr(current, part)
                last_attr_parent = current
                last_attr_name = part
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
            if isinstance(current, list):
                if len(current) <= index:
                    current.extend([None] * (index + 1 - len(current)))
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


def _handle_append_with_nested(list_obj: list, remaining_parts: list[str], value: Any) -> bool:
    """Handle appending to a list with nested field assignment.

    For paths like "items[+].id", this:
    1. Gets the list element type from type hints
    2. Creates a new instance
    3. Sets the nested field value
    4. Appends to the list
    """
    if not isinstance(list_obj, list):
        return False

    if not remaining_parts:
        list_obj.append(value)
        return True

    # Try to get the element type from the list's type annotation
    # This is tricky since we don't have direct access to the parent's type hints
    # Instead, we'll try to create a DocumentReference directly for known cases
    from edi_schema.semantic.models import DocumentReference, Identifier

    # Create a new item - assume DocumentReference for now
    # This is a simplification; a more robust solution would use type introspection
    new_item = None
    remaining_path = ".".join(remaining_parts)

    # Common patterns for document references
    if remaining_path == "id" or remaining_path.endswith(".id"):
        new_item = DocumentReference(id=value)
    else:
        # Try to create a generic object and set the field
        try:
            new_item = DocumentReference()
            if set_nested_attr(new_item, remaining_path, value):
                pass  # Successfully set the field
            else:
                # If DocumentReference doesn't work, try with Identifier
                new_item = DocumentReference(id=Identifier(value=str(value)))
        except Exception:
            return False

    if new_item is not None:
        list_obj.append(new_item)
        return True

    return False


def _create_list_item_for_parent(parent_obj: Any, list_attr_name: str) -> Any:
    """Create a list element instance using the parent's type hints."""
    parent_class = type(parent_obj)
    if not hasattr(parent_class, "model_fields"):
        return None

    field_info = parent_class.model_fields.get(list_attr_name)
    if not field_info or not field_info.annotation:
        return None

    annotation = field_info.annotation
    origin = getattr(annotation, "__origin__", None)
    args = getattr(annotation, "__args__", ())

    if origin is not list or not args:
        return None

    element_type = args[0]
    element_origin = getattr(element_type, "__origin__", None)
    if element_origin is type(None):
        return None

    try:
        return element_type()
    except Exception:
        return None


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


def _create_list_item_from_parent(root_obj: Any, path_parts: list[str], index: int) -> Any:
    """Create a list item based on the parent object's type hints.

    For paths like "delivery[0]", this navigates to "delivery" on root_obj,
    determines the list element type, and creates a new instance.
    """
    if not path_parts:
        return None

    # Navigate to the list attribute
    current = root_obj
    for part in path_parts:
        if part.startswith("[") and part.endswith("]"):
            # Skip index parts - we're looking for the list attribute
            continue
        if hasattr(current, part):
            current = getattr(current, part)
            if current is None:
                return None
        else:
            return None

    # At this point, 'current' should be the list
    # We need to get the parent object and the list attribute name to find the type
    parent = root_obj
    list_attr_name = path_parts[-1] if path_parts else None

    # Navigate to the parent of the list
    for i, part in enumerate(path_parts[:-1]):
        if part.startswith("[") and part.endswith("]"):
            idx = int(part[1:-1])
            if isinstance(parent, list) and 0 <= idx < len(parent):
                parent = parent[idx]
            else:
                return None
        elif hasattr(parent, part):
            parent = getattr(parent, part)
            if parent is None:
                return None

    # Now try to get the list element type from parent's type hints
    try:
        parent_class = type(parent)
        if hasattr(parent_class, "model_fields") and list_attr_name:
            field_info = parent_class.model_fields.get(list_attr_name)
            if field_info and field_info.annotation:
                annotation = field_info.annotation
                # Handle list[T] annotation
                origin = getattr(annotation, "__origin__", None)
                if origin is list:
                    args = getattr(annotation, "__args__", ())
                    if args:
                        element_type = args[0]
                        # Handle Optional or Union types in element
                        if getattr(element_type, "__origin__", None) is type(None):
                            return None
                        # Try to instantiate the element type
                        if hasattr(element_type, "__call__"):
                            return element_type()
    except Exception:
        pass

    return None


def _create_intermediate(obj: Any, attr_name: str) -> bool:
    """Try to create an intermediate object for a path."""
    # This is a simplified version - in practice, you'd use type hints
    # to determine what class to instantiate
    try:
        # For Pydantic models, try to get the field type
        # Access model_fields from the class, not the instance
        obj_class = type(obj)
        if hasattr(obj_class, "model_fields"):
            field_info = obj_class.model_fields.get(attr_name)
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
# Deferred Field Collection Utilities
# =============================================================================


def get_field_type_for_path(model_class: type, path: str) -> type | None:
    """
    Get the type annotation for a field at the given path.

    Args:
        model_class: The Pydantic model class
        path: Dot-separated path like "order_reference" or "order_reference.id"
              or "payment_terms[0]" for list item types

    Returns:
        The type annotation, or None if path not found
    """
    if not hasattr(model_class, "model_fields"):
        return None

    parts = _parse_path_parts(path)
    current_type = model_class

    for part in parts:
        if part.startswith("[") and part.endswith("]"):
            # List index - get the list's element type
            origin = getattr(current_type, "__origin__", None)
            if origin is list:
                args = getattr(current_type, "__args__", ())
                if args:
                    current_type = args[0]
                else:
                    return None
            else:
                return None
        else:
            # Attribute access
            if not hasattr(current_type, "model_fields"):
                return None

            field_info = current_type.model_fields.get(part)
            if not field_info or not field_info.annotation:
                return None

            annotation = field_info.annotation
            origin = getattr(annotation, "__origin__", None)
            args = getattr(annotation, "__args__", ())

            # If it's a list type, keep it as-is (next part might be an index)
            if origin is list:
                current_type = annotation
                continue

            if origin is type(None):
                return None

            # Handle Union types (like Optional)
            if hasattr(origin, "__name__") and origin.__name__ == "UnionType":
                # Python 3.10+ union type
                for arg in args:
                    if arg is not type(None):
                        current_type = arg
                        break
            elif args:
                # Check for Optional pattern (Union[X, None])
                non_none_args = [a for a in args if a is not type(None)]
                if non_none_args:
                    # Check if the non-None type is a list
                    inner_type = non_none_args[0]
                    inner_origin = getattr(inner_type, "__origin__", None)
                    if inner_origin is list:
                        current_type = inner_type  # Keep list type
                    else:
                        current_type = inner_type
                else:
                    current_type = annotation
            else:
                current_type = annotation

    return current_type


def get_required_fields(model_class: type) -> set[str]:
    """Get the set of required field names for a Pydantic model."""
    required = set()
    if hasattr(model_class, "model_fields"):
        for name, field_info in model_class.model_fields.items():
            if field_info.is_required():
                required.add(name)
    return required


def can_instantiate_with_fields(model_class: type, available_fields: set[str]) -> bool:
    """Check if a model can be instantiated with the given fields."""
    required = get_required_fields(model_class)
    return required <= available_fields


def get_parent_path(path: str) -> str | None:
    """
    Get the parent path from a nested path.

    Examples:
        "order_reference.id" -> "order_reference"
        "order_reference.document_reference.id" -> "order_reference.document_reference"
        "payment_terms[0].settlement_period_days" -> "payment_terms[0]"
        "id" -> None (no parent)
    """
    parts = _parse_path_parts(path)
    if len(parts) <= 1:
        return None
    return ".".join(parts[:-1]).replace(".[", "[")


def get_field_name(path: str) -> str:
    """Get the final field name from a path."""
    parts = _parse_path_parts(path)
    return parts[-1] if parts else path


def split_list_item_path(path: str) -> tuple[str, str] | None:
    """Split a path into list item path and field subpath.

    Example:
        "delivery[0].requested_delivery_period.end_date"
        -> ("delivery[0]", "requested_delivery_period.end_date")
    """
    parts = _parse_path_parts(path)
    for i in range(len(parts) - 1, -1, -1):
        part = parts[i]
        if part.startswith("[") and part.endswith("]") and part[1:-1].isdigit():
            list_item_parts = parts[: i + 1]
            remaining_parts = parts[i + 1 :]
            if not remaining_parts:
                return None
            list_item_path = ".".join(list_item_parts).replace(".[", "[")
            sub_path = ".".join(remaining_parts).replace(".[", "[")
            return list_item_path, sub_path
    return None


def analyze_field_groups(field_mappings: list) -> dict[str, list]:
    """
    Analyze field mappings to identify groups that target the same parent.

    Returns dict mapping parent path to list of (field_name, field_mapping) tuples.
    Only includes paths that have nested fields (contain "." in semantic path).
    """
    groups: dict[str, list] = {}

    for fm in field_mappings:
        semantic_path = fm.semantic.path
        parent = get_parent_path(semantic_path)

        if parent:
            field_name = get_field_name(semantic_path)
            if parent not in groups:
                groups[parent] = []
            groups[parent].append((field_name, fm))

    return groups


def _add_deferred_value(
    deferred_values: dict[str, dict[str, Any]],
    semantic_path: str,
    value: Any,
) -> bool:
    """Record a deferred value for later nested object creation."""
    list_item_info = split_list_item_path(semantic_path)
    if list_item_info:
        list_item_path, field_path = list_item_info
        if list_item_path not in deferred_values:
            deferred_values[list_item_path] = {}
        deferred_values[list_item_path][field_path] = value
        return True

    parent_path = get_parent_path(semantic_path)
    if parent_path:
        if parent_path not in deferred_values:
            deferred_values[parent_path] = {}
        field_name = get_field_name(semantic_path)
        deferred_values[parent_path][field_name] = value
        return True

    return False


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

        # Compute which segments have mappings defined
        self._mapped_segments = self._get_mapped_segments()
        self._mapped_qualifiers = self._get_mapped_qualifiers()
        self._mapped_elements = self._get_mapped_elements()

        # Analyze field groups for deferred nested object creation
        self._header_field_groups = analyze_field_groups(self.mapping.field_mappings)
        # Combine with qualified mappings
        for qm in self.mapping.qualified_mappings:
            for mappings in qm.mappings.values():
                qm_groups = analyze_field_groups(mappings)
                for parent, fields in qm_groups.items():
                    if parent not in self._header_field_groups:
                        self._header_field_groups[parent] = []
                    self._header_field_groups[parent].extend(fields)

    def _get_mapped_segments(self) -> set[str]:
        """Get set of segment tags that have mappings defined."""
        segments = set()
        for fm in self.mapping.field_mappings:
            if hasattr(fm.x12, 'segment'):
                segments.add(fm.x12.segment)
        for qm in self.mapping.qualified_mappings:
            segments.add(qm.qualifier_path.segment)
        for lm in self.mapping.loop_mappings:
            segments.add(lm.loop_id)
            for fm in lm.field_mappings:
                if hasattr(fm.x12, 'segment'):
                    segments.add(fm.x12.segment)
        for pm in self.mapping.party_mappings:
            segments.add(pm.loop_id)
        return segments

    def _get_mapped_qualifiers(self) -> dict[str, set[str]]:
        """Get dict of segment -> set of mapped qualifiers."""
        qualifiers: dict[str, set[str]] = {}
        for qm in self.mapping.qualified_mappings:
            seg = qm.qualifier_path.segment
            if seg not in qualifiers:
                qualifiers[seg] = set()
            qualifiers[seg].update(qm.mappings.keys())
        return qualifiers

    def _get_mapped_elements(self) -> dict[str, set[int]]:
        """Get dict of segment -> set of mapped element indices."""
        elements: dict[str, set[int]] = {}
        # From field mappings
        for fm in self.mapping.field_mappings:
            if hasattr(fm.x12, 'segment') and hasattr(fm.x12, 'element'):
                seg = fm.x12.segment
                if seg not in elements:
                    elements[seg] = set()
                elements[seg].add(fm.x12.element)
        # From qualified mappings (the qualifier element)
        for qm in self.mapping.qualified_mappings:
            seg = qm.qualifier_path.segment
            if seg not in elements:
                elements[seg] = set()
            elements[seg].add(qm.qualifier_path.element)
            # Also the mapped elements from each qualifier's mappings
            for mapping in qm.mappings.values():
                for fm in mapping:
                    if hasattr(fm.x12, 'segment') and fm.x12.segment == seg:
                        elements[seg].add(fm.x12.element)
        # From loop mappings
        for lm in self.mapping.loop_mappings:
            for fm in lm.field_mappings:
                if hasattr(fm.x12, 'segment') and hasattr(fm.x12, 'element'):
                    seg = fm.x12.segment
                    if seg not in elements:
                        elements[seg] = set()
                    elements[seg].add(fm.x12.element)

        # Special handling: FOB*02, FOB*03, FOB*05 are handled by _map_fob_to_delivery
        # for transactions 850, 810, 856
        if self.mapping.transaction_id in ("850", "810", "856"):
            if "FOB" not in elements:
                elements["FOB"] = set()
            elements["FOB"].update({2, 3, 5})

            # TD5*02, TD5*03, TD5*04, TD5*05, TD5*12 are handled by _map_td5_to_shipment
            if "TD5" not in elements:
                elements["TD5"] = set()
            elements["TD5"].update({2, 3, 4, 5, 12})

            # MSG*01 is handled by _map_msg_notes
            if "MSG" not in elements:
                elements["MSG"] = set()
            elements["MSG"].add(1)

            # PO1*06-25 are product ID qualifier/value pairs handled by _extract_po1_product_ids
            if "PO1" not in elements:
                elements["PO1"] = set()
            elements["PO1"].update(range(6, 26))

            # IT1*06-25 are product ID qualifier/value pairs handled by _extract_it1_product_ids
            if "IT1" not in elements:
                elements["IT1"] = set()
            elements["IT1"].update(range(6, 26))

            # TDS amounts are handled by _map_tds_totals (converts cents)
            if "TDS" not in elements:
                elements["TDS"] = set()
            elements["TDS"].update([1, 2, 3, 4])

            # CAD carrier details handled by _map_cad_to_shipment
            if "CAD" not in elements:
                elements["CAD"] = set()
            elements["CAD"].update([1, 4, 5, 7, 8, 9])

            # NTE notes handled by _map_nte_notes
            if "NTE" not in elements:
                elements["NTE"] = set()
            elements["NTE"].update([1, 2])

            # CTT is X12 control segment for validation only - not mapped to semantic model
            # CTT*01 = line count, CTT*02 = hash total
            if "CTT" not in elements:
                elements["CTT"] = set()
            elements["CTT"].update([1, 2])

            # AMT*01 is the qualifier, AMT*02 is the value - both handled by _map_amt_totals
            if "AMT" not in elements:
                elements["AMT"] = set()
            elements["AMT"].update({1, 2})

            # CUR*01 is entity identifier (e.g., "SN" = Selling Party) - qualifies currency
            # Not mapped because document_currency_code (CUR*02) applies to whole document
            if "CUR" not in elements:
                elements["CUR"] = set()
            elements["CUR"].add(1)

            # REF*03 is reference description - would need special handling to link
            # to the document reference created by REF*02. Lower priority enhancement.
            if "REF" not in elements:
                elements["REF"] = set()
            elements["REF"].add(3)

        return elements

    def _collect_segment_tags(
        self,
        content: list["ParsedSegment | LoopInstance"],
    ) -> dict[str, int]:
        """Collect counts of all segment tags in the document."""
        counts: dict[str, int] = {}

        def collect(items: list) -> None:
            for item in items:
                if hasattr(item, "tag"):
                    tag = item.tag
                    counts[tag] = counts.get(tag, 0) + 1
                if hasattr(item, "segments"):
                    # It's a loop - collect from its segments
                    collect(item.segments)
                if hasattr(item, "nested_loops"):
                    for nested in item.nested_loops:
                        collect([nested])

        collect(content)
        return counts

    def _report_unmapped_segments(
        self,
        all_segment_tags: dict[str, int],
        content: list["ParsedSegment | LoopInstance"],
        accumulator: ErrorAccumulator,
        metrics: MappingMetrics,
    ) -> None:
        """Report segments that have no mapping defined."""
        from .diagnostics import UnmappedData

        # Segments that have explicit mappings or are handled specially
        handled_segments = self._mapped_segments | {
            "ST", "SE",  # Transaction envelope
        }
        # Add segments handled by special handlers for 850/810/856
        if self.mapping.transaction_id in ("850", "810", "856"):
            # TD5 -> _map_td5_to_shipment, MSG -> _map_msg_notes, AMT -> _map_amt_totals
            # CTT is X12 control segment (intentionally not mapped to semantic model)
            handled_segments |= {"TD5", "MSG", "AMT", "CTT"}
        # Add 810-specific handled segments
        if self.mapping.transaction_id == "810":
            # TDS -> _map_tds_totals, CAD -> _map_cad_to_shipment, NTE -> _map_nte_notes
            handled_segments |= {"TDS", "CAD", "NTE"}
        # N2, N3, N4, PER are only handled WITHIN N1 loops, not at header level

        # Also include segments from loops that have mappings
        for lm in self.mapping.loop_mappings:
            for fm in lm.field_mappings:
                if hasattr(fm.x12, 'segment'):
                    handled_segments.add(fm.x12.segment)
            for qm in lm.qualified_mappings:
                handled_segments.add(qm.qualifier_path.segment)

        # First pass: report unmapped segment TYPES (like TD5, N9, etc.)
        for tag, count in all_segment_tags.items():
            if tag not in handled_segments and tag not in {"N2", "N3", "N4", "PER"}:
                # Get sample values from the first occurrence
                for item in content:
                    if hasattr(item, "tag") and item.tag == tag:
                        element_values = []
                        for i in range(1, 10):
                            val = _get_element_value(item, i)
                            if val:
                                element_values.append(val)
                            else:
                                break

                        metrics.record_unmapped_segment(UnmappedData(
                            segment_tag=tag,
                            qualifier=element_values[0] if element_values else None,
                            value="*".join(element_values) if element_values else None,
                            reason="no_mapping",
                        ))

                        accumulator.add_warning(
                            MappingErrorCode.UNMAPPED_SEGMENT,
                            f"No mapping defined for segment {tag} ({count} occurrence(s))",
                            source_path=tag,
                        )
                        break  # Only report once per segment type

        # Second pass: check for header-level N2/N3/N4 segments
        # PER is now handled at header level for 850/810/856, but N2/N3/N4 are only in N1 loops
        header_level_party_segments = {"N2", "N3", "N4"}
        # Only flag header-level PER if we don't process it
        if self.mapping.transaction_id not in ("850", "810", "856"):
            header_level_party_segments.add("PER")
        for item in content:
            # Only check direct children of content (not inside loops)
            if hasattr(item, "tag") and item.tag in header_level_party_segments:
                element_values = []
                for i in range(1, 10):
                    val = _get_element_value(item, i)
                    if val:
                        element_values.append(val)
                    else:
                        break

                metrics.record_unmapped_segment(UnmappedData(
                    segment_tag=item.tag,
                    qualifier=element_values[0] if element_values else None,
                    value="*".join(element_values) if element_values else None,
                    reason="header_level",
                ))

                accumulator.add_warning(
                    MappingErrorCode.UNMAPPED_SEGMENT,
                    f"Header-level {item.tag} segment not mapped (only handled within N1 loops)",
                    source_path=f"{item.tag}*{element_values[0]}" if element_values else item.tag,
                )

        # Third pass: check for unmapped elements within mapped segments
        self._report_unmapped_elements(content, accumulator, metrics)

    def _report_unmapped_elements(
        self,
        content: list["ParsedSegment | LoopInstance"],
        accumulator: ErrorAccumulator,
        metrics: MappingMetrics,
    ) -> None:
        """Report elements within mapped segments that have values but no mapping."""
        from .diagnostics import UnmappedData

        reported: set[tuple[str, int]] = set()  # Track (segment, element) pairs reported

        def check_segment(segment: "ParsedSegment") -> None:
            tag = segment.tag
            if tag not in self._mapped_elements:
                return  # Segment itself is unmapped, already reported

            mapped_elements = self._mapped_elements[tag]

            # Check each element in the segment
            for i in range(1, 26):  # X12 elements typically up to 25
                val = _get_element_value(segment, i)
                if val is None or (isinstance(val, str) and not val.strip()):
                    continue  # No value or empty string
                if i in mapped_elements:
                    continue  # Element is mapped

                key = (tag, i)
                if key in reported:
                    continue  # Already reported this element for this segment type
                reported.add(key)

                metrics.record_unmapped_segment(UnmappedData(
                    segment_tag=tag,
                    element_index=i,
                    value=val,
                    reason="unmapped_element",
                ))

                accumulator.add_warning(
                    MappingErrorCode.UNMAPPED_ELEMENT,
                    f"Element {tag}*{i:02d} has value but no mapping: {val!r}",
                    source_path=f"{tag}*{i:02d}",
                    value=val,
                )

        def check_content(items: list) -> None:
            from edi_schema.x12.ast import ParsedSegment, RawSegment

            for item in items:
                if isinstance(item, (ParsedSegment, RawSegment)):
                    check_segment(item)
                if hasattr(item, "segments"):
                    check_content(item.segments)
                if hasattr(item, "nested_loops"):
                    for nested in item.nested_loops:
                        check_content([nested])

        check_content(content)

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

            # Collect all segments in the document for unmapped tracking
            all_segment_tags = self._collect_segment_tags(content)
            if metrics:
                metrics.total_segments_in_document = sum(all_segment_tags.values())

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

            # Phase 4: Map optional header-level fields (with deferred collection)
            deferred_values: dict[str, dict[str, Any]] = {}
            field_start = time.perf_counter()
            self._map_optional_field_mappings(
                model,
                content,
                self.mapping.field_mappings,
                accumulator,
                metrics,
                trace,
                deferred_values,
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
                    deferred_values,
                )

            # Phase 5.1: Resolve deferred nested fields
            # This creates nested objects (like order_reference) from collected values
            if deferred_values:
                self._resolve_deferred_fields(
                    model, deferred_values, accumulator, metrics, trace
                )

            # Phase 5.5: Map SAC (Allowance/Charge) segments at header level
            if self.mapping.transaction_id in ("850", "810", "856"):
                self._map_sac_segments(model, content, metrics, trace)

            # Phase 5.6: Map TXI (Tax) segments at header level
            if self.mapping.transaction_id in ("850", "810"):
                self._map_txi_segments(model, content, metrics, trace)

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

            # Phase 6.5: Map header-level PER segments (outside N1 loops)
            if self.mapping.transaction_id in ("850", "810", "856"):
                self._map_header_per_segments(model, content, metrics, trace)

            # Phase 6.6: Map FOB delivery terms to delivery (now that delivery exists)
            if self.mapping.transaction_id in ("850", "810", "856"):
                self._map_fob_to_delivery(model, content, metrics, trace)

            # Phase 6.7: Map TD5 carrier/shipping info to delivery[0].shipment
            if self.mapping.transaction_id in ("850", "810", "856"):
                self._map_td5_to_shipment(model, content, metrics, trace)

            # Phase 6.8: Map MSG notes to note list
            if self.mapping.transaction_id in ("850", "810", "856"):
                self._map_msg_notes(model, content, metrics, trace)

            # Phase 6.9: Map AMT totals (creates MonetaryTotal/Amount objects)
            if self.mapping.transaction_id in ("850", "810", "856"):
                self._map_amt_totals(model, content, metrics, trace)

            # Phase 6.10: Map DTM despatch dates (creates Despatch object)
            if self.mapping.transaction_id in ("850", "810", "856"):
                self._map_dtm_despatch(model, content, metrics, trace)

            # Phase 6.11: Map TDS totals (810-specific, cents conversion)
            if self.mapping.transaction_id == "810":
                self._map_tds_totals(model, content, metrics, trace)

            # Phase 6.12: Map CAD carrier details (810-specific)
            if self.mapping.transaction_id == "810":
                self._map_cad_to_shipment(model, content, metrics, trace)

            # Phase 6.13: Map NTE notes (810-specific header notes)
            if self.mapping.transaction_id == "810":
                self._map_nte_notes(model, content, metrics, trace)

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

            # Phase 9: Report unmapped segments
            if self.warn_on_unmapped and metrics:
                self._report_unmapped_segments(
                    all_segment_tags,
                    content,
                    accumulator,
                    metrics,
                )

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
        deferred_values: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """Map optional (non-required) fields to the model.

        Args:
            model: The model to set values on
            content: Parsed X12 content
            field_mappings: Field mappings to apply
            accumulator: Error accumulator
            metrics: Optional metrics collector
            trace: Optional debug trace
            deferred_values: Optional dict to collect values for nested paths
                             that can't be set immediately (parent is None)
        """
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

            # Try to set the value
            if set_nested_attr(model, field_mapping.semantic.path, value):
                if metrics:
                    metrics.fields_mapped += 1
                if trace:
                    trace.add_field(str(path), field_mapping.semantic.path, value)
            else:
                # Check if this is a nested path that should be deferred
                semantic_path = field_mapping.semantic.path
                if deferred_values is not None and _add_deferred_value(
                    deferred_values, semantic_path, value
                ):
                    if metrics:
                        metrics.fields_mapped += 1  # Count as mapped (deferred)
                    if trace:
                        trace.add_field(str(path), f"[deferred]{semantic_path}", value)
                else:
                    if metrics:
                        metrics.fields_skipped += 1
                    # Generate warning for failed mapping when we had a value
                    if self.warn_on_unmapped and value is not None:
                        accumulator.add_warning(
                            MappingErrorCode.CANNOT_SET_FIELD,
                            f"Failed to set {field_mapping.semantic.path}: path does not exist on model",
                            source_path=str(path),
                            target_path=field_mapping.semantic.path,
                            value=value,
                        )

    def _resolve_deferred_fields(
        self,
        model: Any,
        deferred_values: dict[str, dict[str, Any]],
        accumulator: ErrorAccumulator,
        metrics: MappingMetrics | None,
        trace: MappingTrace | None,
    ) -> None:
        """Create nested objects from collected deferred field values.

        This resolves paths like "order_reference.id" by creating the
        OrderReference object with all collected fields and setting it
        on the parent model.
        """
        for parent_path, field_values in deferred_values.items():
            # Handle list index paths like "payment_terms[0]"
            if "[" in parent_path and "]" in parent_path:
                self._resolve_deferred_list_item(
                    model, parent_path, field_values, accumulator, metrics, trace
                )
            else:
                self._resolve_deferred_object(
                    model, parent_path, field_values, accumulator, metrics, trace
                )

    def _resolve_deferred_object(
        self,
        model: Any,
        parent_path: str,
        field_values: dict[str, Any],
        accumulator: ErrorAccumulator,
        metrics: MappingMetrics | None,
        trace: MappingTrace | None,
    ) -> None:
        """Create and set a nested object from collected field values."""
        # Get the type for this path
        parent_type = get_field_type_for_path(type(model), parent_path)
        if parent_type is None:
            if self.warn_on_unmapped:
                accumulator.add_warning(
                    MappingErrorCode.CANNOT_SET_FIELD,
                    f"Cannot resolve type for deferred path: {parent_path}",
                    source_path="[deferred]",
                    target_path=parent_path,
                )
            return

        # Check if we have the required fields
        required = get_required_fields(parent_type)
        available = set(field_values.keys())

        if not required <= available:
            missing = required - available
            if self.warn_on_unmapped:
                accumulator.add_warning(
                    MappingErrorCode.CANNOT_SET_FIELD,
                    f"Cannot create {parent_type.__name__} for {parent_path}: "
                    f"missing required fields {missing}",
                    source_path="[deferred]",
                    target_path=parent_path,
                )
            return

        # Try to create the object
        try:
            instance = parent_type(**field_values)
            if set_nested_attr(model, parent_path, instance):
                if trace:
                    trace.add_field(
                        "[deferred]",
                        parent_path,
                        f"Created {parent_type.__name__} with {list(field_values.keys())}",
                    )
            else:
                if self.warn_on_unmapped:
                    accumulator.add_warning(
                        MappingErrorCode.CANNOT_SET_FIELD,
                        f"Failed to set deferred object at {parent_path}",
                        source_path="[deferred]",
                        target_path=parent_path,
                    )
        except Exception as e:
            if self.warn_on_unmapped:
                accumulator.add_warning(
                    MappingErrorCode.CANNOT_SET_FIELD,
                    f"Failed to create {parent_type.__name__} for {parent_path}: {e}",
                    source_path="[deferred]",
                    target_path=parent_path,
                )

    def _resolve_deferred_list_item(
        self,
        model: Any,
        parent_path: str,
        field_values: dict[str, Any],
        accumulator: ErrorAccumulator,
        metrics: MappingMetrics | None,
        trace: MappingTrace | None,
    ) -> None:
        """Create and set a list item from collected field values.

        Handles paths like "payment_terms[0].settlement_period_days" where
        we need to create a PaymentTerms object and add it to the list.
        """
        import re

        # Parse the list path: "payment_terms[0]" -> ("payment_terms", 0)
        match = re.match(r"^(.+)\[(\d+)\]$", parent_path)
        if not match:
            return

        list_path = match.group(1)
        target_index = int(match.group(2))

        # Get or create the list
        lst = get_nested_attr(model, list_path)
        if lst is None:
            if not set_nested_attr(model, list_path, []):
                if self.warn_on_unmapped:
                    accumulator.add_warning(
                        MappingErrorCode.CANNOT_SET_FIELD,
                        f"Cannot resolve list for deferred path: {parent_path}",
                        source_path="[deferred]",
                        target_path=parent_path,
                    )
                return
            lst = get_nested_attr(model, list_path)

        if not isinstance(lst, list):
            if self.warn_on_unmapped:
                accumulator.add_warning(
                    MappingErrorCode.CANNOT_SET_FIELD,
                    f"Cannot resolve list for deferred path: {parent_path}",
                    source_path="[deferred]",
                    target_path=parent_path,
                )
            return

        # Get the item type
        item_type = get_field_type_for_path(type(model), f"{list_path}[0]")
        if item_type is None:
            if self.warn_on_unmapped:
                accumulator.add_warning(
                    MappingErrorCode.CANNOT_SET_FIELD,
                    f"Cannot resolve item type for deferred list: {list_path}",
                    source_path="[deferred]",
                    target_path=parent_path,
                )
            return

        # Check if we have required fields
        required = get_required_fields(item_type)
        available = {key.split(".")[0] for key in field_values.keys()}

        if not required <= available:
            missing = required - available
            if self.warn_on_unmapped:
                accumulator.add_warning(
                    MappingErrorCode.CANNOT_SET_FIELD,
                    f"Cannot create {item_type.__name__} for {parent_path}: "
                    f"missing required fields {missing}",
                    source_path="[deferred]",
                    target_path=parent_path,
                )
            return

        # Create the item
        try:
            item_data: dict[str, Any] = {}
            for field_name, field_value in field_values.items():
                if "." in field_name:
                    self._set_nested_dict_value(item_data, field_name, field_value)
                else:
                    item_data[field_name] = field_value

            instance = item_type(**item_data)

            # Extend list if needed
            while len(lst) <= target_index:
                lst.append(instance if len(lst) == target_index else None)

            # Set at target index (if we appended at the right index, it's already there)
            if len(lst) > target_index and lst[target_index] is None:
                lst[target_index] = instance

            if trace:
                trace.add_field(
                    "[deferred]",
                    parent_path,
                    f"Created {item_type.__name__} with {list(field_values.keys())}",
                )
        except Exception as e:
            if self.warn_on_unmapped:
                accumulator.add_warning(
                    MappingErrorCode.CANNOT_SET_FIELD,
                    f"Failed to create {item_type.__name__} for {parent_path}: {e}",
                    source_path="[deferred]",
                    target_path=parent_path,
                )

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
        deferred_values: dict[str, dict[str, Any]] | None = None,
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
                # Skip qualifiers handled by special handlers (850/810/856)
                if self.mapping.transaction_id in ("850", "810", "856"):
                    # DTM*010, DTM*037 handled by _map_dtm_despatch
                    if qualifier_path.segment == "DTM" and qualifier_value in ("010", "037"):
                        continue

                # Track and warn about unmapped qualifier
                if metrics:
                    metrics.record_unmapped_qualifier(qualifier_path.segment, qualifier_value)
                    # Get all element values for context
                    element_values = []
                    for i in range(1, 10):
                        val = _get_element_value(segment, i)
                        if val:
                            element_values.append(val)
                        else:
                            break
                    from .diagnostics import UnmappedData
                    metrics.record_unmapped_segment(UnmappedData(
                        segment_tag=qualifier_path.segment,
                        qualifier=qualifier_value,
                        value="*".join(element_values) if element_values else None,
                        reason="unknown_qualifier",
                    ))
                if self.warn_on_unmapped:
                    accumulator.add_warning(
                        MappingErrorCode.UNMAPPED_QUALIFIER,
                        f"No mapping for {qualifier_path.segment}*{qualifier_value}",
                        source_path=f"{qualifier_path.segment}*{qualifier_value}",
                    )
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
                    # Check if this is a nested path that should be deferred
                    semantic_path = field_mapping.semantic.path
                    if deferred_values is not None and _add_deferred_value(
                        deferred_values, semantic_path, value
                    ):
                        if metrics:
                            metrics.fields_mapped += 1  # Count as mapped (deferred)
                        if trace:
                            trace.add_field(
                                f"{path.segment}[{qualifier_value}]*{path.element}",
                                f"[deferred]{semantic_path}",
                                value,
                            )
                    else:
                        if metrics:
                            metrics.fields_skipped += 1
                        # Generate warning for failed qualified mapping
                        if self.warn_on_unmapped and value is not None:
                            source = f"{path.segment}[{qualifier_value}]*{path.element}"
                            accumulator.add_warning(
                                MappingErrorCode.CANNOT_SET_FIELD,
                                f"Failed to set {field_mapping.semantic.path}: path does not exist on model",
                                source_path=source,
                                target_path=field_mapping.semantic.path,
                                value=value,
                            )

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
        # - Indexed: "delivery[0].despatch.despatch_party" -> specific location

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
        elif "[0]" in path_str:
            # Handle indexed list access like "delivery[0].despatch.despatch_party"
            self._map_party_to_indexed_path(
                model, loop, path_str, party_mapping, accumulator, metrics, trace
            )
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

    def _map_party_to_indexed_path(
        self,
        model: Any,
        loop: "LoopInstance",
        path_str: str,
        party_mapping: PartyLoopMapping,
        accumulator: ErrorAccumulator,
        metrics: MappingMetrics | None,
        trace: MappingTrace | None,
    ) -> None:
        """Map party to an indexed path like 'delivery[0].despatch.despatch_party'."""
        from edi_schema.semantic.models import Delivery, Despatch, Party

        # Parse the path: delivery[0].despatch.despatch_party
        import re

        match = re.match(r"(\w+)\[(\d+)\]\.(.+)", path_str)
        if not match:
            if metrics:
                metrics.fields_skipped += 1
            return

        list_name, index_str, rest_path = match.groups()
        index = int(index_str)

        # Get the list
        list_obj = get_nested_attr(model, list_name)
        if not isinstance(list_obj, list):
            if metrics:
                metrics.fields_skipped += 1
            return

        # Ensure the list has enough items
        while len(list_obj) <= index:
            if list_name == "delivery":
                list_obj.append(Delivery())
            else:
                # Unknown list type
                if metrics:
                    metrics.fields_skipped += 1
                return

        target_obj = list_obj[index]

        # Now navigate the rest of the path and set the party
        # e.g., "despatch.despatch_party"
        path_parts = rest_path.split(".")
        current = target_obj

        for i, part in enumerate(path_parts[:-1]):
            next_obj = getattr(current, part, None)
            if next_obj is None:
                # Create intermediate objects
                if part == "despatch":
                    next_obj = Despatch()
                    setattr(current, part, next_obj)
                else:
                    if metrics:
                        metrics.fields_skipped += 1
                    return
            current = next_obj

        # Create and populate the party
        party = Party()
        self._populate_party_fields(party, loop, party_mapping, accumulator, metrics, trace)

        # Set the party at the final location
        final_attr = path_parts[-1]
        setattr(current, final_attr, party)

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
        from edi_schema.semantic.models import Despatch, Party

        party = Party()
        self._populate_party_fields(party, loop, party_mapping, accumulator, metrics, trace)

        if rest_path.endswith("delivery_party"):
            set_nested_attr(obj, "delivery_party", party)
            # Also set delivery_location from postal_address
            if party.postal_address:
                set_nested_attr(obj, "delivery_location", party.postal_address)
        elif rest_path.endswith("despatch_party"):
            # Handle nested paths like "despatch.despatch_party"
            if "." in rest_path:
                parts = rest_path.split(".")
                current = obj
                for part in parts[:-1]:
                    next_obj = getattr(current, part, None)
                    if next_obj is None:
                        if part == "despatch":
                            next_obj = Despatch()
                            setattr(current, part, next_obj)
                        else:
                            return
                    current = next_obj
                setattr(current, parts[-1], party)
            else:
                set_nested_attr(obj, rest_path, party)
        else:
            # Generic case: just set the path
            set_nested_attr(obj, rest_path, party)

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
        from edi_schema.semantic.models import Quantity

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

                # Initialize nested dict if needed
                if top_field not in item_data:
                    item_data[top_field] = {}

                # Store value in nested dict for later object construction
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

        # Convert nested dicts to proper Pydantic model objects
        for field_name in list(item_data.keys()):
            if isinstance(item_data[field_name], dict) and item_data[field_name]:
                field_type = get_field_type_for_path(item_type, field_name)
                if field_type and hasattr(field_type, "model_validate"):
                    try:
                        item_data[field_name] = field_type.model_validate(item_data[field_name])
                    except Exception:
                        # If validation fails, try direct construction with defaults
                        field_dict = item_data[field_name]
                        # Handle Quantity specially - needs unit_code default
                        if field_type.__name__ == "Quantity" and "unit_code" not in field_dict:
                            field_dict["unit_code"] = "EA"
                        item_data[field_name] = field_type(**field_dict)
            elif isinstance(item_data[field_name], dict) and not item_data[field_name]:
                # Empty dict - create empty instance
                field_type = get_field_type_for_path(item_type, field_name)
                if field_type and hasattr(field_type, "model_validate"):
                    item_data[field_name] = field_type()

        # Ensure required fields have values
        for required_field in model_required_fields:
            if required_field not in item_data:
                field_type = get_field_type_for_path(item_type, required_field)
                # Provide defaults for common required fields
                if required_field == "id":
                    item_data["id"] = ""
                elif field_type and hasattr(field_type, "model_validate"):
                    # Create empty instance for Pydantic models
                    if field_type.__name__ == "Quantity":
                        item_data[required_field] = Quantity(value=Decimal("0"), unit_code="EA")
                    else:
                        try:
                            item_data[required_field] = field_type()
                        except Exception:
                            pass  # Skip if we can't create a default

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

        # Collect deferred values for nested fields that can't be set directly
        deferred_values: dict[str, dict[str, Any]] = {}

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
                # Check if this is a nested path that should be deferred
                if _add_deferred_value(deferred_values, semantic_path, value):
                    if metrics:
                        metrics.fields_mapped += 1  # Count as mapped (deferred)
                    if trace:
                        trace.add_field(str(path), f"[deferred]{semantic_path}", value)
                else:
                    if metrics:
                        metrics.fields_skipped += 1
                    # Generate warning for failed loop item mapping
                    if self.warn_on_unmapped and value is not None:
                        accumulator.add_warning(
                            MappingErrorCode.CANNOT_SET_FIELD,
                            f"Failed to set {semantic_path}: path does not exist on model",
                            source_path=str(path),
                            target_path=semantic_path,
                            value=value,
                        )

        # Resolve deferred nested fields for this loop item
        if deferred_values:
            self._resolve_deferred_fields(item, deferred_values, accumulator, metrics, trace)

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

        # Handle PO1 product ID pairs (elements 06-25)
        if loop_mapping.loop_id == "PO1":
            self._extract_po1_product_ids(item, loop, metrics, trace)
            # Handle line-level SAC segments
            self._extract_line_sac_segments(item, loop, metrics, trace)
            # Handle SCH (delivery schedule) segments
            self._extract_sch_segments(item, loop, metrics, trace)

        # Handle IT1 product ID pairs (elements 06-25) - similar to PO1
        if loop_mapping.loop_id == "IT1":
            self._extract_it1_product_ids(item, loop, metrics, trace)
            # Handle line-level SAC segments
            self._extract_line_sac_segments(item, loop, metrics, trace)
            # Handle line-level TXI segments
            self._extract_line_txi_segments(item, loop, metrics, trace)

    def _extract_line_sac_segments(
        self,
        item: Any,
        loop: "LoopInstance",
        metrics: "MappingMetrics | None",
        trace: "MappingTrace | None",
    ) -> None:
        """Extract line-level SAC (allowance/charge) segments."""
        from decimal import Decimal
        from edi_schema.semantic.models import AllowanceCharge
        from edi_schema.semantic.models.primitives import Amount

        for seg in loop.segments:
            if seg.tag != "SAC":
                continue

            # SAC*01 = Allowance/Charge Indicator
            indicator = _get_element_value(seg, 1)
            if indicator not in ("A", "C"):
                continue

            # SAC*02 = Code
            code = _get_element_value(seg, 2)

            # SAC*05 = Amount
            amount_str = _get_element_value(seg, 5)
            if not amount_str:
                continue

            try:
                amount_value = Decimal(amount_str)
            except Exception:
                continue

            # SAC*12 = Description
            description = _get_element_value(seg, 12)

            # SAC*15 = Percent
            percent_str = _get_element_value(seg, 15)
            percent = None
            if percent_str:
                try:
                    percent = Decimal(percent_str)
                except Exception:
                    pass

            charge = AllowanceCharge(
                charge_indicator=(indicator == "C"),
                allowance_charge_reason_code=code,
                allowance_charge_reason=description,
                amount=Amount(value=amount_value, currency="USD"),
                multiplier_factor_numeric=percent,
            )

            if hasattr(item, "allowance_charges"):
                item.allowance_charges.append(charge)
                if metrics:
                    metrics.fields_mapped += 1
                if trace:
                    trace.add_field("SAC (line)", "allowance_charges[+]", str(charge))

    def _extract_sch_segments(
        self,
        item: Any,
        loop: "LoopInstance",
        metrics: "MappingMetrics | None",
        trace: "MappingTrace | None",
    ) -> None:
        """Extract SCH (delivery schedule) segments for line items."""
        from decimal import Decimal
        from edi_schema.semantic.models import Delivery
        from edi_schema.semantic.models.primitives import Period, Quantity

        for seg in loop.segments:
            if seg.tag != "SCH":
                continue

            # SCH*01 = Quantity
            qty_str = _get_element_value(seg, 1)
            if not qty_str:
                continue

            try:
                qty_value = Decimal(qty_str)
            except Exception:
                continue

            # SCH*02 = Unit of measure
            uom = _get_element_value(seg, 2) or "EA"

            # SCH*05 = Date/Time Qualifier
            # SCH*06 = Date
            date_qual = _get_element_value(seg, 5)
            date_str = _get_element_value(seg, 6)

            delivery = Delivery(
                quantity=Quantity(value=qty_value, unit_code=uom),
            )

            if date_str and len(date_str) >= 8:
                from datetime import date
                try:
                    parsed_date = date(
                        int(date_str[0:4]),
                        int(date_str[4:6]),
                        int(date_str[6:8])
                    )
                    delivery.requested_delivery_period = Period(start_date=parsed_date)
                except Exception:
                    pass

            if hasattr(item, "delivery"):
                item.delivery.append(delivery)
                if metrics:
                    metrics.fields_mapped += 1
                if trace:
                    trace.add_field("SCH", "delivery[+]", str(delivery))

    def _extract_po1_product_ids(
        self,
        item: Any,
        loop: "LoopInstance",
        metrics: "MappingMetrics | None",
        trace: "MappingTrace | None",
    ) -> None:
        """Extract product ID pairs from PO1 elements 06-25."""
        from edi_schema.semantic.models import Identifier, ItemIdentification

        # Find the PO1 segment in the loop
        po1_seg = None
        for seg in loop.segments:
            if seg.tag == "PO1":
                po1_seg = seg
                break

        if po1_seg is None:
            return

        # Ensure item has an Item object
        if not hasattr(item, "item") or item.item is None:
            from edi_schema.semantic.models import Item
            item.item = Item()

        # Map product ID qualifier to (field_type, scheme_id)
        qualifier_map = {
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

        # Process pairs starting at element 6 (qualifier) and 7 (value)
        for i in range(6, 26, 2):
            qualifier = _get_element_value(po1_seg, i)
            value = _get_element_value(po1_seg, i + 1)

            if not qualifier or not value:
                continue

            field_type, scheme = qualifier_map.get(qualifier, ("additional", None))
            item_id = ItemIdentification(id=Identifier(value=value, scheme_id=scheme or qualifier))

            if field_type == "standard":
                if item.item.standard_item_identification is None:
                    item.item.standard_item_identification = item_id
                else:
                    item.item.additional_item_identifications.append(item_id)
            elif field_type == "sellers":
                if item.item.sellers_item_identification is None:
                    item.item.sellers_item_identification = item_id
                else:
                    item.item.additional_item_identifications.append(item_id)
            elif field_type == "buyers":
                if item.item.buyers_item_identification is None:
                    item.item.buyers_item_identification = item_id
                else:
                    item.item.additional_item_identifications.append(item_id)
            elif field_type == "manufacturers":
                if item.item.manufacturers_item_identification is None:
                    item.item.manufacturers_item_identification = item_id
                else:
                    item.item.additional_item_identifications.append(item_id)
            else:
                item.item.additional_item_identifications.append(item_id)

            if metrics:
                metrics.fields_mapped += 1
            if trace:
                trace.add_field(f"PO1*{i:02d}/*{i+1:02d}", f"item.{field_type}_item_identification", value)

    def _map_sac_segments(
        self,
        model: Any,
        content: list["ParsedSegment | LoopInstance"],
        metrics: "MappingMetrics | None",
        trace: "MappingTrace | None",
    ) -> None:
        """Map SAC (Allowance/Charge) segments at header level."""
        from decimal import Decimal
        from edi_schema.semantic.models import AllowanceCharge
        from edi_schema.semantic.models.primitives import Amount

        sac_segments = find_all_segments(content, "SAC")

        for sac_seg in sac_segments:
            # SAC*01 = Allowance/Charge Indicator (A=Allowance, C=Charge)
            indicator = _get_element_value(sac_seg, 1)
            if indicator not in ("A", "C"):
                continue

            # SAC*02 = Service/Promotion/Allowance/Charge Code
            code = _get_element_value(sac_seg, 2)

            # SAC*05 = Amount
            amount_str = _get_element_value(sac_seg, 5)
            if not amount_str:
                continue

            try:
                amount_value = Decimal(amount_str)
            except Exception:
                continue

            # SAC*12 = Description
            description = _get_element_value(sac_seg, 12)

            # SAC*15 = Percent
            percent_str = _get_element_value(sac_seg, 15)
            percent = None
            if percent_str:
                try:
                    percent = Decimal(percent_str)
                except Exception:
                    pass

            # Create AllowanceCharge
            charge = AllowanceCharge(
                charge_indicator=(indicator == "C"),
                allowance_charge_reason_code=code,
                allowance_charge_reason=description,
                amount=Amount(value=amount_value, currency="USD"),
                multiplier_factor_numeric=percent,
            )

            # Add to model
            if hasattr(model, "allowance_charges"):
                model.allowance_charges.append(charge)
                if metrics:
                    metrics.fields_mapped += 1
                if trace:
                    trace.add_field("SAC", "allowance_charges[+]", str(charge))

    def _map_txi_segments(
        self,
        model: Any,
        content: list["ParsedSegment | LoopInstance"],
        metrics: "MappingMetrics | None",
        trace: "MappingTrace | None",
    ) -> None:
        """Map TXI (Tax) segments at header level."""
        from decimal import Decimal
        from edi_schema.semantic.models import TaxTotal, TaxSubtotal, TaxCategory
        from edi_schema.semantic.models.primitives import Amount

        txi_segments = find_all_segments(content, "TXI")

        if not txi_segments:
            return

        # Accumulate tax amounts
        total_tax = Decimal("0")
        subtotals = []

        for txi_seg in txi_segments:
            # TXI*01 = Tax Type Code (e.g., ST=State, CT=County, CY=City)
            tax_type = _get_element_value(txi_seg, 1)

            # TXI*02 = Tax Amount
            amount_str = _get_element_value(txi_seg, 2)
            if amount_str:
                try:
                    amount = Decimal(amount_str)
                    total_tax += amount

                    # TXI*03 = Tax Percent
                    percent_str = _get_element_value(txi_seg, 3)
                    percent = None
                    if percent_str:
                        try:
                            percent = Decimal(percent_str)
                        except Exception:
                            pass

                    subtotal = TaxSubtotal(
                        tax_amount=Amount(value=amount, currency="USD"),
                        percent=percent,
                        tax_category=TaxCategory(id=tax_type) if tax_type else None,
                    )
                    subtotals.append(subtotal)
                except Exception:
                    pass

        if subtotals or total_tax > 0:
            tax_total = TaxTotal(
                tax_amount=Amount(value=total_tax, currency="USD"),
                tax_subtotals=subtotals,
            )

            if hasattr(model, "tax_total"):
                if isinstance(model.tax_total, list):
                    model.tax_total.append(tax_total)
                else:
                    model.tax_total = [tax_total]
                if metrics:
                    metrics.fields_mapped += 1
                if trace:
                    trace.add_field("TXI", "tax_total[+]", str(tax_total))

    def _map_header_per_segments(
        self,
        model: Any,
        content: list["ParsedSegment | LoopInstance"],
        metrics: "MappingMetrics | None",
        trace: "MappingTrace | None",
    ) -> None:
        """Map header-level PER (Contact) segments that appear outside N1 loops.

        Header-level PER segments specify contacts at the document level, such as:
        - PER*OC = Order Contact -> buyer_customer_party.buyer_contact
        - PER*IC = Information Contact -> accounting_customer_party contact
        - PER*BD = Buyer Contact -> buyer_customer_party.buyer_contact
        """
        from edi_schema.semantic.models import Contact, CustomerParty, Party

        # Find header-level PER segments (direct children of content, not in loops)
        for item in content:
            if not hasattr(item, "tag") or item.tag != "PER":
                continue

            # Extract contact info
            qualifier = _get_element_value(item, 1)  # OC, IC, BD, etc.
            name = _get_element_value(item, 2)

            if not name:
                continue

            contact = Contact(name=name)

            # Process paired qualifier/value elements (PER*03-08)
            for i in range(3, 9, 2):
                qual = _get_element_value(item, i)
                val = _get_element_value(item, i + 1)
                if qual and val:
                    if qual == "TE":
                        contact.telephone = val
                    elif qual == "EM":
                        contact.electronic_mail = val
                    elif qual == "FX":
                        contact.telefax = val

            if metrics:
                metrics.fields_mapped += 1

            # Map to appropriate model field based on qualifier
            if qualifier in ("OC", "BD"):
                # Order Contact or Buyer Contact -> buyer_customer_party.buyer_contact
                if hasattr(model, "buyer_customer_party"):
                    if model.buyer_customer_party is None:
                        model.buyer_customer_party = CustomerParty(party=Party())
                    model.buyer_customer_party.buyer_contact = contact
                    if trace:
                        trace.add_field(
                            f"PER*{qualifier}",
                            "buyer_customer_party.buyer_contact",
                            contact.name,
                        )
            elif qualifier == "IC":
                # Information Contact -> accounting_customer_party or buyer party
                if hasattr(model, "accounting_customer_party"):
                    if model.accounting_customer_party is None:
                        model.accounting_customer_party = CustomerParty(party=Party())
                    if model.accounting_customer_party.party is None:
                        model.accounting_customer_party.party = Party()
                    model.accounting_customer_party.party.contact = contact
                    if trace:
                        trace.add_field(
                            f"PER*{qualifier}",
                            "accounting_customer_party.party.contact",
                            contact.name,
                        )
                elif hasattr(model, "buyer_customer_party"):
                    if model.buyer_customer_party is None:
                        model.buyer_customer_party = CustomerParty(party=Party())
                    if model.buyer_customer_party.party is None:
                        model.buyer_customer_party.party = Party()
                    model.buyer_customer_party.party.contact = contact
                    if trace:
                        trace.add_field(
                            f"PER*{qualifier}",
                            "buyer_customer_party.party.contact",
                            contact.name,
                        )
            else:
                # Unknown qualifier - still try to map to buyer party contact
                if hasattr(model, "buyer_customer_party"):
                    if model.buyer_customer_party is None:
                        model.buyer_customer_party = CustomerParty(party=Party())
                    if model.buyer_customer_party.party is None:
                        model.buyer_customer_party.party = Party()
                    if model.buyer_customer_party.party.contact is None:
                        model.buyer_customer_party.party.contact = contact
                        if trace:
                            trace.add_field(
                                f"PER*{qualifier}",
                                "buyer_customer_party.party.contact",
                                contact.name,
                            )

    def _map_fob_to_delivery(
        self,
        model: Any,
        content: list["ParsedSegment | LoopInstance"],
        metrics: "MappingMetrics | None",
        trace: "MappingTrace | None",
    ) -> None:
        """Map FOB segment delivery terms to the first delivery.

        This runs after party loops so that delivery[0] exists.
        Maps FOB*02 (location qualifier) and FOB*03 (description) to delivery_terms.
        """
        from edi_schema.semantic.models import DeliveryTerms

        # Only proceed if there's at least one delivery
        if not hasattr(model, "delivery") or not model.delivery:
            return

        delivery = model.delivery[0]

        # Find FOB segment
        fob_seg = find_segment(content, "FOB")
        if not fob_seg:
            return

        # Ensure delivery_terms exists
        if delivery.delivery_terms is None:
            delivery.delivery_terms = DeliveryTerms()

        # FOB*02 = Location Qualifier (ZZ=Mutually Defined, etc.)
        location_qual = _get_element_value(fob_seg, 2)
        if location_qual:
            delivery.delivery_terms.loss_risk_responsibility_code = location_qual
            if metrics:
                metrics.fields_mapped += 1
            if trace:
                trace.add_field("FOB*02", "delivery[0].delivery_terms.loss_risk_responsibility_code", location_qual)

        # FOB*03 = Description (shipping terms description)
        description = _get_element_value(fob_seg, 3)
        if description:
            delivery.delivery_terms.special_terms = description
            if metrics:
                metrics.fields_mapped += 1
            if trace:
                trace.add_field("FOB*03", "delivery[0].delivery_terms.special_terms", description)

        # FOB*05 = Incoterms code (if present, takes precedence for id)
        incoterms = _get_element_value(fob_seg, 5)
        if incoterms:
            delivery.delivery_terms.id = incoterms
            if metrics:
                metrics.fields_mapped += 1
            if trace:
                trace.add_field("FOB*05", "delivery[0].delivery_terms.id", incoterms)

    def _map_td5_to_shipment(
        self,
        model: Any,
        content: list["ParsedSegment | LoopInstance"],
        metrics: "MappingMetrics | None",
        trace: "MappingTrace | None",
    ) -> None:
        """Map TD5 segment to delivery[0].shipment.

        Creates a Shipment object if TD5 data is present, then populates:
        - TD5*02/03: carrier_party identification
        - TD5*04: transport mode code
        - TD5*05: routing/transit direction
        - TD5*12: service level code
        """
        from edi_schema.semantic.models import (
            Identifier,
            Party,
            PartyIdentification,
            Shipment,
            ShipmentStage,
        )

        # Only proceed if there's at least one delivery
        if not hasattr(model, "delivery") or not model.delivery:
            return

        delivery = model.delivery[0]

        # Find TD5 segment
        td5_seg = find_segment(content, "TD5")
        if not td5_seg:
            return

        # Check if there's any TD5 data to map
        id_qual = _get_element_value(td5_seg, 2)
        carrier_id = _get_element_value(td5_seg, 3)
        transport_mode = _get_element_value(td5_seg, 4)
        routing = _get_element_value(td5_seg, 5)
        service_level = _get_element_value(td5_seg, 12)

        if not any([id_qual, carrier_id, transport_mode, routing, service_level]):
            return

        # Create Shipment if needed
        if delivery.shipment is None:
            delivery.shipment = Shipment()

        shipment = delivery.shipment

        # TD5*02/03 = Carrier identification (qualifier/ID)
        if carrier_id:
            scheme_id = id_qual or "SCAC"  # Default to SCAC if no qualifier
            carrier_party = Party(
                party_identifications=[
                    PartyIdentification(id=Identifier(value=carrier_id, scheme_id=scheme_id))
                ]
            )
            shipment.carrier_party = carrier_party
            if metrics:
                metrics.fields_mapped += 2
            if trace:
                trace.add_field("TD5*02", "delivery[0].shipment.carrier_party.party_identifications[0].id.scheme_id", scheme_id)
                trace.add_field("TD5*03", "delivery[0].shipment.carrier_party.party_identifications[0].id.value", carrier_id)

        # TD5*04 = Transport mode (A=Air, M=Motor, R=Rail, S=Ship)
        # TD5*05 = Routing/transit direction
        if transport_mode or routing:
            if not shipment.shipment_stages:
                shipment.shipment_stages = [ShipmentStage()]
            stage = shipment.shipment_stages[0]
            if transport_mode:
                stage.transport_mode_code = transport_mode
                if metrics:
                    metrics.fields_mapped += 1
                if trace:
                    trace.add_field("TD5*04", "delivery[0].shipment.shipment_stages[0].transport_mode_code", transport_mode)
            if routing:
                stage.transit_direction_code = routing
                if metrics:
                    metrics.fields_mapped += 1
                if trace:
                    trace.add_field("TD5*05", "delivery[0].shipment.shipment_stages[0].transit_direction_code", routing)

        # TD5*12 = Service level code (SG=Standard Ground, etc.)
        if service_level:
            shipment.shipping_priority_level_code = service_level
            if metrics:
                metrics.fields_mapped += 1
            if trace:
                trace.add_field("TD5*12", "delivery[0].shipment.shipping_priority_level_code", service_level)

    def _map_msg_notes(
        self,
        model: Any,
        content: list["ParsedSegment | LoopInstance"],
        metrics: "MappingMetrics | None",
        trace: "MappingTrace | None",
    ) -> None:
        """Map MSG segments to the note list.

        Appends each MSG*01 value to the model's note list.
        Searches both header level and inside loops (e.g., N9 loops).
        """
        if not hasattr(model, "note"):
            return

        def find_msg_segments(items: list) -> None:
            """Recursively find MSG segments in content."""
            for item in items:
                if hasattr(item, "tag") and item.tag == "MSG":
                    note_text = _get_element_value(item, 1)
                    if note_text:
                        model.note.append(note_text)
                        if metrics:
                            metrics.fields_mapped += 1
                        if trace:
                            trace.add_field("MSG*01", f"note[{len(model.note) - 1}]", note_text)
                # Search inside loops (but not PO1 line item loops - those have their own notes)
                if hasattr(item, "segments") and hasattr(item, "loop_id"):
                    if item.loop_id not in ("PO1", "IT1", "SLN"):  # Skip line item loops
                        find_msg_segments(item.segments)

        find_msg_segments(content)

    def _map_amt_totals(
        self,
        model: Any,
        content: list["ParsedSegment | LoopInstance"],
        metrics: "MappingMetrics | None",
        trace: "MappingTrace | None",
    ) -> None:
        """Map AMT*TT to anticipated_monetary_total.payable_amount.

        Creates MonetaryTotal and Amount objects as needed.
        Searches both header level and inside CTT loop.
        """
        from decimal import Decimal

        from edi_schema.semantic.models import Amount, MonetaryTotal

        def process_amt(segment: Any) -> bool:
            """Process an AMT segment. Returns True if mapped."""
            qualifier = _get_element_value(segment, 1)
            amount_str = _get_element_value(segment, 2)

            if qualifier == "TT" and amount_str:
                # Create MonetaryTotal with Amount for total transaction amount
                if model.anticipated_monetary_total is None:
                    model.anticipated_monetary_total = MonetaryTotal()

                currency = getattr(model, "document_currency_code", None) or "USD"
                model.anticipated_monetary_total.payable_amount = Amount(
                    value=Decimal(amount_str),
                    currency=currency,
                )
                if metrics:
                    metrics.fields_mapped += 1
                if trace:
                    trace.add_field(
                        "AMT*TT*02",
                        "anticipated_monetary_total.payable_amount",
                        amount_str,
                    )
                return True
            return False

        for item in content:
            if hasattr(item, "tag") and item.tag == "AMT":
                if process_amt(item):
                    return  # Found and mapped
            # Also search inside CTT loop (where AMT often appears)
            if hasattr(item, "loop_id") and item.loop_id == "CTT":
                for seg in item.segments:
                    if seg.tag == "AMT":
                        if process_amt(seg):
                            return  # Found and mapped

    def _map_dtm_despatch(
        self,
        model: Any,
        content: list["ParsedSegment | LoopInstance"],
        metrics: "MappingMetrics | None",
        trace: "MappingTrace | None",
    ) -> None:
        """Map despatch-related DTM qualifiers to delivery[0].despatch.

        Creates Despatch object if needed. Handles:
        - DTM*010 = Ship Date -> requested_despatch_date
        - DTM*037 = Ship Not Before -> earliest_despatch_date
        """
        from datetime import date as date_type

        from edi_schema.semantic.models import Despatch

        if not hasattr(model, "delivery") or not model.delivery:
            return

        delivery = model.delivery[0]

        for item in content:
            if not hasattr(item, "tag") or item.tag != "DTM":
                continue

            qualifier = _get_element_value(item, 1)
            date_str = _get_element_value(item, 2)

            if not date_str:
                continue

            # Determine which despatch field to set
            field_name = None
            if qualifier == "010":
                field_name = "requested_despatch_date"
            elif qualifier == "037":
                field_name = "earliest_despatch_date"

            if not field_name:
                continue

            # Create Despatch if needed
            if delivery.despatch is None:
                delivery.despatch = Despatch()

            # Parse CCYYMMDD format
            try:
                parsed_date = date_type(
                    year=int(date_str[0:4]),
                    month=int(date_str[4:6]),
                    day=int(date_str[6:8]),
                )
                setattr(delivery.despatch, field_name, parsed_date)
                if metrics:
                    metrics.fields_mapped += 1
                if trace:
                    trace.add_field(
                        f"DTM*{qualifier}*02",
                        f"delivery[0].despatch.{field_name}",
                        str(parsed_date),
                    )
            except (ValueError, IndexError):
                pass  # Invalid date format, skip

    def _extract_it1_product_ids(
        self,
        item: Any,
        loop: "LoopInstance",
        metrics: "MappingMetrics | None",
        trace: "MappingTrace | None",
    ) -> None:
        """Extract product ID pairs from IT1 elements 06-25.

        This is similar to _extract_po1_product_ids but for Invoice lines.
        """
        from edi_schema.semantic.models import Identifier, ItemIdentification

        # Find the IT1 segment in the loop
        it1_seg = None
        for seg in loop.segments:
            if seg.tag == "IT1":
                it1_seg = seg
                break

        if it1_seg is None:
            return

        # Ensure item has an Item object
        if not hasattr(item, "item") or item.item is None:
            from edi_schema.semantic.models import Item
            item.item = Item()

        # Map product ID qualifier to (field_type, scheme_id)
        qualifier_map = {
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

        # Process pairs starting at element 6 (qualifier) and 7 (value)
        for i in range(6, 26, 2):
            qualifier = _get_element_value(it1_seg, i)
            value = _get_element_value(it1_seg, i + 1)

            if not qualifier or not value:
                continue

            field_type, scheme = qualifier_map.get(qualifier, ("additional", None))
            item_id = ItemIdentification(id=Identifier(value=value, scheme_id=scheme or qualifier))

            if field_type == "standard":
                if item.item.standard_item_identification is None:
                    item.item.standard_item_identification = item_id
                else:
                    item.item.additional_item_identifications.append(item_id)
            elif field_type == "sellers":
                if item.item.sellers_item_identification is None:
                    item.item.sellers_item_identification = item_id
                else:
                    item.item.additional_item_identifications.append(item_id)
            elif field_type == "buyers":
                if item.item.buyers_item_identification is None:
                    item.item.buyers_item_identification = item_id
                else:
                    item.item.additional_item_identifications.append(item_id)
            elif field_type == "manufacturers":
                if item.item.manufacturers_item_identification is None:
                    item.item.manufacturers_item_identification = item_id
                else:
                    item.item.additional_item_identifications.append(item_id)
            else:
                item.item.additional_item_identifications.append(item_id)

            if metrics:
                metrics.fields_mapped += 1
            if trace:
                trace.add_field(f"IT1*{i:02d}/*{i+1:02d}", f"item.{field_type}_item_identification", value)

    def _extract_line_txi_segments(
        self,
        item: Any,
        loop: "LoopInstance",
        metrics: "MappingMetrics | None",
        trace: "MappingTrace | None",
    ) -> None:
        """Extract line-level TXI (tax) segments for invoice lines."""
        from decimal import Decimal
        from edi_schema.semantic.models import TaxTotal, TaxSubtotal, TaxCategory
        from edi_schema.semantic.models.primitives import Amount

        total_tax = Decimal("0")
        subtotals = []

        for seg in loop.segments:
            if seg.tag != "TXI":
                continue

            # TXI*01 = Tax Type Code
            tax_type = _get_element_value(seg, 1)

            # TXI*02 = Tax Amount
            amount_str = _get_element_value(seg, 2)
            if not amount_str:
                continue

            try:
                amount = Decimal(amount_str)
                total_tax += amount

                # TXI*03 = Tax Percent
                percent_str = _get_element_value(seg, 3)
                percent = None
                if percent_str:
                    try:
                        percent = Decimal(percent_str)
                    except Exception:
                        pass

                subtotal = TaxSubtotal(
                    tax_amount=Amount(value=amount, currency="USD"),
                    percent=percent,
                    tax_category=TaxCategory(id=tax_type) if tax_type else None,
                )
                subtotals.append(subtotal)
            except Exception:
                pass

        if subtotals or total_tax > 0:
            tax_total = TaxTotal(
                tax_amount=Amount(value=total_tax, currency="USD"),
                tax_subtotals=subtotals,
            )
            if hasattr(item, "tax_total"):
                item.tax_total.append(tax_total)
                if metrics:
                    metrics.fields_mapped += 1
                if trace:
                    trace.add_field("TXI", "tax_total[+]", str(tax_total))

    def _map_tds_totals(
        self,
        model: Any,
        content: list["ParsedSegment | LoopInstance"],
        metrics: "MappingMetrics | None",
        trace: "MappingTrace | None",
    ) -> None:
        """Map TDS (Total Monetary Value Summary) to legal_monetary_total.

        TDS amounts are in cents (2 implied decimal places), so we divide by 100.
        Creates MonetaryTotal and Amount objects as needed.
        """
        from decimal import Decimal
        from edi_schema.semantic.models import Amount, MonetaryTotal

        tds_seg = find_segment(content, "TDS")
        if tds_seg is None:
            return

        # TDS*01 = Total Invoice Amount (in cents)
        total_str = _get_element_value(tds_seg, 1)
        if not total_str:
            return

        try:
            # Convert from cents to decimal
            total_value = Decimal(total_str) / Decimal("100")
        except Exception:
            return

        # Create MonetaryTotal if needed
        if not hasattr(model, "legal_monetary_total") or model.legal_monetary_total is None:
            model.legal_monetary_total = MonetaryTotal()

        currency = getattr(model, "document_currency_code", None) or "USD"
        model.legal_monetary_total.payable_amount = Amount(
            value=total_value,
            currency=currency,
        )

        if metrics:
            metrics.fields_mapped += 1
        if trace:
            trace.add_field(
                "TDS*01",
                "legal_monetary_total.payable_amount",
                str(total_value),
            )

        # TDS*02 = Amount Subject to Terms Discount (optional)
        discount_str = _get_element_value(tds_seg, 2)
        if discount_str:
            try:
                discount_value = Decimal(discount_str) / Decimal("100")
                model.legal_monetary_total.allowance_total_amount = Amount(
                    value=discount_value,
                    currency=currency,
                )
                if metrics:
                    metrics.fields_mapped += 1
            except Exception:
                pass

    def _map_cad_to_shipment(
        self,
        model: Any,
        content: list["ParsedSegment | LoopInstance"],
        metrics: "MappingMetrics | None",
        trace: "MappingTrace | None",
    ) -> None:
        """Map CAD (Carrier Detail) to delivery[0].shipment.

        Creates Shipment and Carrier objects as needed.
        """
        from edi_schema.semantic.models import (
            Delivery,
            Identifier,
            Party,
            PartyIdentification,
            Shipment,
            ShipmentStage,
        )

        cad_seg = find_segment(content, "CAD")
        if cad_seg is None:
            return

        # Ensure delivery[0] exists
        if not hasattr(model, "delivery") or not model.delivery:
            model.delivery = [Delivery()]

        delivery = model.delivery[0]

        # Ensure shipment exists
        if delivery.shipment is None:
            delivery.shipment = Shipment()

        shipment = delivery.shipment

        # CAD*01 = Transport Method
        transport_method = _get_element_value(cad_seg, 1)
        if transport_method:
            if not shipment.shipment_stages:
                shipment.shipment_stages = [ShipmentStage()]
            shipment.shipment_stages[0].transport_mode_code = transport_method
            if metrics:
                metrics.fields_mapped += 1
            if trace:
                trace.add_field("CAD*01", "delivery[0].shipment.shipment_stages[0].transport_mode_code", transport_method)

        # CAD*04 = Standard Carrier Alpha Code (SCAC)
        scac = _get_element_value(cad_seg, 4)
        if scac:
            if shipment.carrier_party is None:
                shipment.carrier_party = Party()
            if not shipment.carrier_party.party_identifications:
                shipment.carrier_party.party_identifications = []
            shipment.carrier_party.party_identifications.append(
                PartyIdentification(id=Identifier(value=scac, scheme_id="SCAC"))
            )
            if metrics:
                metrics.fields_mapped += 1
            if trace:
                trace.add_field("CAD*04", "delivery[0].shipment.carrier_party", scac)

        # CAD*05 = Routing
        routing = _get_element_value(cad_seg, 5)
        if routing:
            if not shipment.shipment_stages:
                shipment.shipment_stages = [ShipmentStage()]
            shipment.shipment_stages[0].transit_direction_code = routing
            if metrics:
                metrics.fields_mapped += 1

        # CAD*08 = Reference ID (often Bill of Lading number)
        ref_qual = _get_element_value(cad_seg, 7)
        ref_id = _get_element_value(cad_seg, 8)
        if ref_id and ref_qual == "BM":
            # Bill of Lading - set as despatch document reference
            from edi_schema.semantic.models.reference import DocumentReference
            if not hasattr(model, "despatch_document_reference") or model.despatch_document_reference is None:
                model.despatch_document_reference = DocumentReference(id=ref_id)
            if metrics:
                metrics.fields_mapped += 1
            if trace:
                trace.add_field("CAD*08", "despatch_document_reference.id", ref_id)

        # CAD*09 = Service Level Code
        service_level = _get_element_value(cad_seg, 9)
        if service_level:
            shipment.shipping_priority_level_code = service_level
            if metrics:
                metrics.fields_mapped += 1

    def _map_nte_notes(
        self,
        model: Any,
        content: list["ParsedSegment | LoopInstance"],
        metrics: "MappingMetrics | None",
        trace: "MappingTrace | None",
    ) -> None:
        """Map NTE (Note/Special Instruction) segments to note list.

        NTE segments contain free-form notes at header level.
        """
        nte_segments = find_all_segments(content, "NTE")

        for nte_seg in nte_segments:
            # NTE*01 = Note Reference Code (optional qualifier)
            # NTE*02 = Description (free-form text)
            description = _get_element_value(nte_seg, 2)
            if not description:
                continue

            if hasattr(model, "note"):
                model.note.append(description)
                if metrics:
                    metrics.fields_mapped += 1
                if trace:
                    trace.add_field("NTE*02", "note[+]", description)

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
