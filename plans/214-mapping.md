# X12 214 Transportation Carrier Shipment Status Message Mapping

## Overview

Maps X12 214 Shipment Status Message to UBL TransportationStatus semantic model.

**Status:** Planning
**X12 Transaction:** 214 - Transportation Carrier Shipment Status Message
**UBL Document:** TransportationStatus

---

## Header Level Mappings

| X12 Segment | Element | X12 Name | Semantic Path | Notes |
|-------------|---------|----------|---------------|-------|
| **B10** | 01 | Shipment ID | `transport_event.shipment.id` | |
| B10 | 02 | Carrier Reference | `transport_service_provider_party.party_identifications[0].id.value` | PRO number |
| B10 | 03 | Standard Carrier Alpha Code | `transport_service_provider_party.party_identifications[0].id.value` | SCAC |
| **L11** | 01 | Reference ID | `document_references[+].id` | |
| L11 | 02 | Reference Qualifier | `document_references[-1].document_type_code` | BM, PO |

---

## Status Event Mappings (AT7 Segment)

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| AT7*01 | Shipment Status Code | `transport_event.transport_event_type_code` |
| AT7*02 | Shipment Status Reason | `transport_event.description` |
| AT7*03 | Shipment Appointment Status | `transport_event.appointment_status_code` |
| AT7*04 | Shipment Status/Reason | `transport_event.description` |
| AT7*05 | Date | `transport_event.occurrence_date` |
| AT7*06 | Time | `transport_event.occurrence_time` |
| AT7*07 | Time Code | `transport_event.occurrence_time_zone` |

---

## Status Code Mapping (AT7*01)

| X12 Code | Meaning | Semantic `transport_event_type_code` |
|----------|---------|-------------------------------------|
| A3 | Shipment Returned | `RETURNED` |
| A7 | Refused | `REFUSED` |
| A9 | Pickup | `PICKUP` |
| AF | Carrier Departed Origin | `DEPARTURE` |
| AG | Estimated Delivery | `ESTIMATED_DELIVERY` |
| AI | Shipment Arrival at Facility | `ARRIVAL` |
| AM | Loaded on Truck | `LOADED` |
| AP | Arrived at Pickup | `ARRIVED_PICKUP` |
| AV | Shipment Available | `AVAILABLE` |
| B6 | Bad Address | `EXCEPTION` |
| C1 | Shipment Delayed | `DELAYED` |
| CD | Carrier Departed | `DEPARTURE` |
| CP | Completed Loading | `LOAD_COMPLETE` |
| CU | Completed Unloading | `UNLOAD_COMPLETE` |
| D1 | Completed Delivery | `DELIVERY` |
| I1 | In Gate | `IN_GATE` |
| J1 | Delivered to Connecting Line | `INTERLINE` |
| OA | Out for Delivery | `OUT_FOR_DELIVERY` |
| OO | Order Received | `ORDER_RECEIVED` |
| P1 | Departed | `DEPARTURE` |
| PR | Paperwork Received | `PAPERWORK_RECEIVED` |
| R1 | Received from Prior Carrier | `RECEIVED_FROM_PRIOR` |
| RL | Rail Departure | `RAIL_DEPARTURE` |
| SD | Short Shipment | `SHORT` |
| X1 | Arrived at Terminal | `TERMINAL_ARRIVAL` |
| X3 | Arrived at Destination | `DESTINATION_ARRIVAL` |
| X4 | Arrived at Delivery Location | `DELIVERY_ARRIVAL` |
| X6 | En Route | `IN_TRANSIT` |
| XB | Shipment Cancelled | `CANCELLED` |

---

## Weight Mappings (AT8 Segment)

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| AT8*01 | Weight Qualifier | (determines field) |
| AT8*02 | Weight Unit | `transport_event.shipment.gross_weight_measure.unit_code` |
| AT8*03 | Weight | `transport_event.shipment.gross_weight_measure.value` |
| AT8*04 | Lading Quantity | `transport_event.shipment.total_goods_item_quantity` |

---

## Location Mappings (MS1/MS2 Segments)

### MS1 - Equipment, Shipment, or Location Identification

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| MS1*01 | City | `transport_event.location.address.city_name` |
| MS1*02 | State | `transport_event.location.address.country_subentity` |
| MS1*03 | Country | `transport_event.location.address.country_code` |
| MS1*04 | Longitude | `transport_event.location.coordinates.longitude` |
| MS1*05 | Latitude | `transport_event.location.coordinates.latitude` |

### MS2 - Equipment or Container Owner and Type

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| MS2*01 | Carrier SCAC | `transport_service_provider_party.party_identifications[0].id.value` |
| MS2*02 | Equipment Number | `transport_event.shipment.transport_handling_unit.id` |
| MS2*03 | Equipment Type | `transport_event.shipment.transport_handling_unit.transport_equipment_type_code` |

---

## Date/Time Mappings (G62 Segment)

| Qualifier | X12 Name | Semantic Path |
|-----------|----------|---------------|
| 35 | Delivered | `transport_event.actual_delivery_date` |
| 36 | Estimated Delivery | `transport_event.estimated_delivery_date` |
| 68 | Requested Pick-up | `transport_event.requested_pickup_date` |
| 69 | Requested Delivery | `transport_event.requested_delivery_date` |
| 86 | Actual Pick-up | `transport_event.actual_pickup_date` |

---

## Exception Mappings (OD/Q7 Segments)

### OD - Origin and Destination (Exception)

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| OD*01 | Origin Location | `transport_event.exception.origin_location` |
| OD*02 | Destination Location | `transport_event.exception.destination_location` |

### Q7 - Lading Exception Code

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| Q7*01 | Exception Code | `transport_event.exception.exception_code` |
| Q7*02 | Pieces | `transport_event.exception.quantity` |
| Q7*03 | Weight | `transport_event.exception.weight` |

---

## Exception Codes (Q7*01)

| X12 Code | Meaning |
|----------|---------|
| D | Damaged |
| O | Over |
| P | Pilfered |
| S | Short |
| W | Wet |

---

## Implementation Tasks

- [ ] Create TransportationStatus semantic model
- [ ] Create 214 mapping definition
- [ ] Add AT7 status code mapping
- [ ] Add MS1/MS2 location handler
- [ ] Add G62 date mapping
- [ ] Add OD/Q7 exception handler
- [ ] Add tests with fixture files

---

## Files to Create/Modify

| File | Changes |
|------|---------|
| `models/transportation_status.py` | Create TransportationStatus semantic model |
| `mapping/x12/shipment_status_214.py` | Create mapping definition |
| `mapping/engine.py` | Add status-specific handlers |
| `tests/semantic/test_x12_shipment_status_mapper.py` | Add tests |
