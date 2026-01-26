# X12 to UBL Logistics Transaction Mappings

This document maps X12 logistics transaction sets to their UBL 2.5 equivalents. Excludes 850 (Purchase Order), 856 (ASN), and 810 (Invoice) which are covered in x12_ubl_mapping.md.

---

## Mapping Summary

| X12 | X12 Name | UBL Document | Notes |
|-----|----------|--------------|-------|
| 204 | Motor Carrier Load Tender | TransportExecutionPlanRequest | Request for transport services |
| 210 | Freight Details and Invoice | FreightInvoice | Carrier billing |
| 211 | Motor Carrier Bill of Lading | BillOfLading / Waybill | Legal transport document |
| 214 | Shipment Status Message | TransportationStatus | Tracking updates |
| 820 | Payment Order/Remittance | RemittanceAdvice | Payment notification |
| 846 | Inventory Inquiry/Advice | InventoryReport | Stock levels |
| 855 | PO Acknowledgement | OrderResponse | Order confirmation |
| 940 | Warehouse Shipping Order | ForwardingInstructions | Ship instruction to 3PL |
| 945 | Warehouse Shipping Advice | DespatchAdvice | Ship confirmation from 3PL |
| 947 | Inventory Adjustment | InventoryReport | Inventory changes |
| 990 | Response to Load Tender | TransportExecutionPlan | Accept/decline load |
| 997 | Functional Acknowledgement | ApplicationResponse | EDI receipt confirmation |

---

## Transportation Transactions

### EDI 204 - Motor Carrier Load Tender → UBL TransportExecutionPlanRequest

**Purpose:** Shipper tenders (offers) a load to a carrier.

| X12 204 Segment | X12 Element | UBL Element | Notes |
|-----------------|-------------|-------------|-------|
| **B2** | Standard Carrier Alpha Code | `cac:TransportServiceProviderParty/cac:PartyIdentification/cbc:ID @schemeID="SCAC"` | Carrier ID |
| **B2** | Shipment ID | `cbc:TransportExecutionPlanRequestID` | |
| **B2** | Payment Method | `cac:MainTransportationService/cac:PaymentTerms` | |
| **B2A** | Purpose Code | `cbc:TransportExecutionPlanRequestTypeCode` | 00=Original, 04=Change |
| **L11** | Reference ID | `cac:AdditionalDocumentReference/cbc:ID` | BOL, PO references |
| **L11** | Reference Qualifier | `cac:AdditionalDocumentReference/cbc:DocumentTypeCode` | |
| **G62** | Date Qualifier | Determines which date element | 10=Pickup, 11=Delivery |
| **G62** | Date | `cac:Consignment/cac:RequestedPickupTransportEvent/cbc:OccurrenceDate` | When qualifier=10 |
| **G62** | Date | `cac:Consignment/cac:RequestedDeliveryTransportEvent/cbc:OccurrenceDate` | When qualifier=11 |
| **MS3** | Transportation Method | `cac:MainTransportationService/cac:TransportMeans/cbc:TransportMeansTypeCode` | |
| **N1** (SF) | Ship From Name | `cac:Consignment/cac:ConsignorParty/cac:PartyName/cbc:Name` | |
| **N3** (SF) | Ship From Address | `cac:Consignment/cac:ConsignorParty/cac:PostalAddress/cbc:StreetName` | |
| **N4** (SF) | Ship From City/State/ZIP | `cac:ConsignorParty/cac:PostalAddress/cbc:CityName`, etc. | |
| **N1** (ST) | Ship To Name | `cac:Consignment/cac:ConsigneeParty/cac:PartyName/cbc:Name` | |
| **N3** (ST) | Ship To Address | `cac:Consignment/cac:ConsigneeParty/cac:PostalAddress/cbc:StreetName` | |
| **N4** (ST) | Ship To City/State/ZIP | `cac:ConsigneeParty/cac:PostalAddress` | |
| **S5** | Stop Sequence | `cac:Consignment/cac:ConsolidatedShipment/cac:TransportHandlingUnit` | Stop-off sequence |
| **L5** | Lading Description | `cac:Consignment/cac:TransportHandlingUnit/cbc:ShippingMarks` | |
| **AT8** | Weight Qualifier | `cac:GoodsItem/cac:MeasurementDimension/cbc:AttributeID` | |
| **AT8** | Weight | `cac:GoodsItem/cac:GrossWeightMeasure` | |
| **AT8** | Weight Unit | `cac:GoodsItem/cac:GrossWeightMeasure/@unitCode` | L=Pounds, K=Kilograms |

