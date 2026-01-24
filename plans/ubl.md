# UBL (Universal Business Language)

## Key Terms

### Data Model (CCTS-based)

**ABIE (Aggregate BIE)** - Complex container holding other BIEs
```xml
<cac:PostalAddress>        <!-- ABIE: Address -->
  <cbc:StreetName>...</cbc:StreetName>
  <cbc:CityName>...</cbc:CityName>
  <cac:Country>...</cac:Country>
</cac:PostalAddress>
```

**BBIE (Basic BIE)** - Leaf element holding actual data values
```xml
<cbc:StreetName>123 Main St</cbc:StreetName>   <!-- BBIE: text -->
<cbc:PostalZone>90210</cbc:PostalZone>         <!-- BBIE: code -->
<cbc:IssueDate>2024-01-15</cbc:IssueDate>      <!-- BBIE: date -->
<cbc:TaxAmount currencyID="USD">25.00</cbc:TaxAmount>  <!-- BBIE: amount -->
```

**ASBIE (Association BIE)** - Links one ABIE to another
```xml
<cac:Party>                    <!-- ABIE: Party -->
  <cac:PostalAddress>          <!-- ASBIE: Party -> Address -->
    <cbc:CityName>Boston</cbc:CityName>
  </cac:PostalAddress>
  <cac:Contact>                <!-- ASBIE: Party -> Contact -->
    <cbc:Name>John Smith</cbc:Name>
  </cac:Contact>
</cac:Party>
```

**Document structure**: Documents contain ABIEs, which contain BBIEs and ASBIEs
```
Invoice (Document)
├── cbc:ID                    (BBIE)
├── cbc:IssueDate             (BBIE)
├── cac:AccountingSupplierParty  (ASBIE -> Party ABIE)
│   └── cac:Party
│       ├── cbc:Name          (BBIE)
│       └── cac:PostalAddress (ASBIE -> Address ABIE)
└── cac:InvoiceLine           (ASBIE -> InvoiceLine ABIE)
    ├── cbc:LineID            (BBIE)
    └── cac:Item              (ASBIE -> Item ABIE)
```

### Schema Structure

| Schema | Prefix | Purpose |
|--------|--------|---------|
| CommonAggregateComponents | `cac:` | Reusable ABIEs (Address, Party, Item) |
| CommonBasicComponents | `cbc:` | Global BBIEs (ID, Name, Description) |
| UnqualifiedDataTypes | - | Base types (Amount, Code, Date, Identifier, Text) |
| QualifiedDataTypes | - | Constrained derivations of UDTs |
| Document Schemas | - | Complete documents (Invoice, Order) |

### Namespaces

**Component namespaces** (shared across all documents):
| Prefix | Schema | Purpose |
|--------|--------|---------|
| `cac:` | CommonAggregateComponents | Reusable ABIEs |
| `cbc:` | CommonBasicComponents | Reusable BBIEs |
| `ext:` | CommonExtensionComponents | Extension mechanism |
| `sig:` | CommonSignatureComponents | Digital signature support |
| `sac:` | SignatureAggregateComponents | Signature ABIEs |
| `sbc:` | SignatureBasicComponents | Signature BBIEs |

**Data type namespaces**: UnqualifiedDataTypes, QualifiedDataTypes

**Document namespaces**: Each document type has its own namespace (Invoice-2, Order-2, etc.)

### Document Types (101 total)

**Planning & Forecasting (6)**
- ExceptionCriteria, ExceptionNotification
- Forecast, ForecastRevision
- RetailEvent, TradeItemLocationProfile

**Pre-Award / Tendering (18)**
- CallForTenders, Tender, TenderReceipt, TenderContract
- TenderStatus, TenderStatusRequest, TenderWithdrawal
- TendererQualification, TendererQualificationResponse
- QualificationApplicationRequest, QualificationApplicationResponse
- ExpressionOfInterestRequest, ExpressionOfInterestResponse
- Enquiry, EnquiryResponse
- PriorInformationNotice, ContractNotice, ContractAwardNotice
- AwardedNotification, UnawardedNotification
- UnsubscribeFromProcedureRequest, UnsubscribeFromProcedureResponse

