# X12 Parser Implementation Record

## Overview

A complete X12 document parser with error recovery capabilities, implemented in 6 sprints. The parser tokenizes, parses,
validates, and generates acknowledgments for X12 EDI documents.

**Total Tests: 502 passing**

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Raw X12 Document                                  │
│  ISA*00*          *00*          *ZZ*SENDER*...~GS*PO*...~ST*850*...~...    │
└─────────────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        1. TOKENIZER / LEXER                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ - Extract delimiters from ISA (pos 3, 104, 105, 106)                │   │
│  │ - Split document into segments                                       │   │
│  │ - Split segments into elements                                       │   │
│  │ - Handle composite sub-elements                                      │   │
│  │ - Track source positions (line, column, offset)                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│                           List[RawSegment]                                  │
└─────────────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        2. ENVELOPE PARSER                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ - Parse ISA/IEA (interchange level)                                 │   │
│  │ - Parse GS/GE (functional group level)                              │   │
│  │ - Extract ST/SE (transaction sets)                                  │   │
│  │ - Validate envelope counts and control numbers                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│                         Interchange AST                                     │
│                    (nested structure with all levels)                       │
└─────────────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     3. TRANSACTION SET PARSER                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ - Match segments to schema structure                                │   │
│  │ - Build loop hierarchy (handle nesting)                             │   │
│  │ - Handle HL hierarchical segments (856 ASN)                         │   │
│  │ - Parse bounded loops (LS/LE)                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│                      Transaction Set AST                                    │
│                  (segments organized in loop hierarchy)                     │
└─────────────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          4. VALIDATOR                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Level 1: Structural - delimiters, terminators, segment tags         │   │
│  │ Level 2: Envelope - ISA/IEA, GS/GE, ST/SE matching                  │   │
│  │ Level 3: Schema - segment order, required segments, loop limits     │   │
│  │ Level 4: Element - data types, lengths, required elements           │   │
│  │ Level 5: Code - coded values against code lists                     │   │
│  │ Level 6: Semantic - cross-element rules, conditional requirements   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│                    Validated AST + List[ValidationError]                    │
└─────────────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     5. ERROR REPORTER / 997 GENERATOR                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ - Generate human-readable error messages                            │   │
│  │ - Generate 997 Functional Acknowledgment                            │   │
│  │ - Generate 999 Implementation Acknowledgment                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
src/edi_schema/x12/
├── ast.py                      # AST node types, error types
├── parser/
│   ├── __init__.py
│   ├── tokenizer.py            # Delimiter extraction, segmentation
│   ├── envelope.py             # ISA/GS/ST envelope parsing
│   ├── loop_hierarchy.py       # Loop tree from schema
│   └── transaction.py          # Schema-driven loop matching, HL parsing
├── validator/
│   ├── __init__.py
│   ├── element.py              # Level 4: Data types, lengths
│   ├── schema.py               # Level 3: Segment order, cardinality
│   ├── code.py                 # Level 5: Code value validation
│   └── core.py                 # Orchestration, ValidationResult
└── ack/
    ├── __init__.py
    └── fa997.py                # 997 Functional Acknowledgment
