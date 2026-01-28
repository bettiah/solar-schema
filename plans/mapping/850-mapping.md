# X12 850 Purchase Order Mapping - Complete Reference

## Overview

This document is the consolidated specification for mapping X12 850 Purchase Order to the semantic Order model. It combines implementation status, gap analysis, and technical details.

**Implementation Files:**
- Mapping Definition: `src/edi_schema/semantic/mapping/x12/order_850.py`
- Mapping Engine: `src/edi_schema/semantic/mapping/engine.py`
- Tests: `tests/semantic/test_x12_order_mapper.py`

**Current Coverage: ~95%**

---

## Implementation Status Summary

| Category | Status | Notes |
|----------|--------|-------|
| Header Segments (BEG, CUR, FOB, ITD, CTT) | ✅ Complete | |
| Date/Time (DTM) | ✅ Complete | All common qualifiers |
| References (REF, N9) | ✅ Complete | 15+ qualifiers mapped |
| Parties (N1 Loop) | ✅ Complete | 8 party types |
| Contacts (PER) | ✅ Complete | Header + loop level |
| Transport (TD5, TD1) | ✅ Complete | Carrier, packaging |
| Line Items (PO1 Loop) | ✅ Complete | Product IDs, pricing |
| Allowances/Charges (SAC) | ✅ Complete | Header + line level |
| Tax (TXI) | ✅ Complete | |
| Schedules (SCH) | ✅ Complete | Line-level delivery |
| Monetary Totals (AMT) | ✅ Complete | |
| Notes (MSG) | ✅ Complete | Header + line + N9 loop |
| Unmapped Tracking | ✅ Complete | Metrics + warnings |

---

## Header-Level Segment Mappings

### BEG - Beginning Segment for Purchase Order

| Element | X12 Name | Status | Semantic Path | Transform |
|---------|----------|--------|---------------|-----------|
| 01 | Purpose Code | ✅ | `document_purpose_code` | |
| 02 | Order Type | ✅ | `order_type_code` | |
| 03 | PO Number | ✅ | `id` | Required |
| 04 | Release Number | ✅ | `sales_order_id` | Blanket PO |
| 05 | Date | ✅ | `issue_date` | PARSE_DATE |
| 06 | Contract Number | ✅ | `contract_document_reference.id` | |

### CUR - Currency

| Element | X12 Name | Status | Semantic Path | Notes |
|---------|----------|--------|---------------|-------|
| 01 | Entity Identifier | ✅ | (handled) | Qualifier only |
| 02 | Currency Code | ✅ | `document_currency_code` | Default: USD |
| 03 | Exchange Rate | ✅ | `pricing_exchange_rate` | PARSE_DECIMAL |

### FOB - F.O.B. Related Instructions

| Element | X12 Name | Status | Semantic Path | Notes |
|---------|----------|--------|---------------|-------|
| 01 | Ship Method Payment | ✅ | `delivery_terms` | PP/CC/etc |
| 02 | Location Qualifier | ✅ | `delivery[0].delivery_terms.loss_risk_responsibility_code` | Via engine |
| 03 | Description | ✅ | `delivery[0].delivery_terms.special_terms` | Via engine |
| 05 | Transport Terms | ✅ | `delivery[0].delivery_terms.special_terms` | Incoterms |

**Implementation:** FOB*02/03 handled by `MappingEngine._map_fob_to_delivery()`

### ITD - Terms of Sale/Deferred Terms of Sale

| Element | X12 Name | Status | Semantic Path |
|---------|----------|--------|---------------|
| 05 | Discount % | ✅ | `payment_terms[0].settlement_discount_percent` |
| 06 | Discount Due Date | ✅ | `payment_terms[0].settlement_period.end_date` |
| 07 | Net Days | ✅ | `payment_terms[0].settlement_period_days` |
| 12 | Description | ✅ | `payment_terms[0].note` |

### TD5 - Carrier Details (Routing Sequence/Transit Time)