**Catalogue (5)**
- Catalogue, CatalogueRequest, CatalogueDeletion
- CatalogueItemSpecificationUpdate, CataloguePricingUpdate

**Quotation & Ordering (7)**
- RequestForQuotation, Quotation
- Order, OrderResponse, OrderResponseSimple
- OrderChange, OrderCancellation

**Inventory & VMI (4)**
- InventoryReport, StockAvailabilityReport
- ProductActivity, ItemInformationRequest

**Fulfillment / Despatch (6)**
- DespatchAdvice, ReceiptAdvice, DeliveryNote
- FulfilmentCancellation, PackingList, PurchaseReceipt

**Billing & Payment (11)**
- Invoice, CreditNote, DebitNote
- SelfBilledInvoice, SelfBilledCreditNote
- FreightInvoice, UtilityStatement
- Reminder, Statement, RemittanceAdvice
- InvoiceStatusRequest, InvoiceStatusResponse

**Transport - General (8)**
- ForwardingInstructions, BillOfLading, Waybill
- Manifest, PackingList, WeightStatement
- TransportationStatus, TransportationStatusRequest

**Transport - Intermodal (8)**
- TransportServiceDescriptionRequest, TransportServiceDescription
- TransportExecutionPlanRequest, TransportExecutionPlan
- GoodsItemItinerary, CommonTransportationReport
- TransportProgressStatus, TransportProgressStatusRequest

**Customs & Trade (10)**
- CertificateOfOrigin, GoodsCertificate, GuaranteeCertificate
- ExportCustomsDeclaration, ImportCustomsDeclaration, TransitCustomsDeclaration
- GoodsItemPassport
- ProofOfReexportation, ProofOfReexportationRequest, ProofOfReexportationReminder

**Returns (1)**
- InstructionForReturns

**Waste Management (2)**
- WasteMovement, WasteNotification

**Business Directory & Agreements (4)**
- BusinessCard, BusinessInformation
- DigitalAgreement, DigitalCapability

**General Purpose (4)**
- ApplicationResponse (generic ack/status for any document)
- AttachedDocument (wrapper for external documents)
- DocumentStatus, DocumentStatusRequest
- WorkReport (service reporting)

**Procurement Status (2)**
- ProcurementStatus, ProcurementStatusRequest

## Schema Files

UBL 2.5 provides:
- `xsd/maindoc/` - Document schemas (UBL-Invoice-2.5.xsd, etc.)
- `xsd/common/` - Shared component schemas
  - `UBL-CommonAggregateComponents-2.5.xsd`
  - `UBL-CommonBasicComponents-2.5.xsd`
  - `BDNDR-UnqualifiedDataTypes-1.1.xsd`
  - `UBL-QualifiedDataTypes-2.5.xsd`

## Schema Generation Strategy

### Source Files
- `mod/UBL-Entities-2.5.ods` - Master spreadsheet with full CCTS model
- `mod/summary/reports/UBL-{Doc}-2.5.html` - Per-document model views
- `mod/summary/reports/All-UBL-2.5-Documents.html` - Complete library

### Spreadsheet Columns (Section D.4)
| Col | Name | Purpose |
|-----|------|---------|
| A | Component Name | Element name |
| C | Cardinality | 0..1, 1, 0..n, 1..n |
| F | Definition | Semantic description |
| L | Object Class | Parent ABIE |
| Q | Representation Term | Data type (BBIE) or associated class (ASBIE) |
| S | Data Type | CCTS type for BBIEs |
| U | Associated Object Class | Target ABIE for ASBIEs |
| V | Component Type | ABIE, BBIE, or ASBIE |

### Generation Process
```
1. Parse UBL-Entities-2.5.ods
   ├── Extract ABIEs → reusable type definitions
   ├── Extract BBIEs → leaf properties with data types
   └── Extract ASBIEs → references to other ABIEs

2. Build Component Registry
   ├── CommonAggregateComponents: Party, Address, Item, Period...
   ├── CommonBasicComponents: ID, Name, Description, Amount...
   └── Document types: Invoice, Order, DespatchAdvice...

3. Map CCTS Types → JSON Schema
   ├── Amount.Type    → number + currencyID attr
   ├── Code.Type      → string + listID attr
   ├── Date.Type      → string, format: date
   ├── Identifier.Type → string + schemeID attr
   ├── Text.Type      → string + languageID attr
   └── Quantity.Type  → number + unitCode attr

4. Generate JSON Schemas
   ├── $defs for reusable ABIEs
   ├── required[] from cardinality 1 or 1..n
   ├── type: array for 0..n or 1..n
   └── $ref for ASBIE associations
```

