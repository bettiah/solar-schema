# X12 810 Invoice Mapping - Complete Reference

## Overview

This document is the consolidated specification for mapping X12 810 Invoice to the semantic Invoice model. It combines implementation status, gap analysis, and technical details.

**Implementation Files:**
- Mapping Definition: `src/edi_schema/semantic/mapping/x12/invoice_810.py`
- Mapping Engine: `src/edi_schema/semantic/mapping/engine.py`
- Tests: `tests/semantic/test_x12_invoice_mapper.py`

**Current Coverage: ~0% (Planning)**

---

## Implementation Status Summary

| Category | Status | Notes |
|----------|--------|-------|
| Header Segments (BIG, CUR, FOB, ITD, CTT, TDS) | ⏳ Planned | |
| Date/Time (DTM) | ⏳ Planned | All common qualifiers |
| References (REF, N9) | ⏳ Planned | 15+ qualifiers mapped |
| Notes (NTE, MSG) | ⏳ Planned | Header + line level |
| Parties (N1 Loop) | ⏳ Planned | 4+ party types |
| Contacts (PER) | ⏳ Planned | Header + loop level |
| Line Items (IT1 Loop) | ⏳ Planned | Product IDs, pricing |
| Allowances/Charges (SAC) | ⏳ Planned | Header + line level |
| Tax (TXI) | ⏳ Planned | Header + line level |
| Summary (TDS, CAD, ISS) | ⏳ Planned | Totals, carrier, shipment |
| Unmapped Tracking | ⏳ Planned | Metrics + warnings |

---

## Header-Level Segment Mappings

### BIG - Beginning Segment for Invoice

| Element | X12 Name | Status | Semantic Path | Transform |
|---------|----------|--------|---------------|-----------|
| 01 | Invoice Date | ⏳ | `issue_date` | PARSE_DATE |
| 02 | Invoice Number | ⏳ | `id` | Required |
| 03 | PO Date | ⏳ | `order_reference.issue_date` | PARSE_DATE |
| 04 | PO Number | ⏳ | `order_reference.id` | |
| 05 | Release Number | ⏳ | `order_reference.sales_order_id` | Blanket PO |
| 06 | Change Order Sequence | ⏳ | `order_reference.version_id` | |
| 07 | Transaction Type Code | ⏳ | `invoice_type_code` | See mapping |
| 08 | Transaction Set Purpose | ⏳ | (handled) | 00=Original, etc. |
| 09 | Action Code | ⏳ | (future) | |
| 10 | Invoice Number (prior) | ⏳ | `billing_references[0].invoice_document_reference.id` | Adjustment |

**Transaction Type Code Mapping (BIG*07):**
| X12 Code | Description | UBL Invoice Type |
|----------|-------------|------------------|
| (blank) | Standard Invoice | 380 |
| CN | Credit Invoice | 381 |
| CR | Credit Memo | 381 |
| DI | Debit Invoice | 383 |
| DR | Debit Memo | 383 |
| RU | Return with Credit | 381 |
| SU | Summary Invoice | 385 |

### NTE - Note/Special Instruction

| Element | X12 Name | Status | Semantic Path | Notes |
|---------|----------|--------|---------------|-------|
| 01 | Note Reference Code | ⏳ | (handled) | Qualifier |
| 02 | Description | ⏳ | `note[]` | Free text |

**Note Reference Code Mapping (NTE*01):**
| Qualifier | Description | Semantic Handling |
|-----------|-------------|-------------------|
| GEN | General Note | `note[]` |
| SHP | Shipping Note | `delivery[0].special_instructions` |
| PAY | Payment Note | `payment_terms[0].note` |
| SPH | Special Handling | `note[]` with prefix |

### CUR - Currency

| Element | X12 Name | Status | Semantic Path | Notes |
|---------|----------|--------|---------------|-------|
| 01 | Entity Identifier | ⏳ | (handled) | Qualifier only |
| 02 | Currency Code | ⏳ | `document_currency_code` | ISO 4217 |
| 03 | Exchange Rate | ⏳ | `pricing_exchange_rate` | PARSE_DECIMAL |
| 04 | Entity ID Qualifier | ⏳ | (handled) | Secondary |
| 05 | Currency Code 2 | ⏳ | `pricing_currency_code` | Alternate |
| 06 | Currency Market/Exchange | ⏳ | (future) | |

### FOB - F.O.B. Related Instructions

