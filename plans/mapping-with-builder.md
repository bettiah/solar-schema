# Plan: Single-Pass Builder Mapping Engine

## Problem

The current `MappingEngine.to_semantic()` runs 13+ phases, each scanning `TransactionSetInstance.content` separately via `find_segment`/`find_all_segments`/`find_all_loops`. This creates:

1. **O(phases * content_size)** scanning instead of O(content_size)
2. **Deferred field resolution** (~200 lines) to work around Pydantic models requiring valid nested objects before values can be set
3. **Fragile phase ordering** - FOB/TD5/DTM handlers depend on party loops having already created `delivery[0]`
4. **Non-pluggable special handlers** - 12 hardcoded methods with `if transaction_id in ("850", "810")` guards scattered through `to_semantic()`

## Proposed Architecture

**Single forward pass** through content using a **Box dict accumulator** instead of direct Pydantic model mutation. Build the Pydantic model once at the end via `model_validate(dict)`.

### Why Box solves the core problems

- **Auto-vivification eliminates deferred fields**: `builder.order_reference.id = "P792940"` auto-creates the intermediate dict — no need for the parent object to exist
- **No phase ordering needed**: `builder.delivery[0].delivery_terms.code = "FOB"` works regardless of whether `delivery[0].delivery_party` has been set yet
- **Single pass**: iterate content once, dispatch each segment/loop to registered handlers

### Key design decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| New class vs replace | New `BuilderMappingEngine` alongside existing | Safe migration, compare outputs |
| Mapping definitions | Unchanged `TransactionMapping` | Full backwards compatibility |
| Special handlers | Pluggable registry per transaction ID | Eliminates scattered conditionals |
| Implicit loops | Pre-normalize content once before pass | Clean separation, cheap O(n) |

## Implementation

### New files

```
src/edi_schema/semantic/mapping/
├── builder_engine.py          # New engine class
├── handlers/
│   ├── __init__.py
│   ├── base.py                # Handler protocols, HandlerContext, set_box_path()
│   ├── field.py               # FieldMappingHandler
│   ├── qualified.py           # QualifiedMappingHandler
│   ├── loop.py                # LoopItemHandler
│   ├── party.py               # PartyLoopHandler
│   ├── registry.py            # Handler registry per transaction type
│   └── special/
│       ├── __init__.py        # Registers all special handlers
│       ├── sac.py             # SAC allowance/charge
│       ├── txi.py             # TXI tax
│       ├── fob.py             # FOB delivery terms
│       ├── td5.py             # TD5 carrier/shipping
│       ├── msg.py             # MSG notes
│       ├── amt.py             # AMT totals
│       ├── tds.py             # TDS invoice totals (cents)
│       ├── cad.py             # CAD carrier detail
│       ├── nte.py             # NTE notes
│       ├── per.py             # PER header contacts
│       ├── dtm_despatch.py    # DTM despatch dates
│       └── product_ids.py     # IT1/PO1 elements 6-25
```

### Modified files

- `pyproject.toml` — add `python-box>=7.0` dependency
- `src/edi_schema/semantic/mapping/__init__.py` — export `BuilderMappingEngine`

### Step 1: Foundation

Add `python-box` dependency. Create `handlers/base.py` with:

```python
class SegmentHandler(Protocol):
    def handle(self, segment: ParsedSegment, builder: Box, ctx: HandlerContext) -> None: ...

class LoopHandler(Protocol):
    def handle(self, loop: LoopInstance, builder: Box, ctx: HandlerContext) -> None: ...

@dataclass
class HandlerContext:
    metrics: MappingMetrics | None
    trace: MappingTrace | None
    accumulator: ErrorAccumulator
    _list_indices: dict[str, int]  # tracks append counters per list path

    def next_index(self, list_path: str) -> int: ...
```

Implement `set_box_path(builder, path, value)` — handles dot paths, `[N]` indexing, and `[+]` append (via HandlerContext counters). Lists are created as Python lists (not Box auto-vivified dicts).

Implement `strip_empty_boxes(d)` — recursively removes empty dicts left by Box auto-vivification before passing to `model_validate`.

### Step 2: Core handlers

