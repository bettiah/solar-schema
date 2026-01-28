# X12 820 Payment Order/Remittance Advice Mapping

## Overview

Maps X12 820 Payment Order/Remittance Advice to UBL RemittanceAdvice semantic model.

**Status:** Planning
**X12 Transaction:** 820 - Payment Order/Remittance Advice
**UBL Document:** RemittanceAdvice

---

## Header Level Mappings

| X12 Segment | Element | X12 Name | Semantic Path | Notes |
|-------------|---------|----------|---------------|-------|
| **BPR** | 01 | Transaction Handling | `payment_means.payment_means_code` | ACH, CHK, etc. |
| BPR | 02 | Amount | `total_payment_amount.value` | |
| BPR | 03 | Credit/Debit Flag | `payment_means.payment_channel_code` | C=Credit, D=Debit |
| BPR | 04 | Payment Method | `payment_means.payment_means_code` | |
| BPR | 05 | Payment Format | `payment_means.payment_channel_code` | |
| BPR | 06 | DFI ID Qualifier (Payer) | `payer_financial_account.financial_institution_branch.id.scheme_id` | |
| BPR | 07 | DFI ID (Payer) | `payer_financial_account.financial_institution_branch.id.value` | Bank routing |
| BPR | 09 | Account Number (Payer) | `payer_financial_account.id` | |
| BPR | 12 | DFI ID Qualifier (Payee) | `payee_financial_account.financial_institution_branch.id.scheme_id` | |
| BPR | 13 | DFI ID (Payee) | `payee_financial_account.financial_institution_branch.id.value` | |
| BPR | 15 | Account Number (Payee) | `payee_financial_account.id` | |
| BPR | 16 | Payment Date | `payment_due_date` | |
| **TRN** | 01 | Trace Type | `id_scheme` | |
| TRN | 02 | Reference ID | `id` | Payment reference |
| TRN | 03 | Originator ID | `payer_party.party_identifications[0].id.value` | |
| **CUR** | 02 | Currency Code | `document_currency_code` | |
| **REF** | (CK) | Check Number | `payment_means.payment_id` | |
| **DTM** | 01 | Date Qualifier | (determines field) | |
| DTM | 02 | Date | `issue_date` or `payment_due_date` | |

---

## Party Mappings (N1 Loop)

| Qualifier | X12 Name | Semantic Path |
|-----------|----------|---------------|
| PR | Payer | `payer_party` |
| PE | Payee | `payee_party` |
| RM | Remit To | `payee_party` (alternate) |

---

## Payment Detail Mappings (ENT/RMR Loop)

The ENT segment groups remittance detail, and RMR provides invoice-level detail:

### ENT - Entity

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| ENT*01 | Assigned Number | `remittance_advice_line.id` |
| ENT*02 | Entity ID Code | (grouping type) |

### RMR - Remittance Advice

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| RMR*01 | Reference ID Qualifier | `remittance_advice_line.billing_reference.document_type_code` | IV=Invoice |
| RMR*02 | Reference ID | `remittance_advice_line.billing_reference.id` | Invoice number |
| RMR*03 | Payment Action Code | `remittance_advice_line.payment_status` | PA=Paid in Full |
| RMR*04 | Amount Paid | `remittance_advice_line.paid_amount.value` | |
| RMR*05 | Amount Billed | `remittance_advice_line.billing_reference.document_description` | Original amount |
| RMR*06 | Amount Claimed | `remittance_advice_line.debit_line_amount.value` | |
| RMR*07 | Discount Amount | `remittance_advice_line.credit_line_amount.value` | |

### REF - Reference (within ENT loop)

| Qualifier | X12 Name | Semantic Path |
|-----------|----------|---------------|
| PO | PO Number | `remittance_advice_line.billing_reference.order_reference.id` |
| BM | Bill of Lading | `remittance_advice_line.billing_reference.despatch_document_reference.id` |

### ADX - Adjustment

| Element | X12 Name | Semantic Path |
|---------|----------|---------------|
| ADX*01 | Adjustment Amount | `remittance_advice_line.debit_line_amount.value` | |
| ADX*02 | Adjustment Reason | `remittance_advice_line.payment_terms.note` | |
| ADX*03 | Reference ID Qualifier | (describes what) | |
| ADX*04 | Reference ID | `remittance_advice_line.document_reference.id` | |

---

## Payment Action Code Mapping

| X12 Code | Meaning | Semantic Status |
|----------|---------|-----------------|
| PA | Paid in Full | `PAID` |
| PP | Partial Payment | `PARTIAL` |
| PR | Payment Refused | `REFUSED` |
| NS | Not Scheduled | `PENDING` |
| CS | Credit/Debit | `ADJUSTED` |

---

## Adjustment Reason Code Mapping

Common adjustment codes in ADX*02:

| X12 Code | Meaning |
|----------|---------|
| 01 | Price Difference |
| 02 | Damaged Goods |
| 03 | Short Shipment |
| 04 | Returned Goods |
| 05 | Discount Taken |
| 06 | Freight Allowance |
| 07 | Advertising Allowance |

---

## Implementation Complexity

1. **BPR Financial Data** - Contains bank routing and account information
2. **Multi-Invoice Payments** - Single 820 can pay multiple invoices
3. **Adjustments** - ADX segments can modify amounts with reasons
4. **ENT Grouping** - Entities can group related invoices

---

## Implementation Tasks

- [ ] Create RemittanceAdvice semantic model
- [ ] Create 820 mapping definition
- [ ] Add BPR financial account mapping
- [ ] Add ENT/RMR loop handler
- [ ] Add ADX adjustment handler
- [ ] Add tests with fixture files

---

## Files to Create/Modify

| File | Changes |
|------|---------|
| `models/remittance_advice.py` | Create RemittanceAdvice semantic model |
| `mapping/x12/remittance_820.py` | Create mapping definition |
| `mapping/engine.py` | Add ENT/RMR/ADX handlers |
| `tests/semantic/test_x12_remittance_mapper.py` | Add tests |