---

### EDI 210 - Motor Carrier Freight Invoice → UBL FreightInvoice

**Purpose:** Carrier invoices shipper for transportation services.

| X12 210 Segment | X12 Element | UBL Element | Notes |
|-----------------|-------------|-------------|-------|
| **B3** | Invoice Number | `cbc:ID` | |
| **B3** | Shipment ID | `cac:Shipment/cbc:ID` | |
| **B3** | Net Amount Due | `cac:LegalMonetaryTotal/cbc:PayableAmount` | |
| **B3** | Payment Method | `cac:PaymentMeans/cbc:PaymentMeansCode` | PP=Prepaid, CC=Collect |
| **B3** | Weight | `cac:Shipment/cbc:GrossWeightMeasure` | |
| **B3** | Date | `cbc:IssueDate` | |
| **C3** | Currency Code | `cbc:DocumentCurrencyCode` | |
| **N1** (SH) | Shipper | `cac:AccountingSupplierParty/cac:Party` | Who pays |
| **N1** (CN) | Consignee | `cac:DeliveryCustomerParty/cac:Party` | Receiver |
| **N1** (BT) | Bill To | `cac:AccountingCustomerParty/cac:Party` | Invoice recipient |
| **N7** | Equipment Initial | `cac:Shipment/cac:TransportHandlingUnit/cbc:ID` | Trailer/container ID |
| **N7** | Equipment Number | `cac:TransportHandlingUnit/cbc:ID` | |
| **LX** | Assigned Number | `cac:InvoiceLine/cbc:ID` | Line sequence |
| **L5** | Lading Description | `cac:InvoiceLine/cac:Item/cbc:Description` | |
| **L0** | Billed Weight | `cac:InvoiceLine/cac:Delivery/cac:Shipment/cbc:GrossWeightMeasure` | |
| **L0** | Weight Qualifier | `/@unitCode` | |
| **L1** | Freight Rate | `cac:InvoiceLine/cac:Price/cbc:PriceAmount` | |
| **L1** | Charge | `cac:InvoiceLine/cbc:LineExtensionAmount` | |
| **L1** | Special Charge Code | `cac:InvoiceLine/cac:AllowanceCharge/cbc:AllowanceChargeReasonCode` | Fuel surcharge, etc. |

---

### EDI 211 - Motor Carrier Bill of Lading → UBL BillOfLading / Waybill

**Purpose:** Legal document for goods in transit.

| X12 211 Segment | X12 Element | UBL Element (BillOfLading) | Notes |
|-----------------|-------------|----------------------------|-------|
| **B2** | Standard Carrier Alpha Code | `cac:CarrierParty/cac:PartyIdentification/cbc:ID @schemeID="SCAC"` | |
| **B2** | Shipment ID | `cbc:ID` | BOL number |
| **B2A** | Transaction Set Purpose | `cbc:BillOfLadingTypeCode` | Original, duplicate |
| **L11** | BOL Number | `cbc:ID` | |
| **L11** | Reference Qualifier | `cac:DocumentReference/cbc:DocumentTypeCode` | PO, SI references |
| **G62** | Pickup Date | `cac:Shipment/cac:ShipmentStage/cac:TransportEvent/cbc:OccurrenceDate` | |
| **MS1** | City/State | `cac:Shipment/cac:OriginAddress` | Origin location |
| **N1** (SH) | Shipper | `cac:ConsignorParty` | |
| **N1** (CN) | Consignee | `cac:ConsigneeParty` | |
| **N1** (SF) | Ship From | `cac:Shipment/cac:Consignment/cac:ConsignorParty` | |
| **N1** (ST) | Ship To | `cac:Shipment/cac:Delivery/cac:DeliveryAddress` | |
| **AT8** | Weight | `cac:Shipment/cac:GoodsItem/cac:GrossWeightMeasure` | |
| **AT8** | Lading Quantity | `cac:Shipment/cac:GoodsItem/cbc:Quantity` | |
| **OID** | Order ID | `cac:Shipment/cac:GoodsItem/cac:Item/cac:BuyersItemIdentification` | |
| **L5** | Commodity Code | `cac:GoodsItem/cac:Item/cac:CommodityClassification/cbc:CommodityCode` | NMFC code |
| **L5** | Lading Description | `cac:GoodsItem/cac:Item/cbc:Description` | |
| **L0** | Weight | `cac:GoodsItem/cac:GrossWeightMeasure` | |
| **L0** | Lading Quantity | `cac:GoodsItem/cbc:Quantity` | |
| **L7** | Tariff Number | `cac:GoodsItem/cac:FreightAllowanceCharge/cbc:ID` | |
| **L7** | Freight Class | `cac:GoodsItem/cac:Item/cac:CommodityClassification/cbc:NatureCode` | |

