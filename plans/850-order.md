# X12 850 Purchase Order → Semantic Order Mapping

## Overview

This document defines the complete mapping between X12 850 Purchase Order and the semantic Order model. It serves as both specification and gap analysis.

## Current Implementation Status

**File:** `src/edi_schema/semantic/mapping/x12/order_850.py`
**Test:** `tests/semantic/test_x12_order_mapper.py`
**Status:** ✅ **IMPLEMENTED** (2024-01-27)

---

## Gap Analysis: Current vs Complete Mapping

### Header-Level Segments

| Segment | Element | X12 Name | Current Status | Semantic Path | Notes |
|---------|---------|----------|----------------|---------------|-------|
| **BEG** | 01 | Purpose Code | ✅ Mapped | `document_purpose_code` | |
| BEG | 02 | Order Type | ✅ Mapped | `order_type_code` | |
| BEG | 03 | PO Number | ✅ Mapped | `id` | Required |
| BEG | 04 | Release Number | ✅ Mapped | `sales_order_id` | Blanket PO release |
| BEG | 05 | Date | ✅ Mapped | `issue_date` | Required |
| BEG | 06 | Contract Number | ✅ Mapped | `contract_document_reference.id` | |
| **CUR** | 02 | Currency Code | ✅ Mapped | `document_currency_code` | Default: USD |
| CUR | 03 | Exchange Rate | ✅ Mapped | `pricing_exchange_rate` | |
| **REF** | (CT) | Contract | ✅ Mapped | `contract_document_reference.id` | |
| REF | (PO) | Prior PO | ✅ Mapped | `order_document_references[0].id` | |
| REF | (QQ) | Quotation | ✅ Mapped | `quotation_document_reference.id` | |
| REF | (VN) | Vendor # | ✅ Mapped | `additional_document_references[0].id` | |
| REF | (BM) | Bill of Lading | ✅ Mapped | `additional_document_references[+].id` | |
| REF | (IT) | Internal Order | ✅ Mapped | `originator_document_reference.id` | |
| REF | (DP) | Department | ✅ Mapped | `additional_document_references[+].id` | |
| REF | (IA) | Internal Vendor | ✅ Mapped | `additional_document_references[+].id` | |
| **PER** | 01 | Contact Function | ✅ Mapped | - | Handled by engine |
| PER | 02 | Contact Name | ✅ Mapped | `party.contact.name` | |
| PER | 03/04 | Phone | ✅ Mapped | `party.contact.telephone` | Paired elements |
| PER | 05/06 | Fax | ✅ Mapped | `party.contact.telefax` | Paired elements |
| PER | 07/08 | Email | ✅ Mapped | `party.contact.electronic_mail` | Paired elements |
| **FOB** | 01 | Ship Method Payment | ✅ Mapped | `delivery_terms` | PP/CC/etc |
| FOB | 05 | Transport Terms | ✅ Mapped | `delivery[0].delivery_terms.special_terms` | Incoterms |
| **ITD** | 05 | Discount % | ✅ Mapped | `payment_terms[0].settlement_discount_percent` | |
| ITD | 06 | Discount Due Date | ✅ Mapped | `payment_terms[0].settlement_period.end_date` | |
| ITD | 07 | Net Days | ✅ Mapped | `payment_terms[0].settlement_period_days` | |
| ITD | 12 | Description | ✅ Mapped | `payment_terms[0].note` | |
| **DTM** | (002) | Delivery Date | ✅ Mapped | `delivery[0].requested_delivery_period.start_date` | |
| DTM | (010) | Ship Date | ✅ Mapped | `delivery[0].despatch.requested_despatch_date` | |
| DTM | (037) | Ship Not Before | ✅ Mapped | `delivery[0].despatch.earliest_despatch_date` | |
| DTM | (038) | Ship No Later | ✅ Mapped | `delivery[0].latest_delivery_date` | |
| DTM | (063) | Do Not Deliver After | ✅ Mapped | `delivery[0].latest_delivery_date` | |
| DTM | (064) | Valid From | ✅ Mapped | `validity_period.start_date` | |
| DTM | (065) | Valid To | ✅ Mapped | `validity_period.end_date` | |
| **TD5** | 02 | ID Qualifier | ✅ Mapped | `delivery[0].shipment.carrier_party.party_identifications[0].id.scheme_id` | |
| TD5 | 03 | Carrier ID (SCAC) | ✅ Mapped | `delivery[0].shipment.carrier_party.party_identifications[0].id.value` | |
| TD5 | 04 | Transport Method | ✅ Mapped | `delivery[0].shipment.shipment_stages[0].transport_mode_code` | |
| TD5 | 05 | Routing | ✅ Mapped | `delivery[0].shipment.shipment_stages[0].transit_direction_code` | |
| TD5 | 12 | Service Level | ✅ Mapped | `delivery[0].shipment.shipping_priority_level_code` | |
| **TD1** | 01 | Packaging Code | ✅ Mapped | `delivery[0].shipment.transport_handling_units[0].transport_handling_unit_type_code` | |
| TD1 | 02 | Lading Quantity | ✅ Mapped | `delivery[0].shipment.total_transport_handling_unit_quantity` | |
| **SAC** | 01 | Allow/Charge Ind | ✅ Mapped | `allowance_charges[].charge_indicator` | A=false, C=true |
| SAC | 02 | Code | ✅ Mapped | `allowance_charges[].allowance_charge_reason_code` | |
| SAC | 05 | Amount | ✅ Mapped | `allowance_charges[].amount.value` | |
| SAC | 12 | Description | ✅ Mapped | `allowance_charges[].allowance_charge_reason` | |
| SAC | 15 | Percent | ✅ Mapped | `allowance_charges[].multiplier_factor_numeric` | |
| **TXI** | 01 | Tax Type | ✅ Mapped | `tax_total[].tax_subtotal[].tax_category.id` | |
| TXI | 02 | Amount | ✅ Mapped | `tax_total[].tax_amount.value` | |
| TXI | 03 | Percent | ✅ Mapped | `tax_total[].tax_subtotal[].percent` | |
| **N9** | 01 | Ref Qualifier | ✅ Mapped | - | LI, DO, CR, PD, AH |
| N9 | 02 | Ref ID | ✅ Mapped | `additional_document_references[+].id` | |
| **MSG** | 01 | Free Form | ✅ Mapped | `note[0]` | |
| **CTT** | 01 | Line Count | ✅ Mapped | `line_count` | |
| **AMT** | (TT) | Total Amount | ✅ Mapped | `anticipated_monetary_total.payable_amount.value` | |