| Element | X12 Name | Status | Semantic Path | Notes |
|---------|----------|--------|---------------|-------|
| 01 | Shipment Method Payment | ⏳ | `delivery[0].delivery_terms.id` | PP/CC/etc |
| 02 | Location Qualifier | ⏳ | `delivery[0].delivery_terms.loss_risk_responsibility_code` | Via engine |
| 03 | Description | ⏳ | `delivery[0].delivery_terms.special_terms` | Via engine |
| 04 | Transport Terms Code | ⏳ | `delivery[0].delivery_terms.special_terms` | Incoterms |
| 05 | Location Qualifier | ⏳ | (handled) | Secondary |
| 06 | Description | ⏳ | (handled) | Secondary |

**Implementation:** FOB*02/03/04 handled by `MappingEngine._map_fob_to_delivery()`

### ITD - Terms of Sale/Deferred Terms of Sale

| Element | X12 Name | Status | Semantic Path | Notes |
|---------|----------|--------|---------------|-------|
| 01 | Terms Type Code | ⏳ | `payment_terms[0].payment_means_id` | |
| 02 | Terms Basis Date Code | ⏳ | `payment_terms[0].installment_due_date_code` | |
| 03 | Terms Discount Percent | ⏳ | `payment_terms[0].settlement_discount_percent` | PARSE_DECIMAL |
| 04 | Terms Discount Due Date | ⏳ | `payment_terms[0].settlement_period.end_date` | PARSE_DATE |
| 05 | Terms Discount Days Due | ⏳ | `payment_terms[0].penalty_period_days` | TO_INT |
| 06 | Terms Net Due Date | ⏳ | `due_date` | PARSE_DATE |
| 07 | Terms Net Days | ⏳ | `payment_terms[0].settlement_period_days` | TO_INT |
| 08 | Terms Discount Amount | ⏳ | `payment_terms[0].penalty_amount.value` | PARSE_DECIMAL |
| 09 | Terms Deferred Due Date | ⏳ | (future) | |
| 10 | Deferred Amount Due | ⏳ | (future) | |
| 12 | Description | ⏳ | `payment_terms[0].note` | |
| 13 | Day of Month | ⏳ | `payment_terms[0].payment_due_date_day` | |

### L7 - Tariff Reference

| Element | X12 Name | Status | Semantic Path | Notes |
|---------|----------|--------|---------------|-------|
| 01 | Lading Line Item Number | ⏳ | (handled) | |
| 02 | Tariff Agency Code | ⏳ | `additional_document_references[+].id` | |
| 03 | Tariff Number | ⏳ | `additional_document_references[+].id` | |

### BAL - Balance Detail

| Element | X12 Name | Status | Semantic Path | Notes |
|---------|----------|--------|---------------|-------|
| 01 | Balance Type Code | ⏳ | (handled) | Qualifier |
| 02 | Amount Qualifier Code | ⏳ | (handled) | |
| 03 | Monetary Amount | ⏳ | `prepaid_payments[0].paid_amount.value` | If BP (Balance Due) |

### CTT - Transaction Totals

| Element | X12 Name | Status | Semantic Path | Notes |
|---------|----------|--------|---------------|-------|
| 01 | Number of Line Items | ⏳ | `line_count` | TO_INT |
| 02 | Hash Total | ⏳ | (handled) | Validation only |
| 03 | Weight | ⏳ | `delivery[0].shipment.gross_weight_measure.value` | |
| 04 | Unit of Measurement | ⏳ | `delivery[0].shipment.gross_weight_measure.unit_code` | |
| 05 | Volume | ⏳ | `delivery[0].shipment.gross_volume_measure.value` | |
| 06 | Unit of Measurement | ⏳ | `delivery[0].shipment.gross_volume_measure.unit_code` | |

---

## Summary Section Segment Mappings

### TDS - Total Monetary Value Summary

| Element | X12 Name | Status | Semantic Path | Notes |
|---------|----------|--------|---------------|-------|
| 01 | Total Invoice Amount | ⏳ | `legal_monetary_total.payable_amount.value` | **IN CENTS** - divide by 100 |
| 02 | Amount Subject to Terms Discount | ⏳ | `legal_monetary_total.allowance_total_amount.value` | In cents |
| 03 | Discounted Amount Due | ⏳ | `legal_monetary_total.prepaid_amount.value` | In cents |
| 04 | Amount Subject to Late Pay | ⏳ | (future) | In cents |

**CRITICAL:** TDS amounts are in cents (2 implied decimal places). Transform: `PARSE_CENTS` = divide by 100.

**Implementation:** Handled by `MappingEngine._map_tds_totals()` which:
1. Parses values as integers
2. Divides by 100 to get decimal amount
3. Creates MonetaryTotal/Amount objects with currency from CUR

### CAD - Carrier Detail