---

### EDI 214 - Shipment Status Message → UBL TransportationStatus

**Purpose:** Real-time shipment tracking updates.

| X12 214 Segment | X12 Element | UBL Element | Notes |
|-----------------|-------------|-------------|-------|
| **B10** | Shipment ID | `cac:TransportEvent/cac:Shipment/cbc:ID` | |
| **B10** | Carrier Reference | `cac:TransportServiceProviderParty/cac:PartyIdentification/cbc:ID` | PRO number |
| **L11** | Reference ID | `cac:DocumentReference/cbc:ID` | BOL, PO refs |
| **AT7** | Status Code | `cac:TransportEvent/cbc:TransportEventTypeCode` | See status codes below |
| **AT7** | Status Reason | `cac:TransportEvent/cbc:Description` | |
| **AT8** | Weight | `cac:TransportEvent/cac:Shipment/cbc:GrossWeightMeasure` | |
| **MS1** | City | `cac:TransportEvent/cac:Location/cac:Address/cbc:CityName` | Current location |
| **MS1** | State | `cac:TransportEvent/cac:Location/cac:Address/cbc:CountrySubentity` | |
| **MS2** | Carrier SCAC | `cac:TransportServiceProviderParty/cac:PartyIdentification/cbc:ID` | |
| **G62** | Date | `cac:TransportEvent/cbc:OccurrenceDate` | Event date |
| **G62** | Time | `cac:TransportEvent/cbc:OccurrenceTime` | Event time |

**Status Code Mapping (AT7 → TransportEventTypeCode):**

| X12 Code | Meaning | UBL Code |
|----------|---------|----------|
| AF | Carrier departed origin | DEPARTURE |
| AG | Estimated delivery | ESTIMATED_DELIVERY |
| AI | Shipment arrival | ARRIVAL |
| D1 | Completed delivery | DELIVERY |
| X1 | Arrived at terminal | TERMINAL_ARRIVAL |
| X6 | En route to delivery | IN_TRANSIT |
| OA | Out for delivery | OUT_FOR_DELIVERY |
| NS | Not shipped | NOT_SHIPPED |
| OD | Over/short/damage | EXCEPTION |

---

### EDI 990 - Response to Load Tender → UBL TransportExecutionPlan

**Purpose:** Carrier accepts or declines a load tender.

| X12 990 Segment | X12 Element | UBL Element | Notes |
|-----------------|-------------|-------------|-------|
| **B1** | Standard Carrier Alpha Code | `cac:TransportServiceProviderParty/cac:PartyIdentification/cbc:ID` | |
| **B1** | Shipment ID | `cac:TransportExecutionPlanRequestDocumentReference/cbc:ID` | Reference to 204 |
| **B1** | Date | `cbc:IssueDate` | |
| **B1** | Response Code | `cbc:TransportExecutionStatusCode` | A=Accept, D=Decline |
| **N9** | Reference ID | `cac:AdditionalDocumentReference/cbc:ID` | |
| **K1** | Remarks | `cbc:Note` | Decline reason if applicable |
| **SE** | Number of Segments | (N/A) | Control segment |

**Response Code Mapping:**

| X12 Code | Meaning | UBL TransportExecutionStatusCode |
|----------|---------|----------------------------------|
| A | Accepted | CONFIRMED |
| D | Declined | REJECTED |
| C | Conditionally Accepted | PENDING |

---

## Warehouse/3PL Transactions

