# Mapping Engine Documentation

The Mapping Engine converts X12 EDI transactions to semantic business models using declarative mapping definitions.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                   Parsed X12 Transaction                        │
│              (TransactionSetInstance from parser)               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  BuilderMappingEngine                            │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              TransactionMapping Definition               │   │
│  │  (e.g., INVOICE_810_MAPPING, ORDER_850_MAPPING)         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│  ┌───────────────────────────┼───────────────────────┐         │
│  │              Dispatch Tables (built once)          │         │
│  │  segment_tag → [handlers]   loop_id → [handlers]  │         │
│  └───────────────────────────┼───────────────────────┘         │
│                              │                                  │
│         ┌────────────────────┼────────────────────┐            │
│         ▼                    ▼                    ▼            │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │   Field     │    │  Qualified  │    │ Loop/Party  │        │
│  │  Handlers   │    │  Handlers   │    │  Handlers   │        │
│  └─────────────┘    └─────────────┘    └─────────────┘        │
│         │                    │                    │            │
│         └────────────────────┼────────────────────┘            │
│                              ▼                                  │
│              Box Dict Accumulator (auto-vivification)           │
│                              │                                  │
│                              ▼                                  │
│              Post-processing (delivery merge, currency, etc.)   │
│                              │                                  │
│                              ▼                                  │
│         strip_empty_boxes → model_validate(dict)               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Semantic Model                              │
│              (Invoice, Order, DespatchAdvice, etc.)             │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### BuilderMappingEngine

Single-pass mapping engine using a Box dict accumulator. Builds a plain dict via Box auto-vivification, then calls `model_validate(dict)` once at the end to produce the Pydantic model.

```python
from edi_schema.semantic.mapping import BuilderMappingEngine
from edi_schema.semantic.mapping.x12 import INVOICE_810_MAPPING

engine = BuilderMappingEngine(
    mapping=INVOICE_810_MAPPING,
    error_mode=ErrorHandlingMode.LENIENT,  # STRICT | LENIENT
    collect_metrics=True,                   # Performance/coverage metrics
    debug_mode=False,                       # Enable tracing
    warn_on_unmapped=True,                  # Warn about unmapped segments
)

result = engine.to_semantic(parsed_transaction, context)
if result.success:
    invoice = result.model  # Semantic Invoice object
```

### How it works

1. **Pre-pass**: Map ISA/GS envelope fields and external context metadata
2. **Normalize**: Convert implicit loops (bare segments) into `LoopInstance` objects — O(n)
3. **Single forward pass**: Iterate content once, dispatching each segment/loop to registered handlers via dispatch tables
4. **Post-processing**: Delivery merging, party wrapper fixups, currency defaults, TXI aggregation
5. **Build model**: `strip_empty_boxes()` → `model_validate(dict)`
6. **Validate**: Run validation rules, report unmapped segments

### Why Box

- **Auto-vivification eliminates deferred fields**: `builder.order_reference.id = "P792940"` auto-creates intermediate dicts — no need for parent objects to exist first
- **No phase ordering needed**: `builder.delivery[0].delivery_terms.code = "FOB"` works regardless of whether `delivery[0].delivery_party` has been set yet
- **Single pass**: iterate content once, dispatch each segment/loop to registered handlers

### TransactionMapping

Defines how an X12 transaction maps to a semantic model:

```python
TransactionMapping(
    transaction_id="810",           # X12 transaction set ID
    semantic_type=Invoice,          # Target Pydantic model
    field_mappings=[...],           # Direct field mappings
    qualified_mappings=[...],       # Qualifier-based mappings (DTM, REF)
    loop_mappings=[...],            # Repeating structure mappings (PO1, IT1)
    party_mappings=[...],           # N1 loop party mappings
    envelope_mappings=[...],        # ISA/GS envelope mappings
    context_mappings=[...],         # External metadata mappings
    validation_rules=[...],         # Post-mapping validation
    validate_on_map=True,           # Run validation during mapping
)
```

---

## Mapping Types

### Field Mappings

Direct segment element to semantic field mapping:

```python
from edi_schema.semantic.mapping import FieldMapping, seg, sem

FieldMapping(
    seg("BIG", 1),              # Source: BIG segment, element 1
    sem("issue_date"),          # Target: issue_date field
    to_semantic_transform=PARSE_DATE,  # Optional transform
)
```

### Qualified Mappings

Map segments where a qualifier determines the target:

