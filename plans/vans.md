# EDI Value Added Networks (VANs) Reference

## How VANs Work

### Core Architecture: Store-and-Forward Mailboxes

All VANs operate on the same fundamental model:

1. **Sender** transmits an EDI document to their mailbox on the VAN using a supported protocol (AS2, SFTP, etc.)
2. **VAN** validates the envelope structure, and routes to the receiver's mailbox based on **ISA Sender/Receiver ID addressing**
3. **Receiver** retrieves documents from their mailbox via their preferred protocol

**EDI Address = ISA Qualifier + ID** (e.g., ISA05/ISA06 for sender, ISA07/ISA08 for receiver). This is how all VANs route documents.

### VAN Interconnect: One VAN Reaches All Partners

**You pick ONE VAN and can reach partners on ANY VAN** -- thanks to VAN interconnect agreements. It works like email providers: a Gmail user can email a Yahoo user. Similarly, a BOLD VAN customer can exchange EDI with an OpenText customer transparently.

Interconnect uses the **X12.56 Mailbag Protocol** and **TA3 Interchange Delivery Notices** for cross-network delivery confirmation. VANs connect at **layer 7** (application/message routing).

#### What Interconnect Gives You
- **Document routing** across VAN boundaries (your 850 on BOLD reaches Walmart on OpenText)
- The VANs handle the cross-network handoff transparently
- Your ISA qualifier/ID is your "address" -- it works regardless of which VAN you're on

