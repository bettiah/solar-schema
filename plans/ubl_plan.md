# UBL Implementation

## Overview

A Python library for parsing UBL schema definitions (XSD), parsing UBL XML documents, validating them, and generating new UBL documents.

**Target:** UBL 2.5 | **Document Types:** 101 | **Format:** XML-based

---

## Architecture

```
Schema Definition Files (xsd/maindoc/, xsd/common/)
         │
         ├──────────────────────────────────────┐
         │                                      │
         ▼                                      ▼
┌─────────────────────┐              ┌─────────────────────┐
│  Runtime Loading    │              │   Code Generation   │
│ (UBLSchemaLoader)   │              │ (UBLSchemaGenerator)│
└─────────────────────┘              └─────────────────────┘
         │                                      │
         │                                      ▼
         │                           ┌─────────────────────┐
         │                           │  Generated Modules  │
         │                           │  (schemas/v2_5/)    │
         │                           └─────────────────────┘
         │                                      │
         ▼                                      ▼
┌─────────────────────────────────────────────────────────┐
│                       UBLSchema                         │
│  document_type + aggregates + basics + data_types      │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    Raw UBL Document (XML)               │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   1. XML PARSER                         │
│  Parse XML, resolve namespaces, build element tree     │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│               2. DOCUMENT MAPPER                        │
│  Map XML elements to schema components (ABIE/BBIE)     │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   3. VALIDATOR                          │
│  Structure → Element → Code → Business Rules           │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│               4. APPLICATION RESPONSE                   │
│  Generate acknowledgment from validation results       │
└─────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
src/edi_schema/ubl/
├── enums.py                  # ComponentType, DataTypeKind, Cardinality
├── models/
│   ├── data_type.py          # UnqualifiedDataType, QualifiedDataType
│   ├── component.py          # ABIE, BBIE, ASBIE, Component
│   ├── document.py           # DocumentType, DocumentSchema
│   └── code_list.py          # CodeList, CodeValue
├── schema_parsers/
│   ├── xsd_parser.py         # XSD schema parser
│   ├── cac_parser.py         # CommonAggregateComponents parser
│   ├── cbc_parser.py         # CommonBasicComponents parser
│   ├── udt_parser.py         # UnqualifiedDataTypes parser
│   ├── qdt_parser.py         # QualifiedDataTypes parser
│   └── code_list_parser.py   # Genericode (.gc) parser
├── schema.py                 # UBLSchema, UBLSchemaLoader
├── schemas/
│   ├── __init__.py           # Public API exports
│   ├── registry.py           # Version dispatch, GeneratedUBLSchemaLoader
│   └── v2_5/                  # Generated 2.5 schemas
├── codegen/
│   ├── generator.py          # UBLSchemaGenerator class
│   └── templates/            # Jinja2 templates
├── ast.py                    # AST node types, error types
├── parser/
│   ├── xml_parser.py         # XML parsing, namespace handling
│   ├── document.py           # Document-level parsing
│   └── mapper.py             # Schema-driven element mapping
├── validator/
│   ├── element.py            # Data types, formats
│   ├── schema.py             # Structure, cardinality
│   ├── code.py               # Code list validation
│   └── core.py               # Orchestration, ValidationResult
├── writer/
│   ├── builder.py            # Document builder API
│   ├── serializer.py         # XML serialization
│   └── namespaces.py         # Namespace management
└── ack/
    └── application_response.py  # ApplicationResponse generation
```

---

## Schema System

### Key Differences from X12/EDIFACT

| Aspect | X12/EDIFACT | UBL |
|--------|-------------|-----|
| **Format** | Delimited text | XML |
| **Schema source** | Proprietary text files | XSD (W3C standard) |
| **Type system** | Simple (AN, ID, N, DT) | Rich (CCTS hierarchy) |
| **Namespaces** | None | Multiple (cac:, cbc:, etc.) |
| **Reusability** | Segments defined per version | Components shared across docs |
| **Extensions** | Limited | Built-in (UBLExtensions) |

### Source Files to Parse

