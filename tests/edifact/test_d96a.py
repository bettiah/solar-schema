"""
Tests for D96A EDIFACT directory loading.

D96A uses a flat file layout different from D23A:
- Files in root: EDED.96A, EDCD.96A, EDSD.96A
- Messages in messages/ subdirectory
- No UNCL file (code lists not available separately)
"""

from pathlib import Path

import pytest

from edi_schema.edifact.schema.registry import EdifactRegistry

# Path to D96A test data
D96A_PATH = Path.home() / "Downloads" / "edi" / "schema" / "edifact" / "d96a"


@pytest.fixture
def d96a_registry() -> EdifactRegistry:
    """Load registry from D96A directory."""
    if not D96A_PATH.exists():
        pytest.skip(f"D96A directory not found at {D96A_PATH}")

    registry = EdifactRegistry()
    registry.load_from_directory(D96A_PATH)
    return registry


class TestD96ADirectoryDetection:
    """Tests for D96A directory layout detection."""

    def test_detects_version_suffix(self, d96a_registry: EdifactRegistry) -> None:
        """Should detect 96A version suffix."""
        assert d96a_registry._version_suffix == "96A"

    def test_detects_message_directory(self, d96a_registry: EdifactRegistry) -> None:
        """Should detect messages/ subdirectory for D96A."""
        assert d96a_registry._message_path is not None
        assert d96a_registry._message_path.name == "messages"
        assert d96a_registry._message_path.exists()


class TestD96AElementLoading:
    """Tests for loading data elements from D96A."""

    def test_loads_elements(self, d96a_registry: EdifactRegistry) -> None:
        """Should load elements from EDED.96A."""
        assert len(d96a_registry.elements) > 0

    def test_loads_common_elements(self, d96a_registry: EdifactRegistry) -> None:
        """Should load well-known elements."""
        # Element 1001 - Document name code
        elem_1001 = d96a_registry.get_element("1001")
        assert elem_1001 is not None
        assert elem_1001.tag == "1001"

        # Element 3035 - Party function code qualifier
        elem_3035 = d96a_registry.get_element("3035")
        assert elem_3035 is not None
        assert elem_3035.tag == "3035"


class TestD96ACompositeLoading:
    """Tests for loading composites from D96A."""

    def test_loads_composites(self, d96a_registry: EdifactRegistry) -> None:
        """Should load composites from EDCD.96A."""
        assert len(d96a_registry.composites) > 0

    def test_loads_common_composites(self, d96a_registry: EdifactRegistry) -> None:
        """Should load well-known composites."""
        # C002 - Document/message name
        c002 = d96a_registry.get_composite("C002")
        assert c002 is not None
        assert c002.tag == "C002"

        # C082 - Party identification details
        c082 = d96a_registry.get_composite("C082")
        assert c082 is not None


class TestD96ASegmentLoading:
    """Tests for loading segments from D96A."""

    def test_loads_segments(self, d96a_registry: EdifactRegistry) -> None:
        """Should load segments from EDSD.96A."""
        assert len(d96a_registry.segments) > 0

    def test_loads_common_segments(self, d96a_registry: EdifactRegistry) -> None:
        """Should load well-known segments."""
        # Note: UNH/UNB/etc. service segments are not in EDSD for D96A
        # BGM - Beginning of message
        bgm = d96a_registry.get_segment("BGM")
        assert bgm is not None
        assert bgm.tag == "BGM"

        # DTM - Date/time/period
        dtm = d96a_registry.get_segment("DTM")
        assert dtm is not None

        # NAD - Name and address
        nad = d96a_registry.get_segment("NAD")
        assert nad is not None


class TestD96AMessageLoading:
    """Tests for loading messages from D96A."""

    def test_lists_available_messages(self, d96a_registry: EdifactRegistry) -> None:
        """Should list all available messages."""
        messages = d96a_registry.list_available_messages()
        assert len(messages) > 0
        # D96A should have common message types
        assert "INVOIC" in messages or "ORDERS" in messages

    def test_message_exists(self, d96a_registry: EdifactRegistry) -> None:
        """Should detect if message exists."""
        # Get first available message
        messages = d96a_registry.list_available_messages()
        if messages:
            assert d96a_registry.message_exists(messages[0])

        # Non-existent message
        assert not d96a_registry.message_exists("ZZZZZZZ")

    def test_loads_message(self, d96a_registry: EdifactRegistry) -> None:
        """Should load a message specification."""
        messages = d96a_registry.list_available_messages()
        if not messages:
            pytest.skip("No messages available")

        # Load first message
        msg = d96a_registry.load_message(messages[0])
        assert msg is not None
        assert msg.code == messages[0]

    def test_loads_invoic_message(self, d96a_registry: EdifactRegistry) -> None:
        """Should load INVOIC message if available."""
        if not d96a_registry.message_exists("INVOIC"):
            pytest.skip("INVOIC not available in D96A")

        msg = d96a_registry.load_message("INVOIC")
        assert msg is not None
        assert msg.code == "INVOIC"

    def test_loads_orders_message(self, d96a_registry: EdifactRegistry) -> None:
        """Should load ORDERS message if available."""
        if not d96a_registry.message_exists("ORDERS"):
            pytest.skip("ORDERS not available in D96A")

        msg = d96a_registry.load_message("ORDERS")
        assert msg is not None
        assert msg.code == "ORDERS"


class TestD96ACodeLists:
    """Tests for code list handling in D96A."""

    def test_code_lists_may_be_empty(self, d96a_registry: EdifactRegistry) -> None:
        """D96A may not have separate UNCL file - code lists can be empty."""
        # This is expected - D96A doesn't always have UNCL file
        # Code lists might be embedded in element definitions instead
        # Just verify it doesn't crash
        assert isinstance(d96a_registry.code_lists, dict)


class TestD96AStats:
    """Tests for registry statistics."""

    def test_stats_populated(self, d96a_registry: EdifactRegistry) -> None:
        """Should have populated stats."""
        stats = d96a_registry.stats
        assert stats["elements"] > 0
        assert stats["composites"] > 0
        assert stats["segments"] > 0


class TestD96AVsD23AComparison:
    """Compare D96A with D23A to verify both layouts work."""

    @pytest.fixture
    def d23a_registry(self) -> EdifactRegistry:
        """Load registry from D23A directory."""
        d23a_path = Path.home() / "Downloads" / "edi" / "schema" / "edifact" / "d23a"
        if not d23a_path.exists():
            pytest.skip(f"D23A directory not found at {d23a_path}")

        registry = EdifactRegistry()
        registry.load_from_directory(d23a_path)
        return registry

    def test_both_load_elements(
        self,
        d96a_registry: EdifactRegistry,
        d23a_registry: EdifactRegistry,
    ) -> None:
        """Both versions should load elements."""
        assert len(d96a_registry.elements) > 0
        assert len(d23a_registry.elements) > 0

    def test_both_load_segments(
        self,
        d96a_registry: EdifactRegistry,
        d23a_registry: EdifactRegistry,
    ) -> None:
        """Both versions should load segments."""
        assert len(d96a_registry.segments) > 0
        assert len(d23a_registry.segments) > 0

    def test_both_detect_message_directory(
        self,
        d96a_registry: EdifactRegistry,
        d23a_registry: EdifactRegistry,
    ) -> None:
        """Both versions should detect message directories."""
        assert d96a_registry._message_path is not None
        assert d23a_registry._message_path is not None

        # D96A uses messages/, D23A uses edmd/
        assert d96a_registry._message_path.name == "messages"
        assert d23a_registry._message_path.name == "edmd"
