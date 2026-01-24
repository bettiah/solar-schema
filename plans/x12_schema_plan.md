# X12 Schema Implementation

## Overview

A Python library for parsing X12 schema definition files and building reusable schemas for reading, validating, and generating X12 EDI documents.

**Features:**
- Runtime parsing from X12 text definition files
- Pre-generated Python modules (~50x faster loading)
- Full type safety and IDE support
- Multi-level validation integration

**Tests:** 826 passing | **Versions:** 005010, 004010

---

## Generated Schema Stats

| Version | Transactions | Segments | Elements | Composites | Size |
|---------|-------------|----------|----------|------------|------|
| 005010  | 318         | 1,035    | 1,419    | 34         | ~9.5MB |
| 004010  | 293         | 1,000    | 1,404    | 28         | ~7.5MB |

All code values and freeform text (purposes, definitions, notes) are embedded.

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
│                      X12Validator                       │
│           Element, Code, Schema validation              │
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
│   ├── v005010/              # Generated 005010 schemas
│   │   ├── __init__.py
│   │   ├── transaction_sets.py
│   │   ├── segments.py
│   │   ├── data_elements.py
│   │   ├── composites.py
│   │   └── lookups.py
│   └── v004010/              # Generated 004010 schemas
└── codegen/
    ├── generator.py          # SchemaGenerator class
    └── templates/            # Jinja2 templates (.j2 files)
```

---

## Public API

```python
# Recommended: Use GeneratedX12SchemaLoader (default, fastest)
from edi_schema.x12.schemas import GeneratedX12SchemaLoader

loader = GeneratedX12SchemaLoader(version="005010")
schema = loader.load("837")

# Convenience functions
from edi_schema.x12.schemas import get_schema, get_segment, get_element

schema = get_schema("837", version="005010")
segment = get_segment("NM1", version="005010")
element = get_element("98", version="005010")

# SchemaRepository (defaults to GeneratedX12SchemaLoader)
from edi_schema.core.repository import SchemaRepository

repo = SchemaRepository()  # No path needed
schema = repo.load("x12", "850")

# Runtime loader for custom schema directories
from edi_schema.x12.schema import X12SchemaLoader

loader = X12SchemaLoader(Path("/custom/schema/path"))
schema = loader.load("837")
```

### Schema Loaders

| Loader                     | Use Case |
|----------------------------|----------|
| `GeneratedX12SchemaLoader` | Default for validation, parsing, production use |
| `X12SchemaLoader`          | Code generation, custom schema directories |

Both provide the same interface:
```python
def exists(self, transaction_id: str) -> bool: ...
def load(self, transaction_id: str) -> X12Schema: ...
def list_schemas(self) -> list[str]: ...
```

---

## Data Models

### Enumerations (`enums.py`)

| Enum | Values | Purpose |
|------|--------|---------|
| `DataElementType` | AN, ID, N0-N9, R, DT, TM, B | Element data types |
| `RequirementDesignator` | M, O, C | Mandatory/Optional/Conditional |
| `TransactionSetArea` | 1, 2, 3 | Heading/Detail/Summary |
| `NoteType` | N, S, C | Syntax/Semantic/Comment |

Also includes `FUNCTIONAL_GROUP_CODES` dictionary (60+ codes).

### Core Models

```python
@dataclass
class DataElement:
    id: str                          # e.g., "98"
    name: str                        # e.g., "Entity Identifier Code"
    data_type: DataElementType       # e.g., ID
    min_length: int
    max_length: int
    definition: str | None           # from ELEDEF
    code_values: dict[str, str]      # from ELECOD

@dataclass
class Segment:
    id: str                          # e.g., "NM1"
    name: str
    purpose: str | None              # from SEGPUR
    elements: list[SegmentElement]
    notes: list[SegmentNote]

@dataclass
class TransactionSet:
    id: str                          # e.g., "837"
    name: str                        # e.g., "Health Care Claim"
    functional_group: str            # e.g., "HC"
    purpose: str | None              # from SETPUR
    structure: list[TransactionSetSegment]

@dataclass
class X12Schema:
    transaction_set: TransactionSet
    segments: dict[str, Segment]
    elements: dict[str, DataElement]
    composites: dict[str, Composite]
    code_sources: dict[str, CodeSource]
    version: str = "005010"

    def get_segment(self, segment_id: str) -> Segment | None
    def get_element(self, element_id: str) -> DataElement | None
    def get_composite(self, composite_id: str) -> Composite | None
    def get_structure(self) -> list[TransactionSetSegment]
    def get_segment_element_definition(self, seg_id, position) -> tuple[DataElement, SegmentElement]
