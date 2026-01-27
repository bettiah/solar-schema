# Unmapped Segment/Element Tracking

## Problem Statement

The mapping engine silently skips segments and elements that don't have mappings defined. This makes it difficult to:
1. Know what data is being lost during mapping
2. Debug mapping issues
3. Identify gaps in mapping coverage
4. Ensure data integrity in transformations

## Current Behavior (Silent Skipping)

### 1. Qualified Segments (REF, DTM, N9, etc.)

**Location:** `engine.py:957-958`
```python
if qualifier_value not in qualified_mapping.mappings:
    continue  # SILENT - no warning, no metric
```

**Example:** `REF*8M*COMPANYB*ORIGIN~` is completely ignored because "8M" isn't in the REF qualified mappings.

### 2. Header-Level PER Segments

**Location:** `_populate_party_fields` only processes PER inside N1 loops.

**Example:** `PER*OC*Donna Person*TE*4255552515*FX*4255553875~` at header level is never processed.

### 3. Unmapped Elements Within Mapped Segments

**Location:** Field mappings only extract specific elements.

**Example:** `FOB*PP*ZZ*UPS Ground #442E1W~`
- FOB*01 (PP) is mapped to `delivery_terms`
- FOB*02 (ZZ) - silently ignored
- FOB*03 (UPS Ground #442E1W) - silently ignored
- FOB*05 - would be mapped if present

### 4. Unrecognized Segments

**Location:** Segments not in any mapping are never touched.

**Example:** Any segment type not explicitly handled (like header-level PER).

---

## Proposed Solution

### Phase 1: Add Unmapped Tracking Data Structure

Add to `MappingMetrics`:
```python
@dataclass
class UnmappedData:
    segment_tag: str
    qualifier: str | None
    element_index: int | None
    value: str | None
    reason: str  # "unknown_qualifier", "no_mapping", "header_level", etc.

@dataclass
class MappingMetrics:
    # ... existing fields ...
    unmapped_segments: list[UnmappedData] = field(default_factory=list)
    unmapped_elements: list[UnmappedData] = field(default_factory=list)
    unmapped_qualifiers: dict[str, list[str]] = field(default_factory=dict)  # {segment: [qualifiers]}
```

### Phase 2: Track Unmapped Qualified Segments

In `_map_qualified_segments`:
```python
if qualifier_value not in qualified_mapping.mappings:
    if metrics:
        metrics.unmapped_qualifiers.setdefault(
            qualifier_path.segment, []
        ).append(qualifier_value)
        metrics.unmapped_segments.append(UnmappedData(
            segment_tag=qualifier_path.segment,
            qualifier=qualifier_value,
            element_index=None,
            value=None,
            reason="unknown_qualifier"
        ))
    if self.warn_on_unmapped:
        accumulator.add_warning(
            MappingErrorCode.UNMAPPED_QUALIFIER,
            f"Unmapped {qualifier_path.segment}*{qualifier_value}",
            source_path=f"{qualifier_path.segment}*{qualifier_value}",
        )
    continue
```

### Phase 3: Track All Segments in Document

Add segment tracking at start of `to_semantic`:
```python
def _collect_all_segments(self, content) -> dict[str, list[ParsedSegment]]:
    """Collect all segments by type for tracking."""
    segments = {}
    for item in content:
        if hasattr(item, 'tag'):
            segments.setdefault(item.tag, []).append(item)
        elif hasattr(item, 'segments'):
            # Recurse into loops
            for seg in item.segments:
                segments.setdefault(seg.tag, []).append(seg)
    return segments
```

At end of mapping, compare mapped vs all segments:
```python
def _report_unmapped_segments(self, all_segments, mapped_segments, metrics, accumulator):
    """Report segments that were not mapped."""
    for tag, segs in all_segments.items():
        if tag not in mapped_segments:
            for seg in segs:
                if metrics:
                    metrics.unmapped_segments.append(UnmappedData(
                        segment_tag=tag,
                        qualifier=_get_element_value(seg, 1),
                        element_index=None,
                        value=None,
                        reason="no_mapping"
                    ))
```

### Phase 4: Add Configuration Options

Add to `MappingEngine.__init__`:
```python
def __init__(
    self,
    mapping: TransactionMapping,
    collect_metrics: bool = False,
    warn_on_unmapped: bool = True,  # NEW
    strict_mode: bool = False,       # NEW - fail on unmapped
):
```

### Phase 5: Add Unmapped Report to MappingResult

```python
@dataclass
class MappingResult:
    # ... existing fields ...
    unmapped_summary: dict[str, Any] | None = None

    def get_unmapped_report(self) -> str:
        """Generate human-readable unmapped data report."""
```

---

## Implementation Tasks

### Phase 1: Unmapped Tracking (COMPLETE)
- [x] Add `UnmappedData` dataclass to diagnostics.py
- [x] Add unmapped tracking fields to `MappingMetrics`
- [x] Add `MappingErrorCode.UNMAPPED_QUALIFIER`, `UNMAPPED_SEGMENT`, `UNMAPPED_ELEMENT`
- [x] Update `_map_qualified_segments` to track/warn on unknown qualifiers
- [x] Add `_collect_segment_tags` method
- [x] Add `_report_unmapped_segments` method
- [x] Add `_report_unmapped_elements` method
- [x] Add `warn_on_unmapped` option
- [x] Add header-level segment tracking (PER, etc.)
- [x] Add unmapped element tracking within segments
- [x] Add tests for unmapped tracking

### Phase 2: Special Segment Handlers (COMPLETE)
- [x] Add `_map_header_per_segments()` for header-level PER*OC, PER*IC contacts
- [x] Add `_map_fob_to_delivery()` for FOB*02, FOB*03, FOB*05 delivery terms
- [x] Add `_map_td5_to_shipment()` for TD5 carrier/shipping info (creates Shipment object)
- [x] Add `_map_msg_notes()` for MSG segments (recursively finds MSG in N9 loops too)

### Phase 3: Failed Mapping Warnings (COMPLETE)
- [x] Add `CANNOT_SET_FIELD` warnings when `set_nested_attr` fails but value exists
- [x] Update `_map_optional_field_mappings`, `_map_qualified_segments`, `_map_loop_item_optional_fields`

### Future Work (Optional)
- [ ] Add `get_unmapped_report()` to MappingResult
- [ ] Add `strict_mode` option
- [ ] Add handlers for AMT and DTM to create intermediate objects
- [ ] Update documentation

---

## Success Criteria

1. ✅ Running the mapper on `850_purchase_order.x12` now:
   - ✅ Successfully maps header-level `PER*OC` to `buyer_customer_party.buyer_contact`
   - ✅ Successfully maps `FOB*02`, `FOB*03` to `delivery[0].delivery_terms`
   - ✅ Successfully maps `TD5` to `delivery[0].shipment` (carrier, mode, service level)
   - ✅ Successfully maps `MSG` to `note[]` list (including MSG inside N9 loops)
   - ✅ Generates warnings for unmapped elements (CUR*01, REF*03, PO1*06/07, CTT*02, AMT*01)
   - ✅ Generates `CANNOT_SET_FIELD` warnings for failed mappings (AMT*TT, DTM*010, PO1*05)

2. ✅ Metrics show:
   - ✅ Total segments in document
   - ✅ Segments mapped
   - ✅ Segments unmapped (with reasons: unknown_qualifier, header_level, unmapped_element)
   - ✅ Qualifiers not recognized

3. [ ] Optional strict mode should fail the mapping if any data is unmapped (not yet implemented)

## Current Verification Output

```
=== Order note list ===
note: ['If items are available for partial shipment, please contact companyA@trading.com for authorization prior to release']

=== Shipment data ===
carrier_party: Party with UPSN identification
shipment_stages: [ShipmentStage(transit_direction_code='UPS Ground #442E2E')]
shipping_priority_level_code: SG

=== Remaining warnings ===
  CANNOT_SET_FIELD: AMT*02 [*1=TT] -> anticipated_monetary_total.payable_amount.value
  CANNOT_SET_FIELD: DTM[010]*2 -> delivery[0].despatch.requested_despatch_date
  CANNOT_SET_FIELD: PO1*05 -> price.base_quantity_unit_code
  UNMAPPED_ELEMENT: CUR*01 -> None
  UNMAPPED_ELEMENT: REF*03 -> None
  UNMAPPED_ELEMENT: PO1*06 -> None
  UNMAPPED_ELEMENT: PO1*07 -> None
  UNMAPPED_ELEMENT: CTT*02 -> None
  UNMAPPED_ELEMENT: AMT*01 -> None
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `mapping/types.py` | Add UnmappedData, update MappingMetrics |
| `mapping/engine.py` | Add tracking logic, configuration options |
| `mapping/errors.py` | Add new error codes |
| `tests/semantic/test_unmapped_tracking.py` | New test file |
