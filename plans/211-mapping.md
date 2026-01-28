# X12 211 Motor Carrier Bill of Lading Mapping

## Overview

Maps X12 211 Motor Carrier Bill of Lading to UBL BillOfLading/Waybill semantic model.

**Status:** Planning
**X12 Transaction:** 211 - Motor Carrier Bill of Lading
**UBL Document:** BillOfLading / Waybill

---

## Header Level Mappings

| X12 Segment | Element | X12 Name | Semantic Path | Notes |
|-------------|---------|----------|---------------|-------|
| **B2** | 02 | Standard Carrier Alpha Code | `carrier_party.party_identifications[0].id.value` | SCAC |
| B2 | 04 | Shipment ID | `id` | BOL number |
| B2 | 06 | Payment Method | `freight_payment_code` | PP=Prepaid, CC=Collect |
| **B2A** | 01 | Purpose Code | `bill_of_lading_type_code` | 00=Original, 01=Duplicate |
| **L11** | 01 | Reference ID | `document_references[+].id` | |
| L11 | 02 | Reference Qualifier | `document_references[-1].document_type_code` | BM, PO, SI |
| **G62** | 01 | Date Qualifier | (determines field) | |
| G62 | 02 | Date | `shipment.shipment_stage.transport_event.occurrence_date` | |
| **MS1** | 01 | City | `shipment.origin_address.city_name` | |
| MS1 | 02 | State | `shipment.origin_address.country_subentity` | |

---

## Party Mappings (N1 Loop)

| Qualifier | X12 Name | Semantic Path |
|-----------|----------|---------------|
| SH | Shipper | `consignor_party` |
| CN | Consignee | `consignee_party` |
| SF | Ship From | `shipment.consignment.consignor_party` |
| ST | Ship To | `shipment.delivery.delivery_address` |
| BT | Bill To | `bill_to_party` |
| 3P | Third Party | `freight_forwarder_party` |

---

## Weight and Quantity Mappings (AT8 Segment)

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| AT8*01 | Weight Qualifier | (determines field) | G=Gross, N=Net |
| AT8*02 | Weight Unit | `shipment.goods_item.gross_weight_measure.unit_code` |
| AT8*03 | Weight | `shipment.goods_item.gross_weight_measure.value` |
| AT8*04 | Lading Quantity | `shipment.goods_item.quantity.value` |
| AT8*05 | Packaging Form Code | `shipment.goods_item.transport_handling_unit_type_code` |

---

## Order/Item Mappings (OID/L5/L0 Segments)

### OID - Order Identification

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| OID*01 | Reference ID | `shipment.goods_item.item.buyers_item_identification.id` |
| OID*02 | PO Number | `shipment.goods_item.order_reference.id` |
| OID*05 | Quantity Ordered | `shipment.goods_item.quantity.value` |
| OID*06 | Unit of Measure | `shipment.goods_item.quantity.unit_code` |

### L5 - Description, Marks and Numbers

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| L5*01 | Lading Line Item Number | `shipment.goods_item.id` |
| L5*02 | Lading Description | `shipment.goods_item.item.description` |
| L5*03 | Commodity Code | `shipment.goods_item.item.commodity_classification.commodity_code` | NMFC |
| L5*04 | Commodity Code Qualifier | (scheme_id) |

### L0 - Line Item - Quantity and Weight

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| L0*01 | Lading Line Item Number | `shipment.goods_item.id` |
| L0*04 | Weight | `shipment.goods_item.gross_weight_measure.value` |
| L0*05 | Weight Qualifier | (unit code) |
| L0*08 | Lading Quantity | `shipment.goods_item.quantity.value` |
| L0*09 | Packaging Form Code | `shipment.goods_item.transport_handling_unit_type_code` |

### L7 - Tariff Reference

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| L7*01 | Lading Line Item Number | `shipment.goods_item.id` |
| L7*02 | Tariff Agency Code | `shipment.goods_item.freight_allowance_charge.id` |
| L7*08 | Freight Class | `shipment.goods_item.item.commodity_classification.nature_code` |

---

## Freight Class Codes (L7*08)

| Code | Class | Description |
|------|-------|-------------|
| 50 | 50 | Clean Freight (over 50 lbs/ft³) |
| 55 | 55 | Bricks, cement |
| 60 | 60 | Car parts |
| 65 | 65 | Car parts, bottled items |
| 70 | 70 | Newspapers, machinery |
| 77.5 | 77.5 | Tires |
| 85 | 85 | Crated machinery |
| 92.5 | 92.5 | Computers |
| 100 | 100 | Boat covers |
| 110 | 110 | Cabinets |
| 125 | 125 | Small appliances |
| 150 | 150 | Auto sheet metal |
| 175 | 175 | Clothing |
| 200 | 200 | Auto sheet metal parts |
| 250 | 250 | Bamboo furniture |
| 300 | 300 | Wood cabinets |
| 400 | 400 | Deer antlers |
| 500 | 500 | Bags of gold dust |

---

## Implementation Tasks

- [ ] Create BillOfLading semantic model
- [ ] Create 211 mapping definition
- [ ] Add OID order reference handler
- [ ] Add L5/L0/L7 goods item handler
- [ ] Add freight class mapping
- [ ] Add tests with fixture files

---

## Files to Create/Modify

| File | Changes |
|------|---------|
| `models/bill_of_lading.py` | Create BillOfLading semantic model |
| `mapping/x12/bol_211.py` | Create mapping definition |
| `mapping/engine.py` | Add BOL-specific handlers |
| `tests/semantic/test_x12_bol_mapper.py` | Add tests |
