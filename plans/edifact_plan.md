# EDIFACT Implementation

## Current State

The EDIFACT implementation provides complete schema generation, parsing, and validation for UN/EDIFACT batch messages.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         EDIFACT Document                                │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
        ┌───────────────────┐           ┌───────────────────────┐
        │     READING       │           │      WRITING          │
        │   (Implemented)   │           │     (Planned)         │
        └───────────────────┘           └───────────────────────┘
                    │
    ┌───────────────┼───────────────┬──────────────────┐
    ▼               ▼               ▼                  ▼
┌────────┐   ┌───────────┐   ┌───────────┐   ┌─────────────┐
│Tokenize│ → │ Envelope  │ → │  Message  │ → │  Validate   │
│        │   │  Parser   │   │  Parser   │   │  (6 levels) │
└────────┘   └───────────┘   └───────────┘   └─────────────┘
    │               │               │                  │
    └───────────────┴───────────────┴──────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────┐
                    │        ParseResult        │
                    │  (AST + Errors + Stats)   │
                    └───────────────────────────┘
```

### Implemented Components

| Layer | Component | File | Description |
|-------|-----------|------|-------------|
| **Models** | Schema Models | `models.py` | DataElement, Composite, Segment, MessageSpec |
| **Models** | AST Nodes | `ast.py` | 18 node types for parsed documents |
| **Parser** | Tokenizer | `parser/tokenizer.py` | UNA detection, delimiter handling |
| **Parser** | Envelope | `parser/envelope.py` | UNB/UNG/UNH structure parsing |
| **Parser** | Message | `parser/message.py` | Schema-driven segment organization |
| **Parser** | Hierarchy | `parser/hierarchy.py` | Segment group tree builder |
| **Schema** | Registry | `schema/registry.py` | Component lookup by tag |
| **Schema** | Resolver | `schema/resolver.py` | Reference linking |
| **Schema** | Loader | `schema/loader.py` | Runtime schema loading |
| **Validator** | Core | `validator/core.py` | 6-level validation orchestrator |
| **Codegen** | Generator | `codegen/generator.py` | Python schema generation |
| **Schemas** | Pre-built | `schemas/d96a/`, `schemas/d23a/` | ~20MB generated code |

### Project Structure

```
src/edi_schema/edifact/
├── __init__.py
├── ast.py                    # 18 AST node types, error model
├── models.py                 # 9 schema models
├── parser/
│   ├── tokenizer.py          # UNA, delimiters, release char
│   ├── envelope.py           # UNB/UNG/UNH parsing
│   ├── message.py            # Schema-driven parsing
│   └── hierarchy.py          # Segment group builder
├── schema/
│   ├── registry.py           # EdifactRegistry
│   ├── resolver.py           # Reference resolution
│   └── loader.py             # EdifactSchemaLoader
├── schema_parsers/           # Directory file parsers
│   ├── uncl.py               # Code lists
│   ├── eded.py               # Data elements
│   ├── edcd.py               # Composites
│   ├── edsd.py               # Segments
│   └── edmd.py               # Messages
├── validator/
│   ├── core.py               # Orchestrator
│   ├── element.py            # Type/length validation
│   ├── schema.py             # Structure validation
│   ├── code.py               # Code list validation
│   └── semantic.py           # Cross-field rules
├── codegen/
│   ├── generator.py          # EdifactSchemaGenerator
│   └── templates/            # Jinja2 templates
└── schemas/
    ├── registry.py           # GeneratedEdifactSchemaLoader
    ├── d96a/                  # 125 messages
    └── d23a/                  # 199 messages
```

---

## Schema Models

### Core Types

```python
DataElement       # Atomic field: tag, type (a/n/an), length, codes
  └── tag: "3039"
  └── data_type: "an"
  └── max_length: 35
  └── codes: {"BY": "Buyer", "SE": "Seller", ...}

Composite         # Group of related elements (C### tags)
  └── tag: "C082"
  └── components: [Component(element_tag="3039", mandatory=True), ...]

Segment           # Named structure (3-letter tags)
  └── tag: "NAD"
  └── elements: [SegmentElement(tag="3035"), SegmentElement(tag="C082"), ...]

MessageSpec       # Complete message definition
  └── code: "INVOIC"
  └── structure: [SegmentRef, SegmentGroup, ...]
