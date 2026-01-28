# X12 210 Motor Carrier Freight Details and Invoice Mapping

## Overview

Maps X12 210 Motor Carrier Freight Details and Invoice to UBL FreightInvoice semantic model.

**Status:** Planning
**X12 Transaction:** 210 - Motor Carrier Freight Details and Invoice
**UBL Document:** FreightInvoice

---

## Header Level Mappings

| X12 Segment | Element | X12 Name | Semantic Path | Notes |
|-------------|---------|----------|---------------|-------|
| **B3** | 02 | Invoice Number | `id` | |
| B3 | 03 | Shipment ID | `shipment.id` | |
| B3 | 04 | Payment Method | `payment_means.payment_means_code` | PP=Prepaid, CC=Collect |
| B3 | 05 | Net Amount Due | `legal_monetary_total.payable_amount.value` | |
| B3 | 06 | Invoice Date | `issue_date` | |
| B3 | 09 | Weight | `shipment.gross_weight_measure.value` | |
| B3 | 10 | Weight Qualifier | (unit code) | |
| **C3** | 01 | Currency Code | `document_currency_code` | |
| **N9** | (varies) | Reference | `additional_document_references[+].id` | |
| **NTE** | 02 | Note | `note[+]` | |

---

## Party Mappings (N1 Loop)

| Qualifier | X12 Name | Semantic Path |
|-----------|----------|---------------|
| SH | Shipper | `accounting_supplier_party` | Who pays |
| CN | Consignee | `delivery_customer_party` | Receiver |
| BT | Bill To | `accounting_customer_party` | Invoice recipient |
| CA | Carrier | `carrier_party` | |

---

## Equipment Mappings (N7 Segment)

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| N7*01 | Equipment Initial | `shipment.transport_handling_unit.id` | Trailer prefix |
| N7*02 | Equipment Number | `shipment.transport_handling_unit.id` | Trailer number |
| N7*05 | Equipment Type | `shipment.transport_handling_unit.transport_equipment_type_code` |
| N7*09 | Seal Numbers | `shipment.transport_handling_unit.seal_id` |

---

## Line Item Mappings (LX Loop)

| Segment | Element | X12 Name | Semantic Path |
|---------|---------|----------|---------------|
| **LX** | 01 | Assigned Number | `invoice_line.id` | Line sequence |
| **L5** | 01 | Lading Line Item Number | `invoice_line.item.id` |
| L5 | 02 | Lading Description | `invoice_line.item.description` |
| L5 | 03 | Commodity Code | `invoice_line.item.commodity_classification.cargo_type_code` |
| L5 | 04 | Commodity Code Qualifier | (scheme_id) | STCC, NMFC |

---

## Weight and Rate Mappings (L0/L1 Segments)

### L0 - Line Item - Quantity and Weight

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| L0*01 | Lading Line Item Number | `invoice_line.id` |
| L0*04 | Weight | `invoice_line.delivery.shipment.gross_weight_measure.value` |
| L0*05 | Weight Qualifier | (unit code) |
| L0*08 | Lading Quantity | `invoice_line.item.quantity.value` |
| L0*09 | Packaging Form Code | `invoice_line.item.transport_handling_unit_type_code` |

### L1 - Rate and Charges

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| L1*01 | Lading Line Item Number | `invoice_line.id` |
| L1*02 | Freight Rate | `invoice_line.price.price_amount.value` |
| L1*03 | Rate/Value Qualifier | `invoice_line.price.price_type_code` |
| L1*04 | Charge | `invoice_line.line_extension_amount.value` |
| L1*08 | Special Charge Code | `invoice_line.allowance_charge.allowance_charge_reason_code` |
| L1*09 | Special Charge Description | `invoice_line.allowance_charge.allowance_charge_reason` |

---

## Special Charge Codes

| X12 Code | Meaning |
|----------|---------|
| 400 | Fuel Surcharge |
| COL | Collect on Delivery |
| DET | Detention |
| HAZ | Hazardous Materials |
| INS | Insurance |
| LHD | Linehaul |
| LFT | Liftgate |
| RES | Residential Delivery |
| STO | Storage |

---

## Summary Mappings (L3 Segment)

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| L3*01 | Weight | `shipment.gross_weight_measure.value` |
| L3*02 | Weight Qualifier | (unit code) |
| L3*03 | Freight Rate | `anticipated_monetary_total.charge_total_amount.value` |
| L3*05 | Total Charges | `legal_monetary_total.tax_exclusive_amount.value` |
| L3*11 | Quantity | `total_goods_item_quantity` |
| L3*12 | Quantity Qualifier | (unit code) |

---

## Implementation Tasks

- [ ] Create FreightInvoice semantic model
- [ ] Create 210 mapping definition
- [ ] Add B3 header mapping
- [ ] Add LX/L0/L1 line item handlers
- [ ] Add L3 summary handler
- [ ] Add special charge code mapping
- [ ] Add tests with fixture files

---

## Files to Create/Modify

| File | Changes |
|------|---------|
| `models/freight_invoice.py` | Create FreightInvoice semantic model |
| `mapping/x12/freight_invoice_210.py` | Create mapping definition |
| `mapping/engine.py` | Add freight-specific handlers |
| `tests/semantic/test_x12_freight_invoice_mapper.py` | Add tests |