| Element | X12 Name | Status | Semantic Path | Notes |
|---------|----------|--------|---------------|-------|
| 01 | Transport Method | ⏳ | `delivery[0].shipment.shipment_stages[0].transport_mode_code` | |
| 02 | Equipment Initial | ⏳ | `delivery[0].shipment.transport_handling_units[0].id` | |
| 03 | Equipment Number | ⏳ | `delivery[0].shipment.transport_handling_units[0].tracking_id` | |
| 04 | Standard Carrier Alpha Code | ⏳ | `delivery[0].shipment.carrier_party.party_identifications[0].id.value` | SCAC |
| 05 | Routing | ⏳ | `delivery[0].shipment.shipment_stages[0].transit_direction_code` | |
| 06 | Shipment/Order Status Code | ⏳ | (future) | |
| 07 | Reference ID Qualifier | ⏳ | (handled) | |
| 08 | Reference ID | ⏳ | `despatch_document_reference.id` | Often BOL |
| 09 | Service Level Code | ⏳ | `delivery[0].shipment.shipping_priority_level_code` | |

**Implementation:** Handled by `MappingEngine._map_cad_to_shipment()`

### AMT - Monetary Amount (Summary)

| Qualifier | X12 Name | Status | Semantic Path | Notes |
|-----------|----------|--------|---------------|-------|
| TT | Total Transaction Amount | ⏳ | `legal_monetary_total.tax_inclusive_amount.value` | |
| SA | Tax Amount | ⏳ | `tax_total[0].tax_amount.value` | |
| 1 | Line Item Total | ⏳ | `legal_monetary_total.line_extension_amount.value` | |
| 2 | Tax Total | ⏳ | `tax_total[0].tax_amount.value` | |
| BAL | Balance Due | ⏳ | `legal_monetary_total.payable_amount.value` | |
| FR | Freight | ⏳ | `allowance_charges[+].amount.value` (charge) | |
| HA | Handling | ⏳ | `allowance_charges[+].amount.value` (charge) | |
| DIS | Discount | ⏳ | `allowance_charges[+].amount.value` (allowance) | |

**Implementation:** Handled by `MappingEngine._map_amt_totals()`

### ISS - Invoice Shipment Summary

| Element | X12 Name | Status | Semantic Path | Notes |
|---------|----------|--------|---------------|-------|
| 01 | Number of Units Shipped | ⏳ | `delivery[0].quantity.value` | PARSE_DECIMAL |
| 02 | Unit of Measurement | ⏳ | `delivery[0].quantity.unit_code` | |
| 03 | Weight | ⏳ | `delivery[0].shipment.gross_weight_measure.value` | |
| 04 | Unit of Measurement | ⏳ | `delivery[0].shipment.gross_weight_measure.unit_code` | |
| 05 | Volume | ⏳ | `delivery[0].shipment.gross_volume_measure.value` | |
| 06 | Unit of Measurement | ⏳ | `delivery[0].shipment.gross_volume_measure.unit_code` | |

---

## Qualified Segment Mappings

### DTM - Date/Time Reference

| Qualifier | X12 Name | Status | Semantic Path | Notes |
|-----------|----------|--------|---------------|-------|
| 003 | Invoice | ⏳ | `issue_date` | Alternate to BIG*01 |
| 011 | Shipped | ⏳ | `delivery[0].actual_delivery_date` | |
| 017 | Estimated Delivery | ⏳ | `delivery[0].requested_delivery_period.end_date` | |
| 035 | Delivered | ⏳ | `delivery[0].actual_delivery_date` | |
| 036 | Expiration | ⏳ | (future) | |
| 050 | Received | ⏳ | `receipt_document_reference.issue_date` | |
| 118 | Rate Effective | ⏳ | (future) | |

**Implementation:** DTM*011/035 handled by `MappingEngine._map_dtm_delivery()`

### REF - Reference Identification

| Qualifier | X12 Name | Status | Semantic Path | Notes |
|-----------|----------|--------|---------------|-------|
| BM | Bill of Lading | ⏳ | `despatch_document_reference.id` | |
| CN | Carrier Number | ⏳ | `delivery[0].shipment.carrier_party.party_identifications[+].id.value` | |
| CO | Customer Order Number | ⏳ | `order_reference.id` | |
| CR | Customer Reference | ⏳ | `buyer_reference` | |
| CT | Contract Number | ⏳ | `contract_document_reference.id` | |
| DP | Department Number | ⏳ | `additional_document_references[+].id` | |
| IA | Internal Vendor Number | ⏳ | `additional_document_references[+].id` | |
| IL | Internal Order Number | ⏳ | `originator_document_reference.id` | |
| IN | Invoice Number | ⏳ | `additional_document_references[+].id` | Prior |
| IV | Seller Invoice Number | ⏳ | `additional_document_references[+].id` | |
| KK | Customer Account | ⏳ | `accounting_customer_party.additional_account_ids[0]` | |
| ON | Order Number | ⏳ | `order_reference.id` | |
| PO | Purchase Order Number | ⏳ | `order_reference.id` | |
| SE | Serial Number | ⏳ | `additional_document_references[+].id` | |
| SI | Shipper's ID | ⏳ | `despatch_document_reference.id` | |
| SU | Special Processing Code | ⏳ | (future) | |
| TN | Transaction Reference | ⏳ | `additional_document_references[+].id` | |
| VN | Vendor Order Number | ⏳ | `seller_supplier_party.additional_account_ids[0]` | |
| ZZ | Mutually Defined | ⏳ | `additional_document_references[+].id` | |

