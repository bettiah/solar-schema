# X12 945 Warehouse Shipping Advice Mapping

## Overview

Maps X12 945 Warehouse Shipping Advice to UBL DespatchAdvice semantic model.

**Status:** Planning
**X12 Transaction:** 945 - Warehouse Shipping Advice
**UBL Document:** DespatchAdvice

---

## Header Level Mappings

| X12 Segment | Element | X12 Name | Semantic Path | Notes |
|-------------|---------|----------|---------------|-------|
| **W06** | 01 | Reporting Code | `document_status_code` | F=Final, P=Partial |
| W06 | 02 | Depositor Order Number | `order_reference.id` | Original order ref |
| W06 | 03 | Ship Date | `issue_date` | |
| W06 | 04 | Shipment ID | `id` | |
| W06 | 05 | Warehouse ID | `despatch_supplier_party.party_identifications[0].id.value` | |
| W06 | 06 | Warehouse ID Qualifier | `despatch_supplier_party.party_identifications[0].id.scheme_id` | |
| **N9** | 01 | Reference Qualifier | `document_references[-1].document_type_code` | |
| N9 | 02 | Reference ID | `document_references[+].id` | |
| **G62** | 01 | Date Qualifier | (determines field) | |
| G62 | 02 | Date | Various date fields | |
| **NTE** | 02 | Note | `note[+]` | |

---

## Reporting Codes (W06*01)

| X12 Code | Meaning | Semantic `document_status_code` |
|----------|---------|--------------------------------|
| F | Final/Complete Shipment | `FINAL` |
| P | Partial Shipment | `PARTIAL` |
| R | Resubmission | `RESUBMITTED` |
| W | Void/Reversal | `VOID` |

---

## Party Mappings (N1 Loop)

| Qualifier | X12 Name | Semantic Path |
|-----------|----------|---------------|
| WH | Warehouse | `despatch_supplier_party` |
| SF | Ship From | `despatch_supplier_party.postal_address` |
| ST | Ship To | `delivery_customer_party` |
| BY | Buyer | `buyer_customer_party` |
| DE | Depositor | `document_issuer_party` |

---

## Carrier Mappings (W27 Segment)

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| W27*01 | Transportation Method | `shipment.shipment_stage.transport_means.transport_means_type_code` |
| W27*02 | Standard Carrier Alpha Code | `shipment.shipment_stage.carrier_party.party_identifications[0].id.value` |
| W27*03 | Routing | `shipment.routing_instructions` |
| W27*04 | Shipment Method of Payment | `shipment.freight_payment_code` |
| W27*05 | Equipment Initial | `shipment.transport_handling_unit.transport_equipment.id` | Prefix |
| W27*06 | Equipment Number | `shipment.transport_handling_unit.transport_equipment.id` | Number |

---

## Reference Mappings (N9 Qualifiers)

| Qualifier | X12 Name | Semantic Path |
|-----------|----------|---------------|
| BM | Bill of Lading | `shipment.id` |
| CN | Carrier's Reference (PRO) | `shipment.shipment_stage.id` |
| PO | Purchase Order | `order_reference.id` |
| SN | Seal Number | `shipment.transport_handling_unit.seal_id` |
| 2I | Tracking Number | `shipment.tracking_id` |

---

## Line Item Mappings (W12 Loop)

### W12 - Warehouse Item Detail

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| W12*01 | Shipment/Order Status | `despatch_line.line_status_code` |
| W12*02 | Quantity Shipped | `despatch_line.delivered_quantity.value` |
| W12*03 | Quantity Ordered | `despatch_line.outstanding_quantity.value` | (for backorders) |
| W12*04 | Quantity Difference | `despatch_line.short_quantity.value` |
| W12*05 | Unit of Measure | `despatch_line.delivered_quantity.unit_code` |
| W12*06 | UPC Code | `despatch_line.item.standard_item_identification.id.value` |
| W12*07 | Product ID Qualifier | `despatch_line.item.*_item_identification.id.scheme_id` |
| W12*08 | Product ID | `despatch_line.item.*_item_identification.id.value` |
| W12*09 | Warehouse Lot Number | `despatch_line.item.lot_identification.lot_number_id` |
| W12*10 | Weight | `despatch_line.goods_item.gross_weight_measure.value` |
| W12*11 | Weight Qualifier | `despatch_line.goods_item.gross_weight_measure.unit_code` |
| W12*12 | Weight Unit | (unit code) |

---

## Shipment Status Codes (W12*01)

| X12 Code | Meaning | Semantic `line_status_code` |
|----------|---------|---------------------------|
| CC | Shipped Complete | `COMPLETE` |
| CP | Shipped Partial | `PARTIAL` |
| BO | Backordered | `BACKORDERED` |
| CN | Cancelled | `CANCELLED` |
| CS | Shipped as Substitute | `SUBSTITUTED` |
| NS | Not Shipped | `NOT_SHIPPED` |
| OS | Overshipped | `OVER` |

---

## Pack/Container Mappings (W20/MAN Segments)

### W20 - Item Pack Detail

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| W20*01 | Pack Size | `despatch_line.item.contained_item.quantity.value` |
| W20*02 | Pack Size Unit | `despatch_line.item.contained_item.quantity.unit_code` |
| W20*03 | Weight | `despatch_line.goods_item.gross_weight_measure.value` |
| W20*04 | Weight Qualifier | (unit code) |
| W20*05 | Unit Weight | `despatch_line.item.weight.value` |
| W20*06 | Volume | `despatch_line.goods_item.gross_volume_measure.value` |
| W20*07 | Volume Qualifier | (unit code) |

### MAN - Marks and Numbers

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| MAN*01 | Marks/Numbers Qualifier | (scheme_id) | GM=SSCC-18, CP=Carton |
| MAN*02 | Marks/Numbers | `despatch_line.shipment.transport_handling_unit.id` |

---

## Description Mappings (G69 Segment)

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| G69*01 | Free-Form Description | `despatch_line.item.description` |

---

## Implementation Tasks

- [ ] Create or extend DespatchAdvice semantic model for 3PL use
- [ ] Create 945 mapping definition
- [ ] Add W06 header mapping
- [ ] Add W27 carrier handler
- [ ] Add W12 line item handler (with status codes)
- [ ] Add W20/MAN pack detail handler
- [ ] Add tests with fixture files

---

## Files to Create/Modify

| File | Changes |
|------|---------|
| `models/despatch_advice.py` | Extend for warehouse shipping advice |
| `mapping/x12/warehouse_advice_945.py` | Create mapping definition |
| `mapping/engine.py` | Add warehouse advice handlers |
| `tests/semantic/test_x12_warehouse_advice_mapper.py` | Add tests |