### EDI 940 - Warehouse Shipping Order → UBL ForwardingInstructions

**Purpose:** Seller instructs 3PL/warehouse to ship goods.

| X12 940 Segment | X12 Element | UBL Element | Notes |
|-----------------|-------------|-------------|-------|
| **W05** | Order Status | `cbc:DocumentStatusCode` | Original, change, cancel |
| **W05** | Depositor Order Number | `cbc:ID` | |
| **N1** (WH) | Warehouse | `cac:FreightForwarderParty` | |
| **N1** (SF) | Ship From | `cac:Consignment/cac:ConsignorParty` | |
| **N1** (ST) | Ship To | `cac:Consignment/cac:ConsigneeParty` | |
| **N1** (BY) | Buyer | `cac:Consignment/cac:BuyerParty` | |
| **N9** | Reference ID | `cac:DocumentReference/cbc:ID` | PO number |
| **G62** | Date | `cac:Consignment/cac:RequestedDeliveryTransportEvent/cbc:OccurrenceDate` | Requested ship date |
| **W66** | Carrier Method | `cac:Consignment/cac:RequestedPickupTransportEvent/cac:TransportMeans` | |
| **W66** | Carrier ID (SCAC) | `cac:Consignment/cac:CarrierParty/cac:PartyIdentification/cbc:ID` | |
| **W66** | FOB Point | `cac:Consignment/cbc:FreightForwarderAssignedID` | FOB terms |
| **LX** | Line Number | `cac:Consignment/cac:TransportHandlingUnit/cbc:ID` | |
| **W01** | Quantity Ordered | `cac:GoodsItem/cbc:Quantity` | |
| **W01** | Unit of Measure | `cac:GoodsItem/cbc:Quantity/@unitCode` | |
| **W01** | UPC Code | `cac:GoodsItem/cac:Item/cac:StandardItemIdentification/cbc:ID` | |
| **N9** | Lot Number | `cac:GoodsItem/cac:Item/cac:AdditionalItemProperty[cbc:Name='LOT']/cbc:Value` | |
| **W20** | Pack Size | `cac:GoodsItem/cac:ContainingPackage/cbc:Quantity` | |

---

### EDI 945 - Warehouse Shipping Advice → UBL DespatchAdvice

**Purpose:** 3PL confirms shipment to seller.

| X12 945 Segment | X12 Element | UBL Element | Notes |
|-----------------|-------------|-------------|-------|
| **W06** | Shipment ID | `cbc:ID` | |
| **W06** | Depositor Order Number | `cac:OrderReference/cbc:ID` | Original order ref |
| **W06** | Date | `cbc:IssueDate` | Ship date |
| **N1** (WH) | Warehouse | `cac:DespatchSupplierParty/cac:Party` | |
| **N1** (SF) | Ship From | `cac:DespatchSupplierParty/cac:Party/cac:PostalAddress` | |
| **N1** (ST) | Ship To | `cac:DeliveryCustomerParty/cac:Party` | |
| **N9** | BOL Number | `cac:Shipment/cbc:ID` | |
| **N9** | PRO Number | `cac:Shipment/cac:ShipmentStage/cbc:ID` | Carrier tracking |
| **W27** | Carrier SCAC | `cac:Shipment/cac:ShipmentStage/cac:CarrierParty/cac:PartyIdentification/cbc:ID` | |
| **W27** | Transport Method | `cac:Shipment/cac:ShipmentStage/cac:TransportMeans/cbc:TransportMeansTypeCode` | |
| **W12** | Line Number | `cac:DespatchLine/cbc:ID` | |
| **W12** | Quantity Shipped | `cac:DespatchLine/cbc:DeliveredQuantity` | |
| **W12** | UPC Code | `cac:DespatchLine/cac:Item/cac:StandardItemIdentification/cbc:ID` | |
| **G69** | Description | `cac:DespatchLine/cac:Item/cbc:Description` | |
| **W20** | Pack Size | `cac:DespatchLine/cac:Item/cac:ContainedItem/cbc:Quantity` | |
| **MAN** | Mark Number | `cac:DespatchLine/cac:Shipment/cac:TransportHandlingUnit/cbc:ID` | Pallet/carton ID |

---

