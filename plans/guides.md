# X12 EDI Implementation Guide Collection

## Overview

Collection of publicly available X12 EDI implementation guides from major trading partners.
**Location**: `/Users/me/Downloads/edi/implementation_guides/`
**Total**: 140 PDFs, 33MB across 41 trading partners

## Inventory by Trading Partner

| Partner | PDFs | Version | Key Transaction Sets |
|---------|------|---------|---------------------|
| **Kroger** | 18 | 5010 | 850, 810, 855, 856, 860, 852, 875, 940, 997, 812, 214 |
| **Walmart** | 10 | 5010 | 810, 850 (Import/Store Planning), 856 (DSDC/Std Carton), 812, 816, 820, 864, 997 |
| **D&H Distributing** | 10 | 4010 | 850, 855, 810, 856, 832, 846, 867, 870 (both customer & vendor) |
| **Walgreens** | 10 | 4010 | 810 (DC/DSD), 820, 832 (DC/DSD), 850, 852, 855, 856 (DC/DSD) |
| **NAPA/GPC** | 8 | 5010/4010 | 850, 855, 824, 846, 812 + welcome packet |
| **Nordstrom** | 5 | mixed | 850, 855, 856, 860, Supplier Compliance Master |
| **Lowe's** | 5 | 4010/3010 | 850, 810, 856, intro, examples |
| **SPS Generic** | 5 | generic | 845, 850, 855, 856, 810 specs |
| **Costco** | 4 | 4010 | 850/856 E-Warehouse, 852/855, Trading Partner Profile, Warehouse List |
| **Kohl's** | 4 | 4010 VICS | 850, 855, 856, 810 (VendorPortal) |
| **AutoZone** | 4 | mixed | 850, 856, 810, 846 |
| **Sally Beauty** | 3 | 5010 | 850, 855, 856 |
| **KeHE Distributors** | 3 | 5010 | 850, 855 (x2) |
| **Advance Auto Parts** | 3 | 4010 | 810, 850, 824 |
| **Kmart** | 3 | mixed | 810, 850, Remittance Reference Codes |
| **Rite Aid** | 2 | 5010 | 852, 810 |
| **Sears** | 2 | 4010 | 820, 850 |
| **Amazon** | 2 | mixed | 810, 850 |
| **Family Dollar** | 2 | 4030 | 850 (Multi-Loc), 810 (DSD) |
| **C.H. Robinson** | 2 | mixed | 204 (Intl Dray), 204 (Truckload/LTL) |
| **Academy Sports** | 2 | 5010 | 856, 855 |
| **Loblaw** | 2 | 5010 VICS | 810, 864 |
| **Lipari Foods** | 2 | 5010 | 850, 855 |
| **BRP Inc** | 2 | mixed | 997, 860 |
| **99 Cents** | 2 | mixed | 810, 856 |
| **Best Buy** | 2 | 4010 | 850 (Canada), 852 VMI |
| **Macy's** | 2 | 4030 VICS | 850, Technology Contact List |
| **Home Depot** | 2 | mixed | Non-Merchandise Guide, Invoice SAC Codes |
| **Vallen Distribution** | 2 | 4010 | 850, 856 |
| **B&H Photo** | 1 | 4010 | 860 |
| **Canadian Tire** | 1 | 4010 | 810 EVOR |
| **Core-Mark** | 1 | 5010 | 850 |
| **Cornerstone** | 1 | 5010 | 846 |
| **CVS** | 1 | mixed | 810 DSD |
| **Dollar General** | 1 | 4010 VICS | -- (HTML, removed) |
| **Orgill** | 1 | 4010 | 855 |
| **Sportsman's Warehouse** | 1 | 4030 | 860 |
| **Target** | 1 | mixed | UCC128 Label Approval |
| **Tillys** | 1 | 5010 | 810 |
| **True Value** | 1 | 4010 | 810 |
| **Ulta** | 1 | 4030 | -- (HTML, removed) |
| **Woodcraft** | 1 | 5010 | 850 |

## Sources

### Primary PDF Sources

