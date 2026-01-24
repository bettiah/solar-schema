# X12 Implementation

## Overview

A Python library for parsing X12 schema definitions, parsing X12 EDI documents, validating them, and generating acknowledgments.

**Tests:** 1,328 passing | **Versions:** 005010, 004010

---

## Architecture

```
Schema Definition Files (005010/, 004010/)
         │
         ├──────────────────────────────────────┐
         │                                      │
         ▼                                      ▼
┌─────────────────────┐              ┌─────────────────────┐
│  Runtime Loading    │              │   Code Generation   │
│  (X12SchemaLoader)  │              │  (SchemaGenerator)  │
└─────────────────────┘              └─────────────────────┘
         │                                      │
         │                                      ▼
         │                           ┌─────────────────────┐
         │                           │  Generated Modules  │
         │                           │  (schemas/v005010/) │
         │                           └─────────────────────┘
         │                                      │
         ▼                                      ▼
┌─────────────────────────────────────────────────────────┐
│                       X12Schema                         │
│  transaction_set + segments + elements + composites     │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    Raw X12 Document                     │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   1. TOKENIZER                          │
│  Extract delimiters from ISA, split into segments       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                 2. ENVELOPE PARSER                      │
│  Parse ISA/IEA, GS/GE, ST/SE hierarchy                  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              3. TRANSACTION PARSER                      │
│  Match segments to schema, build loop hierarchy         │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   4. VALIDATOR                          │
│  Structural → Envelope → Schema → Element → Code        │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│               5. 997 ACKNOWLEDGMENT                     │
│  Generate functional acknowledgment from errors         │
└─────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
src/edi_schema/x12/
├── enums.py                  # DataElementType, RequirementDesignator, etc.
├── models/
│   ├── element.py            # DataElement, Composite, CompositeElement
│   ├── segment.py            # Segment, SegmentElement, SegmentNote
│   ├── transaction.py        # TransactionSet, TransactionSetSegment, LoopDefinition
│   └── codesource.py         # CodeSource
├── parsers/
│   ├── csv_parser.py         # Quote-comma delimited parser
│   └── freeform.py           # FREEFORM.TXT parser
├── schema.py                 # X12Schema, X12SchemaLoader
├── schemas/
│   ├── __init__.py           # Public API exports
│   ├── registry.py           # Version dispatch, GeneratedX12SchemaLoader
│   ├── v005010/              # Generated 005010 schemas (~9.5MB)
│   └── v004010/              # Generated 004010 schemas (~7.5MB)
├── codegen/
│   ├── generator.py          # SchemaGenerator class
│   └── templates/            # Jinja2 templates
├── ast.py                    # AST node types, error types
├── parser/
│   ├── tokenizer.py          # Delimiter extraction, segmentation
│   ├── envelope.py           # ISA/GS/ST envelope parsing
│   ├── loop_hierarchy.py     # Loop tree from schema
│   └── transaction.py        # Schema-driven loop matching, HL parsing
├── validator/
│   ├── element.py            # Data types, lengths
│   ├── schema.py             # Segment order, cardinality
│   ├── code.py               # Code value validation
│   └── core.py               # Orchestration, ValidationResult
└── ack/
    └── fa997.py              # 997 Functional Acknowledgment
```

---

## Schema System

### Generated Schema Stats

| Version | Transactions | Segments | Elements | Composites |
|---------|-------------|----------|----------|------------|
| 005010  | 318         | 1,035    | 1,419    | 34         |
| 004010  | 293         | 1,000    | 1,404    | 28         |

### Source Files Parsed

| File | Purpose |
|------|---------|
| `sethead.txt` / `setdetl.txt` | Transaction Set definitions and structure |
| `seghead.txt` / `segdetl.txt` | Segment definitions and elements |
| `comhead.txt` / `comdetl.txt` | Composite definitions and elements |
| `elehead.txt` / `eledetl.txt` | Data Element definitions and attributes |
| `cshead.txt` | Code Source definitions |
| `freeform.txt` | Purposes, notes, code values |

### Core Models

```python
@dataclass
class DataElement:
    id: str                          # e.g., "98"
    name: str                        # e.g., "Entity Identifier Code"
    data_type: DataElementType       # AN, ID, N0-N9, R, DT, TM, B
    min_length: int
    max_length: int
    definition: str | None
    code_values: dict[str, str]

@dataclass
class Segment:
    id: str                          # e.g., "NM1"
    name: str
    purpose: str | None
    elements: list[SegmentElement]
    notes: list[SegmentNote]

@dataclass
class TransactionSet:
    id: str                          # e.g., "837"
    name: str                        # e.g., "Health Care Claim"
    functional_group: str            # e.g., "HC"
    purpose: str | None
    structure: list[TransactionSetSegment]

@dataclass
class X12Schema:
    transaction_set: TransactionSet
    segments: dict[str, Segment]
    elements: dict[str, DataElement]
    composites: dict[str, Composite]
    code_sources: dict[str, CodeSource]
    version: str = "005010"
```

### Schema API

```python
# Recommended: Generated schemas (fastest)
from edi_schema.x12.schemas import GeneratedX12SchemaLoader, get_schema

loader = GeneratedX12SchemaLoader(version="005010")
schema = loader.load("837")

# Or use convenience functions
schema = get_schema("837", version="005010")

# Runtime loader for custom schema directories
from edi_schema.x12.schema import X12SchemaLoader
loader = X12SchemaLoader(Path("/custom/schema/path"))
```

### Code Generation

```bash
task codegen-005010    # Generate 005010 schemas
task codegen-004010    # Generate 004010 schemas
task codegen-all       # Generate all versions
```