### EDI 947 - Warehouse Inventory Adjustment → UBL InventoryReport

**Purpose:** 3PL reports inventory changes to seller.

| X12 947 Segment | X12 Element | UBL Element | Notes |
|-----------------|-------------|-------------|-------|
| **W15** | Transaction Date | `cbc:IssueDate` | |
| **W15** | Adjustment Number | `cbc:ID` | |
| **N1** (WH) | Warehouse | `cac:InventoryReportingParty` | |
| **N1** (DE) | Depositor | `cac:RetailerCustomerParty` | Goods owner |
| **W07** | Quantity | `cac:InventoryReportLine/cbc:Quantity` | |
| **W07** | Unit of Measure | `cac:InventoryReportLine/cbc:Quantity/@unitCode` | |
| **W07** | UPC Code | `cac:InventoryReportLine/cac:Item/cac:StandardItemIdentification/cbc:ID` | |
| **W07** | Adjustment Reason | `cac:InventoryReportLine/cbc:Note` | |
| **W20** | Pack Size | `cac:InventoryReportLine/cac:Item/cac:ContainedItem/cbc:Quantity` | |
| **N9** | Lot Number | `cac:InventoryReportLine/cac:Item/cac:LotIdentification/cbc:LotNumberID` | |
| **G69** | Description | `cac:InventoryReportLine/cac:Item/cbc:Description` | |

**Adjustment Reason Code Mapping (W07-07):**

| X12 Code | Meaning | UBL InventoryValueCode |
|----------|---------|------------------------|
| DM | Damaged | DAMAGED |
| RC | Received | RECEIVED |
| SH | Shipped | SHIPPED |
| AJ | Adjustment | ADJUSTMENT |
| OS | Overage | OVERAGE |
| US | Underage | UNDERAGE |

---

## Order Management Transactions

### EDI 855 - Purchase Order Acknowledgement → UBL OrderResponse

**Purpose:** Seller confirms or rejects buyer's order.

| X12 855 Segment | X12 Element | UBL Element | Notes |
|-----------------|-------------|-------------|-------|
| **BAK** | Transaction Set Purpose | `cbc:OrderResponseCode` | |
| **BAK** | Acknowledgment Type | `cbc:OrderResponseCode` | AC, AD, AE, AK, RD |
| **BAK** | PO Number | `cac:OrderReference/cbc:ID` | |
| **BAK** | Date | `cbc:IssueDate` | |
| **BAK** | Request Reference Number | `cbc:SalesOrderID` | Seller's order ID |
| **N1** (BY) | Buyer | `cac:BuyerCustomerParty/cac:Party` | |
| **N1** (SE) | Seller | `cac:SellerSupplierParty/cac:Party` | |
| **N1** (ST) | Ship To | `cac:Delivery/cac:DeliveryParty` | |
| **PO1** | Line Number | `cac:OrderLine/cbc:ID` | |
| **PO1** | Quantity Ordered | `cac:OrderLine/cac:LineItem/cbc:Quantity` | |
| **PO1** | Unit Price | `cac:OrderLine/cac:LineItem/cac:Price/cbc:PriceAmount` | |
| **PO1** | Product ID | `cac:OrderLine/cac:LineItem/cac:Item/cac:SellersItemIdentification/cbc:ID` | |
| **ACK** | Line Status | `cac:OrderLine/cbc:LineStatusCode` | IA=Accept, IB=Backorder, IR=Reject |
| **ACK** | Quantity | `cac:OrderLine/cac:LineItem/cbc:Quantity` | Confirmed qty |
| **ACK** | Date Qualifier | Determines date field | 068=Ship, 017=Deliver |
| **ACK** | Date | `cac:OrderLine/cac:LineItem/cac:Delivery/cac:RequestedDeliveryPeriod/cbc:StartDate` | |
| **DTM** | Date/Time | `cac:Delivery/cac:RequestedDeliveryPeriod` | Ship/delivery dates |

**Acknowledgment Code Mapping (BAK-02):**

| X12 Code | Meaning | UBL OrderResponseCode |
|----------|---------|----------------------|
| AC | Acknowledge with Changes | ACCEPTED_WITH_CHANGE |
| AD | Acknowledge with Detail | ACCEPTED |
| AE | Acknowledge with Exception | ACCEPTED_WITH_EXCEPTION |
| AK | Acknowledge (no changes) | ACCEPTED |
| RD | Reject with Detail | REJECTED |

