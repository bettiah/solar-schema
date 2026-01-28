# Nested Path Auto-Creation Enhancement

## Problem Statement

When mapping X12 fields to semantic model paths like `order_reference.issue_date`, the mapping fails because:

1. **Parent object is None**: The `order_reference` field is `None` and can't be auto-created because it has required fields (e.g., `id`)
2. **List is empty**: Paths like `payment_terms[0].settlement_period_days` fail because `payment_terms` list has no items at index 0
3. **Nested required fields**: Objects like `Quantity` have required fields (`value`, `unit_code`) and can't be instantiated empty

### Current Failures

From the 810 Invoice mapping:

| Source | Target Path | Issue |
|--------|-------------|-------|
| `BIG*03` | `order_reference.issue_date` | `order_reference` is None, can't create - requires `id` |
| `BIG*04` | `order_reference.id` | Same - parent is None |
| `ITD*07` | `payment_terms[0].settlement_period_days` | `payment_terms` list is empty |
| `IT1*02` | `invoiced_quantity.value` | `invoiced_quantity` is None, can't create - requires `value` + `unit_code` |
| `IT1*03` | `invoiced_quantity.unit_code` | Same - parent is None |

### Root Cause

The current `_create_intermediate` function (engine.py:448) catches `TypeError, ValueError` but not `ValidationError` from Pydantic. Even if fixed, models with required fields cannot be instantiated without providing those values.

---

## Solution: Deferred Field Collection

### Approach

Instead of setting fields one at a time, collect related fields that target the same parent object, then create the parent with all available values at once.

### Phase 1: Field Grouping Analysis

Before mapping, analyze field mappings to identify "field groups" - sets of fields that target the same parent object:

```python
# Example field groups for Invoice
{
    "order_reference": [
        FieldMapping(seg("BIG", 3), sem("order_reference.issue_date")),
        FieldMapping(seg("BIG", 4), sem("order_reference.id")),
    ],
    "invoice_lines[*].invoiced_quantity": [
        FieldMapping(seg("IT1", 2), sem("invoiced_quantity.value")),
        FieldMapping(seg("IT1", 3), sem("invoiced_quantity.unit_code")),
    ],
}
```

### Phase 2: Deferred Value Collection

During mapping, instead of immediately setting nested paths:

1. **Detect nested target**: If path has `.` and parent is None, defer
2. **Collect values**: Store `{parent_path: {child_field: value}}`
3. **Continue mapping**: Process other non-deferred fields normally

```python
deferred_values = {
    "order_reference": {
        "issue_date": date(2010, 12, 4),
        "id": "P792940",
    },
}
```

### Phase 3: Deferred Object Creation

After all field mappings complete, create deferred objects:

```python
for parent_path, field_values in deferred_values.items():
    # Check if we have enough data to create the object
    parent_type = get_type_for_path(model, parent_path)
    required_fields = get_required_fields(parent_type)

    if required_fields <= field_values.keys():
        # Create object with collected values
        instance = parent_type(**field_values)
        set_nested_attr(model, parent_path, instance)
    else:
        # Warn about missing required fields
        missing = required_fields - field_values.keys()
        warn(f"Cannot create {parent_path}: missing {missing}")
```

---

## Implementation Plan

### Step 1: Add Type Introspection Utilities

Create helper functions to analyze Pydantic model structure:

```python
# In engine.py or new utils.py

def get_field_type(model_class: type, path: str) -> type | None:
    """Get the type annotation for a nested path."""

def get_required_fields(model_class: type) -> set[str]:
    """Get required field names for a Pydantic model."""

def can_instantiate_empty(model_class: type) -> bool:
    """Check if model can be created with no arguments."""
```

### Step 2: Add Field Group Detection

Pre-analyze mappings to detect related field groups:

```python
def _analyze_field_groups(mappings: list[FieldMapping]) -> dict[str, list[FieldMapping]]:
    """Group field mappings by their parent path.

    Returns dict mapping parent path to list of child field mappings.
    E.g., {"order_reference": [mapping1, mapping2]}
    """
```