**Note:** REF*03 (description) is tracked as handled but not mapped (future enhancement).

### N9 - Extended Reference Identification

| Qualifier | X12 Name | Status | Semantic Path | Notes |
|-----------|----------|--------|---------------|-------|
| AH | Agreement Number | ⏳ | `contract_document_reference.id` | |
| CR | Customer Reference | ⏳ | `buyer_reference` | |
| DO | Delivery Order | ⏳ | `despatch_document_reference.id` | |
| L1 | Letters/Notes | ⏳ | `note[]` | From MSG in N9 loop |
| LI | Line Item Reference | ⏳ | `additional_document_references[+].id` | |
| OQ | Order Number | ⏳ | `order_reference.id` | |
| PD | Promotion/Deal | ⏳ | `additional_document_references[+].id` | |
| ZZ | Mutually Defined | ⏳ | `additional_document_references[+].id` | |

---

## Party Loop (N1) Mappings

### Party Qualifiers

| Qualifier | X12 Name | Status | Semantic Path | Notes |
|-----------|----------|--------|---------------|-------|
| BY | Buyer | ⏳ | `buyer_customer_party` | Same as BT often |
| BT | Bill To | ⏳ | `accounting_customer_party` | Primary |
| CA | Carrier | ⏳ | `delivery[0].shipment.carrier_party` | |
| PR | Payer | ⏳ | `buyer_customer_party` | |
| RE | Party to Receive | ⏳ | (future) | Rare |
| RI | Remit To | ⏳ | `payee_party` | |
| SE | Seller | ⏳ | `accounting_supplier_party` | Primary |
| SF | Ship From | ⏳ | `delivery[0].despatch.despatch_party` | |
| ST | Ship To | ⏳ | `delivery[0].delivery_location.party` | |
| SU | Supplier | ⏳ | `seller_supplier_party` | |

### N1 Loop Segment Mappings

| Segment | Element | Status | Semantic Path (relative to party) |
|---------|---------|--------|-----------------------------------|
| N1 | 02 | ⏳ | `party.party_names[0].name` |
| N1 | 03 | ⏳ | `party.party_identifications[0].id.scheme_id` |
| N1 | 04 | ⏳ | `party.party_identifications[0].id.value` |
| N2 | 01 | ⏳ | `party.party_names[1].name` |
| N2 | 02 | ⏳ | `party.party_names[2].name` |
| N3 | 01 | ⏳ | `party.postal_address.street_name` |
| N3 | 02 | ⏳ | `party.postal_address.additional_street_name` |
| N4 | 01 | ⏳ | `party.postal_address.city_name` |
| N4 | 02 | ⏳ | `party.postal_address.country_subentity` |
| N4 | 03 | ⏳ | `party.postal_address.postal_zone` |
| N4 | 04 | ⏳ | `party.postal_address.country_code` |
| PER | 02 | ⏳ | `party.contact.name` |
| PER | 03/04 | ⏳ | `party.contact.telephone` (TE qualifier) |
| PER | 05/06 | ⏳ | `party.contact.telefax` (FX qualifier) |
| PER | 07/08 | ⏳ | `party.contact.electronic_mail` (EM qualifier) |
| REF | (varies) | ⏳ | `party.party_identifications[+]` |
| DMG | 02 | ⏳ | (future) | Demographics |

### Header-Level PER Segments

Header-level PER segments (outside N1 loops) handled by `MappingEngine._map_header_per_segments()`:

| Qualifier | X12 Name | Semantic Path |
|-----------|----------|---------------|
| BD | Buyer Name/Dept | `accounting_customer_party.buyer_contact` |
| IC | Information Contact | `accounting_customer_party.buyer_contact` |
| OC | Order Contact | `accounting_customer_party.buyer_contact` |

---

## Line Item Loop (IT1) Mappings

### IT1 Segment

