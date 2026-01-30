"""Snapshot tests for 997 acknowledgment generation from X12 sample files."""

from pathlib import Path

import pytest

from edi_schema.x12.ack import generate_997
from edi_schema.x12.parser import parse

from .conftest import SAMPLE_FILES, PerSampleSnapshotExtension


@pytest.fixture
def snapshot(snapshot):
    return snapshot.use_extension(PerSampleSnapshotExtension)


@pytest.mark.skipif(
    not SAMPLE_FILES,
    reason="X12 sample files not found",
)
class Test997Generation:
    """Tests for 997 acknowledgment generation from sample files."""

    @pytest.mark.parametrize(
        "x12_file",
        SAMPLE_FILES,
        ids=[f.stem for f in SAMPLE_FILES],
    )
    def test_generate_997_for_sample(self, x12_file: Path, snapshot):
        """Generate 997 for sample file and verify structure matches snapshot."""
        result = parse(x12_file)

        assert result.interchange is not None

        for group in result.interchange.groups:
            ack = generate_997(group, control_number="0001")

            # 997 should have proper structure
            assert "ST*997*0001" in ack
            assert "AK1*" in ack
            assert "AK5*" in ack
            assert "AK9*" in ack
            assert "SE*" in ack
            assert ack.endswith("~")

        # Snapshot the 997 for first group
        ack = generate_997(result.interchange.groups[0], control_number="0001")
        assert ack == snapshot