```

---

## Implementation Summary

### Sprint 1: Foundation

**Files:** `ast.py`, `parser/loop_hierarchy.py`

**AST Types Implemented:**

- `SourcePosition` - Location tracking for error reporting
- `RawElement`, `RawComposite`, `RawSegment` - Pre-schema tokens
- `ParsedElement`, `ParsedSegment` - Schema-attached nodes
- `LoopInstance` - Loop iteration with children
- `TransactionSetInstance`, `FunctionalGroupInstance`, `InterchangeInstance` - Envelope hierarchy
- `Delimiters` - Element/component/segment separators
- `ParseError` - Error with full context (code, category, severity, recovery point)

**Design Decisions:**

- `ParseError` includes `recovery_point` enum to guide error recovery
- `ErrorCategory` enum: STRUCTURAL, ENVELOPE, SCHEMA, ELEMENT, CODE, SEMANTIC
- `ErrorSeverity` enum: WARNING, ERROR, FATAL
- Errors never stop parsing; all are collected

**Loop Hierarchy:**

- `LoopNode` - Tree node with loop_id, level, max_repeat, segments, children
- `LoopHierarchyBuilder` - Builds tree from flat `TransactionSet.structure`
- `LoopMatcher` - Matches segments to loop positions, handles iterations

### Sprint 2: Tokenizer

**File:** `parser/tokenizer.py`

**Key Features:**

- ISA segment fixed-width parsing (106 chars)
- Delimiter extraction from positions 3, 82, 104, 105
- Segment/element splitting with position tracking
- Composite element detection and parsing

**Design Decisions:**

- ISA is special-cased as fixed-width; other segments are delimiter-based
- `TokenizerResult` contains segments, delimiters, errors, and statistics
- Recovery: skip to next segment terminator on errors

### Sprint 3: Envelope Parser

**File:** `parser/envelope.py`

**Key Features:**

- State machine for ISA→GS→ST→SE→GE→IEA transitions
- Control number validation (ISA13↔IEA02, GS06↔GE02, ST02↔SE02)
- Segment count validation (SE01)
- Group/transaction count validation (IEA01, GE01)

**Design Decisions:**

- `EnvelopeParserState` enum tracks expected next segment
- Missing closures (IEA, GE, SE) synthesized with errors logged
- Control number mismatches logged but parsing continues

**Error Recovery:**

- Missing ST → skip to next ST or GE
- Missing SE → close at next ST/GE/IEA
- Missing GE → close at next GS/IEA
- Missing IEA → synthesize at end

### Sprint 4: Transaction Parser

**File:** `parser/transaction.py`

**Key Features:**

- Schema-driven loop matching via `LoopMatcher`
- HL hierarchy parsing for 837/856/270/271 documents
- Fallback to simple segmentation without schema

**HL Hierarchy Design:**

- `HLParser` class processes HL segments at runtime
- `HLNode` dataclass with id, parent_id, level_code, children
- Parent references validated; orphans attached to last valid parent
- Level codes (20=billing, 21=info receiver, 22=subscriber, 23=dependent)

**Design Decisions:**

- HL-based documents detected by presence of HL segments
- HL creates dynamic hierarchy; schema loops are secondary
- `LoopInstance.hl_level_code` field added for HL tracking

### Sprint 5: Validation (6 Levels)

**Files:** `validator/element.py`, `validator/schema.py`, `validator/code.py`, `validator/core.py`

**Validation Levels:**

1. **Structural** - Delimiters, terminators (handled in tokenizer)
2. **Envelope** - ISA/IEA, GS/GE, ST/SE matching (handled in envelope parser)
3. **Schema** - Segment order, required segments, loop cardinality
4. **Element** - Data types (AN, ID, N, R, DT, TM), lengths, required
5. **Code** - Coded values against known code lists
6. **Semantic** - Cross-element rules (not fully implemented)

**Element Validation (`element.py`):**

- Type validation: AN (alphanumeric), ID, N (numeric), R (decimal), DT (date), TM (time)
- Date formats: CCYYMMDD, YYMMDD with month/day validation
- Time formats: HHMM, HHMMSS, HHMMSSD with hour/minute/second validation
- Length min/max checking
- Required element checking

**Schema Validation (`schema.py`):**

- Segment order checking against schema structure
- Required (M) segments presence
- Loop cardinality (max iterations)
- Segment max use checking

**Code Validation (`code.py`):**

- Pre-defined code lists: ID_QUALIFIERS, FUNCTIONAL_ID_CODES, USAGE_INDICATORS
- Strict mode (error) vs non-strict (warning) for unknown codes
- Empty values skip validation

**Design Decisions:**

- `ValidationResult` aggregates errors by category with counts
- `ValidationLevel` enum allows selective validation
- Aliases: `DataType = DataElementType`, `Requirement = RequirementDesignator`

### Sprint 6: 997 Acknowledgment Generation

**File:** `ack/fa997.py`

**997 Structure Generated:**

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

**Data Classes:**

- `AK1Data` - Functional group response header
- `AK2Data` - Transaction response header
- `AK3Data` - Segment error note
- `AK4Data` - Element error note
- `AK5Data` - Transaction status (A/E/R)
- `AK9Data` - Group summary (A/P/R)

**Design Decisions:**

- `FA997Generator` class for generation
- `generate_997()` convenience function
- Custom delimiters supported
- Errors mapped to AK3/AK4 from `ParseError` context
- Status: A=Accepted, E=Accepted with errors, R=Rejected, P=Partially accepted

---

## Error Recovery Strategy

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

### Error Codes (for 997)

- **AK3 Segment Errors:** 1-8 (unrecognized, unexpected, missing, loop max, segment max, not defined, out of sequence,
  element errors)
- **AK4 Element Errors:** 1-10 (missing, conditional, too many, too short, too long, invalid char, invalid code, invalid
  date, invalid time, exclusion)

---

## Test Coverage

| Test File                  | Tests | Coverage                              |
|----------------------------|-------|---------------------------------------|
| test_ast.py                | 39    | AST types, error creation             |
| test_tokenizer.py          | 28    | Delimiters, segmentation, composites  |
| test_envelope_parser.py    | 34    | ISA/GS/ST parsing, control validation |
| test_loop_hierarchy.py     | 23    | Loop tree building, matching          |
| test_transaction_parser.py | 18    | Schema matching, HL parsing           |
| test_validator.py          | 31    | Element, schema, code validation      |
| test_ack.py                | 26    | 997 generation, data classes          |
| test_x12_samples.py        | 37    | Integration with 10 real X12 files    |

**Sample Files Validated:**

- 270/271 - Eligibility Inquiry/Response
- 276/277 - Claim Status Request/Response
- 278 - Authorization Request
- 820 - Premium Payment
- 834 - Benefit Enrollment
- 835 - Remittance Advice
- 837I - Institutional Claim
- 837P - Professional Claim

---

## Usage Example

```python
from edi_schema.x12.parser import tokenize, parse_envelope
from edi_schema.x12.validator import X12Validator, ValidationResult
from edi_schema.x12.ack import generate_997

