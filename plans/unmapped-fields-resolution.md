# Plan: Resolve Unmapped Fields in 850 Order Mapping

## Problem Statement

The test `test_unmapped_tracking_enabled` shows 9 fields that are not being properly mapped:
- 6 `UNMAPPED_ELEMENT` warnings (no mapping defined)
- 3 `CANNOT_SET_FIELD` warnings (mapping exists but fails due to missing intermediate objects)

## Current Warnings Analysis

### From Fixture File: `850_purchase_order.x12`

```
CUR*SN*USD~                    → CUR*01="SN" unmapped
REF*8M*COMPANYB*ORIGIN~        → REF*03="ORIGIN" unmapped
PO1*1*1*EA*8.90**VP*32230538~  → PO1*06="VP", PO1*07="32230538" unmapped
CTT*1*1~                       → CTT*02="1" unmapped
AMT*TT*8.90~                   → AMT*01="TT" unmapped, AMT*02 cannot set
DTM*010*20161206~              → DTM[010]*2 cannot set
```

---

## UNMAPPED_ELEMENT Issues (6 fields)

### 1. CUR*01 - Entity Identifier Code
**Value:** `SN` (Selling Party)
**Purpose:** Qualifies which party the currency (CUR*02) applies to
**Options:**
- A) Add mapping to `pricing_currency_entity_code` (new field needed on Order)
- B) Ignore - currency typically applies to document, not specific party
- **Recommendation:** Option B - Document currency code (CUR*02) is already mapped

### 2. REF*03 - Reference Description
**Value:** `ORIGIN` (for REF*8M*COMPANYB)
**Purpose:** Provides additional description for the reference
**Target:** `additional_document_references[].description`
**Solution:** Update REF qualified mappings to also capture element 03
```python
"8M": [
    FieldMapping(seg("REF", 2), sem("additional_document_references[+].id")),
    FieldMapping(seg("REF", 3), sem("additional_document_references[-1].description")),  # NEW
],
```
**Complexity:** Medium - need to handle `-1` index for "last added item"

### 3. PO1*06 and PO1*07 - Product ID Qualifier/Value
**Value:** `VP` = Vendor's Part Number, `32230538` = the actual ID
**Current Behavior:** Handled by `_extract_po1_product_ids()` special handler
**Issue:** Elements still flagged as "unmapped" because they're not in `_get_mapped_elements()`
**Solution:** Add PO1 elements 06-25 to `_get_mapped_elements()` for 850 transactions
```python
# In _get_mapped_elements():
if self.mapping.transaction_id in ("850", "810", "856"):
    if "PO1" not in elements:
        elements["PO1"] = set()
    elements["PO1"].update(range(6, 26))  # Product ID pairs
```

### 4. CTT*02 - Hash Total
**Value:** `1` (sum of quantities for validation)
**Purpose:** Transmission validation, not business data
**Options:**
- A) Add to a `hash_total` field on Order (new field needed)
- B) Mark as intentionally unmapped (validation-only field)
- **Recommendation:** Option B - Add CTT*02 to "known unmapped" list

### 5. AMT*01 - Amount Qualifier
**Value:** `TT` (Total Transaction Amount)
**Purpose:** Qualifies what AMT*02 represents
**Current Behavior:** The qualified mapping uses `qualifier=(1, "TT")` but element 01 itself isn't "mapped"
**Solution:** The qualifier element is used for routing, not storage. Add to `_get_mapped_elements()`:
```python
# AMT*01 is the qualifier used to route AMT*02, not a separate value
elements["AMT"].add(1)
```

---

## CANNOT_SET_FIELD Issues (3 fields)