---

## Parser System

### AST Types

- `SourcePosition` - Location tracking for error reporting
- `RawElement`, `RawComposite`, `RawSegment` - Pre-schema tokens
- `ParsedElement`, `ParsedSegment` - Schema-attached nodes
- `LoopInstance` - Loop iteration with children
- `TransactionSetInstance`, `FunctionalGroupInstance`, `InterchangeInstance` - Envelope hierarchy
- `Delimiters` - Element/component/segment separators
- `ParseError` - Error with code, category, severity, recovery point

### Tokenizer

- ISA segment fixed-width parsing (106 chars)
- Delimiter extraction from positions 3, 82, 104, 105
- Segment/element splitting with position tracking
- Composite element detection and parsing

### Envelope Parser

- State machine for ISA→GS→ST→SE→GE→IEA transitions
- Control number validation (ISA13↔IEA02, GS06↔GE02, ST02↔SE02)
- Segment/group/transaction count validation
- Missing closure synthesis with error logging

### Transaction Parser

- Schema-driven loop matching via `LoopMatcher`
- HL hierarchy parsing for 837/856/270/271 documents
- `HLNode` with id, parent_id, level_code, children
- Level codes: 20=billing, 21=info receiver, 22=subscriber, 23=dependent

### Loop Hierarchy

- `LoopNode` - Tree node with loop_id, level, max_repeat, segments, children
- `LoopHierarchyBuilder` - Builds tree from flat `TransactionSet.structure`
- `LoopMatcher` - Matches segments to loop positions, handles iterations

---

## Validation Levels

| Level | Description | Location |
|-------|-------------|----------|
| STRUCTURAL | Delimiters, terminators | tokenizer |
| ENVELOPE | ISA/IEA, GS/GE, ST/SE matching | envelope parser |
| SCHEMA | Segment order, required segments, loop cardinality | validator/schema.py |
| ELEMENT | Data types (AN, ID, N, R, DT, TM), lengths, required | validator/element.py |
| CODE | Coded values against code lists | validator/code.py |
| SEMANTIC | Cross-element rules, conditional requirements | (planned) |

### Element Validation

- Type validation: AN (alphanumeric), ID, N (numeric), R (decimal), DT (date), TM (time)
- Date formats: CCYYMMDD, YYMMDD with month/day validation
- Time formats: HHMM, HHMMSS, HHMMSSD with hour/minute/second validation
- Length min/max checking

---

## 997 Acknowledgment

```
ST*997*{control}~
AK1*{func_id}*{group_control}~
  AK2*{txn_id}*{txn_control}~
    AK3*{seg_id}*{pos}*{loop}*{err}~
      AK4*{elem_pos}*{elem_ref}*{err}~
    AK5*{status}*{err1}*...~
AK9*{status}*{inc}*{rcvd}*{accp}~
SE*{count}*{control}~
```

Status codes: A=Accepted, E=Accepted with errors, R=Rejected, P=Partially accepted

---

## Error Recovery

### Principles

1. Never stop on first error - collect all
2. Preserve partial results - build as much AST as possible
3. Clear recovery points - segment/loop/envelope boundaries
4. Rich error context - position, expected, actual, recovery action

### Recovery Points

```python
class RecoveryPoint(Enum):
    SEGMENT_BOUNDARY = "segment"
    LOOP_START = "loop_start"
    TRANSACTION_START = "st"
    TRANSACTION_END = "se"
    GROUP_START = "gs"
    GROUP_END = "ge"
    INTERCHANGE_END = "iea"
```

---

## Usage Example

```python
from edi_schema.x12.parser import tokenize, parse_envelope
from edi_schema.x12.validator import X12Validator, ValidationLevel
from edi_schema.x12.schemas import GeneratedX12SchemaLoader
from edi_schema.x12.ack import generate_997

# Load schema
loader = GeneratedX12SchemaLoader(version="005010")
schema = loader.load("837")

# Parse document
content = open("837P.x12").read()
result = parse_envelope(tokenize(content))

# Validate
validator = X12Validator(
    schema_loader=loader,
    levels={ValidationLevel.SCHEMA, ValidationLevel.ELEMENT, ValidationLevel.CODE},
)
validation = validator.validate(result.interchange)

if not validation.is_valid():
    for error in validation.errors:
        print(f"{error.segment_tag}: {error.message}")

# Generate 997 acknowledgment
for group in result.interchange.groups:
    ack = generate_997(group, control_number="0001")
    print(ack)
```

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Dataclasses for models | Clean, immutable data structures with type hints |
| Factory functions for codegen | Avoid loading all schemas into memory at import |
| Errors as data, not exceptions | Enables full document parsing with all errors collected |
| State machine for envelope | Clear recovery points at each envelope level |
| HL as runtime hierarchy | 837/856 documents define structure at runtime, not schema |
| Separate validation levels | Allows selective validation, maps to 997 error codes |
| `>1` for unlimited | Schema files use ">1" to indicate unlimited repetition |

---

## Future Enhancements

- [ ] Syntax note parsing (conditional rules like P0102, R0305)
- [ ] Composite element validation (nested sub-element validation)
- [ ] 999 Implementation Acknowledgment (HIPAA)
- [ ] TA1 Interchange Acknowledgment
- [ ] Level 6 Semantic validation (cross-element rules)
- [ ] Streaming parser for large documents
- [ ] Schema export to JSON/XML for external tooling
- [ ] Implementation guide overlays (HIPAA 5010X222A1, etc.)
- [ ] Schema diff tool (compare 4010 vs 5010 changes)