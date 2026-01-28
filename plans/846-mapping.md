# X12 846 Inventory Inquiry/Advice Mapping

## Overview

Maps X12 846 Inventory Inquiry/Advice to UBL InventoryReport semantic model.

**Status:** Planning
**X12 Transaction:** 846 - Inventory Inquiry/Advice
**UBL Document:** InventoryReport

---

## Header Level Mappings

| X12 Segment | Element | X12 Name | Semantic Path | Notes |
|-------------|---------|----------|---------------|-------|
| **BIA** | 01 | Purpose Code | `document_status_code` | 00=Original, 01=Replace |
| BIA | 02 | Report Type | `inventory_report_type_code` | 00=Actual, 01=Forecast |
| BIA | 03 | Reference ID | `id` | |
| BIA | 04 | Date | `issue_date` | |
| BIA | 05 | Time | `issue_time` | |
| **CUR** | 02 | Currency Code | `document_currency_code` | |
| **REF** | (varies) | Reference | `additional_document_references[+].id` | |

---

## Party Mappings (N1 Loop)

| Qualifier | X12 Name | Semantic Path |
|-----------|----------|---------------|
| SU | Supplier | `retailer_customer_party` | Inventory owner |
| WH | Warehouse | `inventory_reporting_party` | Location |
| BY | Buyer | `buyer_customer_party` | |

---

## Line Item Mappings (LIN Loop)

| Segment | Element | X12 Name | Semantic Path |
|---------|---------|----------|---------------|
| **LIN** | 01 | Assigned ID | `inventory_report_line.id` | |
| LIN | 02 | Product ID Qualifier | `item.*_item_identification.id.scheme_id` | |
| LIN | 03 | Product ID | `inventory_report_line.item.*_item_identification.id.value` | |
| **PID** | 05 | Description | `inventory_report_line.item.description` | |
| **CTP** | 03 | Unit Price | `inventory_report_line.item.price.price_amount.value` | |
| **MEA** | 01 | Measurement Qualifier | (determines field) | |
| MEA | 02 | Measurement Code | `inventory_report_line.item.dimension.attribute_id` | |
| MEA | 03 | Measurement Value | `inventory_report_line.item.dimension.measure.value` | |

---

## Quantity Mappings (QTY Segment)

The QTY segment uses qualifiers to indicate different inventory quantities:

| Qualifier | X12 Name | Semantic Path |
|-----------|----------|---------------|
| 33 | Quantity on Hand | `inventory_report_line.quantity.value` |
| QA | Quantity Available | `inventory_report_line.availability_quantity.value` |
| QC | Quantity Committed | `inventory_report_line.reserved_quantity.value` |
| QO | Quantity on Order | `inventory_report_line.on_order_quantity.value` |
| QP | Quantity Allocated | `inventory_report_line.allocated_quantity.value` |
| QS | Quantity Scheduled | `inventory_report_line.scheduled_quantity.value` |
| QT | Quantity Transferred | `inventory_report_line.transferred_quantity.value` |
| QR | Quantity Received | `inventory_report_line.received_quantity.value` |

---

## Date Mappings (DTM Segment)

| Qualifier | X12 Name | Semantic Path |
|-----------|----------|---------------|
| 007 | Effective Date | `inventory_report_line.inventory_period.start_date` |
| 036 | Expiration Date | `inventory_report_line.item.expiry_date` |
| 097 | Transaction Date | `inventory_report_line.note` | As-of date |
| 514 | Inventory Date | `inventory_report_line.inventory_period.end_date` |

---

## Location Mappings (LDT/SDQ Segments)

### LDT - Lead Time

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| LDT*01 | Lead Time Code | `inventory_report_line.lead_time_code` |
| LDT*02 | Quantity | `inventory_report_line.lead_time_quantity.value` |
| LDT*03 | Unit of Measure | `inventory_report_line.lead_time_quantity.unit_code` |

### SDQ - Destination Quantity

For inventory by location:

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| SDQ*01 | Unit of Measure | `inventory_location.quantity.unit_code` |
| SDQ*02 | Location Qualifier | `inventory_location.id.scheme_id` |
| SDQ*03 | Location ID | `inventory_location.id.value` |
| SDQ*04 | Quantity | `inventory_location.quantity.value` |

---

## Report Type Mapping

| X12 Code | Meaning | Semantic `inventory_report_type_code` |
|----------|---------|--------------------------------------|
| 00 | Actual Inventory | `ACTUAL` |
| 01 | Forecasted Inventory | `FORECAST` |
| 02 | Inventory Inquiry | `INQUIRY` |
| 03 | Inventory Advice | `ADVICE` |

---

## Implementation Tasks

- [ ] Create InventoryReport semantic model
- [ ] Create 846 mapping definition
- [ ] Add QTY qualified mapping (multiple quantities per line)
- [ ] Add SDQ location-quantity handler
- [ ] Add MEA measurement handler
- [ ] Add tests with fixture files

---

## Files to Create/Modify

| File | Changes |
|------|---------|
| `models/inventory_report.py` | Create InventoryReport semantic model |
| `mapping/x12/inventory_846.py` | Create mapping definition |
| `mapping/engine.py` | Add QTY/SDQ handlers if needed |
| `tests/semantic/test_x12_inventory_mapper.py` | Add tests |
