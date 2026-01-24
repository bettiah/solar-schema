# X12 ↔ UBL Field Mapping

This document provides semantic field-level mappings between X12 transaction sets and UBL documents.

## 850 Purchase Order ↔ UBL Order

### Header Level

| X12 Segment | X12 Element | X12 Name | UBL Path | UBL Element | Notes |
|-------------|-------------|----------|----------|-------------|-------|
| **BEG** | | Beginning Segment | | | |
| BEG | 01 (353) | Transaction Set Purpose Code | Order | OrderTypeCode | 00=Original, 05=Replace |
| BEG | 02 (92) | Purchase Order Type Code | Order | OrderTypeCode | Combined with BEG01 |
| BEG | 03 (324) | Purchase Order Number | Order | ID | Primary identifier |
| BEG | 04 (328) | Release Number | Order | SalesOrderID | Blanket PO release |
| BEG | 05 (373) | Date | Order | IssueDate | PO date |
| BEG | 06 (367) | Contract Number | Order/Contract | ID | |
| **CUR** | | Currency | | | |
| CUR | 01 (98) | Entity ID Code | - | - | Identifies whose currency |
| CUR | 02 (100) | Currency Code | Order | DocumentCurrencyCode | ISO 4217 |
| **REF** | | Reference | Order | AdditionalDocumentReference | Repeating |
| REF | 01 (128) | Reference ID Qualifier | AdditionalDocumentReference | DocumentTypeCode | |
| REF | 02 (127) | Reference ID | AdditionalDocumentReference | ID | |
| **DTM** | | Date/Time | | | |
| DTM | 01 (374) | Date/Time Qualifier | - | - | Determines target field |
| DTM | 02 (373) | Date | Order/ValidityPeriod | StartDate/EndDate | Qualifier-dependent |
| DTM (002) | | Requested Delivery | OrderLine/Delivery | RequestedDeliveryPeriod | |
| **PER** | | Contact | | | |
| PER | 01 (366) | Contact Function Code | Party/Contact | - | BY=Buyer, SE=Seller |
| PER | 02 (93) | Name | Contact | Name | |
| PER | 03 (365) | Comm Number Qualifier | Contact/Telephone or ElectronicMail | - | TE=Phone, EM=Email |
| PER | 04 (364) | Communication Number | Contact | Telephone / ElectronicMail | |
| **FOB** | | Shipping Terms | Order | DeliveryTerms | |
| FOB | 01 (146) | Shipment Method of Payment | DeliveryTerms | ID | CC=Collect, PP=Prepaid |
| FOB | 02 (309) | Location Qualifier | DeliveryTerms/DeliveryLocation | - | |
| FOB | 05 (335) | Transportation Terms Code | DeliveryTerms | SpecialTerms | FOB, CIF, etc. |
| **ITD** | | Payment Terms | Order | PaymentTerms | |
| ITD | 01 (336) | Terms Type Code | PaymentTerms | - | |
| ITD | 05 (351) | Terms Discount Percent | PaymentTerms/SettlementDiscountPercent | Percent | |
| ITD | 06 (446) | Terms Discount Due Date | PaymentTerms | SettlementPeriod | |
| ITD | 07 (386) | Terms Net Days | PaymentTerms/PaymentDueDate | - | Calculate from issue date |
| ITD | 12 (352) | Description | PaymentTerms | Note | |

### Party Identification (N1 Loop)

| X12 Segment | X12 Element | X12 Name | UBL Path | UBL Element | Notes |
|-------------|-------------|----------|----------|-------------|-------|
| **N1** | | Party Identification | | | N101 determines party role |
| N1 (BY) | | Buyer | Order | BuyerCustomerParty/Party | |
| N1 (SE) | | Seller | Order | SellerSupplierParty/Party | |
| N1 (ST) | | Ship To | Order | Delivery/DeliveryLocation | |
| N1 (BT) | | Bill To | Order | AccountingCustomerParty | |
| N1 | 02 (93) | Name | Party/PartyName | Name | |
| N1 | 03 (66) | ID Code Qualifier | Party/PartyIdentification | - | 1=DUNS, 9=DUNS+4 |
| N1 | 04 (67) | ID Code | Party/PartyIdentification | ID | |
| **N2** | | Additional Name | Party/PartyName | Name | 2nd line |
| **N3** | | Address | Party/PostalAddress | | |
| N3 | 01 (166) | Address Line 1 | PostalAddress | StreetName | |
| N3 | 02 (166) | Address Line 2 | PostalAddress | AdditionalStreetName | |
| **N4** | | Geographic Location | Party/PostalAddress | | |
| N4 | 01 (19) | City | PostalAddress | CityName | |
| N4 | 02 (156) | State | PostalAddress | CountrySubentity | |
| N4 | 03 (116) | Postal Code | PostalAddress | PostalZone | |
| N4 | 04 (26) | Country Code | PostalAddress/Country | IdentificationCode | ISO 3166 |