### 1. AMT*02 → `anticipated_monetary_total.payable_amount.value`
**Value:** `8.90`
**Issue:** `Order.anticipated_monetary_total` is None, and `payable_amount` within it is also None
**Solution:** Add `_map_amt_totals()` special handler:
```python
def _map_amt_totals(self, model, content, metrics, trace):
    """Map AMT*TT to anticipated_monetary_total.payable_amount."""
    from edi_schema.semantic.models import Amount, MonetaryTotal

    for item in content:
        if hasattr(item, "tag") and item.tag == "AMT":
            qualifier = _get_element_value(item, 1)
            amount = _get_element_value(item, 2)

            if qualifier == "TT" and amount:
                # Create MonetaryTotal with Amount
                if model.anticipated_monetary_total is None:
                    model.anticipated_monetary_total = MonetaryTotal()
                model.anticipated_monetary_total.payable_amount = Amount(
                    value=Decimal(amount),
                    currency=model.document_currency_code or "USD"
                )
```

### 2. DTM[010]*2 → `delivery[0].despatch.requested_despatch_date`
**Value:** `20161206`
**Issue:** `delivery[0].despatch` is None
**Solution:** Add `_map_dtm_despatch()` special handler:
```python
def _map_dtm_despatch(self, model, content, metrics, trace):
    """Map DTM*010 to delivery[0].despatch.requested_despatch_date."""
    from edi_schema.semantic.models import Despatch

    if not model.delivery:
        return

    for item in content:
        if hasattr(item, "tag") and item.tag == "DTM":
            qualifier = _get_element_value(item, 1)
            date_value = _get_element_value(item, 2)

            if qualifier == "010" and date_value:
                delivery = model.delivery[0]
                if delivery.despatch is None:
                    delivery.despatch = Despatch()
                delivery.despatch.requested_despatch_date = parse_date(date_value)
```

### 3. PO1*05 → `price.base_quantity_unit_code`
**Value:** Empty in this fixture (element not present)
**Issue:** Line item's `price` may not exist when trying to set `base_quantity_unit_code`
**Solution:** The `_set_nested_value_with_construction` already handles price creation.
The warning appears because the value is empty string, not None.
**Fix:** Skip empty string values in field mapping logic.

---

## Implementation Plan

### Task 1: Suppress Validation-Only Fields (Easy)
- Add CTT*02 to "known unmapped" list - it's validation-only data
- Add AMT*01 qualifier element to mapped elements set

### Task 2: Add PO1 Product ID Elements to Mapped Set (Easy)
- Update `_get_mapped_elements()` to include PO1*06-25

### Task 3: Add `_map_amt_totals()` Handler (Medium)
- Create handler to build MonetaryTotal.payable_amount from AMT*TT
- Add to Phase 6.x in `to_semantic()`

### Task 4: Add `_map_dtm_despatch()` Handler (Medium)
- Create handler to build Despatch object for DTM*010
- Add to Phase 6.x in `to_semantic()`

### Task 5: Add REF*03 Description Mapping (Medium-Hard)
- Need mechanism to reference "last added item" in list (`[-1]` syntax)
- Or handle in special handler for REF segments

### Task 6: Skip Empty String Values (Easy)
- Update field mapping to treat empty string same as None

---

## Expected Final State

After implementation:
```
=== Remaining warnings ===
(None - all fields properly mapped or intentionally skipped)
```

Or minimal warnings for truly unmapped data:
```
=== Remaining warnings ===
  UNMAPPED_ELEMENT: CUR*01 -> None  # Intentionally not mapped (entity qualifier)
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `mapping/engine.py` | Add `_map_amt_totals()`, `_map_dtm_despatch()`, update `_get_mapped_elements()` |
| `mapping/x12/order_850.py` | Remove AMT field mapping (handled by special handler) |
| `tests/semantic/test_x12_order_mapper.py` | Update expected warnings |

---

## Priority Order

1. **Task 2** - PO1 product IDs (quick fix, high visibility)
2. **Task 1** - CTT/AMT qualifiers (quick fix)
3. **Task 6** - Empty string handling (quick fix)
4. **Task 3** - AMT totals handler (functional improvement)
5. **Task 4** - DTM despatch handler (functional improvement)
6. **Task 5** - REF description (lower priority, complex)
