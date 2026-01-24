"""
UBL Component Models.

Defines the CCTS-based component types used in UBL:
- BBIE (Basic Business Information Entity) - leaf data elements
- ASBIE (Association Business Information Entity) - references to ABIEs
- ABIE (Aggregate Business Information Entity) - complex containers
"""

from dataclasses import dataclass, field

from ..enums import Cardinality, ComponentType


@dataclass
class BBIE:
    """
    Basic Business Information Entity.

    BBIEs are leaf elements that hold actual data values. They appear in
    the CommonBasicComponents (cbc:) namespace.

    Attributes:
        name: Element name (e.g., 'ID', 'IssueDate', 'Amount')
        definition: Human-readable description
        cardinality: Occurrence constraints (0..1, 1, 0..n, 1..n)
        data_type: Reference to UDT or QDT type name
        representation_term: CCTS representation term (Amount, Code, Date, etc.)
        property_term: The property being represented
        object_class: The parent ABIE's object class
        examples: Example values (optional)
        alternative_terms: Alternative business names
        deprecated: Whether this element is deprecated
    """

    name: str
    definition: str
    cardinality: Cardinality
    data_type: str
    representation_term: str
    property_term: str = ""
    object_class: str = ""
    examples: list[str] = field(default_factory=list)
    alternative_terms: list[str] = field(default_factory=list)
    deprecated: bool = False

    @property
    def component_type(self) -> ComponentType:
        """Return the component type."""
        return ComponentType.BBIE

    @property
    def id(self) -> str:
        """Return unique identifier."""
        return self.name

    @property
    def is_required(self) -> bool:
        """Check if this element is required."""
        return self.cardinality.is_required

    @property
    def is_multiple(self) -> bool:
        """Check if this element can occur multiple times."""
        return self.cardinality.is_multiple


@dataclass
class ASBIE:
    """
    Association Business Information Entity.

    ASBIEs link one ABIE to another. They appear as elements in the
    CommonAggregateComponents (cac:) namespace that reference other ABIEs.

    Attributes:
        name: Element name (e.g., 'AccountingSupplierParty', 'InvoiceLine')
        definition: Human-readable description
        cardinality: Occurrence constraints
        associated_abie: Name of the target ABIE type
        property_term: The property being represented
        object_class: The parent ABIE's object class
        alternative_terms: Alternative business names
    """

    name: str
    definition: str
    cardinality: Cardinality
    associated_abie: str
    property_term: str = ""
    object_class: str = ""
    alternative_terms: list[str] = field(default_factory=list)

    @property
    def component_type(self) -> ComponentType:
        """Return the component type."""
        return ComponentType.ASBIE

    @property
    def id(self) -> str:
        """Return unique identifier."""
        return self.name

    @property
    def is_required(self) -> bool:
        """Check if this element is required."""
        return self.cardinality.is_required

    @property
    def is_multiple(self) -> bool:
        """Check if this element can occur multiple times."""
        return self.cardinality.is_multiple


@dataclass
class ABIE:
    """
    Aggregate Business Information Entity.

    ABIEs are complex containers that hold BBIEs (basic elements) and
    ASBIEs (references to other ABIEs). They define the structure of
    UBL documents and reusable components.

    Attributes:
        name: Type name without 'Type' suffix (e.g., 'Party', 'Address', 'Invoice')
        definition: Human-readable description
        object_class: CCTS object class name
        bbies: List of basic elements in this ABIE
        asbies: List of associations to other ABIEs
        namespace: The namespace this ABIE belongs to (cac: or document-specific)
    """

    name: str
    definition: str
    object_class: str = ""
    bbies: list[BBIE] = field(default_factory=list)
    asbies: list[ASBIE] = field(default_factory=list)
    namespace: str = ""

    @property
    def component_type(self) -> ComponentType:
        """Return the component type."""
        return ComponentType.ABIE

    @property
    def id(self) -> str:
        """Return unique identifier."""
        return self.name

    @property
    def type_name(self) -> str:
        """Return the full XSD type name."""
        return f"{self.name}Type"

    @property
    def elements(self) -> list[BBIE | ASBIE]:
        """Return all child elements (BBIEs and ASBIEs) in order."""
        # In UBL, BBIEs typically come before ASBIEs
        return list(self.bbies) + list(self.asbies)

    def get_required_elements(self) -> list[BBIE | ASBIE]:
        """Return all required child elements."""
        return [el for el in self.elements if el.is_required]

    def get_optional_elements(self) -> list[BBIE | ASBIE]:
        """Return all optional child elements."""
        return [el for el in self.elements if not el.is_required]

    def get_bbie(self, name: str) -> BBIE | None:
        """Find a BBIE by name."""
        for bbie in self.bbies:
            if bbie.name == name:
                return bbie
        return None

    def get_asbie(self, name: str) -> ASBIE | None:
        """Find an ASBIE by name."""
        for asbie in self.asbies:
            if asbie.name == name:
                return asbie
        return None


@dataclass
class CBCElement:
    """
    A CommonBasicComponents element declaration.

    CBC elements are global element declarations that reference data types.
    They provide the actual element names used in documents.

    Attributes:
        name: Element name (e.g., 'ID', 'IssueDate', 'Amount')
        type_name: The associated type name (e.g., 'IDType', 'IssueDateType')
        data_type: Reference to UDT/QDT base type
    """

    name: str
    type_name: str
    data_type: str

    @property
    def id(self) -> str:
        """Return unique identifier."""
        return self.name


@dataclass
class CACElement:
    """
    A CommonAggregateComponents element declaration.

    CAC elements are global element declarations that reference ABIE types.
    A single ABIE type may be used by multiple element names.

    Attributes:
        name: Element name (e.g., 'AccountingSupplierParty', 'BuyerCustomerParty')
        type_name: The associated ABIE type name (e.g., 'SupplierPartyType', 'CustomerPartyType')
    """

    name: str
    type_name: str

    @property
    def id(self) -> str:
        """Return unique identifier."""
        return self.name

    @property
    def abie_name(self) -> str:
        """Return the ABIE name (type name without 'Type' suffix)."""
        if self.type_name.endswith("Type"):
            return self.type_name[:-4]
        return self.type_name