#### What Interconnect Does NOT Give You
- **No automatic trading partner setup**. You still must be onboarded with each trading partner individually. Having a VAN mailbox doesn't mean Walmart knows you exist.
- **Interconnect fees** often apply -- the receiving VAN charges the sending VAN, and that cost gets passed to you (hidden in per-KC pricing, or absorbed in BOLD's per-partner model)
- **Some partners mandate a specific VAN or protocol**. Target requires VAN (no direct AS2). Walmart mandates AS2 for large suppliers. Dollar Tree uses Ariba exclusively.

#### Why Companies Sometimes Use Multiple VANs
- Legacy relationships (acquired a division already on a different VAN)
- Partner mandates (rare but happens)
- Cost optimization (high-volume partners on one VAN, low-volume on another)
- VAN consolidation is a major sales pitch for OpenText and SPS Commerce

### VANs Do NOT Standardize X12 Messages

**Every trading partner has their own Implementation Guide (IG)**, which is a subset of the full X12 spec. VANs do NOT harmonize or standardize these.

#### What the VAN Does (Dumb Pipe)
- Receives your envelope (ISA/GS/ST)
- Validates the envelope structure (ISA/GS are well-formed)
- Routes to the correct mailbox based on ISA addressing
- Delivers and confirms

#### What the VAN Does NOT Do
- Validate content against a partner's implementation guide
- Transform your 856 to match Walmart's format vs Amazon's format
- Enforce that you included the right qualifier codes or segments

#### Where Customization Lives

The customization burden falls on **you (or your EDI managed service provider)**:

```
                    Your ERP System
                         │
                         ▼
              ┌─────────────────────┐
              │   EDI Translator    │  ← Per-partner customization
              │   / Mapper          │    lives HERE
              │                     │
              │  Walmart map        │  ← Different map per partner
              │  Amazon map         │
              │  Target map         │
              │  Kroger map         │
              └─────────────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │      Your VAN       │  ← VAN just routes, doesn't
              │  (OpenText, BOLD,   │    care about content
              │   Descartes, etc.)  │
              └─────────────────────┘
                         │
                    ┌────┴────┐
                    ▼         ▼
               Walmart     Amazon
               (their VAN)  (AS2 direct)
```

#### Who Handles the Mapping?

| Provider Type | What They Do |
|---|---|
| **Pure VAN** (OpenText, BOLD, Descartes) | Transport only. You bring your own translator/mapper. |
| **Managed Service** (SPS Commerce, GraceBlood VelociLink, Cleo) | They build and maintain per-partner maps FOR you. |
| **Hybrid** (TrueCommerce, Orderful) | VAN + mapping + ERP integration bundled. |

SPS Commerce's entire business model is "we already have 4,000+ retailer maps built -- plug in and we handle compliance." That's why they charge more than a pure VAN.

### Common ISA Qualifier Codes

| Qualifier | Description | Common Use |
|-----------|-------------|------------|
| 01 | DUNS Number | Large enterprises |
| 08 | UCC EDI Communications ID | VAN mailbox addresses |
| 12 | Telephone Number | Smaller partners |
| 14 | DUNS+4 (DUNS plus suffix) | Multi-location orgs |
| 20 | Health Industry Number (HIN) | Healthcare |
| 27 | State License Number | Regulated industries |
| 30 | US Federal Tax ID | Tax-related |
| ZZ | Mutually Defined | Most common for VAN mailbox IDs |

---

## VAN 1: OpenText Trading Grid (formerly GXS / GEIS)

### History Timeline

| Year | Event |
|------|-------|
| 1962 | Dartmouth Time-Sharing System begins (Dartmouth College / GE) |
| 1967 | GE establishes Information Services division |
| 1979 | GEISCO formed as GE/Honeywell joint venture |
| ~1982 | GEISCO becomes wholly-owned GE subsidiary, later **GEIS** |
| 1998 | GEIS exceeds 100,000 trading partners |
| Mar 2000 | GEIS rebrands to **GXS** (Global Exchange Services) |
| Jun 2002 | **Francisco Partners** acquires GXS from GE for ~$800M |
| 2004 | Acquires HAHT Commerce ($30M) and **IBM's EDI/Business Exchange Services** |
| Oct 2004 | **GXS Trading Grid** launches as cloud SaaS |
| Jun 2010 | GXS merges with **Inovis** (brings TrustedLink EDI via Harbinger/Peregrine lineage) |
| 2012 | 550K+ businesses connected, 10B+ transactions/year |
| Jan 2014 | **OpenText acquires GXS** for $1.165B enterprise value |
| 2025+ | $11T annual commerce, 1M+ trading partners, 33B+ transactions/year, 175 countries |

### Scale

- **World's largest VAN**
- 1,000,000+ connected trading partners
- 33+ billion transactions/year
- $11 trillion in commerce facilitated annually
- 175 countries, 21+ industries, 200+ ERP connectors

### Connection Protocols

| Protocol | Details |
|----------|---------|
| **AS2** | Over HTTPS (port 443). Digital signatures, encryption, MDN (sync/async). Primary protocol for high-volume partners. |
| **AS3** | FTP-based EDIINT variant |
| **AS4** | SOAP/ebMS3-based web services EDIINT |
| **SFTP** | SSH-2, RSA/DSA keys, 1024 or 2048-bit. **Azure SFTP-SSH connector has known compatibility issues.** |
| **FTPS** | FTP over SSL/TLS. Only qualified client software supported. |
| **HTTPS** | Scripted or portal (Trading Grid Online). **Unencrypted HTTP prohibited.** |
| **OFTP / OFTP2** | Over X.25, ISDN, or IP. OFTP2 adds compression and encryption. |
| **MQ Series** | IBM WebSphere MQ. Requires VPN or leased line. |
| **X.400** | Legacy ITU messaging |
| **RNIF** | RosettaNet Implementation Framework |
| **SAP/ALE** | Direct SAP IDoc integration |
| **Expedite** (Legacy) | Proprietary GXS client. SSL TCP/IP. **Does NOT support AS2.** |

**Important restrictions**:
- Open FTP over internet is **NOT allowed** -- requires VPN/leased line
- Unencrypted HTTP is **prohibited**
- GXS Ecxpress only supports **Active FTP** (firewall config required)

### Network Architecture

- **Mailboxes**: Each customer gets a unique electronic mailbox on registration
- **Mailslots**: Sub-categories within mailbox (by partner, doc type, priority, payment method). Configured via Account Manager.
- **EDI Addresses**: Multiple per mailbox. Configured via Trading Grid Online (TGO) portal.
- **Routing**: Based on ISA qualifier + ID in envelope. Qualifier/destination/alias tables resolve target mailbox.
- **Retention**: Configurable up to **45 days** per interchange

### Key Portals and Endpoints

| Service | URL |
|---------|-----|
| Trading Grid Online (TGO) | `https://tradinggrid.opentext.com/` |
| Trading Grid Catalogue | `https://catalogue.gxs.com/` |
| PKI/Certificate Services | `https://pki.tradinggrid.com/` |
| Certificate Downloads | `https://www.opentext.com/support/digital-certificates-for-trading-partners-and-customers` |
| Trading Grid Intelligence (EU) | `https://visibilityms1.eu.gxs.com/` |

### VAN Interconnect Details

- **Message Classes**: `#E2` (X12), `#EC` (UCS), `#EE` (EDIFACT)
- **Delivery Ack**: Uses **TA3** (Interchange Delivery Notice) between VANs
- Interconnects at **layer 7** (application/message routing)

### Supported Standards

EDI: X12 (all versions), EDIFACT, TRADACOMS, RosettaNet, ebXML, Odette, SWIFT, VICS
Data: XML, JSON, CSV, SAP IDocs, custom formats
E-Invoicing: XRechnung, ZUGFeRD/Factur-X, Peppol BIS 3.0, FatturaPA, UBL/XML

### Service Tiers

| Feature | Foundation | Enterprise |
|---------|-----------|-----------|
| Connectivity | AS2, SFTP, FTPS, HTTPS | Full protocol suite |
| Trading Partners | Up to 50 | Unlimited |
| Document Maps | Up to 100 | Unlimited |
| Support | 24x5 (optional 24x7) | Full 24x7 |
| ERP Adapters | NetSuite, D365, SAP, Infor, Sage | Full catalog |

### Onboarding

1. Contract with OpenText, mailbox provisioned
2. EDI address assignment (qualifier + ID)
3. Certificate exchange via PKI portal
4. Connectivity testing (protocol-level)
5. Document mapping and translation setup
6. Trading partner profile config in TGO
7. End-to-end testing with partners
8. Go-live

### Pricing

- **Not publicly disclosed** -- custom quotes required
- Historical model: per-kilocharacter (1 KC = 1,024 chars)
- Current model: usage-based and/or subscription
- Interconnect fees: negotiated per contract

---

## VAN 2: BOLD VAN

### Company Profile

- **Founded**: 1999, Westlake, OH
- **Type**: Private, veteran-owned
- **Employees**: ~20 (support across 3 US time zones + Europe)
- **Innovation**: First VAN to offer per-partner pricing (launched 2014)
- **Uptime**: 99.998% over 10 years
- **Monthly volume**: ~2 million interchanges
- **Tier**: Tier 1 VAN (full interconnect capability)
- **Certifications**: SOC 2 Type II (continuous monitoring via Vanta), pen-tested

### Connection Protocols

| Protocol | Details |
|----------|---------|
| **AS2** | Certificate-based, encrypted, MDN receipts. No extra charge. |
| **SFTP** | SSH-based. Supports key auth or password. |
| **FTP / FTPS** | Standard and SSL/TLS-secured |
| **HTTP / HTTPS** | Web-based with API connectors for ERPs |
| **Web Services** | API-based real-time ERP connectivity |
| **X.400** | Legacy support |
| **SMTP** | Email-based EDI |
| **Pre-configured Data Mover** | Proprietary secure tool for simplified connectivity |

### Network Architecture

- **Store-and-forward** with centralized mailboxes
- Routing based on **ISA Sender/Receiver ID** combinations
- **One trading partner** = one unique ISA Sender/Receiver ID combo (multiple GS IDs under same ISA = 1 partner)
- Redundant store-and-forward (if partner down, docs stored and retried)
- Immutable audit logs for every send/receive/transform/delivery event
- Proactive alerting for failed transmissions

### VAN Interconnects

- Full Tier 1 interconnect with all major VANs (OpenText, SPS Commerce, Descartes, etc.)
- Partners can be on BOLD VAN, on another VAN, or using direct AS2 -- all work transparently
- Interconnect fees appear included in per-partner pricing (no published surcharge)

### WebEDI Portal (BOLD Manager)

- Web-based dashboard accessible from any device
- Multi-parameter search: trading partner, date, transaction set, control number
- Data retention: 90 days (Essentials), 1 year (Business), 2 years (Enterprise)
- Archive access up to 7 years

### Supported Standards

X12 (all versions), EDIFACT, TRADACOMS (UK retail), ODETTE (automotive), VDA (German auto), X.400, non-EDI docs available on request

### Pricing (Per-Partner, Published)

| Trading Partners | Essentials | Business | Enterprise |
|---|---|---|---|
| 1 | $99/mo | $109/mo | $129/mo |
| 2-9 | $69/partner/mo | $79/partner/mo | $99/partner/mo |
| 10-35 | $59/partner/mo | $69/partner/mo | $89/partner/mo |
| 36-100 | $39/partner/mo | $49/partner/mo | $69/partner/mo |
| 100+ | Custom | Custom | Custom |

**Key pricing rules**:
- You only pay for partners you **actually exchange data with** that month
- Volume per partner is **unlimited** (double your docs, same bill)
- No setup fees, no document fees, no per-KC charges
- First 3 months free
- Month-to-month, no lock-in contracts
- Price-match guarantee (upload current VAN bill)
- Claimed savings: 40-82% vs traditional kilo-character VANs

| Feature | Essentials | Business | Enterprise |
|---------|-----------|----------|------------|
| Unlimited transactions | Yes | Yes | Yes |
| Data retention | 3 months | 1 year | 2 years |
| Support | Chat + email | Phone + chat + email | Dedicated manager |
| Users | 1 | 2+ | Multiple |
| 997 Reconciliation | No | No | Yes |
| API Connectivity | No | No | Yes |

### Onboarding (Same-Day Possible)

1. **Sign up** online -- mailbox created and activated within minutes
2. **Protocol discovery** -- select and test preferred comm method
3. **Trading partner config** -- BOLD handles contacting all partners, AS2 cert exchange, VAN interconnects (free, at no charge)
4. **Portal access** -- BOLD Manager dashboard
5. **Go-live** -- scheduled activation coordinated across all partners

- VAN migration: starts 10 AM, done by noon (same day)
- Full new onboarding: under 2 weeks
- Trading partner onboarding: free, handled by BOLD VAN
- Complimentary EDI compliance service (mapping, translation, testing)

---

## VAN 3: Descartes (Global Logistics Network)

### Company Profile

- **Founded**: 1981, Waterloo, Ontario, Canada
- **Public**: TSX: DSG / NASDAQ: DSGX
- **Revenue**: ~$703.7M USD (trailing 12 months, Oct 2025)
- **Market Cap**: ~$5.4B USD
- **Employees**: ~2,524
- **EBITDA Margin**: ~41% (highest in sector)
- **Total Acquisitions**: 50
- **Focus**: Logistics, transportation, supply chain, customs

### Scale (Global Logistics Network)

- 26,000+ direct customers
- 200,000+ connected trading parties
- 160+ countries
- 24 billion+ messages/year
- 1 billion+ shipping routes managed
- Certified Peppol Access Point since 2019

### Connection Protocols

| Protocol | Details |
|----------|---------|
| **AS2 / AS4** | Primary secure transport. Certificate exchange via Mailbox Maintenance portal. |
| **SFTP / FTPS** | Batch document exchange |
| **HTTP / HTTPS** | Web-based secure connections |
| **REST API** | Real-time synchronous (sub-second latency) |
| **SOAP** | Legacy web services |
| **OFTP** | Odette (European automotive) |
| **X.400** | Legacy messaging |
| **AS1** | Email-based EDI |
| **SMTP** | Email protocol |

**Encryption**: TLS for all internet comms + S/MIME or PGP content encryption. MFA mandatory for admin access.

**Certifications**: SOC 2 Type I & II, ISO 27001, ISO 20000, GDPR processing agreements

### Network Architecture

- **Mailbox system**: Each partner has a mailbox; routing via ISA/GS envelope identifiers
- **Tracking**: Descartes Track and Trace web-based operations center
- **Email notifications** when new documents arrive
- **Data retention**: At least 18 months for message data, 14-31 days for backups

### SLA Specifications

| Metric | Value |
|--------|-------|
| Monthly Uptime | 99.7% (excluding scheduled maintenance) |
| Scheduled Maintenance | Sundays 7:00-11:00 AM EST, max 12/year |
| Maintenance Notice | 96 hours advance |
| Priority 1 Response | 30 min initial, 12 hr target resolution |
| Priority 2 Response | 30 min initial, 48 hr target resolution |
| Priority 3 Response | 30 min initial, 5 business days target |
| Support Hours | Mon-Fri 8:00 AM - 6:00 PM (EST/CET/HKT) |
| 24/7 Support | Available for P1 (when contracted) |
| Data Deletion on Termination | Within 31 days |

### Supported Standards

EDI: X12, EDIFACT, XML, CargoXML, CargoIMP, ebXML, NWDA, RosettaNet, GS1, ODETTE, Peppol BIS
Custom: Flat files, CSV, partner-specific formats

### Three EDI Tiers

1. **Go-webEDI** (Web Portal): Browser-based, no software, fixed monthly subscription, ideal for small suppliers, SSCC label generation
2. **Integrated EDI**: Full ERP integration (SAP, Oracle, D365, Infor, Exact, NetSuite), 24/7 monitoring, pre-built connection library
3. **Outsourced EDI**: Fully managed operations, Descartes handles everything

### Logistics Specialization (Key Differentiator)

**Descartes Aljex TMS** (acquired 2018, $32.4M):
- Cloud TMS for freight brokers/3PLs
- 325,000+ carrier network
- Automated 204 → 990 → 214 → 210 flow

**Descartes MacroPoint** (acquired 2017, $107M):
- Largest carrier visibility network in North America
- Real-time truck tracking (ELD, GPS, TMS, mobile)
- REST API at `docs.macropoint.com`

**Customs & Trade Compliance**:
- US CBP ACE portal (import/export)
- AES filing (Electronic Export Information)
- Canadian ACI eManifest (CBSA)
- Denied Party Screening (MK Data acquisition)
- Datamyne: global trade data for 180+ countries

**Multimodal**: Air (CargoXML, e-AWB), Ocean (booking, VERMAS, status), Road (TL/LTL tender/status/POD), Express/Postal

### Key Acquisitions

| Year | Company | Focus | Price |
|------|---------|-------|-------|
| 2010 | Porthus | B2B integration, global trade | ~$40.5M |
| 2011 | InterCommIT | B2B-as-a-service, Web EDI | ~$13.8M |
| 2016 | Datamyne | Global trade data (180+ countries) | ~$52.7M |
| 2017 | MacroPoint | Real-time carrier visibility | ~$107M |
| 2018 | Aljex | Cloud TMS for freight brokers | ~$32.4M |
| 2024 | Sellercloud | E-commerce inventory/order mgmt | ~$110M |
| 2025 | 3GTMS | Transportation management | ~$115M |
| 2025 | Finale Inventory | Cloud inventory for e-commerce | ~$40M |

### Pricing

- **Not publicly disclosed** -- custom quotes
- Go-webEDI: low fixed monthly subscription
- Integrated/Outsourced: transaction-driven (per-document or per-KC)
- Interconnect fees may apply
- Industry range: $0.03-$0.20 per document depending on volume

### Onboarding

1. Choose protocol (AS2 most common)
2. Exchange SSL/TLS certificates via Mailbox Maintenance portal
3. Configure ISA/GS identifiers (assigned during setup)
4. Document mapping (X12, EDIFACT, XML, custom)
5. Certification testing with Descartes Activations Team
6. Go-live with monitoring via ITIL-based Service Desk

---

## VAN 4: GraceBlood (ECGrid Reseller)

### Company Profile

- **Founded**: 2003, Baltimore, MD
- **Founders**: Amy Grace, Karen Blood (working together since 1997)
- **Type**: Private LLC
- **Employees**: ~17-50 (estimates vary)
- **Tagline**: "Beyond EDI"
- **Product**: **VelociLink** (fully managed cloud EDI platform)
- **Certifications**: SOC 2 Type II
- **Uptime**: 99.995% over 5 years

### Critical Technical Detail

**GraceBlood does not operate its own VAN infrastructure.** They are a **licensed reseller of Loren Data Corp's ECGrid** platform, which is the underlying network powering the "400,000+ trading relationships" claim.

### ECGrid (by Loren Data Corp, est. 1996)

- ECGrid began in 1997 as web-based VAN connected to US DoD EDI Network
- Since 2001, preferred interconnect network for major e-commerce service providers
- 14,000+ local trading partners, 80+ network/service provider connections
- Described as an "Operating System as a Service (OSaaS)" -- 100% programmable routing switch
- **100% X12.56 compatible** (Mailbag Protocol for cross-VAN tracking)
- **SPS Commerce uses ECGrid** as its underlying VAN infrastructure

### Connection Protocols (via ECGrid)

| Protocol | Details |
|----------|---------|
| **AS2** | HTTPS (SSL/TLS) for real-time secure transmission |
| **SFTP** | Batch document exchange |
| **FTPS** | FTP over SSL/TLS |
| **OFTP** | Odette (European automotive) |
| **X.400** | Legacy messaging |
| **ebXML** | Electronic business XML |
| **HTTP/S** | Standard web access |
| **REST API** | Modern integration |
| **SOAP** | Fine-grained API access (200+ APIs) |
| **FTP** | Legacy (not recommended) |

### ECGridOS API (Primary Modern Interface)

- **Version**: 4.1
- **Base URL**: `https://os.ecgrid.io/v4.1/prod/ECGridOS.asmx`
- **Transport**: HTTPS only (mandatory)
- **Auth**: API/Session ID via user profiles, role-based access
- **Implementations**: .NET 6 and .NET Framework 4.8

**Key API Operations**:

| Operation | API Call | Purpose |
|-----------|----------|---------|
| Upload EDI | `ParcelUploadA` | Post documents, returns ParcelID |
| Check status | `InterchangeInfo` | Document metadata and status |
| Audit trail | `InterchangeManifest` | Processing step history |
| List inbox | `ParcelInBox` | Incoming parcels |
| Download | `ParcelDownloadA` | Fetch docs (base64) |
| Confirm download | `ParcelDownloadConfirm` | Remove from pending |
| Find partner | `TPFind` | Search by company (wildcard %) |
| Search partner | `TPSearch` | Search by qualifier + ID |
| Add partner link | `InterconnectAdd` | Establish trading partnership |
| Add ID | `TPAdd` | Add new IDs to mailboxes |
| Create mailbox | `MailboxAdd` | Create new mailboxes |
| Search inbound | `InterchangeInBox` | By date range/control number |
| Resend | `InterchangeResend` | Resend using internal ID |

### Network Architecture

- **Networks** contain **Mailboxes** (each with unique NetworkID and MailboxID)
- Default mailbox per network = "Root" (ID 0)
- Unlimited mailbox provisioning (self-service, no additional cost)
- Partnerships established via ECGridIDs from `TPSearch`/`TPFind`
- `InterconnectAdd` links ECGridIDs across networks
- Receiver qualifier (ISA07) + ID (ISA08) must be active on ECGrid for routing
- Error 1103 = Unknown Route, Error 1105 = Invalid ISA

### VAN Interconnects

- **SPS Commerce** -- ECGrid is SPS's VAN infrastructure
- **OpenText/GXS** -- interconnect relationship (dispute in 2014, resolved)
- **CovalentWorks** -- listed as major connection
- 80+ total network/service provider connections

### Supported Standards

X12 (primary focus), EDIFACT, XML, JSON, custom/proprietary, Managed File Transfer (non-EDI data)

### GraceBlood Services

- **VelociLink**: Fully managed cloud EDI (translation, mapping, communication)
- **ERP Integration**: NetSuite, D365, CloudSuite, Acumatica, Infor SyteLine/FACTS/A+
- **24/7/365 monitoring** of VAN traffic
- **EDI dashboard** for real-time transaction monitoring
- **Supply chain analytics** via CoEnterprise Syncrofy partnership

### Industries & Notable Customers

- **Food & Beverage**: Santa Monica Seafood
- **Manufacturing**: Retractable Technologies (medical devices), Green Bay Packaging
- **Distribution**: Integrated Supply Network (ISN, largest independent auto tools wholesaler)
- **Retail compliance guides for**: AutoZone, Walmart, Lowe's, US Foods, Giant Food, Gordon Food Service

### Pricing

- **Not publicly disclosed** -- custom quotes only
- ECGrid has moved to either usage-based (per-doc) or Active Trading Partner Plan (flat rate per active partner/month)
- Industry range: $0.01-$5.00 per document

### Important Caveats

- The "400,000+ trading relationships" refers to the **total ECGrid network** across all resellers and connected VANs, not GraceBlood's direct customer base
- GraceBlood's own client portfolio appears to be hundreds to low thousands
- No published self-service onboarding -- direct engagement required
- WebEDI portal: GraceBlood is skeptical of portal-based WebEDI; pushes toward fully integrated EDI

---

## VAN Comparison Summary

| Factor | OpenText | BOLD VAN | Descartes | GraceBlood |
|--------|----------|----------|-----------|------------|
| **Type** | Full VAN owner/operator | Full VAN owner/operator | Full VAN owner/operator | ECGrid reseller |
| **Founded** | 1962 (as GEIS) | 1999 | 1981 | 2003 |
| **Scale** | 1M+ partners | ~20K partners | 200K+ parties | ECGrid network (14K+ local) |
| **Volume** | 33B+ txns/year | ~2M interchanges/mo | 24B+ msgs/year | Not disclosed |
| **Revenue** | Part of OpenText ($5.8B) | Private (est. <$10M) | ~$704M | Private (est. <$10M) |
| **Employees** | 10,000+ (OpenText) | ~20 | ~2,524 | ~17-50 |
| **Focus** | Cross-industry | Mid-market mfg/retail | Logistics/transport | Mid-market food/dist |
| **Pricing** | Custom (per-KC legacy) | Per-partner (published) | Custom (per-doc) | Custom |
| **Protocols** | AS2, SFTP, FTPS, HTTPS, AS3/4, OFTP2, MQ, X.400, SAP/ALE | AS2, SFTP, FTP/S, HTTP/S, X.400, SMTP, Data Mover | AS2/4, SFTP/S, HTTP/S, REST, SOAP, OFTP, X.400 | AS2, SFTP/S, OFTP, ebXML, HTTP/S, REST, SOAP, X.400 |
| **Uptime** | Not published | 99.998% (10yr) | 99.7% SLA | 99.995% (5yr, ECGrid) |
| **Certifications** | Not published | SOC 2 Type II | SOC 2 I+II, ISO 27001, ISO 20000 | SOC 2 Type II |
| **Best for** | Enterprise, global, multi-standard | Cost-conscious mid-market | Logistics/freight/customs | Small/mid food & distribution |
| **Unique strength** | Scale, global reach, 200+ ERP connectors | Transparent pricing, fast onboarding | TMS, customs, carrier visibility | ECGrid API, white-glove service |

---

## Schema Design Implications

1. **VANs are transport-only** -- the schema/validation system must handle all per-partner message customization, not the VAN
2. **Base X12 specs** (full standard for each transaction set/version) serve as the foundation
3. **Per-partner implementation profiles** layer on top (marking segments required/optional/not-used, restricting code values, defining conditional rules)
4. **Validation must be profile-aware** -- validating an 856 means nothing without knowing WHICH partner's 856 rules to apply
5. **ISA/GS envelope validation** is the only thing VANs reliably enforce -- the schema system should validate everything else
