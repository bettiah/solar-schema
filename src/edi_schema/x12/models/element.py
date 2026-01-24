"""
X12 Data Element and Composite Models.

This module defines dataclasses for representing X12 data elements and composites.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from edi_schema.x12.enums import DataElementType, RequirementDesignator


@dataclass
class DataElement:
    """
    Represents an X12 simple data element.

    Data elements are the atomic units of data in X12 messages.
    They have a defined type, length constraints, and may have
    associated code values.

    Attributes:
        id: Unique element identifier (e.g., "1", "66", "373")
        name: Human-readable element name (e.g., "Route Code")
        data_type: Data type code (AN, ID, N0-N9, R, DT, TM, B)
        min_length: Minimum length of element value
        max_length: Maximum length of element value
        definition: Free-form definition text from ELEDEF
        code_values: Dictionary mapping code values to descriptions from ELECOD
    """

    id: str
    name: str
    data_type: "DataElementType"
    min_length: int
    max_length: int
    definition: str | None = None
    code_values: dict[str, str] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"Element {self.id}: {self.name} ({self.data_type.value} {self.min_length}-{self.max_length})"

    def has_code_list(self) -> bool:
        """Check if this element has defined code values."""
        return bool(self.code_values)

    def is_valid_code(self, code: str) -> bool:
        """
        Check if a code value is valid for this element.

        Returns True if:
        - Element has no code list (any value allowed)
        - Code is in the defined code list
        """
        if not self.code_values:
            return True
        return code in self.code_values


@dataclass
class CompositeElement:
    """
    Represents an element reference within a composite.

    This defines the position and requirements for a simple element
    when used as part of a composite structure.

    Attributes:
        sequence: Position in composite (e.g., "01", "02")
        element_id: Reference to the DataElement id
        requirement: M=Mandatory, O=Optional, C=Conditional
    """

    sequence: str
    element_id: str
    requirement: "RequirementDesignator"

    def __str__(self) -> str:
        return f"{self.sequence}: Element {self.element_id} ({self.requirement.value})"


@dataclass
class Composite:
    """
    Represents an X12 composite data element.

    Composites are structured groups of related simple elements that
    appear together. In X12, composite IDs typically start with "C"
    (e.g., "C001", "C022").

    Attributes:
        id: Composite identifier (e.g., "C001", "C022")
        name: Human-readable name (e.g., "Composite Unit of Measure")
        purpose: Purpose description from COMPUR in freeform.txt
        elements: List of component element references
        notes: Notes from COMNTE in freeform.txt
    """

    id: str
    name: str
    purpose: str | None = None
    elements: list[CompositeElement] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return f"Composite {self.id}: {self.name} ({len(self.elements)} elements)"

    def get_element(self, sequence: str) -> CompositeElement | None:
        """Get an element by its sequence position."""
        for elem in self.elements:
            if elem.sequence == sequence:
                return elem
        return None