---

## Financial Transactions

### EDI 820 - Payment Order/Remittance Advice → UBL RemittanceAdvice

**Purpose:** Buyer notifies seller of payment.

| X12 820 Segment | X12 Element | UBL Element | Notes |
|-----------------|-------------|-------------|-------|
| **BPR** | Transaction Handling | `cac:PaymentMeans/cbc:PaymentMeansCode` | ACH, CHK, etc. |
| **BPR** | Amount | `cbc:TotalPaymentAmount` | |
| **BPR** | Payment Method | `cac:PaymentMeans/cbc:PaymentMeansCode` | |
| **BPR** | Payment Format | `cac:PaymentMeans/cbc:PaymentChannelCode` | |
| **BPR** | DFI ID (Payer) | `cac:PayerParty/cac:PartyIdentification/cbc:ID` | Bank routing |
| **BPR** | Account Number (Payer) | `cac:PaymentMeans/cac:PayerFinancialAccount/cbc:ID` | |
| **BPR** | DFI ID (Payee) | `cac:PayeeParty/cac:PartyIdentification/cbc:ID` | |
| **BPR** | Account Number (Payee) | `cac:PaymentMeans/cac:PayeeFinancialAccount/cbc:ID` | |
| **TRN** | Reference ID | `cbc:ID` | Payment reference |
| **TRN** | Originator ID | `cac:PayerParty/cac:PartyIdentification/cbc:ID` | |
| **N1** (PR) | Payer | `cac:PayerParty` | |
| **N1** (PE) | Payee | `cac:PayeeParty` | |
| **DTM** | Date | `cbc:IssueDate` | Payment date |
| **ENT** | Entity ID | `cac:RemittanceAdviceLine/cbc:ID` | Line grouping |
| **RMR** | Reference ID Qualifier | `cac:RemittanceAdviceLine/cac:BillingReference/cbc:DocumentTypeCode` | IV=Invoice |
| **RMR** | Reference ID | `cac:RemittanceAdviceLine/cac:BillingReference/cbc:ID` | Invoice number |
| **RMR** | Amount Paid | `cac:RemittanceAdviceLine/cbc:PaidAmount` | |
| **RMR** | Amount Billed | `cac:RemittanceAdviceLine/cac:BillingReference/cbc:DocumentDescription` | Original amount |
| **REF** | Check Number | `cac:PaymentMeans/cbc:PaymentID` | |
| **ADX** | Adjustment Reason | `cac:RemittanceAdviceLine/cac:PaymentTerms/cbc:Note` | Discounts, deductions |
| **ADX** | Adjustment Amount | `cac:RemittanceAdviceLine/cbc:DebitLineAmount` | |

---

### EDI 846 - Inventory Inquiry/Advice → UBL InventoryReport

**Purpose:** Seller reports inventory status to buyer.

| X12 846 Segment | X12 Element | UBL Element | Notes |
|-----------------|-------------|-------------|-------|
| **BIA** | Transaction Set Purpose | `cbc:DocumentStatusCode` | 00=Original, 01=Replace |
| **BIA** | Report Type | `cbc:InventoryReportTypeCode` | 00=Actual, 01=Forecast |
| **BIA** | Date | `cbc:IssueDate` | |
| **N1** (SU) | Supplier | `cac:RetailerCustomerParty/cac:Party` | Inventory owner |
| **N1** (WH) | Warehouse | `cac:InventoryReportingParty` | Location |
| **LIN** | Product ID | `cac:InventoryReportLine/cac:Item/cac:SellersItemIdentification/cbc:ID` | |
| **LIN** | UPC | `cac:InventoryReportLine/cac:Item/cac:StandardItemIdentification/cbc:ID` | |
| **PID** | Description | `cac:InventoryReportLine/cac:Item/cbc:Description` | |
| **QTY** (33) | Quantity on Hand | `cac:InventoryReportLine/cbc:Quantity` | QTY qualifier 33 |
| **QTY** (QA) | Quantity Available | `cac:InventoryReportLine/cbc:AvailabilityStatusCode` + quantity | |
| **QTY** (QC) | Quantity Committed | `cac:InventoryReportLine/cbc:Note` | Reserved qty |
| **QTY** (QO) | Quantity on Order | `cac:InventoryReportLine/cbc:Note` | Incoming qty |
| **DTM** | Date | `cac:InventoryReportLine/cac:InventoryLocation/cac:InventoryPeriod/cbc:EndDate` | As-of date |
| **MEA** | Measurements | `cac:InventoryReportLine/cac:Item/cac:Dimension` | Weight, volume |
| **CUR** | Currency | `cbc:DocumentCurrencyCode` | |
| **CTP** | Unit Price | `cac:InventoryReportLine/cac:Item/cac:Price/cbc:PriceAmount` | |

