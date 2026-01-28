# X12 204 Motor Carrier Load Tender Mapping

## Overview

Maps X12 204 Motor Carrier Load Tender to UBL TransportExecutionPlanRequest semantic model.

**Status:** Planning
**X12 Transaction:** 204 - Motor Carrier Load Tender
**UBL Document:** TransportExecutionPlanRequest

---

## Header Level Mappings

| X12 Segment | Element | X12 Name | Semantic Path | Notes |
|-------------|---------|----------|---------------|-------|
| **B2** | 02 | Standard Carrier Alpha Code | `transport_service_provider_party.party_identifications[0].id.value` | SCAC |
| B2 | 04 | Shipment ID | `id` | |
| B2 | 06 | Payment Method | `main_transportation_service.payment_terms` | PP/CC |
| **B2A** | 01 | Purpose Code | `transport_execution_plan_request_type_code` | 00=Original, 04=Change |
| **L11** | 01 | Reference ID | `additional_document_references[+].id` | |
| L11 | 02 | Reference Qualifier | `additional_document_references[-1].document_type_code` | BM=BOL, PO=PO |
| **MS3** | 01 | Transportation Method | `main_transportation_service.transport_means.transport_means_type_code` | |
| **NTE** | 02 | Note | `note[+]` | Free-form notes |

---

## Date/Time Mappings (G62 Segment)

| Qualifier | X12 Name | Semantic Path |
|-----------|----------|---------------|
| 10 | Pickup Date | `consignment.requested_pickup_transport_event.occurrence_date` |
| 11 | Delivery Date | `consignment.requested_delivery_transport_event.occurrence_date` |
| 53 | Ship Not Before | `consignment.requested_pickup_transport_event.earliest_date` |
| 54 | Ship Not After | `consignment.requested_pickup_transport_event.latest_date` |
| 64 | Delivery Not Before | `consignment.requested_delivery_transport_event.earliest_date` |
| 65 | Delivery Not After | `consignment.requested_delivery_transport_event.latest_date` |

---

## Party Mappings (N1 Loop)

| Qualifier | X12 Name | Semantic Path |
|-----------|----------|---------------|
| SH | Shipper | `consignment.consignor_party` |
| CN | Consignee | `consignment.consignee_party` |
| SF | Ship From | `consignment.consignor_party` |
| ST | Ship To | `consignment.consignee_party` |
| BT | Bill To | `bill_to_party` |
| CA | Carrier | `transport_service_provider_party` |

---

## Stop-Off Mappings (S5 Loop)

The S5 segment defines stops in the shipment route:

| Segment | Element | X12 Name | Semantic Path |
|---------|---------|----------|---------------|
| **S5** | 01 | Stop Sequence Number | `consignment.consolidated_shipment[+].sequence_id` |
| S5 | 02 | Stop Reason Code | `consignment.consolidated_shipment[-1].handling_code` | CL=Complete Load, PL=Partial |
| S5 | 03 | Weight | `consignment.consolidated_shipment[-1].gross_weight_measure.value` |
| S5 | 04 | Weight Qualifier | (unit code) |
| S5 | 05 | Number of Units | `consignment.consolidated_shipment[-1].total_goods_item_quantity` |
| S5 | 06 | Unit of Measure | (unit code) |

### Stop Reason Codes

| X12 Code | Meaning |
|----------|---------|
| CL | Complete Load |
| CU | Complete Unload |
| PL | Partial Load |
| PU | Partial Unload |
| SL | Stop Load |
| SU | Stop Unload |

---

## Lading Detail Mappings (L5/AT8 Segments)

### L5 - Description, Marks and Numbers

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| L5*01 | Lading Line Item Number | `consignment.transport_handling_unit[+].id` |
| L5*02 | Lading Description | `consignment.transport_handling_unit[-1].shipping_marks` |
| L5*03 | Commodity Code | `consignment.goods_item.commodity_classification.cargo_type_code` |
| L5*04 | Commodity Code Qualifier | (scheme_id) | STCC, NMFC |

### AT8 - Shipment Weight, Packaging and Quantity

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| AT8*01 | Weight Qualifier | (determines field) | G=Gross, N=Net |
| AT8*02 | Weight Unit | `goods_item.gross_weight_measure.unit_code` | L=Pounds, K=Kilos |
| AT8*03 | Weight | `goods_item.gross_weight_measure.value` |
| AT8*04 | Lading Quantity | `goods_item.quantity.value` |
| AT8*05 | Lading Quantity Unit | `goods_item.quantity.unit_code` |
| AT8*06 | Volume Qualifier | (determines field) |
| AT8*07 | Volume | `goods_item.gross_volume_measure.value` |
| AT8*08 | Volume Unit | `goods_item.gross_volume_measure.unit_code` |

---

## Equipment Mappings (N7 Segment)

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| N7*01 | Equipment Initial | `transport_handling_unit.transport_equipment.id` | Trailer prefix |
| N7*02 | Equipment Number | `transport_handling_unit.transport_equipment.id` | Trailer number |
| N7*05 | Equipment Type | `transport_handling_unit.transport_equipment.transport_equipment_type_code` |
| N7*09 | Height | `transport_handling_unit.transport_equipment.measurement_dimension.value` |
| N7*10 | Width | `transport_handling_unit.transport_equipment.measurement_dimension.value` |
| N7*11 | Length | `transport_handling_unit.transport_equipment.measurement_dimension.value` |

---

## Implementation Tasks

- [ ] Create TransportExecutionPlanRequest semantic model
- [ ] Create 204 mapping definition
- [ ] Add S5 stop-off loop handler
- [ ] Add L5/AT8 lading detail handler
- [ ] Add N7 equipment handler
- [ ] Add G62 date mapping
- [ ] Add tests with fixture files

---

## Files to Create/Modify

| File | Changes |
|------|---------|
| `models/transport_execution_plan.py` | Create transport semantic models |
| `mapping/x12/load_tender_204.py` | Create mapping definition |
| `mapping/engine.py` | Add stop-off and equipment handlers |
| `tests/semantic/test_x12_load_tender_mapper.py` | Add tests |