| Source | URL Pattern | Content |
|--------|------------|---------|
| **edi.jobisez.com** | `/edi-igs/{Partner}/{file}.pdf` | Largest public archive of trading partner EDI guides. A-Z directory. |
| **community.spscommerce.com** | `/wp-content/uploads/{YYYY}/{MM}/{file}.pdf` | SPS Commerce hosts vendor-specific guides as PDFs. |
| **edi.kroger.com** | `/EDIPortal/documents/Maps/{division}/{file}.pdf` | Official Kroger EDI portal -- best single-retailer source. |
| **iconnect-corp.com** | `/specs/vendors/{partner}/{file}.pdf` | iConnect hosts vendor-specific specs (AutoZone, Advance Auto, Lowe's, Bealls). |
| **dandh.com** | `/docs/EDI_Guides/{Customer\|Vendor}/{file}.pdf` | D&H complete EDI guide set. |
| **fedex.com** | `/content/dam/fedex/.../` | FedEx official 210/820 guides (CDN was down during collection). |
| **partners.bestbuy.com** | `/documents/{docId}/...` | Best Buy partner portal docs. |
| **opentext.com** | `/assets/documents/en-US/pdf/...` | OpenText/B&H Photo guides (some URLs broken). |

### Web-Based Guide Sources (Not Downloaded)

| Source | URL | Content |
|--------|-----|---------|
| **Stedi** | `portal.stedi.com/app/guides/view/{partner}/...` | Interactive web-based guides for Walmart, Home Depot, Target, Costco, Walgreens, Kohl's, JCPenney, Wayfair, FedEx, AutoZone |
| **Stedi Network Index** | `stedi.com/edi/network/{partner}` | Index pages linking to all guides per partner |
| **MacysNet** | `macysnet.com/mdocweb/documents.aspx?category=EDI` | Macy's document manager (requires portal login) |
| **CVS Suppliers** | `cvssuppliers.com/document-library/electronic-data-interchange` | CVS supplier portal |

### GitHub EDI Repositories

| Repo | Description |
|------|-------------|
| `michaelachrisco/Electronic-Interchange-Github-Resources` | Curated list of EDI Github resources |
| `walmartlabs/gozer` | Walmart's open-source X12 parser (Java) |
| `EdiFabric/X12.NET` | X12 4010 and HIPAA 5010 C# examples |
| `databricks-industry-solutions/x12-edi-parser` | X12 reader/writer for Databricks |
| `copyleftdev/x12-edi-tools` | Python X12 EDI tools |
| `olmelabs/EdiEngine` | .NET EDI X12 reader/writer/validator |

## Failed Downloads (Behind Auth/CDN)

These guides exist but could not be downloaded via curl:

### FedEx (CDN was returning "System Down")
- 210/820 X12-4060 Implementation Guide (Jan 2022)
- 210 New Customer Guide
- 210/820 Motor Carrier Details
- 210/997 4060 APAC
- 110/820 X12-4010 Guide
- 110/820 X12-4060 Guide
- EDI Overview Guide (Apr 2021)

### Jobisez.com (Requires guide.aspx viewer, returns HTML)
- **Target**: 850 Domestic Basic/SDQ, 856 Pre-Distro, 860 Domestic Basic, 810 Invoice
- **Home Depot**: 850 PO 4060, 810 Invoice 4060, 856 ASN 4060 (MultiplePO/BEAR), ASN Implementation Guide
- **Walmart**: 850 Basic, 855 POAck, 856 ASN PO, 860 POChange
- **Amazon DC**: 850 Procurement Mapping Guide, 856 ASN X12
- **Dollar General**: 850 PO 4010 VICS
- **Bed Bath & Beyond**: EDI Mapping
- **Office Depot**: 856 ASN
- **Menards**: VMI Implementation
- **Vallen**: 850 PO 4010
- **Costco**: 850 PO/810 Invoice 4010, 810 Invoice Canada

### OpenText/B&H Photo (URLs broken/redirecting)
- 850 PO Guidelines
- 810 Invoice Guidelines
- 855 PO Ack
- 832 Price/Sales Catalog

## Transaction Set Coverage

| Txn Set | Name | # of Guides | Partners With Guides |
|---------|------|-------------|---------------------|
| **850** | Purchase Order | 35+ | Walmart, Kroger, Walgreens, NAPA, Costco, Kohl's, Nordstrom, Lowe's, Sally Beauty, D&H, AutoZone, Advance Auto, Best Buy, Macy's, Family Dollar, etc. |
| **810** | Invoice | 30+ | Walmart, Kroger, Walgreens, NAPA, Kohl's, Rite Aid, D&H, Lowe's, Tillys, True Value, Canadian Tire, Loblaw, Family Dollar, CVS, etc. |
| **856** | ASN / Ship Notice | 20+ | Walmart, Kroger, Walgreens, Costco, Nordstrom, Sally Beauty, D&H, Academy Sports, Vallen, AutoZone, 99 Cents, etc. |
| **855** | PO Acknowledgment | 15+ | Kroger, Walgreens, NAPA, Kohl's, Nordstrom, Sally Beauty, D&H, Academy Sports, Orgill, Lipari, KeHE, etc. |
| **852** | Product Activity (POS) | 5+ | Kroger, Walgreens, Rite Aid, Best Buy |
| **846** | Inventory Inquiry/Advice | 3+ | NAPA, Cornerstone, AutoZone, D&H |
| **860** | PO Change | 5+ | Kroger, Nordstrom, BRP, Sportsman's Warehouse, B&H Photo |
| **820** | Remittance Advice | 3+ | Walmart, Walgreens, Sears |
| **824** | Application Advice | 3+ | NAPA, Kroger, Advance Auto |
| **812** | Credit/Debit Adjustment | 3+ | Walmart, NAPA, Kroger (Fred Meyer) |
| **875** | Grocery PO | 3 | Kroger (Modernized, 5010 UCS, DSD) |
| **832** | Price/Sales Catalog | 3+ | Walgreens (DC/DSD), D&H |
| **816** | Organizational Relationships | 1 | Walmart |
| **864** | Text Message | 2 | Walmart, Loblaw |
| **867** | Product Transfer | 1 | D&H |
| **870** | Order Status | 1 | D&H |
| **940** | Warehouse Shipping Order | 1 | Kroger |
| **997** | Functional Acknowledgment | 3+ | Walmart, Kroger, BRP |
| **204** | Motor Carrier Load Tender | 2 | C.H. Robinson (Intl Dray, Truckload/LTL) |
| **214** | Shipment Status | 1 | Kroger (Fred Meyer) |
| **210** | Motor Carrier Freight Invoice | 0 (FedEx CDN down) | -- |
| **845** | Price Authorization | 1 | SPS Generic |

## Version Distribution

| Version | # of Guides | Primary Partners |
|---------|-------------|-----------------|
| **5010** | ~50 | Kroger, Walmart, NAPA, Sally Beauty, Rite Aid, Core-Mark, Academy Sports, Woodcraft, Cornerstone, Tillys |
| **4010** | ~50 | Walgreens, Costco, Lowe's, D&H, AutoZone, Advance Auto, Kohl's, True Value, Best Buy, Orgill, Sears |
| **4030** | ~10 | Macy's, Family Dollar (4030), Sportsman's Warehouse, Regis |
| **4060** | ~5 | Home Depot (failed downloads), FedEx (failed downloads) |
| **3010** | 1 | Lowe's (810 Invoice -- very old) |

## Download Script

The download script is at `/Users/me/Downloads/edi/implementation_guides/download_guides.sh`.

- Rerunnable (skips already-downloaded files)
- Organized by trading partner subdirectory
- Automatically names files with `{TxnSet}_{Description}_{Version}.pdf` pattern

```bash
# Re-run to pick up any missed downloads
bash /Users/me/Downloads/edi/implementation_guides/download_guides.sh
```

## Schema Design Implications

### What the Guides Reveal About Implementation Variability

1. **DC vs DSD Splits**: Walgreens, Family Dollar, Home Depot all have separate guides for Distribution Center (DC) vs Direct Store Delivery (DSD) flows. The same transaction set (e.g., 810) has different required segments depending on the fulfillment path.

2. **VICS vs Standard X12**: Kohl's, Macy's, Dollar General use VICS (Voluntary Interindustry Commerce Solutions) overlays on X12. VICS restricts the base X12 spec further for retail.

3. **UCS for Grocery**: Kroger uses UCS (Uniform Communication Standard) grocery-specific transaction sets (875/876/880) alongside standard X12. These are industry extensions.

4. **Per-Partner Segment Requirements**: Even for the same transaction set and version, different partners mark different segments as Required vs Optional vs Not Used. The schema system needs layered profiles.

5. **Qualifier Code Restrictions**: Each partner restricts which code values are valid. Walmart's N1-01 accepts BT/RT/ST/FD; Nordstrom accepts different sets. Must model per-partner code lists.

6. **856 Hierarchy Variations**: The HL hierarchy in 856 varies significantly:
   - Walmart: Tare Level (SOPTI with S→O→P→T→I)
   - Amazon: SOPTI (Ship→Order→Pack→Tare→Item)
   - Standard retail: SOPI (Ship→Order→Pack→Item)
   - Some partners: SOI (no Pack level)

7. **Version Coexistence**: Partners range from 3010 (Lowe's legacy) to 5010 (Kroger). Suppliers must support multiple versions simultaneously.

8. **Compliance Penalties Drive Adoption**: Walmart ($50-500/incident), Target ($0.75/carton), Kroger (1% of payment), Costco (1-5% of PO). The 856 ASN is the #1 source of chargebacks.
