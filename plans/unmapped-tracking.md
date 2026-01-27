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
- [ ] Add `get_unmapped_report()` to MappingResult (optional)
- [ ] Add `strict_mode` option (optional)
- [ ] Update documentation (optional)

---

## Success Criteria

1. ✅ Running the mapper on `850_purchase_order.x12` reports:
   - ✅ `REF*8M` as unmapped qualifier
   - ✅ Header-level `PER*OC` as unmapped segment
   - ✅ `FOB*02` and `FOB*03` as unmapped elements

2. ✅ Metrics show:
   - ✅ Total segments in document
   - ✅ Segments mapped
   - ✅ Segments unmapped (with reasons: unknown_qualifier, header_level, unmapped_element)
   - ✅ Qualifiers not recognized

3. [ ] Optional strict mode should fail the mapping if any data is unmapped (not yet implemented)

## Verification Output

```
=== Unmapped Summary ===
Total unmapped: 10
By segment: {'REF': 2, 'PER': 1, 'CUR': 1, 'FOB': 2, 'PO1': 2, 'CTT': 1, 'AMT': 1}
By reason: {'unknown_qualifier': 1, 'header_level': 1, 'unmapped_element': 8}
Unmapped qualifiers: {'REF': ['8M']}

=== Warnings ===
  UNMAPPED_QUALIFIER: No mapping for REF*8M
  UNMAPPED_SEGMENT: Header-level PER segment not mapped (only handled within N1 loops)
  UNMAPPED_ELEMENT: Element CUR*01 has value but no mapping: 'SN'
  UNMAPPED_ELEMENT: Element REF*03 has value but no mapping: 'ORIGIN'
  UNMAPPED_ELEMENT: Element FOB*02 has value but no mapping: 'ZZ'
  UNMAPPED_ELEMENT: Element FOB*03 has value but no mapping: 'UPS Ground #442E1W'
  UNMAPPED_ELEMENT: Element PO1*06 has value but no mapping: 'VP'
  UNMAPPED_ELEMENT: Element PO1*07 has value but no mapping: '32230538'
  UNMAPPED_ELEMENT: Element CTT*02 has value but no mapping: '1'
  UNMAPPED_ELEMENT: Element AMT*01 has value but no mapping: 'TT'
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `mapping/types.py` | Add UnmappedData, update MappingMetrics |
| `mapping/engine.py` | Add tracking logic, configuration options |
| `mapping/errors.py` | Add new error codes |
| `tests/semantic/test_unmapped_tracking.py` | New test file |
