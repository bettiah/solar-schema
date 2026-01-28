# X12 855 Purchase Order Acknowledgement Mapping

## Overview

Maps X12 855 Purchase Order Acknowledgement to UBL OrderResponse semantic model.

**Status:** Planning
**X12 Transaction:** 855 - Purchase Order Acknowledgement
**UBL Document:** OrderResponse

---

## Header Level Mappings

| X12 Segment | Element | X12 Name | Semantic Path | Notes |
|-------------|---------|----------|---------------|-------|
| **BAK** | 01 | Purpose Code | `document_status_code` | |
| BAK | 02 | Acknowledgment Type | `order_response_code` | AC, AD, AE, AK, RD |
| BAK | 03 | PO Number | `order_reference.id` | |
| BAK | 04 | Date | `issue_date` | |
| BAK | 05 | Request Reference Number | `sales_order_id` | Seller's order ID |
| **CUR** | 02 | Currency Code | `document_currency_code` | |
| **REF** | (varies) | Reference | `additional_document_references[+].id` | |
| **DTM** | (varies) | Dates | Various date fields | |

---

## Acknowledgment Code Mapping

| X12 Code | Meaning | Semantic `order_response_code` |
|----------|---------|--------------------------------|
| AC | Acknowledge with Changes | `ACCEPTED_WITH_CHANGE` |
| AD | Acknowledge with Detail | `ACCEPTED` |
| AE | Acknowledge with Exception | `ACCEPTED_WITH_EXCEPTION` |
| AK | Acknowledge (no changes) | `ACCEPTED` |
| RD | Reject with Detail | `REJECTED` |

---

## Party Mappings (N1 Loop)

| Qualifier | X12 Name | Semantic Path |
|-----------|----------|---------------|
| BY | Buyer | `buyer_customer_party` |
| SE | Seller | `seller_supplier_party` |
| ST | Ship To | `delivery[0].delivery_party` |

---

## Line Item Mappings (PO1 Loop)

| Segment | Element | X12 Name | Semantic Path |
|---------|---------|----------|---------------|
| **PO1** | 01 | Line Number | `order_line.id` |
| PO1 | 02 | Quantity Ordered | `order_line.line_item.quantity.value` |
| PO1 | 03 | Unit of Measure | `order_line.line_item.quantity.unit_code` |
| PO1 | 04 | Unit Price | `order_line.line_item.price.price_amount.value` |
| PO1 | 06-25 | Product IDs | `order_line.line_item.item.*_item_identification` |
| **PID** | 05 | Description | `order_line.line_item.item.description` |

---

## Line Status Mappings (ACK Segment)

The ACK segment provides line-level acknowledgment status:

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| ACK*01 | Line Status | `order_line.line_status_code` |
| ACK*02 | Quantity | `order_line.line_item.quantity.value` | Confirmed qty |
| ACK*03 | Unit of Measure | `order_line.line_item.quantity.unit_code` |
| ACK*04 | Date Qualifier | (determines date field) | 068=Ship, 017=Deliver |
| ACK*05 | Date | `order_line.line_item.delivery.requested_delivery_period.start_date` |

### Line Status Code Mapping

| X12 Code | Meaning | Semantic `line_status_code` |
|----------|---------|---------------------------|
| IA | Item Accepted | `ACCEPTED` |
| IB | Item Backordered | `BACKORDERED` |
| IC | Item Accepted - Changes Made | `ACCEPTED_WITH_CHANGE` |
| ID | Item Deleted | `REJECTED` |
| IF | Item on Hold | `ON_HOLD` |
| IQ | Item Accepted - Quantity Changed | `QUANTITY_CHANGED` |
| IR | Item Rejected | `REJECTED` |
| IS | Item Accepted - Substitution Made | `SUBSTITUTED` |
| IW | Item Accepted - Schedule Changed | `SCHEDULE_CHANGED` |

---

## Multiple ACK Segments Per Line

A single PO1 line can have multiple ACK segments for partial shipments:

```
PO1*1*100*EA*10.00**VP*ABC123~
ACK*IA*50*EA*068*20240201~
ACK*IB*50*EA*068*20240301~
```

This indicates 50 units accepted for Feb 1, 50 backordered for Mar 1.

**Semantic Mapping:**
```
order_line:
  id: "1"
  line_status_code: "PARTIAL"
  line_item:
    quantity: 100
  sub_line_items:
    - quantity: 50, status: "ACCEPTED", delivery_date: "2024-02-01"
    - quantity: 50, status: "BACKORDERED", delivery_date: "2024-03-01"
```

---

## Implementation Complexity

1. **Header vs Line Acknowledgment** - BAK*02 is header-level, ACK*01 is line-level
2. **Multiple ACK per Line** - Need to handle partial quantities
3. **Schedule Changes** - ACK can modify delivery dates

---

## Implementation Tasks

- [ ] Create OrderResponse semantic model
- [ ] Create 855 mapping definition
- [ ] Add BAK header mapping
- [ ] Add ACK line status handler (handles multiple ACK per line)
- [ ] Add line status code mapping
- [ ] Add tests with fixture files

---

## Files to Create/Modify

| File | Changes |
|------|---------|
| `models/order_response.py` | Create OrderResponse semantic model |
| `mapping/x12/po_ack_855.py` | Create mapping definition |
| `mapping/engine.py` | Add ACK segment handler |
| `tests/semantic/test_x12_po_ack_mapper.py` | Add tests |