- **FieldMappingHandler**: wraps a `FieldMapping`. Checks qualifier match, extracts element value, applies transform, calls `set_box_path`.
- **QualifiedMappingHandler**: wraps a `QualifiedMapping`. Reads qualifier element, looks up sub-mappings, applies each.
- **LoopItemHandler**: wraps a `LoopMapping`. Calls `ctx.next_index()` to get list position, iterates `loop.segments` applying field/qualified mappings prefixed with `{list_path}[{idx}]`. Processes `loop.children` for nested loops. Invokes line-level special handlers (SAC, TXI within loops).
- **PartyLoopHandler**: wraps a `PartyLoopMapping`. Reads N1*01 qualifier, resolves target path (handling `[+]` append for delivery), maps N1/N2/N3/N4/PER fields.

### Step 3: Special handlers

Extract each `_map_*` method from current engine into a standalone handler class. Each implements `SegmentHandler` and encapsulates its own logic. Example for SAC:

```python
class SACHandler:
    def handle(self, segment, builder, ctx, *, item_prefix=""):
        indicator = get_element_value(segment, 1)
        # ... build allowance_charge dict at item_prefix.allowance_charges[N]
```

Line-level vs header-level: Some handlers (SAC, TXI) run both at header and within loops. The `LoopItemHandler` passes `item_prefix` to distinguish context.

### Step 4: Dispatch table & registry

```python
# Built once in BuilderMappingEngine.__init__()
def _build_dispatch_table(self) -> dict[str, list[Handler]]:
    table = {}
    # From TransactionMapping.field_mappings → FieldMappingHandler per segment tag
    # From TransactionMapping.qualified_mappings → QualifiedMappingHandler per segment tag
    # From TransactionMapping.loop_mappings → LoopItemHandler per loop_id
    # From TransactionMapping.party_mappings → PartyLoopHandler per loop_id
    # From HANDLER_REGISTRY[transaction_id] → special handlers per segment tag
    return table
```

Registry pattern (no changes to TransactionMapping):
```python
HANDLER_REGISTRY: dict[str, dict[str, list[SegmentHandler]]] = {
    "810": {"SAC": [SACHandler()], "TXI": [TXIHandler()], "FOB": [FOBHandler()], ...},
    "850": {"SAC": [SACHandler()], "FOB": [FOBHandler()], ...},
}
```

### Step 5: BuilderMappingEngine

```python
class BuilderMappingEngine:
    def __init__(self, mapping: TransactionMapping, ...):
        self.dispatch = self._build_dispatch_table()

    def to_semantic(self, transaction, context=None) -> MappingResult[T]:
        builder = Box(default_box=True)
        ctx = HandlerContext(...)

        # Pre-pass: envelope + context (not in content)
        self._map_envelope(builder, context)
        self._map_context(builder, context)

        # Normalize implicit loops
        content = self._normalize_content(transaction.content)

        # Single forward pass
        for item in content:
            if isinstance(item, LoopInstance):
                for handler in self.dispatch.get(item.loop_id, []):
                    handler.handle(item, builder, ctx)
            else:  # ParsedSegment
                for handler in self.dispatch.get(item.tag, []):
                    handler.handle(item, builder, ctx)

        # Build Pydantic model
        model_dict = strip_empty_boxes(builder.to_dict())
        model = self.mapping.semantic_type.model_validate(model_dict)

        # Post-pass: validation + unmapped reporting
        ...
        return MappingResult(...)
```

### Step 6: Testing & migration

1. **Comparison tests**: run both `MappingEngine` and `BuilderMappingEngine` on existing test fixtures (810, 850, 856), assert identical semantic model output
2. **Unit tests**: each handler type in isolation
3. **Integration tests**: full round-trip for each transaction type
4. Once verified, export `BuilderMappingEngine` as the default

## Edge cases to handle

- **Box auto-vivifies dicts, not lists** — `set_box_path` must explicitly create `[]` for list paths and pad with `Box()` items for indexed access
- **Empty auto-vivified paths** — `strip_empty_boxes()` removes `{}` artifacts before `model_validate`
- **`delivery[+]` vs `delivery[0]`** — party handler uses `next_index("delivery")` returning 0 first time; FOB/TD5 use explicit `[0]`. Both write to same Box entry
- **Segments inside loops vs header** — main pass only dispatches top-level items; loop handlers dispatch their own child segments independently
- **Product ID pairs (IT1/PO1 elements 6-25)** — `ProductIDHandler` invoked by `LoopItemHandler` for each line loop

## Verification

1. `uv add python-box` — install dependency
2. `pytest tests/semantic/` — existing tests pass (old engine unchanged)
3. Run comparison: `BuilderMappingEngine` output == `MappingEngine` output for all fixtures
4. `pytest tests/semantic/test_builder_engine.py` — new handler unit + integration tests