| Element | X12 Name | Status | Semantic Path | Notes |
|---------|----------|--------|---------------|-------|
| 01 | Line Number | ⏳ | `id` | |
| 02 | Quantity Invoiced | ⏳ | `invoiced_quantity.value` | PARSE_DECIMAL |
| 03 | Unit of Measure | ⏳ | `invoiced_quantity.unit_code` | Default: EA |
| 04 | Unit Price | ⏳ | `price.price_amount.value` | PARSE_DECIMAL |
| 05 | Basis of Unit Price | ⏳ | `price.base_quantity_unit_code` | |
| 06-25 | Product ID Pairs | ⏳ | See Product ID Mapping | |

### Product ID Qualifier Mapping

Handled by `MappingEngine._extract_it1_product_ids()`:

| Qualifier | Category | Semantic Field | Scheme ID |
|-----------|----------|----------------|-----------|
| UP | Standard | `item.standard_item_identification` | UPC |
| EN | Standard | `item.standard_item_identification` | EAN |
| UK | Standard | `item.standard_item_identification` | UCC/EAN-128 |
| UA | Standard | `item.standard_item_identification` | UPC-A |
| UI | Standard | `item.standard_item_identification` | UPC-I |
| VP, SK, VN | Seller | `item.sellers_item_identification` | (qualifier) |
| BP, IN | Buyer | `item.buyers_item_identification` | (qualifier) |
| MG, MN | Manufacturer | `item.manufacturers_item_identification` | (qualifier) |
| CB | Commodity Code | `item.commodity_classification.item_classification_code` | |
| PL | Price List Number | `price.price_list` | |
| Others | Additional | `item.additional_item_identifications[+]` | (qualifier) |

### IT1 Loop Sub-Segments

| Segment | Element | Status | Semantic Path | Notes |
|---------|---------|--------|---------------|-------|
| **CRC** | | ⏳ | (future) | Conditions |
| **QTY** | 02 | ⏳ | (alternate quantity) | |
| **CUR** | 02 | ⏳ | `price.price_amount.currency_code` | Line currency |
| **IT3** | | ⏳ | (future) | Additional info |
| **PID** | 04 | ⏳ | `item.additional_item_properties[0].name` | |
| **PID** | 05 | ⏳ | `item.description` | |
| **MEA** | 03 | ⏳ | `item.measurement_dimension[].measure.value` | |
| **MEA** | 04 | ⏳ | `item.measurement_dimension[].measure.unit_code` | |
| **CTP** | 02 | ⏳ | `price.price_type_code` | |
| **CTP** | 03 | ⏳ | `price.price_amount.value` (alternate) | |
| **PAM** | 02 | ⏳ | (future) | Period amounts |
| **REF** | (LI) | ⏳ | `order_line_references[0].line_id` | |
| **REF** | (PO) | ⏳ | `order_line_references[0].order_reference.id` | |
| **PER** | 02 | ⏳ | (future) | Line contact |
| **DTM** | (varies) | ⏳ | See Line-Level DTM | |
| **MSG** | 01 | ⏳ | `note[0]` | |
| **SDQ** | | ⏳ | (future) | Destination qty |
| **CAD** | | ⏳ | `delivery[0].shipment` | Line carrier |
| **L7** | | ⏳ | (future) | Tariff |

### Line-Level DTM Mappings

| Qualifier | X12 Name | Semantic Path |
|-----------|----------|---------------|
| 002 | Delivery Requested | `delivery[0].requested_delivery_period.start_date` |
| 011 | Shipped | `delivery[0].actual_delivery_date` |
| 017 | Estimated Delivery | `delivery[0].requested_delivery_period.end_date` |
| 035 | Delivered | `delivery[0].actual_delivery_date` |
| 050 | Received | (future) |

### SAC - Service, Promotion, Allowance, Charge (Line Level)

Handled by `MappingEngine._extract_line_sac_segments()`:

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| 01 | Allow/Charge Indicator | `allowance_charges[].charge_indicator` |
| 02 | Service/Allow/Charge Code | `allowance_charges[].allowance_charge_reason_code` |
| 03 | Agency Qualifier | (handled) |
| 04 | Agency Service Code | (handled) |
| 05 | Amount | `allowance_charges[].amount.value` |
| 06 | Allow/Charge % Qualifier | (handled) |
| 07 | Percent | `allowance_charges[].multiplier_factor_numeric` |
| 08 | Rate | `allowance_charges[].per_unit_amount.value` |
| 12 | Description | `allowance_charges[].allowance_charge_reason` |
| 13 | Reference ID Qualifier | (handled) |
| 14 | Reference ID | (handled) |
| 15 | Option Number | (future) |
| 16 | Quantity | `allowance_charges[].base_quantity.value` |

