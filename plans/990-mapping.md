# X12 990 Response to a Load Tender Mapping

## Overview

Maps X12 990 Response to a Load Tender to UBL TransportExecutionPlan semantic model.

**Status:** Planning
**X12 Transaction:** 990 - Response to a Load Tender
**UBL Document:** TransportExecutionPlan

---

## Header Level Mappings

| X12 Segment | Element | X12 Name | Semantic Path | Notes |
|-------------|---------|----------|---------------|-------|
| **B1** | 01 | Standard Carrier Alpha Code | `transport_service_provider_party.party_identifications[0].id.value` | SCAC |
| B1 | 02 | Shipment ID | `transport_execution_plan_request_document_reference.id` | Ref to 204 |
| B1 | 03 | Date | `issue_date` | |
| B1 | 04 | Response Code | `transport_execution_status_code` | A=Accept, D=Decline |
| **N9** | 01 | Reference Qualifier | `document_references[-1].document_type_code` | |
| N9 | 02 | Reference ID | `document_references[+].id` | |
| **G62** | 01 | Date Qualifier | (determines field) | |
| G62 | 02 | Date | Various date fields | |
| **K1** | 01 | Remarks | `note[+]` | Decline reason if applicable |

---

## Response Code Mapping (B1*04)

| X12 Code | Meaning | Semantic `transport_execution_status_code` |
|----------|---------|-------------------------------------------|
| A | Accepted | `CONFIRMED` |
| D | Declined | `REJECTED` |
| C | Conditionally Accepted | `PENDING` |
| P | Pending | `PENDING` |
| R | Rejected | `REJECTED` |
| S | Substitute Offered | `COUNTER_PROPOSAL` |

---

## Party Mappings (N1 Loop)

| Qualifier | X12 Name | Semantic Path |
|-----------|----------|---------------|
| CA | Carrier | `transport_service_provider_party` |
| SH | Shipper | `transport_user_party` |

---

## Reference Mappings (N9 Qualifiers)

| Qualifier | X12 Name | Semantic Path |
|-----------|----------|---------------|
| BM | Bill of Lading | `additional_document_references[+].id` |
| CN | Carrier's Reference | `carrier_assigned_id` |
| PO | Purchase Order | `additional_document_references[+].id` |
| SI | Shipper's Reference | `shipper_assigned_id` |

---

## Date Mappings (G62 Qualifiers)

| Qualifier | X12 Name | Semantic Path |
|-----------|----------|---------------|
| 10 | Pickup Date | `consignment.planned_pickup_transport_event.occurrence_date` |
| 11 | Delivery Date | `consignment.planned_delivery_transport_event.occurrence_date` |
| 69 | Promised Delivery | `consignment.planned_delivery_transport_event.occurrence_date` |

---

## Counter-Proposal Mappings (for Conditional Accept)

When B1*04 = C (Conditionally Accepted), the 990 may include alternate terms:

### MS3 - Interline Information

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| MS3*01 | Transportation Method | `proposed_transport_means.transport_means_type_code` |
| MS3*02 | Carrier SCAC | `proposed_carrier.party_identifications[0].id.value` |

### R3 - Route Information

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| R3*01 | Standard Carrier Alpha Code | `proposed_route.carrier.id` |
| R3*02 | Routing | `proposed_route.description` |
| R3*05 | Service Level | `proposed_route.service_level_code` |

---

## Remarks/Notes (K1 Segment)

The K1 segment is used for decline reasons or special conditions:

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| K1*01 | Free-Form Message | `note[+]` |

Common decline reasons in K1:
- Equipment not available
- Capacity constraints
- Rate not acceptable
- Delivery window not achievable
- Hazmat restrictions
- Geographic limitations

---

## Implementation Complexity

The 990 is relatively simple compared to other transportation documents:

1. **Single Response** - One 990 per 204 load tender
2. **Status Focus** - Primary purpose is accept/decline/counter
3. **Minimal Detail** - Counter-proposals are optional

---

## Typical Flow

```
Shipper                    Carrier
   |                          |
   |------- 204 (Tender) ---->|
   |                          |
   |<------ 990 (Accept) -----|
   |                          |
   |------- 204 (Confirm) --->|  (if changes needed)
```

---

## Implementation Tasks

- [ ] Create TransportExecutionPlan semantic model
- [ ] Create 990 mapping definition
- [ ] Add B1 header mapping with response codes
- [ ] Add K1 remarks handler
- [ ] Add optional counter-proposal mapping (MS3, R3)
- [ ] Add tests with fixture files

---

## Files to Create/Modify

| File | Changes |
|------|---------|
| `models/transport_execution_plan.py` | Create semantic model |
| `mapping/x12/load_tender_response_990.py` | Create mapping definition |
| `tests/semantic/test_x12_load_tender_response_mapper.py` | Add tests |