| File | Purpose |
|------|---------|
| `xsd/maindoc/UBL-*.xsd` | Document type schemas (101 files) |
| `xsd/common/UBL-CommonAggregateComponents-2.5.xsd` | Reusable ABIEs (~55K lines) |
| `xsd/common/UBL-CommonBasicComponents-2.5.xsd` | Reusable BBIEs (~7K lines) |
| `xsd/common/UBL-QualifiedDataTypes-2.5.xsd` | Constrained data types |
| `xsd/common/BDNDR-UnqualifiedDataTypes-1.1.xsd` | Base data types |
| `cl/gc/default/*.gc` | Code lists (14 files, Genericode format) |

### Core Models

```python
class ComponentType(Enum):
    """CCTS component classification."""
    ABIE = "ABIE"   # Aggregate Business Information Entity
    BBIE = "BBIE"   # Basic Business Information Entity
    ASBIE = "ASBIE" # Association Business Information Entity


class Cardinality(Enum):
    """Element occurrence constraints."""
    ZERO_OR_ONE = "0..1"
    EXACTLY_ONE = "1"
    ZERO_OR_MORE = "0..n"
    ONE_OR_MORE = "1..n"


@dataclass
class UnqualifiedDataType:
    """Base CCTS data type."""
    name: str                      # e.g., "Amount", "Code", "Date"
    xsd_type: str                  # e.g., "xsd:decimal", "xsd:string"
    attributes: list[Attribute]    # e.g., currencyID, unitCode


@dataclass
class QualifiedDataType:
    """Constrained data type with restrictions."""
    name: str                      # e.g., "CurrencyCodeType"
    base_type: str                 # Reference to UDT
    code_list: str | None          # e.g., "CurrencyCode-2.4"
    pattern: str | None            # Regex restriction


@dataclass
class BBIE:
    """Basic Business Information Entity - leaf data element."""
    name: str                      # e.g., "ID", "IssueDate", "Amount"
    definition: str
    cardinality: Cardinality
    data_type: str                 # Reference to UDT/QDT
    representation_term: str       # e.g., "Identifier", "Date", "Amount"


@dataclass
class ASBIE:
    """Association BIE - reference to another ABIE."""
    name: str                      # e.g., "AccountingSupplierParty"
    definition: str
    cardinality: Cardinality
    associated_abie: str           # Target ABIE name


@dataclass
class ABIE:
    """Aggregate Business Information Entity - complex type."""
    name: str                      # e.g., "Party", "Address", "Invoice"
    definition: str
    bbies: list[BBIE]              # Basic elements
    asbies: list[ASBIE]            # Associated ABIEs
    namespace: str                 # cac: or document namespace


@dataclass
class DocumentType:
    """Complete document schema."""
    name: str                      # e.g., "Invoice"
    namespace: str                 # Document-specific namespace
    root_abie: ABIE                # Root element definition
    version: str = "2.5"


@dataclass
class CodeList:
    """Controlled vocabulary from Genericode."""
    id: str                        # e.g., "CurrencyCode-2.4"
    name: str                      # e.g., "Currency Code"
    agency: str                    # e.g., "ISO"
    values: dict[str, str]         # code -> description


@dataclass
class UBLSchema:
    """Complete schema for a document type."""
    document_type: DocumentType
    aggregates: dict[str, ABIE]    # All CAC components used
    basics: dict[str, BBIE]        # All CBC elements used
    data_types: dict[str, UnqualifiedDataType | QualifiedDataType]
    code_lists: dict[str, CodeList]
    version: str = "2.5"
```

### Schema API

```python
# Recommended: Generated schemas (fastest)
from edi_schema.ubl.schemas import GeneratedUBLSchemaLoader, get_schema

loader = GeneratedUBLSchemaLoader(version="2.5")
schema = loader.load("Invoice")

# Or use convenience functions
schema = get_schema("Invoice", version="2.5")

# Runtime loader for custom schema directories
from edi_schema.ubl.schema import UBLSchemaLoader
loader = UBLSchemaLoader(Path("/custom/ubl/xsd/path"))
```

### Code Generation

```bash
task codegen-ubl-2.5    # Generate 2.5 schemas
task codegen-ubl-all    # Generate all versions
```

---

## Parser System

### AST Types