**SAC*01 Values:**
- `A` = Allowance → `charge_indicator = False`
- `C` = Charge → `charge_indicator = True`
- `N` = No Allowance/Charge → Skip
- `I` = Included → `charge_indicator = True` (informational)

### TXI - Tax Information (Line Level)

Handled by `MappingEngine._extract_line_txi_segments()`:

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| 01 | Tax Type Code | `tax_total[].tax_subtotal[].tax_category.id` |
| 02 | Monetary Amount | `tax_total[].tax_amount.value` |
| 03 | Percent | `tax_total[].tax_subtotal[].percent` |
| 04 | Tax Jurisdiction Code Qualifier | `tax_total[].tax_subtotal[].tax_category.tax_scheme.jurisdiction_region_address` |
| 05 | Tax Jurisdiction Code | (with above) |
| 06 | Exempt Code | `tax_total[].tax_subtotal[].tax_category.tax_exemption_reason_code` |

**TXI*01 Tax Type Codes:**
| Code | Description | UBL Category |
|------|-------------|--------------|
| CA | City Sales Tax | S |
| GS | Goods & Services Tax | S |
| LS | State & Local Sales Tax | S |
| PS | Provincial Sales Tax | S |
| SL | State Sales Tax | S |
| ST | State Tax | S |
| TX | All Taxes | S |
| VA | Value Added Tax | S |
| EX | Exempt | E |
| ZZ | Mutually Defined | S |

### SLN - Subline Item Detail

| Element | X12 Name | Status | Semantic Path | Notes |
|---------|----------|--------|---------------|-------|
| 01 | Subline Number | ⏳ | `sub_invoice_lines[].id` | |
| 02 | Configuration Code | ⏳ | (future) | |
| 03 | Relationship Code | ⏳ | (handled) | |
| 04 | Quantity | ⏳ | `sub_invoice_lines[].invoiced_quantity.value` | |
| 05 | Composite UOM | ⏳ | `sub_invoice_lines[].invoiced_quantity.unit_code` | |
| 06 | Unit Price | ⏳ | `sub_invoice_lines[].price.price_amount.value` | |
| 09-22 | Product ID Pairs | ⏳ | See Product ID Mapping | |

---

## Header-Level SAC Mappings

Handled by `MappingEngine._map_sac_segments()`:

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| 01 | Allow/Charge Indicator | `allowance_charges[].charge_indicator` |
| 02 | Service/Allow/Charge Code | `allowance_charges[].allowance_charge_reason_code` |
| 05 | Amount | `allowance_charges[].amount.value` |
| 07 | Percent | `allowance_charges[].multiplier_factor_numeric` |
| 12 | Description | `allowance_charges[].allowance_charge_reason` |

**Common SAC*02 Codes:**
| Code | Description |
|------|-------------|
| A310 | Assembly Charge |
| C310 | Discount |
| D170 | Destination Drayage |
| D240 | Freight |
| D340 | Fuel Surcharge |
| D500 | Handling |
| F050 | Fees |
| G830 | Insurance |
| H750 | Minimum Order |
| I430 | Pick-up Allowance |

---

## TXI - Tax Information (Header Level)

Handled by `MappingEngine._map_txi_segments()`:

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| 01 | Tax Type Code | `tax_total[].tax_subtotal[].tax_category.id` |
| 02 | Monetary Amount | `tax_total[].tax_amount.value` |
| 03 | Percent | `tax_total[].tax_subtotal[].percent` |
| 04 | Tax Jurisdiction Code Qualifier | (handled) |
| 05 | Tax Jurisdiction Code | `tax_total[].tax_subtotal[].tax_category.tax_scheme.id` |
| 06 | Exempt Code | `tax_total[].tax_subtotal[].tax_category.tax_exemption_reason_code` |

---

## MSG - Message Text

| Element | X12 Name | Status | Semantic Path |
|---------|----------|--------|---------------|
| 01 | Free Form Message | ⏳ | `note[]` |
| 02 | Printer Carriage Control | ⏳ | (handled) |

**Implementation:** Handled by `MappingEngine._map_msg_notes()` which finds MSG at:
- Header level (N9 loop)
- Line level (IT1 loop)

---

## Unmapped Data Tracking

The mapping engine tracks unmapped segments and elements for debugging and coverage analysis.

### Configuration