| Element | X12 Name | Status | Semantic Path |
|---------|----------|--------|---------------|
| 02 | ID Qualifier | ✅ | `delivery[0].shipment.carrier_party.party_identifications[0].id.scheme_id` |
| 03 | Carrier ID (SCAC) | ✅ | `delivery[0].shipment.carrier_party.party_identifications[0].id.value` |
| 04 | Transport Method | ✅ | `delivery[0].shipment.shipment_stages[0].transport_mode_code` |
| 05 | Routing | ✅ | `delivery[0].shipment.shipment_stages[0].transit_direction_code` |
| 12 | Service Level | ✅ | `delivery[0].shipment.shipping_priority_level_code` |

**Implementation:** Handled by `MappingEngine._map_td5_to_shipment()`

### TD1 - Carrier Details (Quantity and Weight)

| Element | X12 Name | Status | Semantic Path |
|---------|----------|--------|---------------|
| 01 | Packaging Code | ✅ | `delivery[0].shipment.transport_handling_units[0].transport_handling_unit_type_code` |
| 02 | Lading Quantity | ✅ | `delivery[0].shipment.total_transport_handling_unit_quantity` |

### CTT - Transaction Totals

| Element | X12 Name | Status | Semantic Path | Notes |
|---------|----------|--------|---------------|-------|
| 01 | Line Count | ✅ | `line_count` | |
| 02 | Hash Total | ✅ | (handled) | Validation only |

### AMT - Monetary Amount

| Qualifier | X12 Name | Status | Semantic Path |
|-----------|----------|--------|---------------|
| TT | Total Transaction Amount | ✅ | `anticipated_monetary_total.payable_amount.value` |

**Implementation:** Handled by `MappingEngine._map_amt_totals()` which creates MonetaryTotal/Amount objects.

### MSG - Message Text

| Element | X12 Name | Status | Semantic Path |
|---------|----------|--------|---------------|
| 01 | Free Form Message | ✅ | `note[]` |

**Implementation:** Handled by `MappingEngine._map_msg_notes()` which finds MSG at header, line, and N9 loop levels.

---

## Qualified Segment Mappings

### DTM - Date/Time Reference

| Qualifier | X12 Name | Status | Semantic Path |
|-----------|----------|--------|---------------|
| 002 | Delivery Requested | ✅ | `delivery[0].requested_delivery_period.start_date` |
| 010 | Ship Date | ✅ | `delivery[0].despatch.requested_despatch_date` |
| 037 | Ship Not Before | ✅ | `delivery[0].despatch.earliest_despatch_date` |
| 038 | Ship No Later | ✅ | `delivery[0].latest_delivery_date` |
| 063 | Do Not Deliver After | ✅ | `delivery[0].latest_delivery_date` |
| 064 | Valid From | ✅ | `validity_period.start_date` |
| 065 | Valid To | ✅ | `validity_period.end_date` |

**Implementation:** DTM*010/037 handled by `MappingEngine._map_dtm_despatch()` which creates Despatch objects.

### REF - Reference Identification

| Qualifier | X12 Name | Status | Semantic Path |
|-----------|----------|--------|---------------|
| CT | Contract Number | ✅ | `contract_document_reference.id` |
| PO | Prior PO Number | ✅ | `order_document_references[0].id` |
| QQ | Quotation Number | ✅ | `quotation_document_reference.id` |
| VN | Vendor Order Number | ✅ | `additional_document_references[0].id` |
| BM | Bill of Lading | ✅ | `additional_document_references[+].id` |
| IT | Internal Order | ✅ | `originator_document_reference.id` |
| DP | Department Number | ✅ | `additional_document_references[+].id` |
| IA | Internal Vendor | ✅ | `additional_document_references[+].id` |
| 8M | Related Vendor Order | ✅ | `additional_document_references[+].id` |
| IV | Invoice Number | ✅ | `additional_document_references[+].id` |
| SI | Shipper's ID | ✅ | `additional_document_references[+].id` |
| KK | Customer Account | ✅ | `additional_document_references[+].id` |
| SE | Serial Number | ✅ | `additional_document_references[+].id` |
| TN | Transaction Ref | ✅ | `additional_document_references[+].id` |
| ZZ | Mutually Defined | ✅ | `additional_document_references[+].id` |

**Note:** REF*03 (description) is tracked as handled but not mapped (future enhancement).

### N9 - Extended Reference Identification

