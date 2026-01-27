"""
Message Context for Mapping Operations.

Provides envelope data and external metadata to the mapping engine.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from edi_schema.x12.ast import FunctionalGroupInstance, InterchangeInstance


@dataclass
class MessageContext:
    """
    Context passed to mapper with envelope and external metadata.

    This allows mappings to access:
    1. ISA/GS envelope data (sender/receiver IDs, control numbers, etc.)
    2. External metadata (filename, timestamps, source system info)
    3. Custom key-value pairs for application-specific needs
    """

    # X12 Envelope data (ISA/GS segments)
    interchange: "InterchangeInstance | None" = None
    functional_group: "FunctionalGroupInstance | None" = None

    # External metadata
    filename: str | None = None
    file_path: Path | None = None
    received_at: datetime | None = None
    source_system: str | None = None

    # Arbitrary key-value pairs for application-specific data
    custom: dict[str, Any] = field(default_factory=dict)

    def get_envelope_value(self, segment: str, element: int) -> str | None:
        """
        Get value from envelope (ISA or GS segment).

        Args:
            segment: "ISA" or "GS"
            element: 1-indexed element position

        Returns:
            Element value or None if not available
        """
        if segment == "ISA" and self.interchange:
            return self._get_isa_element(element)
        elif segment == "GS" and self.functional_group:
            return self._get_gs_element(element)
        return None

    def _get_isa_element(self, element: int) -> str | None:
        """Get ISA element by position."""
        if not self.interchange:
            return None

        isa_map = {
            1: self.interchange.auth_qualifier,
            2: self.interchange.auth_info,
            3: self.interchange.security_qualifier,
            4: self.interchange.security_info,
            5: self.interchange.sender_qualifier,
            6: self.interchange.sender_id,
            7: self.interchange.receiver_qualifier,
            8: self.interchange.receiver_id,
            9: self.interchange.date,
            10: self.interchange.time,
            11: self.interchange.repetition_separator,
            12: self.interchange.version,
            13: self.interchange.control_number,
            14: self.interchange.ack_requested,
            15: self.interchange.usage_indicator,
            16: self.interchange.component_separator,
        }
        value = isa_map.get(element)
        # Strip padding from ISA values
        return value.strip() if value else None

    def _get_gs_element(self, element: int) -> str | None:
        """Get GS element by position."""
        if not self.functional_group:
            return None

        gs_map = {
            1: self.functional_group.functional_id,
            2: self.functional_group.sender_id,
            3: self.functional_group.receiver_id,
            4: self.functional_group.date,
            5: self.functional_group.time,
            6: self.functional_group.control_number,
            7: self.functional_group.responsible_agency,
            8: self.functional_group.version,
        }
        return gs_map.get(element)

    def get_context_value(self, key: str) -> Any:
        """
        Get value from context by key.

        Supports dot notation for nested access:
        - "filename" -> self.filename
        - "custom.my_key" -> self.custom["my_key"]

        Args:
            key: Dot-separated key path

        Returns:
            Value or None if not found
        """
        parts = key.split(".", 1)

        if parts[0] == "custom" and len(parts) > 1:
            return self.custom.get(parts[1])

        # Direct attributes
        attr_map = {
            "filename": self.filename,
            "file_path": str(self.file_path) if self.file_path else None,
            "received_at": self.received_at,
            "source_system": self.source_system,
        }
        return attr_map.get(key)

    @classmethod
    def from_parse_result(
        cls,
        parse_result: Any,
        group_index: int = 0,
        **kwargs: Any,
    ) -> "MessageContext":
        """
        Create context from a ParseResult.

        Args:
            parse_result: ParseResult from X12 parser
            group_index: Which functional group to use (default 0)
            **kwargs: Additional context values (filename, received_at, etc.)

        Returns:
            MessageContext with envelope data populated
        """
        interchange = parse_result.interchange if parse_result else None
        functional_group = None

        if interchange and interchange.groups:
            if 0 <= group_index < len(interchange.groups):
                functional_group = interchange.groups[group_index]

        return cls(
            interchange=interchange,
            functional_group=functional_group,
            **kwargs,
        )
