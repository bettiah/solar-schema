# X12 Codegen: Split Transaction Sets into Individual Files

## Current State
- X12 codegen generates a single `transaction_sets.py` file (~128K lines, ~300 transaction sets)
- All transaction sets in one file makes it slow to load and hard to navigate
- Each transaction set has `id` (e.g., "850") and `name` (e.g., "Purchase Order")

## Goal
- Split into `transaction_sets/` package with individual files per transaction set
- File naming: `{tx_id}_{tx_name_snake_case}.py` (e.g., `850_purchase_order.py`)
- Match UBL's per-document-type file approach

## Implementation Steps

### 1. Create new template: `transaction_set.py.j2` (single transaction)
```python
"""
Transaction Set {id} - {name}
Auto-generated. Do not edit.
"""
from edi_schema.x12.models import TransactionSet, TransactionSetSegment
from edi_schema.x12.enums import TransactionSetArea, RequirementDesignator

TRANSACTION_SET = TransactionSet(...)

def get_transaction_set() -> TransactionSet:
    return TRANSACTION_SET
```

### 2. Create new template: `transaction_sets_init.py.j2` (package init)
```python
"""Transaction Sets package for X12 version {version}."""
from .{module_name} import TRANSACTION_SET as TS_{id}
# ... for each transaction

TRANSACTION_SETS: dict[str, TransactionSet] = {
    "{id}": TS_{id},
    # ...
}

def get_transaction_set(transaction_id: str) -> TransactionSet | None:
    return TRANSACTION_SETS.get(transaction_id)
```

### 3. Modify `generator.py`
- Add `_to_snake_case(name: str) -> str` helper
- Change `_generate_transaction_sets()`:
  - Create `transaction_sets/` subdirectory
  - For each transaction: generate `{id}_{snake_name}.py`
  - Generate `transaction_sets/__init__.py`

### 4. Update `__init__.py.j2` template
- Change import from `from .transaction_sets import ...`
- To `from .transaction_sets import ...` (same, but now it's a package)

### 5. Regenerate schemas
```bash
python -m edi_schema.x12.codegen.generator \
  --source /path/to/005010 \
  --output src/edi_schema/x12/schemas/v005010 \
  --version 005010
```

## File Structure (After)
```
schemas/v005010/
├── __init__.py
├── data_elements.py
├── segments.py
├── composites.py
├── lookups.py
└── transaction_sets/
    ├── __init__.py
    ├── 100_insurance_plan_description.py
    ├── 810_invoice.py
    ├── 850_purchase_order.py
    ├── 856_ship_notice_manifest.py
    └── ... (one file per transaction set)
```

## Benefits
- Faster imports (only load what you need)
- Easier navigation and code review
- Consistent with UBL codegen approach
- Git diffs are cleaner when transaction sets change
