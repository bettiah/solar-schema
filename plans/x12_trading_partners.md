# X12 EDI Trading Partners Reference (Non-HIPAA)

## Part 1: Traders and Their X12 Messages

### Mass Retail / General Merchandise

#### Walmart
| Transaction | Name | Direction |
|---|---|---|
| 850 | Purchase Order | Walmart → Vendor |
| 855 | PO Acknowledgment | Vendor → Walmart |
| 856 | Advance Ship Notice (ASN) | Vendor → Walmart |
| 810 | Invoice | Vendor → Walmart |
| 812 | Credit/Debit Adjustment | Either |
| 860 | PO Change Request | Walmart → Vendor |
| 820 | Payment/Remittance Advice | Walmart → Vendor |
| 864 | Text Message | Either |
| 997 | Functional Acknowledgment | Both |

- **Version**: 4010 and 5010
- **Protocol**: AS2 (mandatory for suppliers >5,500 invoices/yr; WebEDI for smaller)
- **Portal**: Retail Link

#### Amazon (Vendor Central)
| Transaction | Name | Direction |
|---|---|---|
| 850 | Purchase Order | Amazon → Vendor |
| 855 | PO Acknowledgment | Vendor → Amazon |
| 856 | Advance Ship Notice | Vendor → Amazon |
| 810 | Invoice | Vendor → Amazon |
| 846 | Inventory Inquiry/Advice | Vendor → Amazon |
| 753 | Request for Routing Instructions | Vendor → Amazon |
| 754 | Routing Instructions | Amazon → Vendor |
| 820 | Payment/Remittance Advice | Amazon → Vendor |
| 990 | Response to Load Tender | Within 90 min of 204 |
| 997 | Functional Acknowledgment | Both |

- **Version**: 4010+ (5010 required for ASN)
- **Protocol**: AS2 (preferred), SFTP, VAN
- **Portal**: Vendor Central (1P); Seller Central (3P uses SP-API, not EDI)

#### Target
| Transaction | Name | Direction |
|---|---|---|
| 850 | Purchase Order | Target → Vendor |
| 855 | PO Acknowledgment | Vendor → Target |
| 856 | Advance Ship Notice | Vendor → Target |
| 810 | Invoice | Vendor → Target |
| 820 | Payment/Remittance Advice | Target → Vendor |
| 830 | Planning Schedule | Target → Vendor |
| 846 | Inventory Inquiry/Advice | Vendor → Target |
| 852 | Product Activity Data (POS) | Target → Vendor |
| 860 | PO Change Request | Target → Vendor |
| 214 | Transportation Carrier Status | Carrier → Target |
| 997 | Functional Acknowledgment | Both |

- **Version**: 4010
- **Protocol**: VAN required (no direct AS2)

#### Costco
| Transaction | Name | Direction |
|---|---|---|
| 850 | Purchase Order | Costco → Vendor |
| 855 | PO Acknowledgment | Vendor → Costco |
| 856 | Advance Ship Notice | Vendor → Costco |
| 810 | Invoice | Vendor → Costco |
| 997 | Functional Acknowledgment | Both |

- **Version**: 4010
- **Protocol**: VAN (SPS Commerce for testing/validation)

### Home Improvement

#### Home Depot
| Transaction | Name | Direction |
|---|---|---|
| 850 | Purchase Order | HD → Vendor |
| 856 | Advance Ship Notice | Vendor → HD |
| 810 | Invoice | Vendor → HD |
| 820 | Payment/Remittance Advice | HD → Vendor |
| 832 | Product Catalog Update | Vendor → HD |
| 840 | Return Material Authorization | Vendor → HD |
| 846 | Inventory Inquiry/Advice | Vendor → HD |
| 864 | Text Message | Either |
| 997 | Functional Acknowledgment | Both |

- **Version**: 4060 (unusual)
- **Protocol**: AS2

#### Lowe's
| Transaction | Name | Direction |
|---|---|---|
| 850 | Purchase Order | Lowe's → Vendor |
| 855 | PO Acknowledgment | Vendor → Lowe's |
| 856 | Advance Ship Notice | Vendor → Lowe's |
| 810 | Invoice | Vendor → Lowe's |
| 753 | Request for Routing Instructions | Vendor → Lowe's |
| 824 | Application Advice | Lowe's → Vendor |
| 997 | Functional Acknowledgment | Both |

- **Version**: 4010/4030
- **Protocol**: VAN (preferred), AS2, FTP, HTTPS
- **Portal**: LowesLink