```

### Hierarchy Example (INVOIC)

```
INVOIC Message
├── BGM (Beginning of message)      M  1
├── DTM (Date/time/period)          M  35
├── Segment Group 1 ───────────────── C  99999 ────┐
│   ├── RFF (Reference)             M  1           │
│   └── DTM (Date/time/period)      C  5 ─────────┘
├── Segment Group 2 ───────────────── C  99 ──────┐
│   ├── NAD (Name and address)      M  1          │
│   ├── Segment Group 3 ─────────── C  9999 ─────┐│
│   │   ├── RFF (Reference)         M  1         ││
│   │   └── DTM                     C  5 ────────┘│
│   └── Segment Group 5 ─────────── C  5 ────────┐│
│       └── CTA (Contact)           M  1         ││
│       └── COM (Communication)     C  5 ────────┘┘
└── ... (more groups)
```

---

## Envelope Structure

```
UNA (optional)  ← Service String Advice (defines separators)
UNB             ← Interchange Header
  UNG (optional) ← Functional Group Header
    UNH          ← Message Header
    ...          ← Message content
    UNT          ← Message Trailer
  UNE (optional) ← Functional Group Trailer
UNZ             ← Interchange Trailer
```

### UNA - Service String Advice

```
UNA:+.? '
   ││││└─ Segment terminator (')
   │││└── Reserved (space)
   ││└─── Release character (?)
   │└──── Decimal notation (.)
   └───── Data element separator (+)
         Component separator (:)
```

### Key Differences from X12

| Aspect | X12 | EDIFACT |
|--------|-----|---------|
| **Separators** | Fixed in ISA | Defined in UNA |
| **Functional group** | Always present (GS/GE) | Optional (UNG/UNE) |
| **Partner fields** | Fixed 15 chars | Variable length |
| **Composites** | Less common | Fundamental |
| **Release character** | None | `?` escapes special chars |

---

## AST Structure

### Envelope Hierarchy

```
ParseResult
├── interchanges: list[InterchangeInstance]
│   ├── control_reference: str
│   ├── sender_id / recipient_id
│   ├── unb_segment / unz_segment
│   ├── groups: list[FunctionalGroupInstance]  # Optional
│   │   ├── reference_number
│   │   ├── messages: list[MessageInstance]
│   │   └── ung_segment / une_segment
│   └── messages: list[MessageInstance]  # If no groups
│       ├── reference_number: str
│       ├── message_type: str
│       ├── version / release
│       ├── segments: list[ParsedSegment | SegmentGroupInstance]
│       └── unh_segment / unt_segment
├── errors: list[ParseError]
└── statistics: ParseStatistics
```

---

## Validation Levels

| Level | Category | Checks |
|-------|----------|--------|
| 1 | Structural | Delimiters, segment terminators, UNA format |
| 2 | Envelope | UNB↔UNZ, UNG↔UNE, UNH↔UNT matching, counts |
| 3 | Schema | Segment order, required segments, group cardinality |
| 4 | Element | Data types (a/n/an), min/max length |
| 5 | Code | Coded values against UNCL code lists |
| 6 | Semantic | Cross-element rules, conditional requirements |

---

## Generated Schemas

### Available Versions

| Version | Messages | Segments | Data Elements | Size |
|---------|----------|----------|---------------|------|
| D.96A | 125 | ~400 | 359 | ~6 MB |
| D.23A | 199 | ~500 | 649 | ~11 MB |

### Usage

```python
# Pre-generated (fast, ~50x)
from edi_schema.edifact.schemas import GeneratedEdifactSchemaLoader
loader = GeneratedEdifactSchemaLoader(version="d23a")
schema = loader.load("INVOIC")

# Runtime parsing (flexible)
from edi_schema.edifact.schema import EdifactSchemaLoader
loader = EdifactSchemaLoader("/path/to/d23a")
schema = loader.load("INVOIC")
```

---

## Interactive Messages

### What Makes Them Different

Interactive EDIFACT messages are designed for **real-time request-response dialogues** rather than batch processing. They use ISO 9735 Version 4 syntax with different envelope segments.

| Aspect | Batch Messages | Interactive Messages |
|--------|---------------|---------------------|
| **Message Header** | UNH (Message header) | UIH (Interactive message header) |
| **Message Trailer** | UNT (Message trailer) | UIT (Interactive message trailer) |
| **Interchange** | UNB/UNZ | UIB/UIZ |
| **Use Case** | Bulk document exchange | Real-time queries |
| **Processing** | Store-and-forward | Synchronous request-response |

### Directory Structure

Interactive messages have separate directories with specialized components:

```
d23a/
├── eded/      # Batch data elements
├── edcd/      # Batch composites
├── edsd/      # Batch segments (NAD, DTM, MOA...)
├── edmd/      # Batch messages (195)
│
├── idcd/      # Interactive composites (IDCD.23A)
├── idsd/      # Interactive segments (IDSD.23A)
│   └── AAI, ADI, DAV, HDR, MSD, ORG, RCI, TVL...
└── idmd/      # Interactive messages (17)
    ├── AVLREQ   # Availability request (travel)
    ├── AVLRSP   # Availability response
    ├── IHCEBI   # Health insurance eligibility
    ├── IHCLME   # Health care claim
    ├── RESREQ   # Reservation request
    ├── RESRSP   # Reservation response
    └── ...
```

### Interactive Segments

| Segment | Name | Purpose |
|---------|------|---------|
| AAI | Accommodation allocation | Hotel room assignments |
| ADI | Health care adjudication | Claim processing results |
| DAV | Daily availability | Date-based inventory |
| HDR | Header information | Message context |
| MSD | Message action details | Industry type, action |
| ORG | Originator details | Request source (agent, system) |
| RCI | Reservation control | Booking references |
| TVL | Travel product | Flight, hotel, car details |

### Message Structure Comparison

**Batch (INVOIC)**:
```
UNH+1+INVOIC:D:23A:UN'
BGM+380+INV001+9'
DTM+137:20240115:102'
...
UNT+25+1'
```

**Interactive (AVLREQ)**:
```
UIH+AVLREQ:D:23A:UN+1'
MSD+A::AIR'
ORG+AA:HDQ'
TVL+240301:0800::JFK:LAX'
...
UIT+1+15'
```

---

## Future Work

### 1. Reader Interface

High-level navigation of parsed documents:

```python
@dataclass
class EdifactReader:
    """Navigate parsed EDIFACT documents."""
    result: ParseResult

    def interchanges(self) -> Iterator[InterchangeReader]:
        for ic in self.result.interchanges:
            yield InterchangeReader(ic)

    @property
    def is_valid(self) -> bool:
        return not any(e.severity == ErrorSeverity.ERROR
                       for e in self.result.errors)


@dataclass
class MessageReader:
    """Navigate a parsed message."""
    instance: MessageInstance

    def segments(self, tag: str | None = None) -> Iterator[SegmentReader]:
        """Iterate segments, optionally filtering by tag."""
        ...

    def find_segment(self, tag: str) -> SegmentReader | None:
        """Find first segment with given tag."""
        ...

    def groups(self, number: int | None = None) -> Iterator[GroupReader]:
        """Iterate segment groups."""
        ...


@dataclass
class SegmentReader:
    """Access segment content."""
    segment: ParsedSegment

    def element(self, position: int) -> ElementReader | None:
        """Get element by position (0-indexed)."""
        ...

    def __getitem__(self, index: int) -> str | None:
        """Shorthand: segment[0] for first element value."""
        ...


# Usage
reader = EdifactReader(parse(data))
for ic in reader.interchanges():
    for msg in ic.messages("INVOIC"):
        bgm = msg.find_segment("BGM")
        invoice_num = bgm[1] if bgm else None
```

### 2. Writer Interface

Programmatic document construction:

```python
class EdifactWriter:
    """Build EDIFACT documents."""

    def __init__(self, version: str = "d23a"):
        self.version = version
        self._loader = GeneratedEdifactSchemaLoader(version)

    def create_interchange(
        self,
        sender_id: str,
        recipient_id: str,
        control_ref: str,
    ) -> InterchangeBuilder:
        ...


@dataclass
class MessageBuilder:
    """Build message content."""

    def add_segment(self, tag: str) -> SegmentBuilder:
        """Add a segment to the message."""
        ...


@dataclass
class SegmentBuilder:
    """Build segment content."""

    def set(self, *values: str | list[str] | None) -> SegmentBuilder:
        """Set element values in order."""
        ...

    def element(self, pos: int, value: str | list[str]) -> SegmentBuilder:
        """Set specific element by position."""
        ...


# Usage
writer = EdifactWriter(version="d23a")
ic = writer.create_interchange("SENDER", "RECEIVER", "000001")
msg = ic.add_message("INVOIC", "1")

msg.add_segment("BGM").set(["380"], "INV001", "9")
msg.add_segment("DTM").set(["137", "20240115", "102"])
msg.add_segment("NAD").set("BY", None, None, None, ["Buyer Corp"])
msg.add_segment("NAD").set("SE", None, None, None, ["Seller Inc"])

output = ic.build()
```

### 3. Interactive Message Support

| Task | Description |
|------|-------------|
| Schema parsers | Extend to parse `idcd/`, `idsd/`, `idmd/` |
| Envelope parser | Handle UIB/UIZ, UIH/UIT segments |
| Code generation | Include interactive schemas |

### 4. Additional Work

| Item | Priority |
|------|----------|
| CONTRL generator (acknowledgments) | High |
| APERAK Support | Application-level acknowledgments |
| More versions (D.22A, D.21B) | Low |
| Streaming parser | Low |
| JSON Schema export | Medium |

### 5. CONTRL Acknowledgment Generation

#### 5.1 CONTRL Message Structure

```
UNH+1+CONTRL:D:3:UN'
UCI+12345+SENDER+RECEIVER+7'          <- Interchange response
UCM+1+INVOIC:D:23A:UN+7'              <- Message response
UCS+5+16'                              <- Segment error
UCD+1+3039+12'                         <- Element error
UNT+5+1'
```

#### 5.2 CONTRL Response Codes

**UCI (Interchange Level):**
| Code | Meaning |
|------|---------|
| 4 | This level and all lower levels rejected |
| 7 | Acknowledged (with/without errors at lower level) |
| 8 | Interchange received but could not be processed |

**UCM (Message Level):**
| Code | Meaning |
|------|---------|
| 4 | Message rejected |
| 7 | Message acknowledged |

**UCS (Segment Error) Codes:**
| Code | Meaning |
|------|---------|
| 12 | Invalid value |
| 13 | Missing |
| 14 | Value not supported |
| 15 | Not supported at this position |
| 16 | Too many constituents |

**UCD (Element Error) Codes:**
| Code | Meaning |
|------|---------|
| 12 | Invalid value |
| 13 | Missing |
| 14 | Value not supported |
| 35 | Too many repetitions |
| 36 | Too many segment groups |
| 37 | Invalid character |
| 38 | Numeric when alphabetic expected |
| 39 | Alphabetic when numeric expected |

#### 5.3 CONTRL Generator Implementation

```python
@dataclass
class UCIData:
    """UCI segment data."""
    interchange_reference: str
    sender_id: str
    recipient_id: str
    action_code: str  # 4, 7, 8
    syntax_error_code: str | None = None
    segment_position: int | None = None

@dataclass
class UCMData:
    """UCM segment data."""
    message_reference: str
    message_identifier: str  # Type:Version:Release:Agency
    action_code: str  # 4, 7
    syntax_error_code: str | None = None

@dataclass
class UCSData:
    """UCS segment data."""
    segment_position: int
    syntax_error_code: str

@dataclass
class UCDData:
    """UCD segment data."""
    data_element_position: int
    component_position: int | None
    syntax_error_code: str
    data_element_reference: str | None = None

class CONTRLGenerator:
    """Generate CONTRL acknowledgment messages."""

    def __init__(self, delimiters: Delimiters | None = None):
        self.delimiters = delimiters or Delimiters.defaults()

    def generate(self, result: ParseResult, validation: ValidationResult) -> str:
        """Generate CONTRL for parsed interchange."""
        segments = []

        # UNH header
        segments.append(self._build_unh(result))

        # UCI for each interchange
        for interchange in result.interchanges:
            segments.append(self._build_uci(interchange, validation))

            # UCM for each message
            for message in self._get_all_messages(interchange):
                ucm_segments = self._build_ucm(message, validation)
                segments.extend(ucm_segments)

        # UNT trailer
        segments.append(self._build_unt(len(segments) + 1))

        return self._format_segments(segments)

    def _map_error_to_ucs(self, error: ParseError) -> UCSData | None:
        """Map parse error to UCS segment error code."""
        ...

    def _map_error_to_ucd(self, error: ParseError) -> UCDData | None:
        """Map parse error to UCD element error code."""
        ...
```

#### 5.4 Deliverables

| File | Description |
|------|-------------|
| `edifact/ack/__init__.py` | ACK package |
| `edifact/ack/contrl.py` | CONTRL generator |
| `tests/edifact/test_contrl.py` | CONTRL tests |

#### 5.5 Acceptance Criteria

- [ ] Generates valid CONTRL message structure
- [ ] UCI reflects interchange-level status
- [ ] UCM reflects message-level status
- [ ] UCS/UCD map validation errors correctly
- [ ] Handles multiple interchanges/messages
- [ ] Uses correct syntax error codes
- [ ] Output uses same delimiters as input (or defaults)
- [ ] 95%+ test coverage

---

## References

- [UN/EDIFACT Directories](https://unece.org/trade/uncefact/unedifact/download)
- [ISO 9735](https://www.iso.org/standard/17592.html) - EDIFACT syntax
- [EDIFACT Wikipedia](https://en.wikipedia.org/wiki/EDIFACT)
