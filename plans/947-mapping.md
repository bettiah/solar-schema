# X12 947 Warehouse Inventory Adjustment Advice Mapping

## Overview

Maps X12 947 Warehouse Inventory Adjustment Advice to UBL InventoryReport semantic model.

**Status:** Planning
**X12 Transaction:** 947 - Warehouse Inventory Adjustment Advice
**UBL Document:** InventoryReport

---

## Header Level Mappings

| X12 Segment | Element | X12 Name | Semantic Path | Notes |
|-------------|---------|----------|---------------|-------|
| **W15** | 01 | Transaction Date | `issue_date` | |
| W15 | 02 | Adjustment Number | `id` | |
| W15 | 03 | Depositor Order Number | `related_document_reference.id` | |
| W15 | 04 | Warehouse ID | `inventory_reporting_party.party_identifications[0].id.value` | |
| W15 | 05 | Warehouse ID Qualifier | `inventory_reporting_party.party_identifications[0].id.scheme_id` | |
| **N9** | 01 | Reference Qualifier | `document_references[-1].document_type_code` | |
| N9 | 02 | Reference ID | `document_references[+].id` | |
| **G62** | 02 | Date | `inventory_period.end_date` | As-of date |
| **NTE** | 02 | Note | `note[+]` | |

---

## Party Mappings (N1 Loop)

| Qualifier | X12 Name | Semantic Path |
|-----------|----------|---------------|
| WH | Warehouse | `inventory_reporting_party` |
| DE | Depositor | `retailer_customer_party` | Goods owner |
| SF | Ship From | `previous_location_party` | For transfers |
| ST | Ship To | `destination_location_party` | For transfers |

---

## Line Item Mappings (W07 Loop)

### W07 - Item Detail for Stock Transfer

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| W07*01 | Quantity | `inventory_report_line.quantity.value` |
| W07*02 | Unit of Measure | `inventory_report_line.quantity.unit_code` |
| W07*03 | UPC Code | `inventory_report_line.item.standard_item_identification.id.value` |
| W07*04 | Product ID Qualifier | `inventory_report_line.item.*_item_identification.id.scheme_id` |
| W07*05 | Product ID | `inventory_report_line.item.*_item_identification.id.value` |
| W07*06 | Warehouse Lot Number | `inventory_report_line.item.lot_identification.lot_number_id` |
| W07*07 | Adjustment Reason Code | `inventory_report_line.note` | See codes below |
| W07*08 | Weight | `inventory_report_line.item.weight.value` |
| W07*09 | Weight Qualifier | `inventory_report_line.item.weight.unit_code` |
| W07*10 | Weight Unit | (unit code) |

---

## Adjustment Reason Codes (W07*07)

| X12 Code | Meaning | Semantic Code |
|----------|---------|---------------|
| 01 | Price Protection | `PRICE_PROTECTION` |
| 02 | Damaged in Warehouse | `DAMAGED` |
| 03 | Damaged in Transit | `DAMAGED_TRANSIT` |
| 04 | Destroyed | `DESTROYED` |
| 05 | Inventory Recount | `RECOUNT` |
| 06 | Returned to Supplier | `RETURNED` |
| 07 | Shipped (Outbound) | `SHIPPED` |
| 08 | Received (Inbound) | `RECEIVED` |
| 09 | Shelf Life Expired | `EXPIRED` |
| 10 | Lost | `LOST` |
| 11 | Theft/Pilferage | `STOLEN` |
| 12 | Transferred Out | `TRANSFERRED_OUT` |
| 13 | Transferred In | `TRANSFERRED_IN` |
| 14 | Quality Hold | `QUALITY_HOLD` |
| 15 | Cycle Count Variance | `CYCLE_COUNT` |
| 16 | Overage | `OVERAGE` |
| 17 | Shortage | `SHORTAGE` |
| DM | Damaged | `DAMAGED` |
| RC | Received | `RECEIVED` |
| SH | Shipped | `SHIPPED` |
| AJ | Adjustment | `ADJUSTMENT` |
| OS | Overage | `OVERAGE` |
| US | Underage | `SHORTAGE` |

---

## Pack Size Mappings (W20 Segment)

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| W20*01 | Pack Size | `inventory_report_line.item.contained_item.quantity.value` |
| W20*02 | Pack Size Unit | `inventory_report_line.item.contained_item.quantity.unit_code` |
| W20*03 | Weight | `inventory_report_line.gross_weight_measure.value` |
| W20*04 | Weight Qualifier | (unit code) |
| W20*05 | Unit Weight | `inventory_report_line.item.weight.value` |
| W20*06 | Volume | `inventory_report_line.gross_volume_measure.value` |
| W20*07 | Volume Qualifier | (unit code) |

---

## Reference Mappings (N9 within W07 Loop)

| Qualifier | X12 Name | Semantic Path |
|-----------|----------|---------------|
| LO | Lot Number | `inventory_report_line.item.lot_identification.lot_number_id` |
| SE | Serial Number | `inventory_report_line.item.item_instance.serial_id` |
| PO | Purchase Order | `inventory_report_line.document_reference.id` |
| LI | Line Item Reference | `inventory_report_line.id` |

---

## Description Mappings (G69 Segment)

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| G69*01 | Free-Form Description | `inventory_report_line.item.description` |

---

## Date Mappings (G62 Segment)

| Qualifier | X12 Name | Semantic Path |
|-----------|----------|---------------|
| 10 | Received Date | `inventory_report_line.received_date` |
| 36 | Expiration Date | `inventory_report_line.item.expiry_date` |
| 94 | Production Date | `inventory_report_line.item.manufacture_date` |
| 97 | Transaction Date | `inventory_report_line.adjustment_date` |

---

## Implementation Tasks

- [ ] Extend InventoryReport semantic model for adjustments
- [ ] Create 947 mapping definition
- [ ] Add W15 header mapping
- [ ] Add W07 adjustment line handler
- [ ] Add adjustment reason code mapping
- [ ] Add W20 pack size handler
- [ ] Add tests with fixture files

---

## Files to Create/Modify

| File | Changes |
|------|---------|
| `models/inventory_report.py` | Extend for adjustment advice |
| `mapping/x12/inventory_adjustment_947.py` | Create mapping definition |
| `mapping/engine.py` | Add adjustment-specific handlers |
| `tests/semantic/test_x12_inventory_adjustment_mapper.py` | Add tests |
