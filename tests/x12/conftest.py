"""Shared fixtures and helpers for X12 tests."""

import re
from pathlib import Path

import pytest
from syrupy.extensions.amber import AmberSnapshotExtension

from edi_schema.x12.ast import LoopInstance, ParsedSegment, RawSegment
from edi_schema.x12.schemas import GeneratedX12SchemaLoader


class PerSampleSnapshotExtension(AmberSnapshotExtension):
    """Syrupy extension that creates one snapshot file per parametrized sample.

    For a parametrized test like test_foo[945_warehouse_shipping_advice],
    this creates: __snapshots__/test_module/945_warehouse_shipping_advice.ambr
    instead of the default: __snapshots__/test_module.ambr
    """

    @classmethod
    def dirname(cls, *, test_location):
        test_dir = Path(test_location.filepath).parent
        return str(test_dir / cls.snapshot_dirname / Path(test_location.filepath).stem)

    @classmethod
    def get_file_basename(cls, *, test_location, index):
        if test_location.is_item_parametrized:
            match = re.search(r"\[(.+)\]$", test_location.testname)
            if match:
                return match.group(1)
        return test_location.basename

# Path to X12 sample files
X12_SAMPLES_DIR = Path(__file__).parent.parent / "fixtures" / "x12_samples"
HIPAA_SAMPLES_DIR = X12_SAMPLES_DIR / "hipaa"
LOGISTICS_SAMPLES_DIR = X12_SAMPLES_DIR / "logistics"


def get_sample_files(directory: Path) -> list[Path]:
    """Get all X12 sample files from a directory."""
    if not directory.exists():
        return []
    return sorted(directory.glob("*.x12"))


def get_schema_version_for_file(x12_file: Path) -> str:
    """Determine the schema version to use for a given X12 file.

    Reads the ISA segment to detect the version (ISA12), then maps to schema version.
    """
    content = x12_file.read_text()

    # ISA is always 106 characters with fixed positions
    # ISA12 (version) is at positions 84-88 (0-indexed: 83-88)
    if len(content) >= 89:
        version_raw = content[84:89]
        if version_raw == "00401":
            return "004010"
        elif version_raw == "00501":
            return "005010"

    # Default to 005010 for HIPAA files
    if "hipaa" in str(x12_file).lower():
        return "005010"

    # Default to 004010 for logistics files
    if "logistics" in str(x12_file).lower():
        return "004010"

    return "005010"


def get_schema_loader_for_file(x12_file: Path) -> GeneratedX12SchemaLoader:
    """Get the appropriate schema loader for a given X12 file."""
    version = get_schema_version_for_file(x12_file)
    return GeneratedX12SchemaLoader(version=version)


def get_all_sample_files() -> list[Path]:
    """Get all X12 sample files from all subdirectories."""
    files = []
    files.extend(get_sample_files(HIPAA_SAMPLES_DIR))
    files.extend(get_sample_files(LOGISTICS_SAMPLES_DIR))
    return files


# Get list of sample files for parametrization
HIPAA_SAMPLE_FILES = get_sample_files(HIPAA_SAMPLES_DIR)
LOGISTICS_SAMPLE_FILES = get_sample_files(LOGISTICS_SAMPLES_DIR)
SAMPLE_FILES = get_all_sample_files()


@pytest.fixture
def schema_loader() -> GeneratedX12SchemaLoader:
    """Load X12 005010 schema using pre-generated schemas."""
    return GeneratedX12SchemaLoader(version="005010")


def interchange_to_dict(interchange) -> dict | None:
    """Convert an InterchangeInstance to a dictionary for snapshot comparison."""
    if interchange is None:
        return None

    return {
        "sender_id": interchange.sender_id.strip(),
        "receiver_id": interchange.receiver_id.strip(),
        "control_number": interchange.control_number,
        "version": interchange.version,
        "groups": [group_to_dict(g) for g in interchange.groups],
    }


def group_to_dict(group) -> dict:
    """Convert a FunctionalGroupInstance to a dictionary."""
    return {
        "functional_id": group.functional_id,
        "control_number": group.control_number,
        "version": group.version,
        "transactions": [transaction_to_dict(t) for t in group.transactions],
    }


def transaction_to_dict(txn) -> dict:
    """Convert a TransactionSetInstance to a dictionary."""
    return {
        "transaction_id": txn.transaction_id,
        "control_number": txn.control_number,
        "segment_count": txn.segment_count,
        "content": [content_item_to_dict(item) for item in txn.content],
    }


def content_item_to_dict(item) -> dict:
    """Convert content item (segment or loop) to a dictionary."""
    if isinstance(item, LoopInstance):
        return {
            "type": "loop",
            "loop_id": item.loop_id,
            "iteration": item.iteration,
            "segments": [segment_to_dict(s) for s in item.segments],
            "children": [content_item_to_dict(c) for c in item.children],
        }
    elif isinstance(item, ParsedSegment):
        return segment_to_dict(item)
    elif isinstance(item, RawSegment):
        return raw_segment_to_dict(item)
    else:
        return {"type": "unknown", "value": str(item)}


def segment_to_dict(seg: ParsedSegment) -> dict:
    """Convert a ParsedSegment to a dictionary."""
    return {
        "type": "segment",
        "tag": seg.tag,
        "elements": [elem.value for elem in seg.elements],
    }


def raw_segment_to_dict(seg: RawSegment) -> dict:
    """Convert a RawSegment to a dictionary."""
    elements = []
    for elem in seg.elements:
        if hasattr(elem, "value"):
            elements.append(elem.value)
        elif hasattr(elem, "components"):
            elements.append(":".join(elem.components))
        else:
            elements.append(str(elem))
    return {
        "type": "segment",
        "tag": seg.tag,
        "elements": elements,
    }
