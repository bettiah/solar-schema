"""
X12 Code Source Models.

This module defines dataclasses for representing X12 code sources,
which are external references for code lists maintained by other organizations.
"""

from dataclasses import dataclass, field


@dataclass
class CodeSource:
    """
    Represents an X12 code source definition.

    Code sources are external references to code lists maintained by
    organizations outside of X12 (e.g., IATA codes, D-U-N-S numbers).
    These provide metadata about where to find the authoritative
    code list for certain data elements.

    Attributes:
        id: Code source identifier (e.g., "1", "2", "17")
        name: Name of the code source (e.g., "Standard Carrier Alpha Code (SCAC)")
        source_info: Source information from CSSRCE in freeform.txt
        address: Available from address from CSFROM in freeform.txt
        internet_address: Internet address from CSINET in freeform.txt
        abstract: Abstract description from CSABST in freeform.txt
        notes: Notes from CSNOTE in freeform.txt
        elements: List of element IDs that reference this code source
        code_values: Dictionary mapping code values to descriptions (if defined)
    """

    id: str
    name: str
    source_info: str | None = None
    address: str | None = None
    internet_address: str | None = None
    abstract: str | None = None
    notes: str | None = None
    elements: list[str] = field(default_factory=list)
    code_values: dict[tuple[str, str], str] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"CodeSource {self.id}: {self.name}"

    def get_elements(self) -> list[str]:
        """Get list of element IDs that reference this code source."""
        return self.elements

    def get_code_value(self, element_id: str, code: str) -> str | None:
        """
        Get the description for a code value for a specific element.

        Args:
            element_id: The element ID
            code: The code value

        Returns:
            Description if found, None otherwise
        """
        return self.code_values.get((element_id, code))

    def add_code_value(self, element_id: str, code: str, description: str) -> None:
        """
        Add a code value to this code source.

        Args:
            element_id: The element ID
            code: The code value
            description: The code description
        """
        self.code_values[(element_id, code)] = description