### Grocery / Pharmacy

#### Kroger
| Transaction | Name | Direction |
|---|---|---|
| 850/875 | Purchase Order / Grocery PO | Kroger → Vendor |
| 856 | Advance Ship Notice | Vendor → Kroger |
| 810/880 | Invoice / Grocery Invoice | Vendor → Kroger |
| 876 | Grocery PO Change | Kroger → Vendor |
| 824 | Application Advice | Kroger → Vendor |
| 997 | Functional Acknowledgment | Both |

- **Version**: 005010
- **Protocol**: VAN
- **Note**: Uses UCS grocery-specific transaction sets (875/876/880) alongside standard X12

#### Albertsons
| Transaction | Name | Direction |
|---|---|---|
| 850 | Purchase Order | Albertsons → Vendor |
| 856 | Advance Ship Notice | Vendor → Albertsons |
| 810 | Invoice | Vendor → Albertsons |
| 852 | Product Activity Data | Albertsons → Vendor |
| 997 | Functional Acknowledgment | Both |

- **Version**: 004030
- **Protocol**: VAN

#### CVS
| Transaction | Name | Direction |
|---|---|---|
| 850 | Purchase Order | CVS → Vendor |
| 855 | PO Acknowledgment | Vendor → CVS |
| 856 | Advance Ship Notice | Vendor → CVS |
| 860 | PO Change Request | CVS → Vendor |
| 810 | Invoice | Vendor → CVS |
| 997 | Functional Acknowledgment | Both |

- **Protocol**: VAN

#### Walgreens
| Transaction | Name | Direction |
|---|---|---|
| 850 | Purchase Order | Walgreens → Vendor |
| 855 | PO Acknowledgment | Vendor → Walgreens |
| 856 | Advance Ship Notice | Vendor → Walgreens |
| 810 | Invoice | Vendor → Walgreens |
| 997 | Functional Acknowledgment | Both |

- **Protocol**: VAN, AS2, FTP
- **Standards**: ANSI X12, EDIFACT, and UCS

### Department Stores / Fashion

#### Macy's
| Transaction | Name | Direction |
|---|---|---|
| 850 | Purchase Order | Macy's → Vendor |
| 855 | PO Acknowledgment | Vendor → Macy's |
| 856 | Advance Ship Notice | Vendor → Macy's |
| 810 | Invoice | Vendor → Macy's |
| 820 | Payment/Remittance Advice | Macy's → Vendor |
| 846 | Inventory Inquiry/Advice | Vendor → Macy's |
| 852 | Product Activity Data (POS) | Macy's → Vendor |
| 997 | Functional Acknowledgment | Both |

- **Protocol**: VAN, AS2
- **Standards**: X12, EDIFACT, XML
- **Portal**: MacysNet

#### Nordstrom
| Transaction | Name | Direction |
|---|---|---|
| 850 | Purchase Order | Nordstrom → Vendor |
| 856 | Advance Ship Notice | Vendor → Nordstrom |
| 810 | Invoice | Vendor → Nordstrom |
| 832 | Price/Sales Catalog | Vendor → Nordstrom |
| 852 | Product Activity Data | Nordstrom → Vendor |
| 997 | Functional Acknowledgment | Both |

#### JCPenney
| Transaction | Name | Direction |
|---|---|---|
| 850 | Purchase Order | JCP → Vendor |
| 855 | PO Acknowledgment | Vendor → JCP |
| 856 | Advance Ship Notice | Vendor → JCP |
| 810 | Invoice | Vendor → JCP |
| 997 | Functional Acknowledgment | Both |

- **Protocol**: VAN, AS2, FTP
- **Standards**: X12, EDIFACT, UCS

#### Kohl's
| Transaction | Name | Direction |
|---|---|---|
| 850 | Purchase Order | Kohl's → Vendor |
| 855 | PO Acknowledgment | Vendor → Kohl's |
| 856 | Advance Ship Notice | Vendor → Kohl's |
| 810 | Invoice | Vendor → Kohl's |
| 846 | Inventory Inquiry/Advice | Vendor → Kohl's |
| 852 | Product Activity Data | Kohl's → Vendor |
| 816 | Organizational Relationships | Either |
| 997 | Functional Acknowledgment | Both |

### Electronics