### Party Loop (N1)

| Qualifier | Current Status | Semantic Path |
|-----------|----------------|---------------|
| BY | ✅ Mapped | `buyer_customer_party` |
| SE | ✅ Mapped | `seller_supplier_party` |
| ST | ✅ Mapped | `delivery[+].delivery_party` |
| BT | ✅ Mapped | `accounting_customer_party` |
| SF | ✅ Mapped | `delivery[0].despatch.despatch_party` |
| OB | ✅ Mapped | `originator_customer_party` |
| CA | ✅ Mapped | `freight_forwarder_party` |
| RI | ✅ Mapped | `payee_party` |

**N1 Loop Field Mappings:**

| Segment | Element | Current Status | Semantic Path (relative) |
|---------|---------|----------------|--------------------------|
| N1 | 02 | ✅ Mapped | `party.party_names[0].name` |
| N1 | 03 | ✅ Mapped | `party.party_identifications[0].scheme_id` |
| N1 | 04 | ✅ Mapped | `party.party_identifications[0].id` |
| N2 | 01 | ✅ Mapped | `party.party_names[1].name` |
| N3 | 01 | ✅ Mapped | `party.postal_address.street_name` |
| N3 | 02 | ✅ Mapped | `party.postal_address.additional_street_name` |
| N4 | 01 | ✅ Mapped | `party.postal_address.city_name` |
| N4 | 02 | ✅ Mapped | `party.postal_address.country_subentity` |
| N4 | 03 | ✅ Mapped | `party.postal_address.postal_zone` |
| N4 | 04 | ✅ Mapped | `party.postal_address.country_code` |
| PER | 02 | ✅ Mapped | `party.contact.name` |
| PER | 03/04 | ✅ Mapped | `party.contact.telephone` (when 03=TE) |
| PER | 05/06 | ✅ Mapped | `party.contact.telefax` (when 05=FX) |
| PER | 07/08 | ✅ Mapped | `party.contact.electronic_mail` (when 07=EM) |

### Line Item Loop (PO1)

| Segment | Element | Current Status | Semantic Path (relative to line) |
|---------|---------|----------------|----------------------------------|
| PO1 | 01 | ✅ Mapped | `id` |
| PO1 | 02 | ✅ Mapped | `quantity.value` |
| PO1 | 03 | ✅ Mapped | `quantity.unit_code` |
| PO1 | 04 | ✅ Mapped | `price.price_amount.value` |
| PO1 | 05 | ✅ Mapped | `price.base_quantity_unit_code` |
| PO1 | 06-25 | ✅ Mapped | Product ID pairs (VP, UP, EN, BP, etc.) |
| **PID** | 04 | ✅ Mapped | `item.additional_item_properties[0].name` |
| PID | 05 | ✅ Mapped | `item.description` |
| **CTP** | 02 | ✅ Mapped | `price.price_type_code` |
| CTP | 03 | ✅ Mapped | `price.price_amount.value` (alternate) |
| **SAC** | (line) | ✅ Mapped | `allowance_charges[]` |
| **DTM** | (line) | ✅ Mapped | Line-level delivery dates (002, 010, 038, 063) |
| **SCH** | 01 | ✅ Mapped | `delivery[].quantity.value` |
| SCH | 02 | ✅ Mapped | `delivery[].quantity.unit_code` |
| SCH | 05/06 | ✅ Mapped | `delivery[].requested_delivery_period` |
| **REF** | (LI) | ✅ Mapped | `document_references[0].id` |
| **MSG** | 01 | ✅ Mapped | `note[0]` |