```

---

## Source Files Parsed

| File | Purpose | Parser |
|------|---------|--------|
| `sethead.txt` | Transaction Set definitions | `parse_sethead()` |
| `setdetl.txt` | Transaction structure (loops) | `parse_setdetl()` |
| `seghead.txt` | Segment definitions | `parse_seghead()` |
| `segdetl.txt` | Segment elements | `parse_segdetl()` |
| `comhead.txt` | Composite definitions | `parse_comhead()` |
| `comdetl.txt` | Composite elements | `parse_comdetl()` |
| `elehead.txt` | Data Element definitions | `parse_elehead()` |
| `eledetl.txt` | Data Element attributes | `parse_eledetl()` |
| `cshead.txt` | Code Source definitions | `parse_cshead()` |
| `freeform.txt` | Purposes, notes, codes | `parse_freeform_file()` |

---

## Code Generation

### Taskipy Commands

```bash
task codegen-005010    # Generate 005010 schemas
task codegen-004010    # Generate 004010 schemas
task codegen-all       # Generate all versions
```

### Programmatic

```python
from pathlib import Path
from edi_schema.x12.codegen import SchemaGenerator

generator = SchemaGenerator(
    source_path=Path("/path/to/005010"),
    output_path=Path("src/edi_schema/x12/schemas/v005010"),
    version="005010",
)
generator.generate()
```

### CLI

```bash
python -m edi_schema.x12.codegen.generator \
    --source /path/to/005010 \
    --output src/edi_schema/x12/schemas/v005010 \
    --version 005010
```

### Generated Code Pattern

Factory functions with lazy instantiation:

```python
def _create_element_98() -> DataElement:
    """98 - Entity Identifier Code"""
    return DataElement(
        id="98",
        name='Entity Identifier Code',
        data_type=DataElementType.ID,
        min_length=2,
        max_length=3,
        code_values={'85': 'Billing Provider', 'QC': 'Patient', ...},
    )

DATA_ELEMENTS: dict[str, callable] = {"98": _create_element_98, ...}

def get_data_element(element_id: str) -> DataElement | None:
    factory = DATA_ELEMENTS.get(element_id)
    return factory() if factory else None
```

### Adding New Versions

1. Obtain schema source files for the version
2. Run: `python -m edi_schema.x12.codegen.generator --source /path --output src/.../vNEWVER --version NEWVER`
3. Update `registry.py` to add the new version
4. Add taskipy command to `pyproject.toml`

---

## Validation Integration

### Validation Levels

| Level | Description |
|-------|-------------|
| STRUCTURAL | Basic syntax (delimiters, terminators) |
| ENVELOPE | ISA/IEA, GS/GE, ST/SE matching |
| SCHEMA | Segment order, required segments, loop cardinality |
| ELEMENT | Data types, lengths, required elements |
| CODE | Coded values against code lists |
| SEMANTIC | Cross-element rules, conditional requirements |

### Element Definition Lookup

```python
# Get element definition for NM101
elem_def, seg_ref = schema.get_segment_element_definition("NM1", 1)
# elem_def: DataElement with data_type, min_length, max_length, code_values
# seg_ref: SegmentElement with requirement (M/O/C)
```

### Validation Notes

- **Required Segments**: Only checks segments at transaction root (`loop_level=0`)
- **Max Use**: Only enforced for segments at root level
- **Element Validation**: Uses `get_segment_element_definition()` for lookups
- **Composite Elements**: Currently skipped (need nested validation)

---

## Usage Example

```python
from edi_schema.x12.schemas import GeneratedX12SchemaLoader
from edi_schema.x12.parser import parse_envelope, tokenize
from edi_schema.x12.validator import X12Validator, ValidationLevel

# Load schema
loader = GeneratedX12SchemaLoader(version="005010")
schema = loader.load("837")

print(f"Transaction: {schema.name}")
print(f"Functional Group: {schema.transaction_set.functional_group}")

# Get segment details
nm1 = schema.get_segment("NM1")
if nm1:
    print(f"NM1 Purpose: {nm1.purpose}")
    for elem in nm1.elements:
        element = schema.get_element(elem.element_id)
        if element:
            print(f"  {element.id}: {element.name} ({element.data_type.value})")

# Validate a document
content = open("837.x12").read()
result = parse_envelope(tokenize(content))

validator = X12Validator(schema_loader=loader)
validation = validator.validate(result.interchange)

if not validation.is_valid():
    for error in validation.errors:
        print(f"{error.segment_tag}: {error.message}")
```

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Dataclasses for models | Clean, immutable data structures with type hints |
| Lazy loading with caching | Only load schemas when needed; reuse loaded |
| Factory functions for codegen | Avoid loading all schemas into memory at import |
| Union types over Protocol | Simpler, explicit type checking without runtime overhead |
| `>1` for unlimited | Schema files use ">1" to indicate unlimited repetition |

---

## Future Enhancements

- [ ] Syntax note parsing (conditional rules like P0102, R0305)
- [ ] Composite element validation (nested sub-element validation)
- [ ] Schema export to JSON/XML for external tooling
- [ ] Implementation guide overlays (HIPAA 5010X222A1, etc.)
- [ ] Schema diff tool (compare 4010 vs 5010 changes)
- [ ] Code value validation against external code sources
- [ ] Semantic validation rules engine