| Qualifier | X12 Name | Status | Semantic Path |
|-----------|----------|--------|---------------|
| LI | Line Item Reference | ✅ | `additional_document_references[+].id` |
| DO | Delivery Order | ✅ | `additional_document_references[+].id` |
| CR | Customer Reference | ✅ | `additional_document_references[+].id` |
| PD | Promotion/Deal | ✅ | `additional_document_references[+].id` |
| AH | Agreement Number | ✅ | `additional_document_references[+].id` |
| ZZ | Mutually Defined | ✅ | `additional_document_references[+].id` |
| L1 | Letters/Notes | ✅ | `additional_document_references[+].id` |
| OQ | Order Number | ✅ | `additional_document_references[+].id` |

---

## Party Loop (N1) Mappings

### Party Qualifiers

| Qualifier | X12 Name | Status | Semantic Path |
|-----------|----------|--------|---------------|
| BY | Buyer | ✅ | `buyer_customer_party` |
| SE | Seller | ✅ | `seller_supplier_party` |
| ST | Ship To | ✅ | `delivery[+].delivery_party` |
| BT | Bill To | ✅ | `accounting_customer_party` |
| SF | Ship From | ✅ | `delivery[0].despatch.despatch_party` |
| OB | Ordered By | ✅ | `originator_customer_party` |
| CA | Carrier | ✅ | `freight_forwarder_party` |
| RI | Remit To | ✅ | `payee_party` |

### N1 Loop Segment Mappings

| Segment | Element | Status | Semantic Path (relative to party) |
|---------|---------|--------|-----------------------------------|
| N1 | 02 | ✅ | `party.party_names[0].name` |
| N1 | 03 | ✅ | `party.party_identifications[0].id.scheme_id` |
| N1 | 04 | ✅ | `party.party_identifications[0].id.value` |
| N2 | 01 | ✅ | `party.party_names[1].name` |
| N3 | 01 | ✅ | `party.postal_address.street_name` |
| N3 | 02 | ✅ | `party.postal_address.additional_street_name` |
| N4 | 01 | ✅ | `party.postal_address.city_name` |
| N4 | 02 | ✅ | `party.postal_address.country_subentity` |
| N4 | 03 | ✅ | `party.postal_address.postal_zone` |
| N4 | 04 | ✅ | `party.postal_address.country_code` |
| PER | 02 | ✅ | `party.contact.name` |
| PER | 03/04 | ✅ | `party.contact.telephone` (TE qualifier) |
| PER | 05/06 | ✅ | `party.contact.telefax` (FX qualifier) |
| PER | 07/08 | ✅ | `party.contact.electronic_mail` (EM qualifier) |

### Header-Level PER Segments

Header-level PER segments (outside N1 loops) are handled by `MappingEngine._map_header_per_segments()`:

| Qualifier | X12 Name | Semantic Path |
|-----------|----------|---------------|
| OC | Order Contact | `buyer_customer_party.buyer_contact` |
| IC | Information Contact | `buyer_customer_party.buyer_contact` |

---

## Line Item Loop (PO1) Mappings

### PO1 Segment

| Element | X12 Name | Status | Semantic Path |
|---------|----------|--------|---------------|
| 01 | Line Number | ✅ | `id` |
| 02 | Quantity | ✅ | `quantity.value` |
| 03 | Unit | ✅ | `quantity.unit_code` |
| 04 | Unit Price | ✅ | `price.price_amount.value` |
| 05 | Basis of Unit Price | ✅ | `price.base_quantity_unit_code` |
| 06-25 | Product ID Pairs | ✅ | See Product ID Mapping |

### Product ID Qualifier Mapping

Handled by `MappingEngine._extract_po1_product_ids()`:

| Qualifier | Category | Semantic Field | Scheme ID |
|-----------|----------|----------------|-----------|
| UP | Standard | `standard_item_identification` | UPC |
| EN | Standard | `standard_item_identification` | EAN |
| UK | Standard | `standard_item_identification` | UCC/EAN-128 |
| UA | Standard | `standard_item_identification` | UPC-A |
| UI | Standard | `standard_item_identification` | UPC-I |
| VP, SK, VN | Seller | `sellers_item_identification` | (qualifier) |
| BP, IN | Buyer | `buyers_item_identification` | (qualifier) |
| MG, MN | Manufacturer | `manufacturers_item_identification` | (qualifier) |
| Others | Additional | `additional_item_identifications[+]` | (qualifier) |

