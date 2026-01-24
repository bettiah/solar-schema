# EDI Schema

A Python library for parsing and validating Electronic Data Interchange (EDI) documents using schema definitions.

## Overview

This project provides tooling to:

1. **Read EDI format specifications** from their text definitions
2. **Generate Python schemas** from those definitions
3. **Parse EDI documents** into an Abstract Syntax Tree (AST)
4. **Validate parsed documents** against the appropriate schema

## Supported Formats

| Format | Status | Description |
|--------|--------|-------------|
| X12 | Planned | ANSI ASC X12 - primary standard for North American EDI |
| EDIFACT | Planned | UN/EDIFACT - international EDI standard |
| HIPAA | Future | Healthcare-specific X12 transaction sets with additional constraints |
| UBL | Future | Universal Business Language - XML-based business documents |
| FHIR | Future | Fast Healthcare Interoperability Resources |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     EDI Document Input                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Format Detection                             │
│         (Identify X12, EDIFACT, etc. from document)             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Schema Repository                             │
│    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │
│    │    X12      │  │  EDIFACT    │  │   HIPAA     │  ...      │
│    │  Schemas    │  │  Schemas    │  │  Schemas    │           │
│    └─────────────┘  └─────────────┘  └─────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Parser                                   │
│              (Format-specific tokenization & AST)               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Validator                                 │
│            (Validate AST against loaded schema)                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Validated AST / Errors                        │
└─────────────────────────────────────────────────────────────────┘
```

## Core Component
[x12 schemas](/Users/me/Downloads/edi/schema/x12/005010/)
[x12_schema_plan.md](plans/x12_schema_plan.md)
[x12.md](plans/x12.md)

[edifact schemas](/Users/me/Downloads/edi/schema/edifact/d23a/)
[edifact_plan.md](plans/edifact_plan.md)
[edifact.md](plans/edifact.md)

### Schema Definitions

Python dataclasses/models representing EDI structure definitions:

- **Segments** - Named groups of related data elements (e.g., `ISA`, `GS`, `ST`)
- **Elements** - Individual data fields with type, length, and optionality constraints
- **Loops** - Repeating groups of segments
- **Transaction Sets** - Complete message types (e.g., 850 Purchase Order, 837 Healthcare Claim)

### Objective 

- Use the x12 and edifact schema libraries to build re-usable schemas needed for reading, validating, and building raw EDI files.

### Schema Repository

Local storage and lookup for schema definitions:

```python
repository.exists("x12", "850", version="005010")  # Check if schema available
repository.load("x12", "850", version="005010")    # Load schema for parsing
```

### Parser

Format-specific parsers that produce a common AST structure:

- Tokenize raw EDI text based on declared delimiters
- Build hierarchical AST from segments and loops
- Preserve source positions for error reporting

### Validator

Validate parsed AST against schema rules:

- Required vs optional segments/elements
- Cardinality constraints (min/max occurrences)
- Data type validation (numeric, date, identifier codes)
- Length constraints
- Code list validation

## Project Structure

```
src/
├── x12/                    # X12-specific implementation
│   ├── parser.py           # X12 tokenizer and parser
│   ├── schemas/            # X12 schema definitions
│   └── ...
├── edifact/                # EDIFACT-specific implementation
│   ├── parser.py
│   ├── schemas/
│   └── ...
├── core/                   # Shared components
│   ├── ast.py              # Common AST node types
│   ├── validator.py        # Schema validation logic
│   └── repository.py       # Schema storage and lookup
└── ...
```

## Usage (Planned API)

```python
from edi_schema import parse, validate
from edi_schema.repository import SchemaRepository

# Initialize repository with local schema path
repo = SchemaRepository("/path/to/schemas")

# Parse an EDI document
with open("purchase_order.edi") as f:
    ast = parse(f.read())

# Check if schema exists for this document
schema_id = ast.get_schema_identifier()  # e.g., ("x12", "850", "005010")
if not repo.exists(*schema_id):
    raise ValueError(f"No schema found for {schema_id}")

# Load schema and validate
schema = repo.load(*schema_id)
errors = validate(ast, schema)

if errors:
    for error in errors:
        print(f"{error.path}: {error.message}")
else:
    print("Document is valid")
```

## Development

```bash
# Install dependencies
uv sync

# Run tests
pytest
```

## License

TBD