#### Best Buy
| Transaction | Name | Direction |
|---|---|---|
| 850 | Purchase Order | BB → Vendor |
| 856 | Advance Ship Notice | Vendor → BB |
| 810 | Invoice | Vendor → BB |
| 997 | Functional Acknowledgment | Both |

- **Protocol**: VAN, AS2

### Discount / Value Retail

#### Dollar General
| Transaction | Name | Direction |
|---|---|---|
| 850 | Purchase Order | DG → Vendor |
| 810 | Invoice | Vendor → DG |
| 852 | Product Activity Data (POS) | DG → Vendor |
| 997 | Functional Acknowledgment | Both |

#### Dollar Tree
| Transaction | Name | Direction |
|---|---|---|
| 850 | Purchase Order | DT → Vendor |
| 810 | Invoice | Vendor → DT |
| 997 | Functional Acknowledgment | Both |

- **Protocol**: Ariba Supplier Network (unique)

### E-Commerce

#### Wayfair
| Transaction | Name | Direction |
|---|---|---|
| 850 | Purchase Order | Wayfair → Vendor |
| 855 | PO Acknowledgment | Vendor → Wayfair |
| 856 | Advance Ship Notice | Vendor → Wayfair |
| 810 | Invoice | Vendor → Wayfair |
| 846 | Inventory Inquiry/Advice | Vendor → Wayfair |
| 997 | Functional Acknowledgment | Both |

- **Protocol**: VAN, AS2
- **Note**: Also supports proprietary Flat File Format V2

### Transportation / Logistics

#### UPS
| Transaction | Name | Direction |
|---|---|---|
| 204 | Motor Carrier Load Tender | Shipper → UPS |
| 990 | Response to Load Tender | UPS → Shipper |
| 214 | Carrier Shipment Status | UPS → Shipper |
| 210 | Freight Details/Invoice | UPS → Shipper |
| 997 | Functional Acknowledgment | Both |

#### FedEx
| Transaction | Name | Direction |
|---|---|---|
| 204 | Motor Carrier Load Tender | Shipper → FedEx |
| 990 | Response to Load Tender | FedEx → Shipper |
| 214 | Carrier Shipment Status | FedEx → Shipper |
| 210 | Freight Details/Invoice | FedEx → Shipper |
| 820 | Payment/Remittance Advice | Shipper → FedEx |
| 997 | Functional Acknowledgment | Both |

- **Version**: 4060 (for 210/820)

### CPG / Manufacturing

#### Procter & Gamble
| Transaction | Name | Direction |
|---|---|---|
| 850 | Purchase Order | P&G → Supplier |
| 856 | Advance Ship Notice | Supplier → P&G |
| 810 | Invoice | Supplier → P&G |
| 997 | Functional Acknowledgment | Both |

- **Standards**: X12, EDIFACT, XCBL (XML Common Business Library)

#### Nike
| Transaction | Name | Direction |
|---|---|---|
| 850 | Purchase Order | Nike → Vendor |
| 855 | PO Acknowledgment | Vendor → Nike |
| 856 | Advance Ship Notice | Vendor → Nike |
| 810 | Invoice | Vendor → Nike |
| 997 | Functional Acknowledgment | Both |

### Automotive (Ford, GM, Toyota, etc.)
| Transaction | Name | Direction |
|---|---|---|
| 830 | Planning Schedule / Material Release | OEM → Supplier |
| 850 | Purchase Order | OEM → Supplier |
| 856 | Advance Ship Notice | Supplier → OEM |
| 860 | PO Change Request | OEM → Supplier |
| 862 | Shipping Schedule (JIT) | OEM → Supplier |
| 810 | Invoice | Supplier → OEM |
| 824 | Application Advice | OEM → Supplier |
| 997 | Functional Acknowledgment | Both |

- **Note**: 830 for long-term forecasts, 862 for JIT replenishment triggered by inventory dips

---

## Part 2: Messages and Their Users (Reverse Mapping)

### Core Retail Documents

#### 850 - Purchase Order
**Used by**: Walmart, Amazon, Target, Costco, Home Depot, Lowe's, Kroger (also 875), Albertsons, CVS, Walgreens, Macy's, Nordstrom, JCPenney, Kohl's, Best Buy, Dollar General, Dollar Tree, Wayfair, P&G, Nike, Automotive OEMs

#### 855 - PO Acknowledgment
**Used by**: Walmart, Amazon, Target, Costco, CVS, Walgreens, Macy's, JCPenney, Kohl's, Wayfair, Nike, Lowe's

