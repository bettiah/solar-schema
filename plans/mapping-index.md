# X12 to Semantic Model Mapping Index

This index provides an overview of all X12 transaction set mappings to semantic models.

---

## Implementation Status

| Status | Description |
|--------|-------------|
| **Implemented** | Mapping complete with tests |
| **Planning** | Mapping specification defined |
| **Not Started** | No mapping work done |

---

## Transaction Set Mappings

### Order-to-Cash

| X12 | Name | UBL/Semantic Model | Status | Plan |
|-----|------|-------------------|--------|------|
| **850** | Purchase Order | Order | **Implemented** | [850-mapping.md](850-mapping.md) |
| **855** | PO Acknowledgement | OrderResponse | Planning | [855-mapping.md](855-mapping.md) |
| **810** | Invoice | Invoice | Planning | [810-mapping.md](810-mapping.md) |
| **820** | Payment/Remittance | RemittanceAdvice | Planning | [820-mapping.md](820-mapping.md) |

### Fulfillment

| X12 | Name | UBL/Semantic Model | Status | Plan |
|-----|------|-------------------|--------|------|
| **856** | Advance Ship Notice | DespatchAdvice | Planning | [856-mapping.md](856-mapping.md) |
| **846** | Inventory Inquiry/Advice | InventoryReport | Planning | [846-mapping.md](846-mapping.md) |

### Transportation

| X12 | Name | UBL/Semantic Model | Status | Plan |
|-----|------|-------------------|--------|------|
| **204** | Load Tender | TransportExecutionPlanRequest | Planning | [204-mapping.md](204-mapping.md) |
| **210** | Freight Invoice | FreightInvoice | Planning | [210-mapping.md](210-mapping.md) |
| **211** | Bill of Lading | BillOfLading | Planning | [211-mapping.md](211-mapping.md) |
| **214** | Shipment Status | TransportationStatus | Planning | [214-mapping.md](214-mapping.md) |
| **990** | Load Tender Response | TransportExecutionPlan | Planning | [990-mapping.md](990-mapping.md) |

### Warehouse/3PL

| X12 | Name | UBL/Semantic Model | Status | Plan |
|-----|------|-------------------|--------|------|
| **940** | Warehouse Shipping Order | ForwardingInstructions | Planning | [940-mapping.md](940-mapping.md) |
| **945** | Warehouse Shipping Advice | DespatchAdvice | Planning | [945-mapping.md](945-mapping.md) |
| **947** | Inventory Adjustment | InventoryReport | Planning | [947-mapping.md](947-mapping.md) |

### Technical

| X12 | Name | UBL/Semantic Model | Status | Plan |
|-----|------|-------------------|--------|------|
| **997** | Functional Acknowledgement | ApplicationResponse | Planning | [997-mapping.md](997-mapping.md) |

---

## Common Mapping Patterns

### Party Qualifiers (N1*01)

| Qualifier | Meaning | Common Semantic Path |
|-----------|---------|---------------------|
| BY | Buyer | `buyer_customer_party` |
| SE | Seller | `seller_supplier_party` |
| ST | Ship To | `delivery[].delivery_party` |
| SF | Ship From | `despatch.despatch_party` |
| BT | Bill To | `accounting_customer_party` |
| RI | Remit To | `payee_party` |
| CA | Carrier | `carrier_party` |
| WH | Warehouse | `freight_forwarder_party` |

### Date Qualifiers (DTM*01)

| Qualifier | Meaning | Common Semantic Path |
|-----------|---------|---------------------|
| 002 | Delivery Requested | `delivery[].requested_delivery_period.start_date` |
| 010 | Ship Date | `despatch.requested_despatch_date` |
| 011 | Shipped | `despatch.actual_despatch_date` |
| 017 | Estimated Delivery | `delivery[].estimated_delivery_date` |
| 035 | Delivered | `delivery[].actual_delivery_date` |
| 037 | Ship Not Before | `despatch.earliest_despatch_date` |
| 038 | Ship No Later | `delivery[].latest_delivery_date` |

### Reference Qualifiers (REF*01)

| Qualifier | Meaning | Common Semantic Path |
|-----------|---------|---------------------|
| BM | Bill of Lading | `despatch_document_reference.id` |
| CT | Contract | `contract_document_reference.id` |
| IV | Invoice | `invoice_document_reference.id` |
| PO | Purchase Order | `order_reference.id` |
| VN | Vendor Number | `seller_supplier_party.party_identifications[].id` |

### Product ID Qualifiers (LIN*02, PO1*06, etc.)

| Qualifier | Meaning | Semantic Field |
|-----------|---------|----------------|
| UP | UPC | `standard_item_identification` (scheme="UPC") |
| EN | EAN | `standard_item_identification` (scheme="EAN") |
| VP | Vendor Part | `sellers_item_identification` |
| BP | Buyer Part | `buyers_item_identification` |
| MG | Manufacturer | `manufacturers_item_identification` |

---

## Data Type Conversions

### Date/Time

| X12 Format | Semantic Format |
|------------|-----------------|
| CCYYMMDD | `date` (YYYY-MM-DD) |
| YYMMDD | `date` (20YY-MM-DD) |
| HHMM | `time` (HH:MM:00) |
| HHMMSS | `time` (HH:MM:SS) |

### Amounts

| X12 Format | Semantic Format |
|------------|-----------------|
| Integer (implied decimal) | `Decimal` |
| Cents (TDS segment) | `Decimal` / 100 |

### Units of Measure

X12 uses ANSI codes; semantic models use UN/ECE Rec 20. Most codes are identical (EA, CA, LB, KG).

---

## Implementation Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        X12 Document                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    X12 Parser (AST)                             │
│              src/edi_schema/x12/parser.py                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Mapping Engine                               │
│           src/edi_schema/semantic/mapping/engine.py             │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              Transaction Mapping Definition              │   │
│   │         (e.g., order_850.py, invoice_810.py)            │   │
│   └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Semantic Model                              │
│             src/edi_schema/semantic/models/                     │
│                                                                 │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐          │
│   │  Order  │  │ Invoice │  │Despatch │  │   ...   │          │
│   └─────────┘  └─────────┘  └─────────┘  └─────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Priority Order for Implementation

### High Priority (Core Order-to-Cash)
1. ~~850 Purchase Order~~ ✅ Implemented
2. 855 PO Acknowledgement
3. 856 ASN
4. 810 Invoice

### Medium Priority (Logistics)
5. 214 Shipment Status
6. 204 Load Tender
7. 990 Load Tender Response

### Lower Priority (Warehouse/Financial)
8. 940 Warehouse Shipping Order
9. 945 Warehouse Shipping Advice
10. 820 Payment/Remittance
11. 846 Inventory

### Technical
12. 997 Functional Acknowledgement

---

## Related Documentation

- [X12 Parser](../src/edi_schema/x12/parser.py)
- [Mapping Engine](../src/edi_schema/semantic/mapping/engine.py)
- [Semantic Models](../src/edi_schema/semantic/models/)
- [X12 Plan](x12_plan.md)
- [UBL Plan](ubl_plan.md)
