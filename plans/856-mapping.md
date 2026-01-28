# X12 856 ASN (Advance Ship Notice) Mapping

## Overview

Maps X12 856 Ship Notice/Manifest (ASN) to UBL DespatchAdvice semantic model.

**Status:** Planning
**X12 Transaction:** 856 - Ship Notice/Manifest
**UBL Document:** DespatchAdvice

---

## Header Level Mappings

| X12 Segment | Element | X12 Name | Semantic Path | Notes |
|-------------|---------|----------|---------------|-------|
| **BSN** | 01 | Purpose Code | `document_status_code` | 00=Original |
| BSN | 02 | Shipment ID | `id` | |
| BSN | 03 | Date | `issue_date` | |
| BSN | 04 | Time | `issue_time` | |
| BSN | 05 | Hierarchical Structure Code | (internal) | X12-specific |
| **DTM** | (011) | Shipped Date | `shipment.actual_despatch_date` | |
| DTM | (017) | Est. Delivery Date | `shipment.estimated_delivery_period` | |
| **REF** | (PO) | PO Number | `order_reference.id` | |
| REF | (BM) | Bill of Lading | `shipment.id` | |

---

## Shipment Level Mappings (HL Loop - S)

| X12 Segment | Element | X12 Name | Semantic Path | Notes |
|-------------|---------|----------|---------------|-------|
| **TD1** | 01 | Packaging Code | `shipment.transport_handling_units[0].transport_handling_unit_type_code` | |
| TD1 | 02 | Lading Quantity | `shipment.total_transport_handling_unit_quantity` | |
| TD1 | 06 | Weight Qualifier | (determines unit) | |
| TD1 | 07 | Weight | `shipment.gross_weight_measure.value` | |
| TD1 | 08 | Unit of Measure | `shipment.gross_weight_measure.unit_code` | |
| **TD5** | 02 | ID Code Qualifier | `shipment.carrier_party.party_identifications[0].id.scheme_id` | SCAC |
| TD5 | 03 | Carrier ID | `shipment.carrier_party.party_identifications[0].id.value` | |
| TD5 | 04 | Transport Method Code | `shipment.shipment_stages[0].transport_means.transport_means_type_code` | |
| TD5 | 05 | Routing | `shipment.shipment_stages[0].transit_direction_code` | |
| **TD3** | 01 | Equipment Type Code | `shipment.transport_equipment[0].transport_equipment_type_code` | |
| TD3 | 03 | Equipment Number | `shipment.transport_equipment[0].id` | |

---

## Party Mappings (N1 Loop)

| Qualifier | X12 Name | Semantic Path |
|-----------|----------|---------------|
| SF | Ship From | `despatch_supplier_party` |
| ST | Ship To | `delivery_customer_party` |

---

## Hierarchical Level Mappings (HL Loop)

The 856 uses hierarchical levels (HL segments) to structure shipment data:

| HL Code | Level | Semantic Mapping |
|---------|-------|------------------|
| S | Shipment | `shipment` |
| O | Order | `despatch_line.order_line_reference` |
| P | Pack | `shipment.transport_handling_unit` |
| I | Item | `despatch_line.item` |

### Order Level (HL=O)

| Segment | Element | Semantic Path |
|---------|---------|---------------|
| **PRF** | 01 | `despatch_line.order_line_reference.order_reference.id` |
| PRF | 04 | `despatch_line.order_line_reference.order_reference.issue_date` |

### Pack Level (HL=P)

| Segment | Element | Semantic Path |
|---------|---------|---------------|
| **MAN** | 01 | Marks/Numbers Qualifier | GM=SSCC-18 |
| MAN | 02 | `shipment.transport_handling_units[+].id` | SSCC barcode |

### Item Level (HL=I)

| Segment | Element | Semantic Path |
|---------|---------|---------------|
| **LIN** | 01 | `despatch_line.id` | |
| LIN | 02 | Product ID Qualifier | |
| LIN | 03 | `despatch_line.item.*_item_identification.id` | |
| **SN1** | 02 | `despatch_line.delivered_quantity.value` | |
| SN1 | 03 | `despatch_line.delivered_quantity.unit_code` | |
| **PID** | 05 | `despatch_line.item.description` | |

---

## Semantic Gaps

### X12 → Semantic
- HL hierarchical structure - UBL uses flat DespatchLine with nesting via references
- Multiple tracking numbers per shipment - X12 REF loop vs UBL single Shipment.ID

### Semantic → X12
- `despatch_advice.despatch_supplier_party` - map to N1*SF
- `estimated_despatch_period` - no direct X12 equivalent

---

## Implementation Complexity

The 856 has unique complexity due to hierarchical structure:

1. **HL Loop Parsing** - Must track parent-child relationships via HL*02 (parent ID)
2. **Pack-Item Association** - Items belong to packs which belong to shipments
3. **SSCC Barcodes** - MAN segment with GM qualifier contains SSCC-18

### Recommended Approach

```python
# Pseudo-structure for 856 mapping
class ASN856Mapping:
    def map_shipment_level(self, hl_segment, content) -> Shipment
    def map_order_level(self, hl_segment, content) -> OrderReference
    def map_pack_level(self, hl_segment, content) -> TransportHandlingUnit
    def map_item_level(self, hl_segment, content) -> DespatchLine
```

---

## Implementation Tasks

- [ ] Create DespatchAdvice semantic model (or reuse from UBL)
- [ ] Create 856 mapping definition
- [ ] Implement HL loop hierarchy parser
- [ ] Add MAN segment SSCC handling
- [ ] Add TD1/TD3 transport equipment mapping
- [ ] Add tests with fixture files

---

## Files to Create/Modify

| File | Changes |
|------|---------|
| `models/despatch_advice.py` | Create DespatchAdvice semantic model |
| `mapping/x12/asn_856.py` | Create mapping definition |
| `mapping/engine.py` | Add HL hierarchy handler |
| `tests/semantic/test_x12_asn_mapper.py` | Add tests |