---

## Acknowledgement Transactions

### EDI 997 - Functional Acknowledgement → UBL ApplicationResponse

**Purpose:** Confirm receipt of EDI transmission (technical acknowledgment, not business acceptance).

| X12 997 Segment | X12 Element | UBL Element | Notes |
|-----------------|-------------|-------------|-------|
| **AK1** | Functional ID | `cac:DocumentResponse/cac:DocumentReference/cbc:DocumentTypeCode` | PO, IN, SH, etc. |
| **AK1** | Group Control Number | `cac:DocumentResponse/cac:DocumentReference/cbc:ID` | |
| **AK2** | Transaction Set ID | `cac:DocumentResponse/cac:DocumentReference/cbc:DocumentType` | 850, 856, etc. |
| **AK2** | Control Number | `cac:DocumentResponse/cac:DocumentReference/cbc:VersionID` | |
| **AK5** | Acknowledgment Code | `cac:DocumentResponse/cac:Response/cbc:ResponseCode` | A, E, R |
| **AK5** | Error Code 1-5 | `cac:DocumentResponse/cac:Response/cbc:Description` | Error details |
| **AK9** | Acknowledgment Code | `cac:DocumentResponse/cac:Response/cbc:ResponseCode` | Group level |
| **AK9** | Transactions Included | `cac:DocumentResponse/cac:DocumentReference/cbc:UUID` | Count |
| **AK9** | Transactions Received | (derived) | |
| **AK9** | Transactions Accepted | (derived) | |

**Acknowledgment Code Mapping:**

| X12 Code | Meaning | UBL ResponseCode |
|----------|---------|------------------|
| A | Accepted | ACCEPTED |
| E | Accepted with Errors | ACCEPTED_WITH_ERRORS |
| R | Rejected | REJECTED |
| P | Partially Accepted | PARTIALLY_ACCEPTED |

---

## Data Type Mappings

### Date/Time Formats

| X12 Format | UBL Format | Example |
|------------|------------|---------|
| CCYYMMDD | xs:date (YYYY-MM-DD) | 20240115 → 2024-01-15 |
| YYMMDD | xs:date (20YY-MM-DD) | 240115 → 2024-01-15 |
| HHMM | xs:time (HH:MM:00) | 1430 → 14:30:00 |
| HHMMSS | xs:time (HH:MM:SS) | 143022 → 14:30:22 |

### Unit of Measure Codes

| X12 Code | UBL UN/ECE Rec 20 | Meaning |
|----------|-------------------|---------|
| EA | EA | Each |
| CA | CA | Case |
| BX | BX | Box |
| PL | PL | Pallet |
| LB | LBR | Pounds |
| KG | KGM | Kilograms |
| CU | FTQ | Cubic Feet |
| CF | FTQ | Cubic Feet |

### Party Role Codes

| X12 N1 Code | UBL Party Element |
|-------------|-------------------|
| BY | BuyerCustomerParty |
| SE | SellerSupplierParty |
| ST | DeliveryCustomerParty |
| SF | DespatchSupplierParty |
| SH | ConsignorParty |
| CN | ConsigneeParty |
| WH | FreightForwarderParty |
| CA | CarrierParty |
| BT | AccountingCustomerParty |
| PR | PayerParty |
| PE | PayeeParty |

---

## References

- [UBL 2.5 Specification](https://docs.oasis-open.org/ubl/UBL-2.5.html)
- [X12 EDI Standards](https://www.stedi.com/edi/x12-005010)
- [Babelway EDI Transaction Reference](https://www.babelway.com/edi-transactions/)
