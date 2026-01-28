# X12 810 Invoice Mapping

## Overview

Maps X12 810 Invoice to UBL Invoice semantic model.

**Status:** Planning
**X12 Transaction:** 810 - Invoice
**UBL Document:** Invoice

---

## Header Level Mappings

| X12 Segment | Element | X12 Name | Semantic Path | Notes |
|-------------|---------|----------|---------------|-------|
| **BIG** | 01 | Invoice Date | `issue_date` | |
| BIG | 02 | Invoice Number | `id` | |
| BIG | 03 | PO Date | `order_reference.issue_date` | |
| BIG | 04 | PO Number | `order_reference.id` | |
| BIG | 07 | Transaction Type Code | `invoice_type_code` | |
| **CUR** | 02 | Currency Code | `document_currency_code` | ISO 4217 |
| **REF** | (varies) | Reference | `additional_document_references[+].id` | |
| REF | (BM) | Bill of Lading | `despatch_document_reference.id` | |
| **ITD** | 05 | Discount % | `payment_terms[0].settlement_discount_percent` | |
| ITD | 07 | Net Days | `payment_terms[0].settlement_period_days` | |
| ITD | 12 | Description | `payment_terms[0].note` | |
| **DTM** | (003) | Ship Date | `delivery[0].actual_delivery_date` | |

---

## Party Mappings (N1 Loop)

| Qualifier | X12 Name | Semantic Path |
|-----------|----------|---------------|
| BY | Buyer | `accounting_customer_party` |
| SE | Seller | `accounting_supplier_party` |
| ST | Ship To | `delivery[0].delivery_location` |
| RI | Remit To | `payee_party` |

### N1 Loop Field Mappings

| Segment | Element | Semantic Path (relative) |
|---------|---------|--------------------------|
| N1 | 02 | `party.party_names[0].name` |
| N1 | 03 | `party.party_identifications[0].id.scheme_id` |
| N1 | 04 | `party.party_identifications[0].id.value` |
| N3 | 01 | `party.postal_address.street_name` |
| N3 | 02 | `party.postal_address.additional_street_name` |
| N4 | 01 | `party.postal_address.city_name` |
| N4 | 02 | `party.postal_address.country_subentity` |
| N4 | 03 | `party.postal_address.postal_zone` |
| N4 | 04 | `party.postal_address.country_code` |

---

## Line Item Mappings (IT1 Loop)

| Segment | Element | X12 Name | Semantic Path |
|---------|---------|----------|---------------|
| **IT1** | 01 | Line Number | `id` |
| IT1 | 02 | Quantity Invoiced | `invoiced_quantity.value` |
| IT1 | 03 | Unit of Measure | `invoiced_quantity.unit_code` |
| IT1 | 04 | Unit Price | `price.price_amount.value` |
| IT1 | 06-25 | Product IDs | `item.*_item_identification` |
| **PID** | 05 | Description | `item.description` |
| **SAC** | 01 | Allow/Charge Ind | `allowance_charges[].charge_indicator` |
| SAC | 05 | Amount | `allowance_charges[].amount.value` |
| SAC | 12 | Description | `allowance_charges[].allowance_charge_reason` |
| **TXI** | 01 | Tax Type Code | `tax_total[].tax_subtotal[].tax_category.id` |
| TXI | 02 | Tax Amount | `tax_total[].tax_amount.value` |
| TXI | 03 | Tax Percent | `tax_total[].tax_subtotal[].percent` |

---

## Summary Segment Mappings

| Segment | Element | X12 Name | Semantic Path | Notes |
|---------|---------|----------|---------------|-------|
| **TDS** | 01 | Total Invoice Amount | `legal_monetary_total.tax_inclusive_amount.value` | In cents |
| **CAD** | - | Carrier Detail | `delivery[0].shipment` | Freight info |
| **ISS** | 01 | Units Shipped | `delivery[0].quantity.value` | |
| ISS | 02 | Unit of Measure | `delivery[0].quantity.unit_code` | |
| **CTT** | 01 | Line Count | `line_count` | |

---

## Semantic Gaps

### X12 → Semantic (fields without direct equivalent)
- TDS amounts in cents - need decimal conversion
- BIG07 transaction type codes need mapping to InvoiceTypeCode
- Tax handling differs significantly

### Semantic → X12 (fields without X12 equivalent)
- `accounting_cost` - no direct X12 field
- `tax_total.tax_subtotal` breakdown - X12 TXI is simpler
- `prepaid_payment` - no X12 equivalent
- `payment_alternative_exchange_rate` - complex FX handling

---

## Implementation Tasks

- [ ] Create Invoice semantic model
- [ ] Create 810 mapping definition
- [ ] Add IT1 loop handler
- [ ] Add TDS decimal conversion (cents to decimal)
- [ ] Add TXI tax mapping
- [ ] Add tests with fixture files

---

## Files to Create/Modify

| File | Changes |
|------|---------|
| `models/invoice.py` | Create Invoice semantic model |
| `mapping/x12/invoice_810.py` | Create mapping definition |
| `mapping/engine.py` | Add invoice-specific handlers if needed |
| `tests/semantic/test_x12_invoice_mapper.py` | Add tests |