#### 856 - Advance Ship Notice (ASN)
**Used by**: Walmart, Amazon, Target, Costco, Home Depot, Lowe's, Kroger, Albertsons, CVS, Walgreens, Macy's, Nordstrom, JCPenney, Kohl's, Best Buy, Wayfair, P&G, Nike, Automotive OEMs

#### 810 - Invoice
**Used by**: Walmart, Amazon, Target, Costco, Home Depot, Lowe's, Kroger (also 880), Albertsons, CVS, Walgreens, Macy's, Nordstrom, JCPenney, Kohl's, Best Buy, Dollar General, Dollar Tree, Wayfair, P&G, Nike, Automotive OEMs

#### 997 - Functional Acknowledgment
**Used by**: All trading partners (universal requirement)

#### 860 - PO Change Request (Buyer Initiated)
**Used by**: Walmart, Target, CVS, Automotive OEMs

### Financial Documents

#### 820 - Payment Order/Remittance Advice
**Used by**: Walmart, Target, Home Depot, Macy's, Amazon, FedEx

#### 812 - Credit/Debit Adjustment
**Used by**: Walmart

#### 824 - Application Advice
**Used by**: Kroger, Lowe's, Automotive OEMs

### Inventory & Catalog Documents

#### 846 - Inventory Inquiry/Advice
**Used by**: Amazon, Target, Home Depot, Macy's, Kohl's, Wayfair

#### 852 - Product Activity Data (POS)
**Used by**: Target, Albertsons, Macy's, Nordstrom, Kohl's, Dollar General

#### 832 - Price/Sales Catalog
**Used by**: Home Depot, Nordstrom

#### 830 - Planning Schedule
**Used by**: Target, Automotive OEMs (Ford, GM, Toyota)

### Logistics Documents

#### 204 - Motor Carrier Load Tender
**Used by**: UPS, FedEx, Amazon (to carriers), JB Hunt, XPO, C.H. Robinson

#### 214 - Transportation Carrier Shipment Status
**Used by**: UPS, FedEx, Target (from carriers), Old Dominion, DHL, Ryder

#### 210 - Motor Carrier Freight Invoice
**Used by**: UPS, FedEx

#### 990 - Response to Load Tender
**Used by**: UPS, FedEx, Amazon (from carriers)

### Routing Documents

#### 753 - Request for Routing Instructions
**Used by**: Amazon, Lowe's

#### 754 - Routing Instructions
**Used by**: Amazon, Lowe's

### Specialty Documents

#### 816 - Organizational Relationships
**Used by**: Kohl's (unusual)

#### 840 - Return Material Authorization
**Used by**: Home Depot

#### 864 - Text Message
**Used by**: Walmart, Home Depot

#### 862 - Shipping Schedule (JIT)
**Used by**: Automotive OEMs (Ford, GM, Toyota)

### Grocery-Specific (UCS)

#### 875 - Grocery Products Purchase Order
**Used by**: Kroger

#### 876 - Grocery Products PO Change
**Used by**: Kroger

#### 880 - Grocery Products Invoice
**Used by**: Kroger

### Warehouse / 3PL

#### 940 - Warehouse Shipping Order
**Used by**: Amazon, Walmart, Target (3PL operations)

#### 943 - Warehouse Stock Transfer Shipment Advice
**Used by**: Amazon, Walmart, Target (inter-warehouse)

#### 944 - Warehouse Stock Transfer Receipt Advice
**Used by**: Amazon, Walmart, Target (inter-warehouse)

#### 945 - Warehouse Shipping Advice
**Used by**: Amazon, Walmart, Target (3PL confirms shipment)

---

## Part 3: How Messages Differ Across Traders

### 850 - Purchase Order Differences

| Aspect | Walmart | Amazon | Target | Home Depot | Kroger |
|--------|---------|--------|--------|------------|--------|
| **Version** | 4010/5010 | 4010+ | 4010 | 4060 | 5010 |
| **Item ID** | UP (UPC), UK (GTIN) | ASIN-based | IN qualifier | SKU-based | UA (UPC), UK (GTIN) |
| **N1 Party Codes** | BT, RT, ST, FD (FD is Walmart-specific) | Standard | Standard | Standard | DUNS+4 for ST and BT |
| **Ship Date** | CSH or DTM (DTM when items have different dates) | Standard | DTM01 set by AP team (037/038 or 063/064) | Standard | Standard |
| **Invoice Rule** | Per-store, separate | Standard | Within 30 days | Standard | One 810 per 850 (no consolidation) |
| **GLN Required** | Yes (N1 ST element 04) | No | No | No | No |
| **Separate Guides** | Multiple (DC types) | Standard | Retail vs Drop-ship | Standard vs Dropship | Standard |