### Line Item (PO1 Loop)

| X12 Segment | X12 Element | X12 Name | UBL Path | UBL Element | Notes |
|-------------|-------------|----------|----------|-------------|-------|
| **PO1** | | Baseline Item Data | Order | OrderLine | |
| PO1 | 01 (350) | Assigned Identification | OrderLine | ID | Line number |
| PO1 | 02 (380) | Quantity Ordered | LineItem | Quantity | |
| PO1 | 03 (355) | Unit of Measure | LineItem/Quantity | @unitCode | UN/ECE Rec 20 |
| PO1 | 04 (212) | Unit Price | LineItem/Price | PriceAmount | |
| PO1 | 05 (639) | Basis of Unit Price | LineItem/Price | BaseQuantity | |
| PO1 | 06-25 | Product ID Qualifier/Value | LineItem/Item | | Pairs: qualifier + value |
| PO1 | 06 (235)=UP | UPC | Item/StandardItemIdentification | ID (schemeID="UPC") | |
| PO1 | 06 (235)=VP | Vendor Part | Item/SellersItemIdentification | ID | |
| PO1 | 06 (235)=BP | Buyer Part | Item/BuyersItemIdentification | ID | |
| PO1 | 06 (235)=SK | SKU | Item/SellersItemIdentification | ID | |
| **PID** | | Product Description | LineItem/Item | | |
| PID | 05 (352) | Description | Item | Description | |
| PID | 04 (349) | Product Characteristic Code | Item/AdditionalItemProperty | Name | |
| **SAC** | | Service/Allowance/Charge | OrderLine | AllowanceCharge | |
| SAC | 01 (248) | Allow/Charge Indicator | AllowanceCharge | ChargeIndicator | A=false, C=true |
| SAC | 05 (610) | Amount | AllowanceCharge | Amount | |
| SAC | 12 (331) | Charge/Allow Description | AllowanceCharge | AllowanceChargeReason | |
| **CTT** | | Transaction Totals | Order | LineCountNumeric | |
| CTT | 01 (354) | Number of Line Items | Order | LineCountNumeric | |

### Semantic Gaps

**X12 → UBL (fields without direct UBL equivalent):**
- BEG08: Acknowledgment Type - UBL handles via separate OrderResponse
- N1 entity codes beyond BY/SE/ST - need mapping table

**UBL → X12 (UBL fields without X12 equivalent):**
- Order.UUID - no standard X12 UUID field
- Order.Note - use MSG segment
- Order.TaxTotal - X12 uses TAX segment differently
- DeliveryTerms.Incoterms - partial via FOB
- Item.CommodityClassification - partial via LIN segment

---

## 856 ASN ↔ UBL DespatchAdvice

### Header Level

| X12 Segment | X12 Element | X12 Name | UBL Path | UBL Element | Notes |
|-------------|-------------|----------|----------|-------------|-------|
| **BSN** | | Beginning Segment | | | |
| BSN | 01 (353) | Transaction Set Purpose Code | DespatchAdvice | - | 00=Original |
| BSN | 02 (396) | Shipment ID | DespatchAdvice | ID | |
| BSN | 03 (373) | Date | DespatchAdvice | IssueDate | |
| BSN | 04 (337) | Time | DespatchAdvice | IssueTime | |
| BSN | 05 (1005) | Hierarchical Structure Code | - | - | X12-specific |
| **DTM** | | Date/Time Reference | | | |
| DTM (011) | | Shipped Date | Shipment | ActualDespatchDate | |
| DTM (017) | | Est. Delivery Date | Shipment | EstimatedDeliveryPeriod | |
| **REF** | | Reference | DespatchAdvice | OrderReference | |
| REF (PO) | 02 | Purchase Order Number | OrderReference | ID | |
| REF (BM) | 02 | Bill of Lading | Shipment | ID | |

### Shipment Level (HL Loop - S)

