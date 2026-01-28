# X12 940 Warehouse Shipping Order Mapping

## Overview

Maps X12 940 Warehouse Shipping Order to UBL ForwardingInstructions semantic model.

**Status:** Planning
**X12 Transaction:** 940 - Warehouse Shipping Order
**UBL Document:** ForwardingInstructions

---

## Header Level Mappings

| X12 Segment | Element | X12 Name | Semantic Path | Notes |
|-------------|---------|----------|---------------|-------|
| **W05** | 01 | Order Status Type | `document_status_code` | N=New, U=Update, X=Cancel |
| W05 | 02 | Depositor Order Number | `id` | |
| W05 | 03 | Deposit Date | `issue_date` | |
| W05 | 04 | Shipment ID | `shipment_id` | |
| W05 | 05 | Time Qualifier | (determines field) | |
| W05 | 06 | Time | `issue_time` | |
| **N9** | 01 | Reference Qualifier | `document_references[-1].document_type_code` | |
| N9 | 02 | Reference ID | `document_references[+].id` | |
| **G62** | 01 | Date Qualifier | (determines field) | |
| G62 | 02 | Date | Various date fields | |
| **NTE** | 02 | Note | `note[+]` | |

---

## Order Status Codes (W05*01)

| X12 Code | Meaning | Semantic `document_status_code` |
|----------|---------|--------------------------------|
| N | New Order | `NEW` |
| U | Update | `UPDATED` |
| X | Cancel | `CANCELLED` |
| R | Replace | `REPLACED` |

---

## Party Mappings (N1 Loop)

| Qualifier | X12 Name | Semantic Path |
|-----------|----------|---------------|
| WH | Warehouse | `freight_forwarder_party` |
| SF | Ship From | `consignment.consignor_party` |
| ST | Ship To | `consignment.consignee_party` |
| BY | Buyer | `consignment.buyer_party` |
| SE | Seller | `consignment.seller_party` |
| DE | Depositor | `document_issuer_party` |

---

## Carrier/Shipping Mappings (W66 Segment)

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| W66*01 | Shipment Method of Payment | `consignment.freight_payment_code` | PP=Prepaid, CC=Collect |
| W66*02 | Transportation Method | `consignment.transport_means.transport_means_type_code` |
| W66*03 | Pallet Exchange Code | `consignment.pallet_exchange_code` |
| W66*04 | Unit Load Option Code | `consignment.unit_load_option_code` |
| W66*05 | Routing | `consignment.routing_instructions` |
| W66*06 | FOB Point Code | `consignment.fob_point_code` |
| W66*07 | FOB Point | `consignment.fob_point_description` |
| W66*08 | COD Method of Payment | `consignment.cod_payment_method` |
| W66*09 | COD Amount | `consignment.cod_amount.value` |
| W66*10 | Standard Carrier Alpha Code | `consignment.carrier_party.party_identifications[0].id.value` |

---

## Date Mappings (G62 Qualifiers)

| Qualifier | X12 Name | Semantic Path |
|-----------|----------|---------------|
| 10 | Requested Ship Date | `consignment.requested_pickup_transport_event.occurrence_date` |
| 11 | Requested Delivery Date | `consignment.requested_delivery_transport_event.occurrence_date` |
| 53 | Ship Not Before | `consignment.requested_pickup_transport_event.earliest_date` |
| 54 | Ship Not After | `consignment.requested_pickup_transport_event.latest_date` |

---

## Line Item Mappings (LX/W01 Loop)

### LX - Assigned Number

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| LX*01 | Line Number | `consignment.goods_item[+].id` |

### W01 - Item Detail for Stock Transfer

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| W01*01 | Quantity | `consignment.goods_item[-1].quantity.value` |
| W01*02 | Unit of Measure | `consignment.goods_item[-1].quantity.unit_code` |
| W01*03 | UPC Code | `consignment.goods_item[-1].item.standard_item_identification.id.value` |
| W01*04 | Product ID Qualifier | `consignment.goods_item[-1].item.*_item_identification.id.scheme_id` |
| W01*05 | Product ID | `consignment.goods_item[-1].item.*_item_identification.id.value` |

### N9 - Line-Level References

| Qualifier | X12 Name | Semantic Path |
|-----------|----------|---------------|
| LI | Line Item Reference | `goods_item.document_references[+].id` |
| LO | Lot Number | `goods_item.item.lot_identification.lot_number_id` |
| SE | Serial Number | `goods_item.item.item_instance.serial_id` |

### G69 - Line Free-Form Description

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| G69*01 | Description | `goods_item.item.description` |

---

## Pack Size Mappings (W20 Segment)

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| W20*01 | Pack Size | `goods_item.item.contained_item.quantity.value` |
| W20*02 | Pack Size Unit | `goods_item.item.contained_item.quantity.unit_code` |
| W20*03 | Weight | `goods_item.gross_weight_measure.value` |
| W20*04 | Weight Qualifier | `goods_item.gross_weight_measure.unit_code` |
| W20*05 | Unit Weight | `goods_item.item.weight.value` |
| W20*06 | Volume | `goods_item.gross_volume_measure.value` |
| W20*07 | Volume Qualifier | `goods_item.gross_volume_measure.unit_code` |

---

## Implementation Tasks

- [ ] Create ForwardingInstructions semantic model
- [ ] Create 940 mapping definition
- [ ] Add W05 header mapping
- [ ] Add W66 carrier/shipping handler
- [ ] Add LX/W01 line item loop handler
- [ ] Add W20 pack size handler
- [ ] Add tests with fixture files

---

## Files to Create/Modify

| File | Changes |
|------|---------|
| `models/forwarding_instructions.py` | Create ForwardingInstructions semantic model |
| `mapping/x12/warehouse_shipping_940.py` | Create mapping definition |
| `mapping/engine.py` | Add warehouse-specific handlers |
| `tests/semantic/test_x12_warehouse_shipping_mapper.py` | Add tests |
