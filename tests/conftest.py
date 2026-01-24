"""
Common test fixtures for EDI Schema tests.
"""

from pathlib import Path

import pytest

# Schema source directories (adjust paths as needed for your environment)
X12_SCHEMA_PATH = Path("/Users/me/Downloads/edi/schema/x12/005010")
EDIFACT_SCHEMA_PATH = Path("/Users/me/Downloads/edi/schema/edifact/d23a")


@pytest.fixture
def x12_schema_path() -> Path:
    """Path to X12 005010 schema files."""
    if not X12_SCHEMA_PATH.exists():
        pytest.skip(f"X12 schema path not found: {X12_SCHEMA_PATH}")
    return X12_SCHEMA_PATH


@pytest.fixture
def edifact_schema_path() -> Path:
    """Path to EDIFACT D.23A schema files."""
    if not EDIFACT_SCHEMA_PATH.exists():
        pytest.skip(f"EDIFACT schema path not found: {EDIFACT_SCHEMA_PATH}")
    return EDIFACT_SCHEMA_PATH


@pytest.fixture
def x12_sethead_path(x12_schema_path: Path) -> Path:
    """Path to X12 sethead.txt file."""
    return x12_schema_path / "sethead.txt"


@pytest.fixture
def x12_seghead_path(x12_schema_path: Path) -> Path:
    """Path to X12 seghead.txt file."""
    return x12_schema_path / "seghead.txt"


@pytest.fixture
def x12_elehead_path(x12_schema_path: Path) -> Path:
    """Path to X12 elehead.txt file."""
    return x12_schema_path / "elehead.txt"


@pytest.fixture
def x12_freeform_path(x12_schema_path: Path) -> Path:
    """Path to X12 freeform.txt file."""
    return x12_schema_path / "freeform.txt"


@pytest.fixture
def edifact_uncl_path(edifact_schema_path: Path) -> Path:
    """Path to EDIFACT UNCL.23A code list file."""
    return edifact_schema_path / "UNCL.23A"


@pytest.fixture
def edifact_eded_path(edifact_schema_path: Path) -> Path:
    """Path to EDIFACT EDED.23A data element file."""
    return edifact_schema_path / "eded" / "EDED.23A"