### Step 3: Add Deferred Collection to MappingEngine

```python
class MappingEngine:
    def __init__(self, ...):
        ...
        self._deferred_values: dict[str, dict[str, Any]] = {}
        self._field_groups = self._analyze_field_groups(mapping.field_mappings)

    def _should_defer(self, model: Any, path: str) -> bool:
        """Check if this path should be deferred for batch creation."""

    def _collect_deferred(self, path: str, value: Any) -> None:
        """Store value for deferred object creation."""

    def _create_deferred_objects(self, model: Any) -> None:
        """Create all deferred nested objects from collected values."""
```

### Step 4: Modify `_map_segment_fields` Flow

```python
def _map_segment_fields(self, model, content, ...):
    for field_mapping in self.mapping.field_mappings:
        value = extract_value(...)

        if self._should_defer(model, field_mapping.semantic.path):
            self._collect_deferred(field_mapping.semantic.path, value)
        else:
            set_nested_attr(model, field_mapping.semantic.path, value)
```

### Step 5: Add Resolution Phase

Call deferred creation after field mapping:

```python
def to_semantic(self, transaction):
    model = create_model()

    # Existing mapping phases...
    self._map_segment_fields(model, content, ...)

    # NEW: Resolve deferred nested objects
    self._create_deferred_objects(model, accumulator, metrics)

    return result
```

---

## Handling List Indexing (`payment_terms[0]`)

For paths like `payment_terms[0].settlement_period_days`:

### Option A: Auto-extend List (Simple)

When accessing index N, ensure list has at least N+1 items by creating empty instances:

```python
def _ensure_list_index(self, obj: Any, list_attr: str, index: int) -> bool:
    lst = getattr(obj, list_attr, None)
    if lst is None:
        return False

    item_type = get_list_item_type(type(obj), list_attr)
    while len(lst) <= index:
        if can_instantiate_empty(item_type):
            lst.append(item_type())
        else:
            # Use deferred collection for this list item too
            return False
    return True
```

### Option B: Deferred List Items (Complex)

Treat `payment_terms[0]` as a deferred object path:

```python
deferred_values = {
    "payment_terms[0]": {
        "settlement_period_days": 60,
        "note": "Net 60 days",
    },
}
```

Then create and append when resolved.

**Recommendation**: Start with Option A for models with no required fields, fall back to Option B (deferred) for models with required fields.

---

## Edge Cases

### 1. Partial Data

If we only get `order_reference.issue_date` but not `order_reference.id`:
- **Current**: Warning, no object created
- **After**: Same - warn about missing required `id` field

### 2. Deep Nesting

Path like `delivery[0].shipment.carrier_party.party_names[0].name`:
- Each level needs to be checked/created
- Collect at the deepest deferrable parent

### 3. Loop Context

In IT1 loops, `invoiced_quantity.value` refers to the current line item's quantity:
- Deferred collection must be scoped to the loop iteration
- Clear deferred values after each loop item is created

### 4. Conflicting Values

Multiple segments setting same path:
- Later value wins (current behavior)
- Log a trace/warning if values differ

---

## Testing Strategy

1. **Unit tests for type introspection**
2. **Unit tests for field group detection**
3. **Unit tests for deferred collection/creation**
4. **Integration test with 810 fixture** - verify `order_reference` is created
5. **Integration test with list indexing** - verify `payment_terms[0]` works

---

## Migration / Backwards Compatibility

- Existing behavior preserved for simple paths
- New deferred behavior only activates for nested paths with None parents
- Warnings remain for fields that still can't be set (missing required data)

---

## Summary

| Component | Change |
|-----------|--------|
| `_create_intermediate` | Catch `ValidationError`, recognize when deferral needed |
| New `_analyze_field_groups` | Pre-compute related field groups |
| New `_deferred_values` | Collect values for batch object creation |
| New `_create_deferred_objects` | Create nested objects from collected values |
| `set_nested_attr` | Add list auto-extension support |
| `to_semantic` | Add deferred resolution phase after field mapping |

**Estimated effort**: Medium - core changes to mapping flow, but well-contained