### 856 - ASN Differences (Most Variable Transaction Set)

| Aspect | Walmart | Amazon | Target | Costco |
|--------|---------|--------|--------|--------|
| **Timing** | Before gate-in (30 min of ship) | 4+ hours before arrival | 24-48 hours before delivery | Before delivery |
| **Hierarchy** | Tare Level (Ship→Order→Pallet→Pack→Item) | SOPTI (Ship→Order→Pack→Tare→Item) | Standard Pack | Standard |
| **SSCC-18** | Mandatory (MAN segment) | Enables License Plate Receive | Required or GTIN-14 or UPC | Must match physical label exactly |
| **Pallet data** | Required for palletized | Mandatory for single-ASIN pallets, optional for mixed | Standard | Standard |
| **Perishables** | Standard | Mandatory ASN with expiration dates | Standard | Standard |
| **SAC segment** | Shipping costs mandatory at Pack level | Not specified | Not specified | Not specified |
| **LTL** | PRO numbers required | Standard | Standard | Standard |
| **Non-compliance penalty** | $50-500 per incident | Chargebacks/suspension | $0.75/carton, $100 min | $50-200 per incident or 1-5% of PO |

### 810 - Invoice Differences

| Aspect | Walmart | Amazon | Kroger |
|--------|---------|--------|--------|
| **Timing** | Standard | Within 24 hours of ship confirmation | Standard |
| **Consolidation** | Per-store, separate invoices | Standard | Prohibited (one 810 per 850) |
| **GLN** | Required (N1 ST element 04) | Not required | Not required |
| **TXI segment** | Mandatory for Canada invoices | Not specified | Not specified |
| **Allowances** | Standard | Standard | Order level only, negative values |
| **Error handling** | 864 Text Message for errors | Standard | 824 Application Advice |

### 855 - PO Acknowledgment Differences

| Aspect | Walmart | Amazon | Target |
|--------|---------|--------|--------|
| **Timing** | Within 24 hours | Within 8 hours | Varies |
| **CTP segment** | Not included | Optional (pricing info) | Standard |
| **Separate guides** | Standard | Standard | Retail vs Drop-ship |

### 997 vs 999

| Aspect | Retail Partners | Healthcare |
|--------|----------------|------------|
| **Type** | 997 (Functional Ack) | 999 (Implementation Ack) |
| **Detail** | Accept/reject/error only | Segment and element-level validation |
| **Version** | 4010+ | 5010 required |

### Version Landscape

| Version | Used By |
|---------|---------|
| 4010 | Costco, Target, Amazon (minimum), most legacy systems |
| 4030 | Lowe's, Albertsons |
| 4060 | Home Depot, FedEx (210/820) |
| 5010 | Walmart, Kroger, Amazon (for ASN) |

### Communication Protocol

| Protocol | Used By |
|----------|---------|
| AS2 (mandatory) | Walmart (>5,500 inv/yr), Home Depot |
| AS2 (preferred) | Amazon, FedEx, UPS |
| VAN only | Target |
| VAN (preferred) | Costco, Kroger, Lowe's, Nordstrom, Dollar General |
| Multiple | Walgreens, JCPenney, Macy's |
| Ariba Network | Dollar Tree (unique) |

### Compliance Penalties

| Retailer | Penalty | Amount |
|----------|---------|--------|
| Walmart | OTIF shortfall | 3% of cost of goods |
| Walmart | ASN errors | $50-500 per incident |
| Walmart | Labeling violations | $25-200 per violation |
| Target | ASN non-compliance | $0.75 per carton, $100 minimum |
| Costco | General non-compliance | $50-200 per incident or 1-5% of PO value |
| Nordstrom | Non-compliant invoices | $10 per occurrence |
| Kroger | No EDI within 90 days | 1% of payment or $250 (whichever is greater) |
| Lowe's | 824 errors unfixed | Withheld payments or vendor removal |

---

## Part 4: Third-Party EDI Service Providers

> **VAN deep dive**: See [vans.md](vans.md) for detailed VAN architecture, protocols, connectivity, pricing, and how VANs relate to X12 message customization.

### Major VANs (Value Added Networks)