| X12 Segment | X12 Element | X12 Name | UBL Path | UBL Element | Notes |
|-------------|-------------|----------|----------|-------------|-------|
| **TD1** | | Carrier Details | Shipment | | |
| TD1 | 01 (103) | Packaging Code | TransportHandlingUnit | TransportHandlingUnitTypeCode | |
| TD1 | 02 (80) | Lading Quantity | Shipment | TotalTransportHandlingUnitQuantity | |
| TD1 | 06 (187) | Weight Qualifier | Shipment/GrossWeightMeasure | - | |
| TD1 | 07 (81) | Weight | Shipment | GrossWeightMeasure | |
| TD1 | 08 (355) | Unit of Measure | GrossWeightMeasure | @unitCode | |
| **TD5** | | Carrier Details | Shipment/ShipmentStage | | |
| TD5 | 02 (133) | ID Code Qualifier | CarrierParty/PartyIdentification | - | SCAC |
| TD5 | 03 (2) | Carrier ID | CarrierParty/PartyIdentification | ID | |
| TD5 | 04 (66) | Transport Method Code | TransportMeans | TransportMeansTypeCode | |
| TD5 | 05 (387) | Routing | TransportMeans | - | |
| **TD3** | | Carrier Equipment | TransportEquipment | | |
| TD3 | 01 (40) | Equipment Type Code | TransportEquipment | TransportEquipmentTypeCode | |
| TD3 | 03 (207) | Equipment Number | TransportEquipment | ID | |
| **N1/N3/N4** | | Ship From/To | | | Same as 850 |
| N1 (SF) | | Ship From | Shipment | ShipperParty | |
| N1 (ST) | | Ship To | Shipment | DeliveryAddress | |

### Order/Pack/Item Levels (HL Loop - O/P/I)