### Example: Invoice JSON Schema
```json
{
  "$id": "ubl:Invoice-2",
  "type": "object",
  "required": ["ID", "IssueDate", "AccountingSupplierParty",
               "AccountingCustomerParty", "LegalMonetaryTotal", "InvoiceLine"],
  "properties": {
    "ID": { "$ref": "#/$defs/Identifier" },
    "IssueDate": { "$ref": "#/$defs/Date" },
    "InvoicePeriod": { "$ref": "#/$defs/Period" },
    "AccountingSupplierParty": { "$ref": "#/$defs/SupplierParty" },
    "InvoiceLine": {
      "type": "array",
      "items": { "$ref": "#/$defs/InvoiceLine" },
      "minItems": 1
    }
  },
  "$defs": {
    "Party": { "type": "object" },
    "Address": { "type": "object" },
    "Period": { "type": "object" }
  }
}
```

### Implementation Notes
- Parse ODS with `odfpy` or `pandas` (reads OpenDocument spreadsheets)
- BBIEs always come before ASBIEs within an ABIE (ordering matters in XML)
- Empty elements prohibited - every ASBIE must have at least one child
- Attributes (currencyID, unitCode, etc.) come from CCTS data type definitions

## X12 ↔ UBL Mapping

### Order-to-Cash / Procure-to-Pay Flow
```
X12:  850 ────→ 855 ────→ 856 ────→ 810 ────→ 820
UBL:  Order ──→ OrderResponse ──→ DespatchAdvice ──→ Invoice ──→ RemittanceAdvice
```

### Transaction Mapping

| X12 | Name | UBL Equivalent | Notes |
|-----|------|----------------|-------|
| **Ordering** |
| 850 | Purchase Order | Order | |
| 875 | Grocery PO | Order | grocery-specific |
| 855 | PO Acknowledgment | OrderResponse | |
| 860 | PO Change | OrderChange | |
| 860 | PO Cancellation | OrderCancellation | same X12, different use |
| **Fulfillment** |
| 856 | ASN / Ship Notice | DespatchAdvice | response to 850/830/862 |
| 945 | Warehouse Ship Advice | DespatchAdvice | |
| 943 | Stock Transfer Ship Advice | DespatchAdvice | transfer context |
| 944 | Stock Transfer Receipt | ReceiptAdvice | 3PL to seller |
| **Billing** |
| 810 | Invoice | Invoice | |
| 880 | Grocery Invoice | Invoice | grocery-specific |
| 812 | Debit/Credit Adjustment | CreditNote / DebitNote | |
| 820 | Payment Order/Remittance | RemittanceAdvice | |
| **Inventory** |
| 846 | Inventory Advice | InventoryReport | |
| **Warehouse** |
| 940 | Warehouse Ship Order | Order / ForwardingInstructions | warehouse context |
| **Transport** |
| 214 | Transport Carrier Status | TransportationStatus | carrier → shipper |
| **General** |
| 997 | Functional Ack | ApplicationResponse | generic ack |
| 816 | Address Listing | BusinessCard | party info |
| 864 | Text Message | AttachedDocument | free-form |

### Key Differences
- X12 uses separate transactions for grocery (875, 880); UBL uses same docs with different content
- X12 856 (ASN) combines ship notice + manifest; UBL has DespatchAdvice + Manifest separately
- X12 warehouse transactions (940, 943-945) map to standard UBL docs with context
- UBL has richer tendering/procurement docs not common in X12

## References

- [UBL 2.5 Spec](https://docs.oasis-open.org/ubl/UBL-2.5.html)
- [CCTS 2.01](http://www.unece.org/cefact/codesfortrade/ccts_index.html)