```python
engine = MappingEngine(
    INVOICE_810_MAPPING,
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
| BIG*08 | Transaction Set Purpose - structural |
| CUR*01 | Entity qualifier - routing only |
| CTT*02 | Hash total - validation only |
| TDS amounts | Already converted via total mapping |
| REF*03 | Description field (future enhancement) |

---

## Special Handler Methods

The `MappingEngine` needs these handlers for 810-specific scenarios:

| Method | Purpose | Status |
|--------|---------|--------|
| `_map_header_per_segments()` | Header-level PER*BD/IC/OC to contact | Existing (850) |
| `_map_fob_to_delivery()` | FOB*02/03/04 to delivery_terms | Existing (850) |
| `_map_cad_to_shipment()` | CAD to shipment carrier info | **NEW** |
| `_map_msg_notes()` | MSG to note[] at all levels | Existing (850) |
| `_map_tds_totals()` | TDS to monetary_total (cents conversion) | **NEW** |
| `_map_amt_totals()` | AMT to monetary_total (summary level) | Existing (850) |
| `_map_dtm_delivery()` | DTM*011/035 to delivery dates | **NEW** |
| `_map_sac_segments()` | Header SAC to allowance_charges | Existing (850) |
| `_map_txi_segments()` | TXI to tax_total | Existing (850) |
| `_extract_it1_product_ids()` | IT1*06-25 product ID pairs | **NEW** (similar to PO1) |
| `_extract_line_sac_segments()` | Line-level SAC | Existing (850) |
| `_extract_line_txi_segments()` | Line-level TXI | **NEW** |

---

## Transformation Functions

### New Transforms Required

```python
# TDS amounts are in cents
PARSE_CENTS = lambda v: Decimal(v) / Decimal("100") if v else None

# Transaction type code mapping
INVOICE_TYPE_MAP = {
    "": "380",      # Standard Invoice
    "CN": "381",    # Credit Invoice
    "CR": "381",    # Credit Memo
    "DI": "383",    # Debit Invoice
    "DR": "383",    # Debit Memo
    "SU": "385",    # Summary Invoice
}