```python
QualifiedMapping(
    qualifier_path=seg("DTM", 1),  # Qualifier element
    mappings={
        "002": [  # DTM*002 = Delivery Requested
            FieldMapping(
                seg("DTM", 2),
                sem("delivery[0].requested_delivery_period.start_date"),
                to_semantic_transform=PARSE_DATE,
            ),
        ],
        "010": [  # DTM*010 = Ship Date
            FieldMapping(
                seg("DTM", 2),
                sem("despatch.requested_despatch_date"),
                to_semantic_transform=PARSE_DATE,
            ),
        ],
    },
)
```

### Loop Mappings

Map repeating structures (PO1, IT1 line items):

```python
LoopMapping(
    loop_id="IT1",
    semantic_path=sem("invoice_lines"),
    item_type=InvoiceLine,
    field_mappings=[
        FieldMapping(seg("IT1", 1), sem("id")),
        FieldMapping(seg("IT1", 2), sem("invoiced_quantity.value")),
        FieldMapping(seg("IT1", 3), sem("invoiced_quantity.unit_code")),
        FieldMapping(seg("IT1", 4), sem("price.price_amount.value")),
    ],
    qualified_mappings=[...],
)
```

### Party Mappings

Map N1 party loops with qualifier-based routing:

```python
PartyLoopMapping(
    loop_id="N1",
    qualifiers={
        "ST": ("delivery[+].delivery_party", Party),  # Ship To
        "BT": ("accounting_customer_party.party", Party),  # Bill To
        "BY": ("buyer_customer_party.party", Party),  # Buyer
        "SE": ("accounting_supplier_party.party", Party),  # Seller
    },
)
```

---

## Handler Architecture

### Dispatch Tables

Built once in `BuilderMappingEngine.__init__()`, mapping segment tags and loop IDs to lists of handlers:

```python
# Segment dispatch: tag → [FieldMappingHandler, QualifiedMappingHandler, special handlers]
# Loop dispatch:    loop_id → [LoopItemHandler, PartyLoopHandler]
```

### Core Handlers

| Handler | Source | Description |
|---------|--------|-------------|
| `FieldMappingHandler` | `handlers/field.py` | Wraps a `FieldMapping`. Checks qualifier, extracts value, applies transform, writes via `set_box_path` |
| `QualifiedMappingHandler` | `handlers/qualified.py` | Wraps a `QualifiedMapping`. Reads qualifier element, looks up sub-mappings |
| `LoopItemHandler` | `handlers/loop.py` | Wraps a `LoopMapping`. Creates list entries, maps fields/qualified within loop context. Handles product IDs (PO1/IT1 elements 6-25) and SCH delivery schedules |
| `PartyLoopHandler` | `handlers/party.py` | Wraps a `PartyLoopMapping`. Reads N1*01 qualifier, resolves target path, maps N1/N2/N3/N4/PER fields |

### Special Handlers

Pluggable handlers registered per transaction type in `handlers/registry.py`. Each encapsulates segment-specific logic beyond declarative mappings:

| Handler | File | Segment | Description |
|---------|------|---------|-------------|
| `SACHandler` | `special/sac.py` | SAC | Allowance/charge (header + line level) |
| `TXIHandler` | `special/txi.py` | TXI | Tax segments (header + line level) |
| `FOBHandler` | `special/fob.py` | FOB | Delivery terms |
| `TD5Handler` | `special/td5.py` | TD5 | Carrier/routing info |
| `MSGHandler` | `special/msg.py` | MSG | Message notes |
| `AMTHandler` | `special/amt.py` | AMT | Monetary totals |
| `TDSHandler` | `special/tds.py` | TDS | Invoice totals (cents → dollars) |
| `CADHandler` | `special/cad.py` | CAD | Carrier detail (810) |
| `NTEHandler` | `special/nte.py` | NTE | Header notes (810) |
| `HeaderPERHandler` | `special/per.py` | PER | Header-level contacts |
| `DTMDespatchHandler` | `special/dtm_despatch.py` | DTM | Despatch dates |

### Handler Registry

```python
# handlers/registry.py
HANDLER_REGISTRY: dict[str, dict[str, list]] = {
    "850": {"SAC": [_sac], "TXI": [_txi], "FOB": [_fob], "TD5": [_td5], ...},
    "810": {"SAC": [_sac], "TXI": [_txi], "FOB": [_fob], "TDS": [_tds], ...},
    "856": {"SAC": [_sac], "FOB": [_fob], "TD5": [_td5], ...},
}

# Line-level handlers invoked per loop item (with item_prefix)
LINE_HANDLER_REGISTRY: dict[str, dict[str, list]] = {
    "850": {"PO1": {"SAC": [_sac]}},
    "810": {"IT1": {"SAC": [_sac], "TXI": [_txi]}},
}
```