### PO1 Loop Sub-Segments

| Segment | Element | Status | Semantic Path |
|---------|---------|--------|---------------|
| PID | 04 | ✅ | `item.additional_item_properties[0].name` |
| PID | 05 | ✅ | `item.description` |
| CTP | 02 | ✅ | `price.price_type_code` |
| CTP | 03 | ✅ | `price.price_amount.value` (alternate) |
| REF | (LI) | ✅ | `document_references[0].id` |
| MSG | 01 | ✅ | `note[0]` |
| DTM | (002) | ✅ | `delivery[0].requested_delivery_period.start_date` |
| DTM | (010) | ✅ | `delivery[0].despatch.requested_despatch_date` |
| DTM | (038) | ✅ | `delivery[0].latest_delivery_date` |
| DTM | (063) | ✅ | `delivery[0].latest_delivery_date` |

### SAC - Service, Promotion, Allowance, Charge (Line Level)

Handled by `MappingEngine._extract_line_sac_segments()`:

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| 01 | Allowance/Charge Indicator | `allowance_charges[].charge_indicator` |
| 02 | Code | `allowance_charges[].allowance_charge_reason_code` |
| 05 | Amount | `allowance_charges[].amount.value` |
| 12 | Description | `allowance_charges[].allowance_charge_reason` |
| 15 | Percent | `allowance_charges[].multiplier_factor_numeric` |

### SCH - Line Item Schedule

Handled by `MappingEngine._extract_sch_segments()`:

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| 01 | Quantity | `delivery[].quantity.value` |
| 02 | Unit | `delivery[].quantity.unit_code` |
| 05 | Date Qualifier | (routing) |
| 06 | Date | `delivery[].requested_delivery_period.start_date` |

---

## Header-Level SAC Mappings

Handled by `MappingEngine._map_sac_segments()`:

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| 01 | Allowance/Charge Indicator | `allowance_charges[].charge_indicator` |
| 02 | Code | `allowance_charges[].allowance_charge_reason_code` |
| 05 | Amount | `allowance_charges[].amount.value` |
| 12 | Description | `allowance_charges[].allowance_charge_reason` |
| 15 | Percent | `allowance_charges[].multiplier_factor_numeric` |

---

## TXI - Tax Information

Handled by `MappingEngine._map_txi_segments()`:

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| 01 | Tax Type | `tax_total[].tax_subtotal[].tax_category.id` |
| 02 | Amount | `tax_total[].tax_amount.value` |
| 03 | Percent | `tax_total[].tax_subtotal[].percent` |

---

## Unmapped Data Tracking

The mapping engine tracks unmapped segments and elements for debugging and coverage analysis.

### Configuration

```python
engine = MappingEngine(
    ORDER_850_MAPPING,
    collect_metrics=True,    # Collect coverage metrics
    warn_on_unmapped=True,   # Generate warnings for unmapped data
)
```

### Tracked Metrics

| Metric | Description |
|--------|-------------|
| `total_segments_in_document` | All segments found |
| `segments_mapped` | Segments with mappings applied |
| `unmapped_segments` | Segments with no mapping |
| `unmapped_qualifiers` | Qualifier values not recognized |

### Warning Types

| Code | Description |
|------|-------------|
| `UNMAPPED_SEGMENT` | Entire segment type has no mapping |
| `UNMAPPED_QUALIFIER` | Qualified segment with unknown qualifier |
| `UNMAPPED_ELEMENT` | Element within mapped segment not mapped |
| `CANNOT_SET_FIELD` | Mapping exists but target path creation failed |

### Intentionally Unmapped Fields

These fields are tracked as "handled" but not mapped to semantic model:

| Field | Reason |
|-------|--------|
| CUR*01 | Entity qualifier, not business data |
| CTT*02 | Hash total for validation only |
| REF*03 | Description field (future enhancement) |

---

## Special Handler Methods

The `MappingEngine` has special handlers for complex mapping scenarios:

| Method | Purpose |
|--------|---------|
| `_map_header_per_segments()` | Header-level PER*OC/IC to buyer_contact |
| `_map_fob_to_delivery()` | FOB*02/03/05 to delivery_terms |
| `_map_td5_to_shipment()` | TD5 to shipment carrier info |
| `_map_msg_notes()` | MSG to note[] at all levels |
| `_map_amt_totals()` | AMT*TT to monetary_total (creates objects) |
| `_map_dtm_despatch()` | DTM*010/037 to despatch (creates objects) |
| `_map_sac_segments()` | Header SAC to allowance_charges |
| `_map_txi_segments()` | TXI to tax_total |
| `_extract_po1_product_ids()` | PO1*06-25 product ID pairs |
| `_extract_line_sac_segments()` | Line-level SAC |
| `_extract_sch_segments()` | Line-level SCH schedules |

---

## Validation Rules

Defined in `mapping/x12/validations/order_rules.py`:

| Rule | Description |
|------|-------------|
| Required Fields | BEG*03 (id), BEG*05 (issue_date) |
| Date Formats | YYYYMMDD or YYMMDD |
| Decimal Parsing | Handles implied decimals |

---

## Future Enhancements

### Lower Priority Items

| Item | Description | Complexity |
|------|-------------|------------|
| SLN Sublines | Sub-line item details | Medium |
| CSH Segment | Sales requirements (backorder policy) | Low |
| PKG Segment | Packaging details | Low |
| REF*03 Description | Capture reference descriptions | Medium |
| Additional REF Qualifiers | 100+ possible qualifiers | Low each |

### Model Enhancements Needed

For future segments, these model fields may need to be added:

```python
# Order model
backorder_policy: str | None = None
special_instructions: str | None = None

# DeliveryTerms model
risk_description: str | None = None
risk_code: str | None = None

# Shipment model
tracking_id: str | None = None
packaging_description: str | None = None
```

---

## Testing

### Test File
`tests/semantic/test_x12_order_mapper.py`

### Test Fixture
`tests/fixtures/x12_samples/logistics/850_purchase_order.x12`

### Key Test Cases

| Test | Validates |
|------|-----------|
| `test_mapping_succeeds` | Basic mapping completion |
| `test_mapped_order_snapshot` | Full output structure |
| `test_order_basic_fields` | BEG segment mapping |
| `test_order_has_line_items` | PO1 loop mapping |
| `test_order_has_price` | Price/amount mapping |
| `test_order_has_delivery` | Delivery party mapping |
| `test_product_id_with_scheme` | Product ID qualifier handling |
| `test_party_identifications_mapped` | N1*03/04 mapping |
| `test_delivery_terms_mapped` | FOB mapping |
| `test_contact_info_mapped` | PER mapping in N1 loop |
| `test_header_level_per_mapped` | Header PER*OC mapping |
| `test_fob_delivery_terms_mapped` | FOB*02/03 mapping |
| `test_unmapped_tracking_enabled` | Zero unmapped warnings |
| `test_unmapped_warnings_can_be_disabled` | Warning suppression |
| `test_metrics_contain_unmapped_summary` | Metrics structure |

### Running Tests

```bash
# All 850 mapping tests
pytest tests/semantic/test_x12_order_mapper.py -v

# Update snapshot
pytest tests/semantic/test_x12_order_mapper.py -v --snapshot-update
```

---

## Files Reference

| File | Purpose |
|------|---------|
| `src/edi_schema/semantic/mapping/x12/order_850.py` | Mapping definition |
| `src/edi_schema/semantic/mapping/engine.py` | Mapping engine with special handlers |
| `src/edi_schema/semantic/mapping/types.py` | Mapping type definitions |
| `src/edi_schema/semantic/mapping/transforms.py` | Value transforms (PARSE_DATE, etc.) |
| `src/edi_schema/semantic/mapping/errors.py` | Error codes |
| `src/edi_schema/semantic/mapping/diagnostics.py` | Metrics and tracking |
| `src/edi_schema/semantic/mapping/x12/shared/parties.py` | Party qualifier mappings |
| `src/edi_schema/semantic/mapping/x12/validations/order_rules.py` | Validation rules |
| `src/edi_schema/semantic/models/order.py` | Order semantic model |