MAP_INVOICE_TYPE = lambda v: INVOICE_TYPE_MAP.get(v or "", "380")
```

---

## Validation Rules

Defined in `mapping/x12/validations/invoice_rules.py`:

| Rule | Description |
|------|-------------|
| Required Fields | BIG*01 (issue_date), BIG*02 (id), TDS*01 (total) |
| Date Formats | YYYYMMDD or YYMMDD |
| Currency Codes | Must be ISO 4217 |
| TDS Amounts | Must be positive integers (cents) |
| Line Items | Each IT1 must have line number (IT1*01) |
| Party Minimum | At least SE (Seller) and BT (Bill To) required |

---

## Semantic Gaps Analysis

### X12 → Semantic (fields without direct equivalent)

| X12 Field | Issue | Workaround |
|-----------|-------|------------|
| BIG*08 | Transaction Set Purpose Code | Informational, not mapped |
| BIG*09 | Action Code | No semantic field |
| BAL | Balance Detail | Partial mapping to prepaid_payments |
| INC | Installment Information | No semantic equivalent |
| PAM | Period Amount | No direct mapping |
| LM/LQ | Code Source | No semantic equivalent |
| FA1/FA2 | Financial Accounting | No direct equivalent |
| V1/R4 | Vessel/Port | Specialized shipping only |
| PKG | Marking/Packaging | Limited support |
| SDQ | Destination Quantity | No semantic equivalent |

### Semantic → X12 (fields without X12 equivalent)

| Semantic Field | Issue |
|----------------|-------|
| `accounting_cost` | No direct X12 field |
| `tax_total.tax_subtotal` breakdown | X12 TXI is simpler |
| `prepaid_payment` | Limited to BAL segment |
| `payment_alternative_exchange_rate` | Complex FX handling |
| `invoice_period` | No standard segment |
| `customization_id` | UBL-specific |
| `profile_id` | UBL-specific |
| `withholding_tax_total` | Specialized, rarely used |

---

## Implementation Tasks

### Phase 1: Core Mapping (Priority: High)
- [ ] Create Invoice mapping definition (`invoice_810.py`)
- [ ] Add BIG segment mapping with type code transform
- [ ] Add TDS handling with cents conversion (`_map_tds_totals`)
- [ ] Add IT1 loop handler (similar to PO1)
- [ ] Add IT1 product ID extraction (`_extract_it1_product_ids`)
- [ ] Add N1 party loop mappings (reuse from 850)

### Phase 2: Dates & References (Priority: High)
- [ ] Add DTM qualified mappings
- [ ] Add REF qualified mappings
- [ ] Add N9 qualified mappings
- [ ] Add delivery date handling (`_map_dtm_delivery`)

### Phase 3: Financial Details (Priority: Medium)
- [ ] Add ITD payment terms mapping
- [ ] Add SAC header-level mapping
- [ ] Add SAC line-level mapping
- [ ] Add TXI tax mapping (header + line)
- [ ] Add AMT summary amounts

### Phase 4: Shipping Details (Priority: Medium)
- [ ] Add FOB mapping (reuse from 850)
- [ ] Add CAD carrier detail mapping (`_map_cad_to_shipment`)
- [ ] Add ISS shipment summary mapping
- [ ] Add header PER contact mapping

### Phase 5: Notes & Validation (Priority: Low)
- [ ] Add NTE note handling
- [ ] Add MSG note handling
- [ ] Add validation rules
- [ ] Add unmapped tracking

### Phase 6: Testing (Priority: High)
- [ ] Create comprehensive test fixture
- [ ] Add basic mapping tests
- [ ] Add snapshot tests
- [ ] Add edge case tests
- [ ] Add unmapped tracking tests

---

## Files to Create/Modify

| File | Changes |
|------|---------|
| `src/edi_schema/semantic/mapping/x12/invoice_810.py` | **CREATE** - Mapping definition |
| `src/edi_schema/semantic/mapping/x12/shared/parties.py` | **MODIFY** - Add INVOICE_PARTY_QUALIFIERS |
| `src/edi_schema/semantic/mapping/x12/validations/invoice_rules.py` | **CREATE** - Validation rules |
| `src/edi_schema/semantic/mapping/engine.py` | **MODIFY** - Add _map_tds_totals, _map_cad_to_shipment, etc. |
| `src/edi_schema/semantic/mapping/transforms.py` | **MODIFY** - Add PARSE_CENTS, MAP_INVOICE_TYPE |
| `tests/semantic/test_x12_invoice_mapper.py` | **CREATE** - Test suite |
| `tests/fixtures/x12_samples/logistics/810_invoice_comprehensive.x12` | **CREATE** - Full test fixture |

---

## Testing

### Test File
`tests/semantic/test_x12_invoice_mapper.py`

### Test Fixtures
- `tests/fixtures/x12_samples/logistics/810_invoice.x12` (existing, basic)
- `tests/fixtures/x12_samples/logistics/810_invoice_comprehensive.x12` (to create)

### Key Test Cases

| Test | Validates |
|------|-----------|
| `test_mapping_succeeds` | Basic mapping completion |
| `test_mapped_invoice_snapshot` | Full output structure |
| `test_invoice_basic_fields` | BIG segment mapping |
| `test_invoice_has_line_items` | IT1 loop mapping |
| `test_invoice_has_price` | Price/amount mapping |
| `test_invoice_type_code_mapping` | BIG*07 to UBL type |
| `test_tds_cents_conversion` | TDS amount parsing |
| `test_invoice_has_parties` | N1 loop parties |
| `test_product_id_with_scheme` | Product ID qualifier handling |
| `test_party_identifications_mapped` | N1*03/04 mapping |
| `test_payment_terms_mapped` | ITD mapping |
| `test_delivery_mapped` | CAD/ISS/DTM mapping |
| `test_tax_mapped` | TXI mapping |
| `test_allowance_charges_mapped` | SAC mapping |
| `test_contact_info_mapped` | PER mapping in N1 loop |
| `test_header_level_per_mapped` | Header PER*BD mapping |
| `test_unmapped_tracking_enabled` | Zero unmapped warnings |
| `test_unmapped_warnings_can_be_disabled` | Warning suppression |
| `test_metrics_contain_unmapped_summary` | Metrics structure |

### Running Tests

```bash
# All 810 mapping tests
pytest tests/semantic/test_x12_invoice_mapper.py -v

# Update snapshot
pytest tests/semantic/test_x12_invoice_mapper.py -v --snapshot-update
```

---

## Files Reference

| File | Purpose |
|------|---------|
| `src/edi_schema/semantic/mapping/x12/invoice_810.py` | Mapping definition |
| `src/edi_schema/semantic/mapping/engine.py` | Mapping engine with special handlers |
| `src/edi_schema/semantic/mapping/types.py` | Mapping type definitions |
| `src/edi_schema/semantic/mapping/transforms.py` | Value transforms (PARSE_DATE, etc.) |
| `src/edi_schema/semantic/mapping/errors.py` | Error codes |
| `src/edi_schema/semantic/mapping/diagnostics.py` | Metrics and tracking |
| `src/edi_schema/semantic/mapping/x12/shared/parties.py` | Party qualifier mappings |
| `src/edi_schema/semantic/mapping/x12/validations/invoice_rules.py` | Validation rules |
| `src/edi_schema/semantic/models/invoice.py` | Invoice semantic model |
| `src/edi_schema/x12/schemas/v005010/transaction_sets/ts_810_invoice.py` | X12 schema definition |