```python
@dataclass
class SourcePosition:
    """Location in source XML."""
    line: int
    column: int
    xpath: str


@dataclass
class ParsedAttribute:
    """Parsed XML attribute."""
    name: str
    value: str
    namespace: str | None


@dataclass
class ParsedElement:
    """Parsed XML element with schema binding."""
    tag: str
    namespace: str
    value: str | None              # For BBIEs
    attributes: list[ParsedAttribute]
    children: list[ParsedElement]  # For ABIEs
    position: SourcePosition
    schema_component: ABIE | BBIE | ASBIE | None


@dataclass
class ParsedDocument:
    """Complete parsed UBL document."""
    document_type: str             # e.g., "Invoice"
    version: str                   # e.g., "2.5"
    root: ParsedElement
    namespaces: dict[str, str]     # prefix -> uri


@dataclass
class ParseError:
    """Parse or validation error."""
    code: str
    message: str
    severity: ErrorSeverity
    position: SourcePosition | None
    xpath: str | None
    category: ErrorCategory


@dataclass
class ParseResult:
    """Result of parsing a UBL document."""
    document: ParsedDocument | None
    errors: list[ParseError]
    warnings: list[ParseError]
```

### XML Parser

- Use `lxml` for fast XML parsing with namespace support
- Extract document type from root element
- Resolve namespace prefixes to URIs
- Build element tree with position tracking
- Handle XML entities and CDATA

### Document Mapper

- Match elements to schema ABIEs/BBIEs by qualified name
- Track traversal path for error reporting
- Detect unknown elements
- Handle optional vs required elements

---

## Validation Levels

| Level | Description | Location |
|-------|-------------|----------|
| STRUCTURAL | Well-formed XML, namespace resolution | xml_parser |
| SCHEMA | Element presence, order, cardinality | validator/schema.py |
| ELEMENT | Data types, lengths, formats | validator/element.py |
| CODE | Coded values against code lists | validator/code.py |
| BUSINESS | Cross-element rules, Schematron | validator/business.py |

### Element Validation

Data type validation for CCTS types:

| Type | Validation |
|------|------------|
| Amount | Decimal, currencyID attribute required |
| Code | String, optional listID/listVersionID |
| Date | ISO 8601 date (YYYY-MM-DD) |
| DateTime | ISO 8601 datetime |
| Identifier | String, optional schemeID/schemeAgencyID |
| Indicator | Boolean ("true"/"false") |
| Measure | Decimal, unitCode attribute required |
| Numeric | Decimal |
| Percent | Decimal (0-100) |
| Quantity | Decimal, unitCode attribute required |
| Rate | Decimal |
| Text | String, optional languageID |
| Time | ISO 8601 time (HH:MM:SS) |
| BinaryObject | Base64, mimeCode attribute |

### Cardinality Validation

```python
# Schema defines cardinality
InvoiceLine: 1..n  # Required, one or more
InvoicePeriod: 0..1  # Optional, at most one
Note: 0..n  # Optional, any number
ID: 1  # Required, exactly one
```

---

## Writer System

### Document Builder

```python
from edi_schema.ubl.writer import UBLWriter, InvoiceBuilder

# Method 1: Fluent builder
writer = UBLWriter(version="2.5")
invoice = (
    writer.invoice()
    .id("INV-001")
    .issue_date("2024-01-15")
    .supplier_party(
        lambda p: p
        .name("Supplier Corp")
        .address(street="123 Main St", city="Boston", country="US")
    )
    .customer_party(
        lambda p: p
        .name("Customer Inc")
        .address(street="456 Oak Ave", city="New York", country="US")
    )
    .add_line(
        lambda l: l
        .id("1")
        .quantity(10, unit="EA")
        .line_amount(100.00, currency="USD")
        .item(name="Widget", description="Standard widget")
    )
    .legal_monetary_total(
        line_extension=100.00,
        tax_exclusive=100.00,
        payable=100.00,
        currency="USD"
    )
    .build()
)

xml_output = invoice.to_xml()

# Method 2: Dict-based construction
invoice_data = {
    "ID": "INV-001",
    "IssueDate": "2024-01-15",
    "AccountingSupplierParty": {
        "Party": {
            "PartyName": {"Name": "Supplier Corp"},
            "PostalAddress": {...}
        }
    },
    "InvoiceLine": [...]
}
xml_output = writer.build("Invoice", invoice_data)
```

### Serialization Options

```python
# Pretty print with indentation
xml = document.to_xml(pretty=True, indent=2)

# Compact (no whitespace)
xml = document.to_xml(pretty=False)

# With XML declaration
xml = document.to_xml(xml_declaration=True, encoding="UTF-8")

# Namespace prefix preferences
xml = document.to_xml(prefix_map={"cac": "...", "cbc": "..."})
```