| X12 Segment | X12 Element | X12 Name | UBL Path | UBL Element | Notes |
|-------------|-------------|----------|----------|-------------|-------|
| **HL** | | Hierarchical Level | | | Defines structure |
| HL | 03='O' | Order Level | DespatchLine | OrderLineReference | |
| HL | 03='P' | Pack Level | TransportHandlingUnit | | |
| HL | 03='I' | Item Level | DespatchLine/Item | | |
| **PRF** | | Purchase Order Reference | DespatchLine | OrderLineReference | |
| PRF | 01 (324) | PO Number | OrderLineReference/OrderReference | ID | |
| PRF | 04 (373) | PO Date | OrderLineReference/OrderReference | IssueDate | |
| **MAN** | | Marks and Numbers | TransportHandlingUnit | | |
| MAN | 01 (88) | Marks/Numbers Qualifier | - | - | GM=SSCC-18 |
| MAN | 02 (87) | Marks/Numbers | TransportHandlingUnit | ID | SSCC barcode |
| **LIN** | | Item Identification | DespatchLine/Item | | |
| LIN | 01 (350) | Assigned ID | DespatchLine | ID | |
| LIN | 02 (235) | Product ID Qualifier | Item/*ItemIdentification | - | |
| LIN | 03 (234) | Product ID | Item | ID | |
| **SN1** | | Item Detail | DespatchLine | | |
| SN1 | 02 (382) | Shipped Quantity | DespatchLine | DeliveredQuantity | |
| SN1 | 03 (355) | Unit of Measure | DeliveredQuantity | @unitCode | |
| **PID** | | Product Description | Item | Description | Same as 850 |

### Semantic Gaps

**X12 → UBL:**
- HL hierarchical structure - UBL uses flat DespatchLine with nesting via references
- Multiple tracking numbers per shipment - X12 REF loop vs UBL single Shipment.ID

**UBL → X12:**
- DespatchAdvice.DespatchSupplierParty - map to N1*SF
- EstimatedDespatchPeriod - no direct X12 equivalent

---

## 810 Invoice ↔ UBL Invoice

### Header Level

| X12 Segment | X12 Element | X12 Name | UBL Path | UBL Element | Notes |
|-------------|-------------|----------|----------|-------------|-------|
| **BIG** | | Beginning Invoice | | | |
| BIG | 01 (373) | Invoice Date | Invoice | IssueDate | |
| BIG | 02 (76) | Invoice Number | Invoice | ID | |
| BIG | 03 (373) | PO Date | Invoice/OrderReference | IssueDate | |
| BIG | 04 (324) | PO Number | Invoice/OrderReference | ID | |
| BIG | 07 (640) | Transaction Type Code | Invoice | InvoiceTypeCode | |
| **CUR** | | Currency | Invoice | DocumentCurrencyCode | Same as 850 |
| **REF** | | Reference | Invoice | AdditionalDocumentReference | Same as 850 |
| REF (BM) | | Bill of Lading | DespatchDocumentReference | ID | |
| **ITD** | | Payment Terms | Invoice | PaymentTerms | Same as 850 |
| **DTM** | | Date/Time | | | |
| DTM (003) | | Ship Date | Invoice/Delivery | ActualDeliveryDate | |

### Party Identification (N1 Loop)

| X12 Segment | X12 Element | X12 Name | UBL Path | UBL Element | Notes |
|-------------|-------------|----------|----------|-------------|-------|
| N1 (BY) | | Buyer | Invoice | AccountingCustomerParty | |
| N1 (SE) | | Seller | Invoice | AccountingSupplierParty | |
| N1 (ST) | | Ship To | Invoice | Delivery/DeliveryLocation | |
| N1 (RI) | | Remit To | Invoice | PayeeParty | |

### Line Item (IT1 Loop)

| X12 Segment | X12 Element | X12 Name | UBL Path | UBL Element | Notes |
|-------------|-------------|----------|----------|-------------|-------|
| **IT1** | | Baseline Item Data | Invoice | InvoiceLine | |
| IT1 | 01 (350) | Line Number | InvoiceLine | ID | |
| IT1 | 02 (358) | Quantity Invoiced | InvoiceLine | InvoicedQuantity | |
| IT1 | 03 (355) | Unit of Measure | InvoicedQuantity | @unitCode | |
| IT1 | 04 (212) | Unit Price | InvoiceLine/Price | PriceAmount | |
| IT1 | 06-25 | Product IDs | Item | *ItemIdentification | Same pattern as PO1 |
| **PID** | | Product Description | Item | Description | Same as 850 |
| **SAC** | | Service/Allowance/Charge | InvoiceLine | AllowanceCharge | Same as 850 |
| **TXI** | | Tax Information | InvoiceLine | TaxTotal | |
| TXI | 01 (963) | Tax Type Code | TaxCategory | ID | |
| TXI | 02 (782) | Tax Amount | TaxTotal | TaxAmount | |
| TXI | 03 (954) | Tax Percent | TaxCategory | Percent | |

### Summary (TDS/CAD/ISS)

| X12 Segment | X12 Element | X12 Name | UBL Path | UBL Element | Notes |
|-------------|-------------|----------|----------|-------------|-------|
| **TDS** | | Total Monetary Value | Invoice | LegalMonetaryTotal | |
| TDS | 01 (610) | Total Invoice Amount | LegalMonetaryTotal | TaxInclusiveAmount | In cents |
| **CAD** | | Carrier Detail | Invoice/Delivery | - | Freight info |
| **ISS** | | Invoice Ship Summary | Invoice/Delivery | - | |
| ISS | 01 (380) | Number of Units Shipped | Delivery | Quantity | |
| ISS | 02 (355) | Unit of Measure | Delivery/Quantity | @unitCode | |
| **CTT** | | Transaction Totals | Invoice | | |
| CTT | 01 (354) | Number of Line Items | Invoice | LineCountNumeric | |

### Semantic Gaps

**X12 → UBL:**
- TDS amounts in cents - UBL uses decimal
- BIG07 transaction type codes need mapping to InvoiceTypeCode
- Tax handling differs significantly

**UBL → X12:**
- Invoice.AccountingCost - no direct X12 field
- TaxTotal.TaxSubtotal breakdown - X12 TXI is simpler
- PrepaidPayment - no X12 equivalent
- PaymentAlternativeExchangeRate - complex FX handling

---

## Common Data Type Mappings

| X12 Type | X12 Format | UBL Type | Notes |
|----------|------------|----------|-------|
| Date | CCYYMMDD | Date | xs:date format |
| Time | HHMM | Time | xs:time format |
| Amount | Implied decimal | Amount | Explicit decimal + currencyID |
| Quantity | Numeric | Quantity | Decimal + unitCode |
| Identifier | AN | Identifier | String + schemeID |

## Party Role Code Mapping

| X12 N101 | Description | UBL Party Role |
|----------|-------------|----------------|
| BY | Buying Party | BuyerCustomerParty |
| SE | Selling Party | SellerSupplierParty |
| ST | Ship To | Delivery/DeliveryParty |
| SF | Ship From | DespatchParty |
| BT | Bill To | AccountingCustomerParty |
| RI | Remit To | PayeeParty |
| CA | Carrier | CarrierParty |
| VN | Vendor | SellerSupplierParty |

## Product ID Qualifier Mapping

| X12 235 Code | Description | UBL Item Element |
|--------------|-------------|------------------|
| UP | UPC | StandardItemIdentification (schemeID="UPC") |
| EN | EAN | StandardItemIdentification (schemeID="EAN") |
| UK | UCC/EAN-128 | StandardItemIdentification |
| VP | Vendor Part Number | SellersItemIdentification |
| BP | Buyer Part Number | BuyersItemIdentification |
| MG | Manufacturer Part | ManufacturersItemIdentification |
| SK | SKU | SellersItemIdentification |
| IN | Buyer Item Number | BuyersItemIdentification |

## References

- ANSI X12 005010 Standard
- UBL 2.5 OASIS Standard
- UN/CEFACT Code Lists (currency, units)
