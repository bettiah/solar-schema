# X12 850 Comprehensive Mapping Enhancements

## Problem Statement

The current 850 mapping has gaps that cause real-world EDI data to be silently dropped:

1. **Missing REF qualifiers** - Only 8 of 100+ qualifiers mapped
2. **Header-level PER not processed** - Contact info outside N1 loops ignored
3. **FOB incomplete** - Only elements 01 and 05 mapped
4. **Many other gaps** - Real EDI files use many more fields

## Observed Unmapped Data (From Real Files)

### REF Segment Qualifiers Not Mapped

| Qualifier | Name | Should Map To |
|-----------|------|---------------|
| 8M | Related Vendor Order Number | `additional_document_references[+].id` |
| 2I | Tracking Number | `shipment.tracking_id` |
| AH | Agreement Number | `contract_document_reference.id` |
| CO | Customer Order Number | `order_document_references[+].id` |
| CR | Customer Reference Number | `buyer_customer_party.customer_assigned_account_id` |
| IV | Invoice Number | `additional_document_references[+].id` |
| KK | Carrier's Reference Number | `shipment.carrier_reference` |
| MA | Ship Notice Number | `despatch_document_reference.id` |
| OQ | Order Number | `order_document_references[+].id` |
| PD | Promotion/Deal Number | `additional_document_references[+].id` |
| SE | Serial Number | `additional_document_references[+].id` |
| TN | Transaction Reference Number | `additional_document_references[+].id` |
| ZZ | Mutually Defined | `additional_document_references[+].id` |

### Header-Level PER Segment (Outside N1 Loop)

Currently **NOT PROCESSED**. Example:
```
PER*OC*Donna Person*TE*4255552515*FX*4255553875~
```

| Element | Value | Should Map To |
|---------|-------|---------------|
| 01 | OC (Order Contact) | Determines which contact field |
| 02 | Donna Person | `buyer_customer_party.buyer_contact.name` |
| 03/04 | TE/4255552515 | `buyer_customer_party.buyer_contact.telephone` |
| 05/06 | FX/4255553875 | `buyer_customer_party.buyer_contact.telefax` |

**PER*01 Qualifier Mapping:**
| Qualifier | Meaning | Target Path |
|-----------|---------|-------------|
| OC | Order Contact | `buyer_customer_party.buyer_contact` |
| BD | Buyer Name/Dept | `buyer_customer_party.buyer_contact` |
| CN | General Contact | `additional_contacts[+]` |
| IC | Information Contact | `additional_contacts[+]` |
| BI | Billing Contact | `accounting_customer_party.accounting_contact` |
| SC | Shipping Contact | `delivery[0].contact` |

### FOB Segment Complete Mapping

Current: Only FOB*01 and FOB*05
Example: `FOB*PP*ZZ*UPS Ground #442E1W~`

| Element | Name | Current | Should Map To |
|---------|------|---------|---------------|
| 01 | Shipment Method of Payment | ✅ Mapped | `delivery_terms` |
| 02 | Location Qualifier | ❌ Missing | `delivery[0].delivery_terms.location_qualifier` |
| 03 | Description | ❌ Missing | `delivery[0].delivery_terms.description` |
| 04 | Transport Terms Qualifier | ❌ Missing | - |
| 05 | Transport Terms | ✅ Mapped | `delivery[0].delivery_terms.special_terms` |
| 06 | Location Qualifier | ❌ Missing | - |
| 07 | Description | ❌ Missing | `delivery[0].delivery_terms.risk_description` |
| 08 | Risk of Loss Code | ❌ Missing | `delivery[0].delivery_terms.risk_code` |
| 09 | Description | ❌ Missing | - |

### N9 Segment (Extended References)

Currently only LI, DO, CR, PD, AH mapped. Missing many common qualifiers:

| Qualifier | Name | Should Map To |
|-----------|------|---------------|
| L1 | Letters or Notes | `note[+]` |
| OC | Order Contact | References contact |
| PO | Purchase Order Number | `order_document_references[+].id` |
| SI | Shipper's Identifying Number | `shipment.id` |
| VR | Vendor ID Number | `seller_supplier_party.supplier_assigned_account_id` |
| ZZ | Mutually Defined | `additional_document_references[+].id` |

### MSG Segment Handling

Currently only MSG*01 mapped. MSG can appear:
- At header level (order notes)
- Within N1 loop (party notes)
- Within PO1 loop (line item notes)

### CSH Segment (Sales Requirements)

Not currently mapped. Example: `CSH*N~`

| Element | Name | Should Map To |
|---------|------|---------------|
| 01 | Sales Requirement Code | `order_type_code` (N=No backorder) |
| 02 | Action Code | `special_instructions` |
| 03-05 | Quantity/Percent | Backorder handling |

### PKG Segment (Packaging)

Not currently mapped.

| Element | Name | Should Map To |
|---------|------|---------------|
| 01 | Item Description Type | - |
| 02 | Packaging Characteristic Code | `delivery[0].shipment.packaging_type_code` |
| 03 | Agency Qualifier | - |
| 04 | Packaging Description Code | `delivery[0].shipment.packaging_code` |
| 05 | Description | `delivery[0].shipment.packaging_description` |

---

## Implementation Plan

### Phase 1: Header-Level PER Processing

**Priority: HIGH** - This is commonly used data being completely dropped.

Add to `engine.py`:
```python
def _map_header_per_segments(
    self,
    model: Any,
    content: list,
    accumulator: ErrorAccumulator,
    metrics: MappingMetrics | None,
    trace: MappingTrace | None,
) -> None:
    """Map header-level PER segments (outside N1 loops)."""
    per_segments = find_all_segments(content, "PER")

    for per_seg in per_segments:
        # Skip if this PER is inside an N1 loop (handled elsewhere)
        if self._is_in_loop(per_seg, content, "N1"):
            continue

        qualifier = _get_element_value(per_seg, 1)
        contact = self._build_contact_from_per(per_seg)

        # Route based on qualifier
        if qualifier == "OC":  # Order Contact
            self._set_contact(model, "buyer_customer_party.buyer_contact", contact)
        elif qualifier == "BD":  # Buyer Dept
            self._set_contact(model, "buyer_customer_party.buyer_contact", contact)
        # ... etc
```

### Phase 2: Expand REF Qualifiers

Add to `order_850.py` `_REF_QUALIFIED_MAPPINGS`:

```python
"8M": [FieldMapping(seg("REF", 2), sem("additional_document_references[+].id"))],
"2I": [FieldMapping(seg("REF", 2), sem("shipment.tracking_id"))],
"AH": [FieldMapping(seg("REF", 2), sem("contract_document_reference.id"))],
"CO": [FieldMapping(seg("REF", 2), sem("order_document_references[+].id"))],
"CR": [FieldMapping(seg("REF", 2), sem("buyer_customer_party.customer_assigned_account_id"))],
"IV": [FieldMapping(seg("REF", 2), sem("additional_document_references[+].id"))],
"KK": [FieldMapping(seg("REF", 2), sem("delivery[0].shipment.carrier_reference"))],
"MA": [FieldMapping(seg("REF", 2), sem("despatch_document_reference.id"))],
"OQ": [FieldMapping(seg("REF", 2), sem("order_document_references[+].id"))],
"SE": [FieldMapping(seg("REF", 2), sem("additional_document_references[+].id"))],
"TN": [FieldMapping(seg("REF", 2), sem("additional_document_references[+].id"))],
"ZZ": [FieldMapping(seg("REF", 2), sem("additional_document_references[+].id"))],
```

### Phase 3: Complete FOB Mapping

Update `_HEADER_FIELD_MAPPINGS`:

```python
# FOB segment - complete mapping
FieldMapping(seg("FOB", 1), sem("delivery_terms")),
FieldMapping(seg("FOB", 2), sem("delivery[0].delivery_terms.location_qualifier")),
FieldMapping(seg("FOB", 3), sem("delivery[0].delivery_terms.description")),
FieldMapping(seg("FOB", 5), sem("delivery[0].delivery_terms.special_terms")),
FieldMapping(seg("FOB", 7), sem("delivery[0].delivery_terms.risk_description")),
FieldMapping(seg("FOB", 8), sem("delivery[0].delivery_terms.risk_code")),
```

**Note:** Need to add `location_qualifier`, `description`, `risk_description`, `risk_code` to `DeliveryTerms` model.

### Phase 4: Expand N9 Qualifiers

Add to `_N9_QUALIFIED_MAPPINGS`:

```python
"L1": [FieldMapping(seg("N9", 2), sem("note[+]"))],
"PO": [FieldMapping(seg("N9", 2), sem("order_document_references[+].id"))],
"SI": [FieldMapping(seg("N9", 2), sem("delivery[0].shipment.id"))],
"VR": [FieldMapping(seg("N9", 2), sem("seller_supplier_party.supplier_assigned_account_id"))],
"ZZ": [FieldMapping(seg("N9", 2), sem("additional_document_references[+].id"))],
```

### Phase 5: Add CSH and PKG Segments

Add new header field mappings:

```python
# CSH segment - Sales Requirements
FieldMapping(seg("CSH", 1), sem("backorder_policy")),  # Need to add to Order model
FieldMapping(seg("CSH", 2), sem("special_instructions")),

# PKG segment - Packaging
FieldMapping(seg("PKG", 2), sem("delivery[0].shipment.packaging_characteristic_code")),
FieldMapping(seg("PKG", 4), sem("delivery[0].shipment.packaging_code")),
FieldMapping(seg("PKG", 5), sem("delivery[0].shipment.packaging_description")),
```

### Phase 6: Model Enhancements

Add missing fields to models:

**Order model:**
```python
backorder_policy: str | None = None
special_instructions: str | None = None
additional_contacts: list[Contact] = Field(default_factory=list)
```

**DeliveryTerms model:**
```python
location_qualifier: str | None = None
description: str | None = None
risk_description: str | None = None
risk_code: str | None = None
```

**Shipment model:**
```python
carrier_reference: str | None = None
tracking_id: str | None = None
packaging_characteristic_code: str | None = None
packaging_code: str | None = None
packaging_description: str | None = None
```

---

## Implementation Order

1. **Phase 1: Header PER** (Critical - data being lost)
2. **Phase 2: REF qualifiers** (Common, easy to add)
3. **Phase 3: FOB completion** (Low effort, high value)
4. **Phase 4: N9 expansion** (Medium effort)
5. **Phase 5: CSH/PKG** (Lower priority)
6. **Phase 6: Model updates** (As needed by above)

---

## Verification

After implementation, parse test file and verify:
1. `REF*8M*COMPANYB*ORIGIN~` maps to `additional_document_references`
2. `PER*OC*Donna Person*TE*4255552515*FX*4255553875~` maps to `buyer_contact`
3. `FOB*PP*ZZ*UPS Ground #442E1W~` maps all elements
4. All warnings for truly unmapped data (not just missing mappings)

---

## Files to Modify

| File | Changes |
|------|---------|
| `mapping/x12/order_850.py` | Add REF, N9, FOB, CSH, PKG mappings |
| `mapping/engine.py` | Add `_map_header_per_segments` method |
| `models/order.py` | Add `backorder_policy`, `special_instructions`, `additional_contacts` |
| `models/delivery.py` | Update DeliveryTerms model |
| `models/shipment.py` | Add carrier_reference, tracking_id, packaging fields |
| `tests/semantic/test_x12_order_mapper.py` | Add tests for new mappings |
