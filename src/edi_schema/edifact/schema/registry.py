"""
EDIFACT Schema Registry.

Holds all parsed EDIFACT components (elements, composites, segments, messages)
in a central location for lookup and reference resolution.

Supports multiple EDIFACT directory layouts:
- D23A style: Organized subdirectories (eded/, edcd/, edsd/, edmd/)
- D96A style: Flat layout with files in root and messages/ subdirectory
"""

from pathlib import Path

from ..models import Composite, DataElement, MessageSpec, Segment
from ..schema_parsers import parse_edcd, parse_eded, parse_edmd, parse_edsd, parse_uncl


class EdifactRegistry:
    """
    Central registry for all parsed EDIFACT schema components.

    Loads and holds:
    - Code lists (from UNCL)
    - Data elements (from EDED)
    - Composites (from EDCD)
    - Segments (from EDSD)
    - Messages (from EDMD, loaded on demand)

    Supports multiple directory layouts:
    - D23A style: eded/, edcd/, edsd/, edmd/ subdirectories
    - D96A style: flat files in root, messages/ subdirectory

    Attributes:
        code_lists: Dict of element_tag -> {code: description}
        elements: Dict of element_tag -> DataElement
        composites: Dict of composite_tag -> Composite
        segments: Dict of segment_tag -> Segment
        messages: Dict of message_code -> MessageSpec (loaded on demand)
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self.code_lists: dict[str, dict[str, str]] = {}
        self.elements: dict[str, DataElement] = {}
        self.composites: dict[str, Composite] = {}
        self.segments: dict[str, Segment] = {}
        self.messages: dict[str, MessageSpec] = {}

        # Track paths for lazy message loading
        self._message_path: Path | None = None
        self._base_path: Path | None = None
        self._version_suffix: str | None = None

    def load_from_directory(self, base_path: Path) -> None:
        """
        Load all schema components from an EDIFACT directory.

        Supports multiple directory layouts:

        D23A style (organized):
            base_path/
                UNCL.23A           - Code lists
                eded/EDED.23A      - Data elements
                edcd/EDCD.22B      - Composites
                edsd/EDSD.23A      - Segments
                edmd/*_D.23A       - Messages

        D96A style (flat):
            base_path/
                UNCL.96A           - Code lists (may not exist)
                EDED.96A           - Data elements
                EDCD.96A           - Composites
                EDSD.96A           - Segments
                messages/*_D.96A   - Messages

        Args:
            base_path: Path to the EDIFACT version directory (e.g., d23a/, d96a/)
        """
        self._base_path = base_path
        self._version_suffix = self._detect_version_suffix(base_path)

        self._load_code_lists(base_path)
        self._load_elements(base_path)
        self._load_composites(base_path)
        self._load_segments(base_path)

        # Detect message directory (edmd/ or messages/ or root)
        self._message_path = self._detect_message_directory(base_path)

    def _detect_version_suffix(self, base_path: Path) -> str | None:
        """
        Detect the version suffix from files in the directory.

        Looks for patterns like EDED.96A, EDED.23A to determine suffix.
        """
        # Try common component files
        for pattern in ["EDED.*", "EDSD.*", "EDCD.*"]:
            # Check root
            for file in base_path.glob(pattern):
                suffix = file.suffix.lstrip(".")
                if suffix and len(suffix) >= 2:
                    return suffix

            # Check subdirectories
            for subdir in ["eded", "edsd", "edcd"]:
                subdir_path = base_path / subdir
                if subdir_path.exists():
                    for file in subdir_path.glob(pattern):
                        suffix = file.suffix.lstrip(".")
                        if suffix and len(suffix) >= 2:
                            return suffix

        return None

    def _detect_message_directory(self, base_path: Path) -> Path | None:
        """
        Detect the message directory, handling different layouts.

        Checks in order:
        1. edmd/ (D23A style)
        2. messages/ (D96A style)
        3. root directory
        """
        # D23A style
        edmd = base_path / "edmd"
        if edmd.exists() and edmd.is_dir():
            return edmd

        # D96A style
        messages = base_path / "messages"
        if messages.exists() and messages.is_dir():
            return messages

        # Check if message files exist in root
        for file in base_path.glob("*_D.*"):
            if file.is_file():
                return base_path

        return None

    def _find_file(
        self,
        base_path: Path,
        base_name: str,
        subdirs: list[str] | None = None,
    ) -> Path | None:
        """
        Find a file, checking both organized and flat layouts.

        Args:
            base_path: Base directory to search
            base_name: Base filename without suffix (e.g., "EDED", "EDCD")
            subdirs: Optional subdirectories to check first (e.g., ["eded"])

        Returns:
            Path to the file if found, None otherwise
        """
        # Build patterns to search
        patterns = [f"{base_name}.*"]

        # Try subdirectories first (D23A style)
        if subdirs:
            for subdir in subdirs:
                subdir_path = base_path / subdir
                if subdir_path.exists():
                    for pattern in patterns:
                        for file in subdir_path.glob(pattern):
                            if file.is_file():
                                return file

        # Fall back to root (D96A style)
        for pattern in patterns:
            for file in base_path.glob(pattern):
                if file.is_file():
                    return file

        return None

    def _load_code_lists(self, base_path: Path) -> None:
        """Load code lists from UNCL file."""
        uncl_path = self._find_file(base_path, "UNCL")
        if uncl_path and uncl_path.exists():
            self.code_lists = parse_uncl(uncl_path)
        # Note: Some versions (like D96A) may not have UNCL files
        # Code lists will be empty in that case

    def _load_elements(self, base_path: Path) -> None:
        """Load data elements from EDED file."""
        eded_path = self._find_file(base_path, "EDED", subdirs=["eded"])
        if eded_path:
            self.elements = parse_eded(eded_path, self.code_lists)

    def _load_composites(self, base_path: Path) -> None:
        """Load composites from EDCD file."""
        edcd_path = self._find_file(base_path, "EDCD", subdirs=["edcd"])
        if edcd_path:
            self.composites = parse_edcd(edcd_path)

    def _load_segments(self, base_path: Path) -> None:
        """Load segments from EDSD file."""
        edsd_path = self._find_file(base_path, "EDSD", subdirs=["edsd"])
        if edsd_path:
            self.segments = parse_edsd(edsd_path)

    def load_message(self, code: str) -> MessageSpec | None:
        """
        Load a specific message definition.

        Messages are loaded on demand to avoid parsing all message files
        when only a few are needed.

        Args:
            code: Message code (e.g., 'INVOIC', 'ORDERS')

        Returns:
            MessageSpec if found, None otherwise
        """
        # Check cache first
        if code in self.messages:
            return self.messages[code]

        if self._message_path is None:
            return None

        # Build patterns based on detected version suffix
        code_upper = code.upper()
        patterns = [f"{code_upper}_D.*"]
        if code != code_upper:
            patterns.append(f"{code}_D.*")

        # Search for message file
        for pattern in patterns:
            for file in self._message_path.glob(pattern):
                if file.is_file():
                    msg = parse_edmd(file)
                    self.messages[code_upper] = msg
                    return msg

        return None

    def message_exists(self, code: str) -> bool:
        """
        Check if a message definition exists.

        Args:
            code: Message code to check

        Returns:
            True if message file exists
        """
        if code.upper() in self.messages:
            return True

        if self._message_path is None:
            return False

        # Build patterns based on code
        code_upper = code.upper()
        patterns = [f"{code_upper}_D.*"]
        if code != code_upper:
            patterns.append(f"{code}_D.*")

        for pattern in patterns:
            for file in self._message_path.glob(pattern):
                if file.is_file():
                    return True

        return False

    def list_available_messages(self) -> list[str]:
        """
        List all available message codes.

        Returns:
            List of message codes found in the message directory
        """
        if self._message_path is None or not self._message_path.exists():
            return []

        messages = []
        for file in self._message_path.iterdir():
            if file.is_file() and "_D." in file.name:
                code = file.name.split("_")[0]
                if code not in messages:
                    messages.append(code)

        return sorted(messages)

    def get_element(self, tag: str) -> DataElement | None:
        """Get a data element by tag."""
        return self.elements.get(tag)

    def get_composite(self, tag: str) -> Composite | None:
        """Get a composite by tag."""
        return self.composites.get(tag)

    def get_segment(self, tag: str) -> Segment | None:
        """Get a segment by tag."""
        return self.segments.get(tag)

    def get_codes(self, element_tag: str) -> dict[str, str] | None:
        """Get code list for an element."""
        return self.code_lists.get(element_tag)

    @property
    def stats(self) -> dict[str, int]:
        """Get statistics about loaded components."""
        return {
            "code_lists": len(self.code_lists),
            "elements": len(self.elements),
            "composites": len(self.composites),
            "segments": len(self.segments),
            "messages_loaded": len(self.messages),
        }