---

## Box Path Utilities

`set_box_path(builder, path, value, ctx)` in `handlers/base.py` handles:

| Syntax | Example | Behavior |
|--------|---------|----------|
| Dot paths | `order_reference.id` | Auto-vivifies intermediate dicts |
| Indexed lists | `delivery[0].delivery_terms.code` | Auto-creates list, pads with Box items |
| Append | `additional_document_references[+].id` | Appends new item to list |

`strip_empty_boxes(d)` recursively removes empty dicts/Boxes left by auto-vivification before `model_validate`.

`ensure_list(builder, path)` converts auto-vivified Box dicts to Python lists at a given path.

---

## Post-Processing

After the single forward pass, several post-processing steps normalize the accumulated dict:

| Step | Method | Description |
|------|--------|-------------|
| Unseen defaults | `_apply_unseen_defaults` | Apply `default` values for segments not seen in content |
| TXI aggregation | `_resolve_txi_subtotals` | Convert accumulated TXI subtotals to TaxTotal |
| Delivery merge | `_merge_delivery_entries` | Merge FOB/TD5/DTM `delivery[0]` with party `delivery[1]` |
| Location copy | `_copy_delivery_locations` | Copy delivery_party.postal_address to delivery_location |
| Party wrappers | `_ensure_party_wrappers` | Ensure CustomerParty/SupplierParty have required `party` field |
| Price currency | `_ensure_price_currency` | Add default currency to price amounts |
| Amount currency | `_ensure_amount_currencies` | Add currency to monetary total amounts |
| Empty cleanup | `strip_empty_boxes` | Remove empty dicts from auto-vivification |
| Required restore | `_restore_required_empty_objects` | Restore required empty `party: {}` removed by cleanup |

---

## Transforms

Transforms convert values between X12 and semantic formats:

```python
from edi_schema.semantic.mapping.transforms import (
    PARSE_DATE,       # "20240115" -> date(2024, 1, 15)
    PARSE_DECIMAL,    # "123.45" -> Decimal("123.45")
    PARSE_AMOUNT_CENTS,  # "12345" -> Decimal("123.45") (cents to dollars)
    TO_INT,           # "42" -> 42
)

FieldMapping(
    seg("TDS", 1),
    sem("legal_monetary_total.payable_amount.value"),
    to_semantic_transform=PARSE_AMOUNT_CENTS,  # TDS amounts are in cents
)
```

---

## Error Handling

### Error Modes

```python
class ErrorHandlingMode(Enum):
    STRICT = "strict"    # Fail on first error
    LENIENT = "lenient"  # Collect all errors, continue processing
```

### Error Codes

| Code | Description |
|------|-------------|
| `REQUIRED_FIELD_MISSING` | Required field not found in source |
| `TRANSFORM_FAILED` | Value transformation failed |
| `TYPE_MISMATCH` | Value doesn't match expected type |
| `CANNOT_SET_FIELD` | Failed to set value on target path |
| `UNMAPPED_SEGMENT` | Segment has no mapping defined |
| `UNMAPPED_QUALIFIER` | Qualifier value has no mapping |
| `UNMAPPED_ELEMENT` | Element within mapped segment is unmapped |

### MappingResult

```python
result = engine.to_semantic(transaction)

result.success      # bool - True if no errors/fatals
result.model        # The mapped semantic model (or None)
result.errors       # List of all errors
result.warnings     # List of warnings only
result.metrics      # MappingMetrics (if collect_metrics=True)
```

---

## Metrics and Diagnostics

### MappingMetrics

```python
metrics = result.metrics

# Counts
metrics.fields_mapped           # Successfully mapped fields
metrics.fields_skipped          # Fields skipped (no value)
metrics.fields_defaulted        # Fields with default values used
metrics.transforms_applied      # Transforms executed
metrics.loops_processed         # Loops mapped
metrics.loop_iterations         # Total loop items
metrics.validation_rules_run    # Validation rules executed

# Timing
metrics.field_mapping_time      # Time spent on field mapping
metrics.loop_mapping_time       # Time spent on loop mapping
metrics.validation_time         # Time spent on validation
metrics.total_time              # Total mapping time

# Coverage
metrics.total_segments_in_document  # Segments in source
metrics.get_unmapped_summary()      # Unmapped segments/elements
```

### Debug Tracing

Enable `debug_mode=True` for detailed execution trace:

```python
engine = BuilderMappingEngine(mapping, debug_mode=True)
result = engine.to_semantic(transaction)

for step in result.trace.steps:
    print(f"{step.source_path} -> {step.target_path}: {step.value}")
```

---

## Validation Rules

Post-mapping validation ensures business rules are met:

```python
from edi_schema.semantic.mapping.validation import (
    RequiredFieldRule,
    FieldValidationRule,
    is_valid_date,
    is_positive,
)

INVOICE_VALIDATION_RULES = [
    RequiredFieldRule(path="id", message="Invoice ID is required"),
    RequiredFieldRule(path="issue_date", message="Issue date is required"),
    FieldValidationRule(
        path="invoice_lines[].invoiced_quantity.value",
        validator=is_positive,
        message="Line quantity must be positive",
    ),
]
```

---

## Usage Example

```python
from edi_schema.x12.parser import parse_file
from edi_schema.x12.schemas import GeneratedX12SchemaLoader
from edi_schema.semantic.mapping import BuilderMappingEngine
from edi_schema.semantic.mapping.x12 import INVOICE_810_MAPPING

# Parse X12 document
loader = GeneratedX12SchemaLoader(version="004010")
parse_result = parse_file("invoice.x12", schema_loader=loader)
transaction = parse_result.interchange.groups[0].transactions[0]

# Map to semantic model
engine = BuilderMappingEngine(INVOICE_810_MAPPING, collect_metrics=True)
result = engine.to_semantic(transaction)

if result.success:
    invoice = result.model
    print(f"Invoice: {invoice.id}")
    print(f"Date: {invoice.issue_date}")
    print(f"Total: {invoice.legal_monetary_total.payable_amount.value}")
    print(f"Lines: {len(invoice.invoice_lines)}")

    if invoice.order_reference:
        print(f"PO: {invoice.order_reference.id}")
else:
    for error in result.errors:
        print(f"Error: {error.message}")
```

---

## Creating New Mappings

To add support for a new X12 transaction:

1. **Create mapping definition** in `src/edi_schema/semantic/mapping/x12/`:

```python
# my_transaction_999.py
from edi_schema.semantic.mapping import (
    TransactionMapping, FieldMapping, LoopMapping,
    QualifiedMapping, PartyLoopMapping, seg, sem,
)
from edi_schema.semantic.models import MyModel

MY_999_MAPPING = TransactionMapping(
    transaction_id="999",
    semantic_type=MyModel,
    field_mappings=[...],
    qualified_mappings=[...],
    loop_mappings=[...],
    party_mappings=[...],
)
```

2. **Register special handlers** (if needed) in `handlers/registry.py`

3. **Add validation rules** in `validations/my_rules.py`

4. **Export from `__init__.py`**

5. **Add tests** in `tests/semantic/test_x12_my_mapper.py`

---

## File Structure

```
src/edi_schema/semantic/mapping/
├── __init__.py              # Public API exports
├── builder_engine.py        # BuilderMappingEngine (single-pass engine)
├── segment_utils.py         # Shared utilities (get_element_value, find_all_loops)
├── types.py                 # Mapping type definitions (FieldMapping, etc.)
├── transforms.py            # Value transformation functions
├── validation.py            # Validation rule framework
├── errors.py                # Error types and accumulator
├── diagnostics.py           # Metrics and tracing
├── context.py               # Message context for envelope data
├── result.py                # MappingResult container
├── handlers/
│   ├── __init__.py          # Handler exports
│   ├── base.py              # Handler protocols, HandlerContext, set_box_path()
│   ├── field.py             # FieldMappingHandler
│   ├── qualified.py         # QualifiedMappingHandler
│   ├── loop.py              # LoopItemHandler
│   ├── party.py             # PartyLoopHandler
│   ├── registry.py          # Handler registry per transaction type
│   └── special/
│       ├── __init__.py
│       ├── sac.py           # SAC allowance/charge
│       ├── txi.py           # TXI tax
│       ├── fob.py           # FOB delivery terms
│       ├── td5.py           # TD5 carrier/shipping
│       ├── msg.py           # MSG notes
│       ├── amt.py           # AMT totals
│       ├── tds.py           # TDS invoice totals (cents)
│       ├── cad.py           # CAD carrier detail
│       ├── nte.py           # NTE notes
│       ├── per.py           # PER header contacts
│       └── dtm_despatch.py  # DTM despatch dates
└── x12/
    ├── __init__.py
    ├── order_850.py         # ORDER_850_MAPPING
    ├── invoice_810.py       # INVOICE_810_MAPPING
    └── despatch_856.py      # DESPATCH_856_MAPPING
```