---

## ApplicationResponse Generation

UBL's equivalent of X12 997 / EDIFACT CONTRL:

```xml
<ApplicationResponse xmlns="...">
  <ID>AR-001</ID>
  <IssueDate>2024-01-15</IssueDate>
  <ResponseCode>AP</ResponseCode>  <!-- AP=Accepted, RE=Rejected -->
  <DocumentResponse>
    <Response>
      <ResponseCode>RE</ResponseCode>
      <Description>Validation errors found</Description>
    </Response>
    <DocumentReference>
      <ID>INV-001</ID>
      <DocumentType>Invoice</DocumentType>
    </DocumentReference>
    <LineResponse>
      <LineReference>
        <LineID>1</LineID>
      </LineReference>
      <Response>
        <ResponseCode>RE</ResponseCode>
        <Description>Invalid currency code</Description>
      </Response>
    </LineResponse>
  </DocumentResponse>
</ApplicationResponse>
```

### Response Codes

| Code | Meaning |
|------|---------|
| AP | Accepted |
| RE | Rejected |
| AB | Message acknowledged |
| CA | Conditionally accepted |
| IP | In process |

---

## Code Lists

### Genericode Parser

Parse `.gc` files from `cl/gc/default/`:

```python
@dataclass
class GenericodeList:
    short_name: str           # e.g., "CurrencyCode"
    version: str              # e.g., "2.4"
    canonical_uri: str
    agency: str               # e.g., "ISO"
    columns: list[Column]
    values: list[Row]


def parse_genericode(path: Path) -> GenericodeList:
    """Parse Genericode XML file."""
    ...
```

### Available Code Lists

| File | Description | Source |
|------|-------------|--------|
| CurrencyCode-2.4.gc | ISO 4217 currencies | ISO |
| CountryIdentificationCode-2.4.gc | ISO 3166-1 countries | ISO |
| LanguageCode-2.4.gc | ISO 639 languages | ISO |
| UnitOfMeasureCode-2.4.gc | UNECE Rec 20 units | UNECE |
| PaymentMeansCode-2.4.gc | Payment methods | UNTDID |
| TransportModeCode-2.4.gc | Transport modes | UNTDID |
| AllowanceChargeReasonCode-2.4.gc | Discount/charge reasons | UNTDID |
| PackagingTypeCode-2.4.gc | Packaging types | UNECE |
| ChannelCode-2.4.gc | Communication channels | UNTDID |

---

## Implementation Phases

### Phase 1: Schema Models & Parsers

**Goal:** Parse XSD schemas into Python models

