"""Snapshot tests for parsing X12 sample files with schema binding."""

from pathlib import Path

import pytest

from edi_schema.x12.ast import ErrorSeverity
from edi_schema.x12.parser import parse_file

from .conftest import (
    SAMPLE_FILES,
    PerSampleSnapshotExtension,
    get_schema_loader_for_file,
    interchange_to_dict,
)


@pytest.fixture
def snapshot(snapshot):
    return snapshot.use_extension(PerSampleSnapshotExtension)


@pytest.mark.skipif(
    not SAMPLE_FILES,
    reason="X12 sample files not found",
)
class TestX12SampleFiles:
    """Tests for parsing X12 sample files with schema binding."""

    @pytest.mark.parametrize(
        "x12_file",
        SAMPLE_FILES,
        ids=[f.stem for f in SAMPLE_FILES],
    )
    def test_parse_sample_file_with_schema(
        self,
        x12_file: Path,
        snapshot,
    ):
        """Parse sample file with schema binding and verify structure matches snapshot."""
        schema_loader = get_schema_loader_for_file(x12_file)
        result = parse_file(x12_file, schema_loader=schema_loader)

        # Should parse without fatal errors
        fatal_errors = [e for e in result.errors if e.severity == ErrorSeverity.FATAL]
        assert len(fatal_errors) == 0, f"Parse failed: {fatal_errors}"
        assert result.interchange is not None

        parsed = interchange_to_dict(result.interchange)
        assert parsed == snapshot