| Provider | Scale | Key Differentiator |
|----------|-------|--------------------|
| **OpenText Trading Grid** (fka GXS) | 1M+ partners, $11T annual commerce | World's largest VAN, 200+ ERP connectors |
| **BOLD VAN** | ~20K partners | Per-partner pricing (not per-document) |
| **Descartes** | 200K+ parties | Logistics/transportation specialization |
| **GraceBlood** | ECGrid reseller | White-glove managed service |

### Managed Service Providers

| Provider | Scale | Key Differentiator |
|----------|-------|--------------------|
| **SPS Commerce** | 1M+ connections, 50K+ customers | Largest retail network, 4K+ pre-built retailer maps |
| **Cleo** | 4,200+ customers | AI-powered mapping and orchestration |
| **TrueCommerce** | 92K+ organizations | Strong ERP integration (SAP-certified) |
| **Integration, Inc.** | Mid-market | Full BPO for EDI |

### Cloud/SaaS EDI Platforms

| Provider | Scale | Key Differentiator |
|----------|-------|--------------------|
| **Orderful** | 10K+ trading partners | Cloud-native, API-first, $189/mo starting |
| **Stedi** | Growing | Developer-focused, open-source EDI tools |
| **Boomi** (Dell) | 20K+ customers | iPaaS that includes EDI + API |

### EDI Translation Software (On-Premises)

| Provider | Status | Key Differentiator |
|----------|--------|--------------------|
| **IBM Sterling B2B Integrator** | Active, IDC leader | 3B+ order transactions/yr, 99.99% uptime |
| **IBM Sterling Gentran** | Legacy (still supported) | 30+ years most widely used EDI translator |
| **Microsoft BizTalk** | Legacy (moving to Azure) | TwoConnect EDI enhancement available |
| **Edifecs** | Active (acquired by Cotiviti 2025) | Healthcare Interoperability Cloud, FHIR + EDI |
| **Axway B2Bi** | Active | Analyst rating 95, robust security |

### Retail-Specific Platforms

| Provider | Scale | Key Differentiator |
|----------|-------|--------------------|
| **SPS Commerce** | 4K+ retailers | Full-service "do it for you" model |
| **Rithum** (fka CommerceHub + ChannelAdvisor) | $50B GMV, 420+ marketplaces | Kohl's, Saks, QVC, HD, Lowe's, BB, Costco |
| **eZCom Software (Lingo)** | 25 years | Sub-2-min human support response |

### Which Retailers Recommend Which Providers

| Retailer | Recommended / Certified Providers |
|----------|----------------------------------|
| **Walmart** | SPS Commerce (20+ yr), 1 EDI Source (30+ yr), TrueCommerce, Cleo, Orderful |
| **Amazon** | SPS Commerce, EDICOM, Cleo, Orderful, TrueCommerce |
| **Target** | SPS Commerce (2,300+ supplier connections) |
| **Kroger** | Edict, Easylink, Softshare, Infocon Systems, SPS Commerce |
| **Home Depot** | Cleo, SPS Commerce, Integration Inc., TrueCommerce, Rithum |
| **Costco** | SPS Commerce (testing/validation partner) |

---

## Part 5: Schema Design Implications

### Key Architectural Takeaways

1. **Implementation Guides are Subsets**: Each trading partner's guide narrows the full X12 spec. Schema system must support per-partner profiles marking segments/elements as required, optional, or not used.

2. **Conditional Logic Varies**: Different retailers have different conditional rules (e.g., "if X present, Y required"). Must be modeled per-partner, separate from base schema.

3. **Qualifier Code Restrictions**: Partners restrict valid qualifier codes. Walmart N1-01 accepts BT/RT/ST/FD; others accept different sets. Code list validation must be per-partner.

4. **856 Hierarchy is Most Variable**: The HL hierarchy structure in the 856 differs significantly across partners. Schema must support configurable hierarchy patterns.

5. **Version Coexistence**: Suppliers must support 4010, 4030, 4060, and 5010 simultaneously.

6. **Universal Core**: Nearly every partner requires at minimum 850 + 856 + 810 + 997.

7. **Industry-Specific Sets**: Grocery (875/876/880), Transportation (204/214/210/990), Automotive (830/862), Warehouse (940/943/944/945).

8. **VANs are transport-only**: The VAN is a dumb pipe -- all per-partner message customization and validation must live in the schema/mapper layer, not the VAN. See [vans.md](vans.md) for details.