---

## Coverage Summary

| Category | Mapped | Total | Coverage |
|----------|--------|-------|----------|
| BEG Segment | 6 | 6 | 100% |
| CUR Segment | 2 | 2 | 100% |
| REF Qualifiers | 8 | 8 | 100% |
| PER Segment | 4 | 4 | 100% |
| FOB Segment | 2 | 3 | 67% |
| ITD Segment | 4 | 4 | 100% |
| DTM Qualifiers | 7 | 7 | 100% |
| TD5 Segment | 5 | 5 | 100% |
| TD1 Segment | 2 | 4 | 50% |
| SAC Segment | 5 | 5 | 100% |
| TXI Segment | 3 | 3 | 100% |
| N1 Party Qualifiers | 8 | 8 | 100% |
| N1 Loop Fields | 14 | 14 | 100% |
| PO1 Fields | 11 | 12 | 92% |
| **OVERALL** | ~81 | ~85 | **95%** |

---

## Implementation Tasks

### Phase 1: Contact/Party Enhancement ✅ COMPLETE
- [x] Implement PER paired element handler for phone/email/fax
- [x] Add N1*03/04 party identification mapping
- [x] Add N2 additional name support
- [x] Add remaining party qualifiers (SF, OB, CA, RI)

### Phase 2: Product ID Handling ✅ COMPLETE
- [x] Implement PO1 product ID pair handler (elements 06-25)
- [x] Map qualifiers: UP→UPC, VP→Vendor, BP→Buyer, EN→EAN, etc.
- [x] Create proper ItemIdentification objects with scheme_id

### Phase 3: Transport/Logistics ✅ COMPLETE
- [x] Add TD5 carrier mapping
- [x] Add TD1 packaging mapping
- [x] Enhance FOB with Incoterms (FOB*05)

### Phase 4: Financial ✅ COMPLETE
- [x] Add header-level SAC allowances/charges
- [x] Add line-level SAC
- [x] Add TXI tax mapping
- [x] Add CUR exchange rate

### Phase 5: Advanced Features ✅ COMPLETE
- [x] Add SCH delivery schedules
- [x] Add N9 additional references
- [x] Add CTP pricing segment
- [x] Add line-level DTM qualifiers
- [ ] Add SLN sublines (deferred - less common)

---

## Technical Notes

### Paired Element Pattern

PER and PO1 segments use a paired element pattern where qualifier/value pairs appear adjacent:

```
PER*OC*John Doe*TE*5551234567*EM*john@example.com~
     ^qualifier  ^value    ^qualifier ^value
```

**Implementation:** Handled by `MappingEngine._populate_party_fields()` for PER and `_extract_po1_product_ids()` for PO1.

### Product ID Qualifier Mapping

| Qualifier | Field Type | Scheme ID |
|-----------|------------|-----------|
| UP | standard | UPC |
| EN | standard | EAN |
| UK | standard | UCC/EAN-128 |
| UA | standard | UPC-A |
| UI | standard | UPC-I |
| VP, SK, VN | sellers | None |
| BP, IN | buyers | None |
| MG, MN | manufacturers | None |
| Others | additional | qualifier value |

### Loop Iteration Semantics

The `[+]` syntax in semantic paths indicates "append to list":
- `delivery[0]` = first delivery (create if missing)
- `delivery[+]` = append new delivery

---

## Verification

1. Run tests: `pytest tests/semantic/test_x12_order_mapper.py -v`
2. Check snapshot for mapped fields
3. All 13 tests passing

---

## Files Modified

| File | Changes |
|------|---------|
| `mapping/x12/order_850.py` | Added field mappings for TD5, TD1, FOB, ITD, N9, CTP, line-level DTM |
| `mapping/engine.py` | Added `_map_sac_segments`, `_map_txi_segments`, `_extract_po1_product_ids`, `_extract_line_sac_segments`, `_extract_sch_segments`, `_map_party_to_indexed_path` |
| `mapping/x12/shared/parties.py` | Added SF, CA, RI party qualifiers |
| `models/order.py` | Added `payee_party` field |
| `models/payment.py` | Added `settlement_period_days` field |
| `tests/semantic/test_x12_order_mapper.py` | Added tests for product ID scheme, party identifications, delivery terms, contact info |