| Task | Description |
|------|-------------|
| Define enums | ComponentType, Cardinality, DataTypeKind |
| Define models | ABIE, BBIE, ASBIE, DataType, CodeList |
| UDT parser | Parse BDNDR-UnqualifiedDataTypes-1.1.xsd |
| QDT parser | Parse UBL-QualifiedDataTypes-2.5.xsd |
| CBC parser | Parse UBL-CommonBasicComponents-2.5.xsd |
| CAC parser | Parse UBL-CommonAggregateComponents-2.5.xsd |
| Document parser | Parse maindoc/*.xsd files |
| Code list parser | Parse cl/gc/default/*.gc files |
| Schema loader | UBLSchemaLoader class |

**Acceptance Criteria:**
- [ ] Load any of 101 document types
- [ ] Resolve all ABIE/BBIE/ASBIE references
- [ ] Extract CCTS metadata (definitions, cardinality)
- [ ] Parse all 14 code lists

### Phase 2: Document Parser

**Goal:** Parse UBL XML documents into AST

| Task | Description |
|------|-------------|
| XML parser | lxml-based parser with namespace handling |
| Position tracking | Line/column/xpath for error reporting |
| Document mapper | Map elements to schema components |
| Error collection | Parse errors with recovery |

**Acceptance Criteria:**
- [ ] Parse valid UBL documents
- [ ] Track source positions for all elements
- [ ] Bind elements to schema components
- [ ] Collect parse errors without stopping

### Phase 3: Validation

**Goal:** Validate parsed documents against schema

| Task | Description |
|------|-------------|
| Schema validator | Element presence, cardinality |
| Element validator | Data types, formats |
| Code validator | Code list membership |
| Core orchestrator | ValidationResult, error aggregation |

**Acceptance Criteria:**
- [ ] Validate all CCTS data types
- [ ] Check required elements
- [ ] Validate cardinality constraints
- [ ] Validate code values

### Phase 4: Code Generation

**Goal:** Pre-generate schemas for fast loading

| Task | Description |
|------|-------------|
| Generator class | UBLSchemaGenerator |
| Templates | Jinja2 templates for Python modules |
| Registry | GeneratedUBLSchemaLoader |
| Build integration | Taskfile targets |

**Acceptance Criteria:**
- [ ] Generate schemas for all 101 document types
- [ ] Factory functions (lazy loading)
- [ ] ~50x faster than runtime parsing

### Phase 5: Document Writer

**Goal:** Generate valid UBL XML documents

| Task | Description |
|------|-------------|
| Builder API | Fluent interface for document construction |
| Serializer | XML output with namespace handling |
| Validation | Validate before serialization |

**Acceptance Criteria:**
- [ ] Generate valid UBL XML
- [ ] Support all 101 document types
- [ ] Pretty print and compact modes
- [ ] Validate output against schema

### Phase 6: ApplicationResponse

**Goal:** Generate acknowledgments from validation results

| Task | Description |
|------|-------------|
| Response builder | Map validation errors to response |
| Response codes | Implement standard codes |

**Acceptance Criteria:**
- [ ] Generate ApplicationResponse for any document type
- [ ] Include line-level error details
- [ ] Valid UBL structure

---

## Usage Example

```python
from edi_schema.ubl.parser import parse
from edi_schema.ubl.validator import UBLValidator, ValidationLevel
from edi_schema.ubl.schemas import GeneratedUBLSchemaLoader
from edi_schema.ubl.writer import UBLWriter

# Load schema
loader = GeneratedUBLSchemaLoader(version="2.5")
schema = loader.load("Invoice")

# Parse document
content = open("invoice.xml").read()
result = parse(content, schema)

# Validate
validator = UBLValidator(
    schema_loader=loader,
    levels={ValidationLevel.SCHEMA, ValidationLevel.ELEMENT, ValidationLevel.CODE},
)
validation = validator.validate(result.document)

if not validation.is_valid():
    for error in validation.errors:
        print(f"{error.xpath}: {error.message}")

# Generate new document
writer = UBLWriter(version="2.5")
invoice = (
    writer.invoice()
    .id("INV-002")
    .issue_date("2024-01-15")
    # ... builder chain
    .build()
)
print(invoice.to_xml(pretty=True))
```

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| lxml for parsing | Fast, namespace-aware, XPath support |
| Dataclasses for models | Clean, immutable, type-hinted |
| Factory functions for codegen | Avoid loading all schemas at import |
| Errors as data | Enables full document parsing with all errors |
| Fluent builder API | Clean, discoverable API for document creation |
| XSD as source of truth | Standard format, well-defined semantics |

---

## Generated Schema Stats (Estimated)

| Version | Documents | ABIEs | BBIEs | Code Lists |
|---------|-----------|-------|-------|------------|
| 2.5 | 101 | ~500 | ~300 | 14 |

---

## Future Enhancements

- [ ] Schematron business rule validation
- [ ] UBL Extensions support
- [ ] Digital signature validation (XAdES)
- [ ] JSON-LD serialization (UBL-JSON)
- [ ] Streaming parser for large documents
- [ ] XSLT transformation support
- [ ] UBL 2.3, 2.4 version support
- [ ] PEPPOL BIS profile validation

---

## X12/EDIFACT Mapping

Common document mappings for interoperability:

| UBL | X12 | EDIFACT |
|-----|-----|---------|
| Order | 850 | ORDERS |
| OrderResponse | 855 | ORDRSP |
| DespatchAdvice | 856 | DESADV |
| Invoice | 810 | INVOIC |
| CreditNote | 812 | CREMUL |
| RemittanceAdvice | 820 | REMADV |
| ApplicationResponse | 997 | CONTRL |

---

## References

- [UBL 2.5 Specification](https://docs.oasis-open.org/ubl/UBL-2.5.html)
- [OASIS UBL TC](https://www.oasis-open.org/committees/ubl/)
- [CCTS 2.01](http://www.unece.org/cefact/codesfortrade/ccts_index.html)
- [Genericode 1.0](https://docs.oasis-open.org/codelist/genericode/)