# Parse document
with open("claim.x12") as f:
    content = f.read()

tokens = tokenize(content)
result = parse_envelope(tokens)

# Validate (optional - requires schema loader)
validator = X12Validator()
validation = validator.validate(result.interchange)

# Generate 997 acknowledgment
for group in result.interchange.groups:
    ack = generate_997(group, control_number="0001")
    print(ack)
```

### Validation Usage

```python
from edi_schema.x12.parser import tokenize, parse_envelope
from edi_schema.x12.validator import X12Validator, ValidationLevel
from edi_schema.x12.schema import X12SchemaLoader

# Load document
content = open("837P.x12").read()
result = parse_envelope(tokenize(content))

# Initialize validator with schema
schema_loader = X12SchemaLoader(Path("/path/to/005010"))
validator = X12Validator(
    schema_loader=schema_loader,
    levels={ValidationLevel.SCHEMA, ValidationLevel.ELEMENT, ValidationLevel.CODE},
)

# Run validation
validation = validator.validate(result.interchange)

if validation.is_valid():
    print("Document is valid")
else:
    for error in validation.errors:
        print(f"{error.segment_tag}{error.element_position:02d}: {error.message}")
```

---

## Design Decisions Summary

| Decision                       | Rationale                                                 |
|--------------------------------|-----------------------------------------------------------|
| Errors as data, not exceptions | Enables full document parsing with all errors collected   |
| State machine for envelope     | Clear recovery points at each envelope level              |
| HL as runtime hierarchy        | 837/856 documents define structure at runtime, not schema |
| Separate validation levels     | Allows selective validation, maps to 997 error codes      |
| Dataclasses for AK segments    | Clean separation of data from generation logic            |
| Lenient ISA parsing            | Sample files often lack proper padding                    |

---

## Future Enhancements

- [ ] 999 Implementation Acknowledgment (HIPAA)
- [ ] Level 6 Semantic validation (cross-element rules)
- [ ] Streaming parser for large documents
- [ ] Composite element validation (nested sub-element validation)
- [ ] TA1 Interchange Acknowledgment

## Open Questions

1. **HL Segment Handling**: The 856 ASN uses HL segments to create parent-child hierarchies dynamically at runtime.
   Should we:
    - Treat HL as a special case in the loop builder?
    - Create a separate HierarchyParser for HL-based documents?

2. **Version Differences**: How much do we need to handle multiple X12 versions (4010, 5010)?
    - Different segment definitions?
    - Different validation rules?

3. **Code Value Sources**: cs_de.txt and cs_cv.txt reference external code sources. How complete does code validation
   need to be?