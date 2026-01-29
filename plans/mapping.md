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
│                      MappingEngine                              │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              TransactionMapping Definition               │   │
│  │  (e.g., INVOICE_810_MAPPING, ORDER_850_MAPPING)         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│         ┌────────────────────┼────────────────────┐            │
│         ▼                    ▼                    ▼            │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │   Field     │    │  Qualified  │    │    Loop     │        │
│  │  Mappings   │    │  Mappings   │    │  Mappings   │        │
│  └─────────────┘    └─────────────┘    └─────────────┘        │
│                              │                                  │
│                              ▼                                  │
│            Deferred Field Resolution                            │
│           (for nested object creation)                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Semantic Model                              │
│              (Invoice, Order, DespatchAdvice, etc.)             │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### MappingEngine

The main class that executes declarative mappings.

```python
from edi_schema.semantic.mapping import MappingEngine
from edi_schema.semantic.mapping.x12 import INVOICE_810_MAPPING

engine = MappingEngine(
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

## Mapping Phases

The engine processes mappings in a specific order:

| Phase | Description | Method |
|-------|-------------|--------|
| **1** | Extract required fields for model creation | `_extract_required_fields` |
| **2** | Map ISA/GS envelope fields | `_map_envelope_fields` |
| **3** | Map external context metadata | `_map_context_fields` |
| **4** | Map optional header fields | `_map_optional_field_mappings` |
| **5** | Map qualified segments (DTM, REF) | `_map_qualified_segments` |
| **5.1** | Resolve deferred nested fields | `_resolve_deferred_fields` |
| **5.5** | Map SAC allowance/charge segments | `_map_sac_segments` |
| **5.6** | Map TXI tax segments | `_map_txi_segments` |
| **6** | Map N1 party loops | `_map_party_loops` |
| **6.5** | Map header-level PER segments | `_map_header_per_segments` |
| **6.6-6.13** | Special segment handlers (FOB, TD5, MSG, AMT, TDS, CAD, NTE) | Various |
| **7** | Map item loops (PO1, IT1) | `_map_loop` |
| **8** | Run validation rules | Validation rules |
| **9** | Report unmapped segments | `_report_unmapped_segments` |

---

## Deferred Field Collection

### Problem

When mapping nested paths like `order_reference.issue_date`, the parent object (`order_reference`) may be `None` and can't be auto-created because it has required fields.

**Examples that fail without deferred collection:**

| Source | Target Path | Issue |
|--------|-------------|-------|
| `BIG*03` | `order_reference.issue_date` | `order_reference` is None, requires `id` |
| `BIG*04` | `order_reference.id` | Same - parent is None |
| `ITD*07` | `payment_terms[0].settlement_period_days` | List is empty |
| `IT1*02` | `invoiced_quantity.value` | Requires `value` + `unit_code` together |

### Solution

Instead of setting nested fields immediately, collect related fields targeting the same parent, then create the parent with all values at once.

```python
# During mapping, collect deferred values:
deferred_values = {
    "order_reference": {
        "issue_date": date(2010, 12, 4),
        "id": "P792940",
    },
    "payment_terms[0]": {
        "settlement_period_days": 60,
    },
}

# After all field mappings, resolve deferred objects:
for parent_path, field_values in deferred_values.items():
    parent_type = get_field_type_for_path(model, parent_path)
    required_fields = get_required_fields(parent_type)

    if required_fields <= field_values.keys():
        instance = parent_type(**field_values)
        set_nested_attr(model, parent_path, instance)
```

### Implementation

Key functions in `engine.py`:

| Function | Description |
|----------|-------------|
| `get_field_type_for_path()` | Get type annotation for any nested path |
| `get_required_fields()` | Get required fields of a Pydantic model |
| `get_parent_path()` | Extract parent from nested path |
| `analyze_field_groups()` | Pre-analyze mappings to detect field groups |
| `_resolve_deferred_fields()` | Create objects from collected values |
| `_resolve_deferred_object()` | Create nested objects |
| `_resolve_deferred_list_item()` | Create and append list items |

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
engine = MappingEngine(mapping, debug_mode=True)
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

## Special Handlers

Some segments require custom handling beyond declarative mappings:

| Handler | Segment | Description |
|---------|---------|-------------|
| `_map_tds_totals` | TDS | Converts cents to dollars for 810 |
| `_map_cad_to_shipment` | CAD | Carrier details for 810 |
| `_map_nte_notes` | NTE | Header notes for 810 |
| `_map_fob_to_delivery` | FOB | Delivery terms |
| `_map_td5_to_shipment` | TD5 | Carrier/routing info |
| `_map_msg_notes` | MSG | Message notes |
| `_map_amt_totals` | AMT | Monetary totals |
| `_map_dtm_despatch` | DTM | Despatch dates |
| `_extract_po1_product_ids` | PO1 | Product ID pairs in elements 06-25 |
| `_extract_it1_product_ids` | IT1 | Product ID pairs in elements 06-25 |

---

## Usage Example

```python
from edi_schema.x12.parser import parse_file
from edi_schema.x12.schemas import GeneratedX12SchemaLoader
from edi_schema.semantic.mapping import MappingEngine
from edi_schema.semantic.mapping.x12 import INVOICE_810_MAPPING

# Parse X12 document
loader = GeneratedX12SchemaLoader(version="004010")
parse_result = parse_file("invoice.x12", schema_loader=loader)
transaction = parse_result.interchange.groups[0].transactions[0]

# Map to semantic model
engine = MappingEngine(INVOICE_810_MAPPING, collect_metrics=True)
result = engine.to_semantic(transaction)

if result.success:
    invoice = result.model
    print(f"Invoice: {invoice.id}")
    print(f"Date: {invoice.issue_date}")
    print(f"Total: {invoice.legal_monetary_total.payable_amount.value}")
    print(f"Lines: {len(invoice.invoice_lines)}")

    # Order reference (created via deferred field collection)
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

2. **Add validation rules** in `validations/my_rules.py`

3. **Export from `__init__.py`**

4. **Add tests** in `tests/semantic/test_x12_my_mapper.py`

5. **Update mapping index** in `plans/mapping/mapping-index.md`

---

## Related Files

| File | Description |
|------|-------------|
| `engine.py` | Core mapping engine implementation |
| `types.py` | Mapping type definitions (FieldMapping, etc.) |
| `transforms.py` | Value transformation functions |
| `validation.py` | Validation rule framework |
| `errors.py` | Error types and accumulator |
| `diagnostics.py` | Metrics and tracing |
| `context.py` | Message context for envelope data |
| `result.py` | MappingResult container |
| `x12/*.py` | Transaction-specific mappings (810, 850, etc.) |
