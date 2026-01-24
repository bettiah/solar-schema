"""
UBL Schema Enumerations.

This module defines enumerations for UBL (Universal Business Language) schema components
based on the UN/CEFACT Core Components Technical Specification (CCTS) and OASIS UBL 2.5.
"""

from enum import Enum


class ComponentType(str, Enum):
    """
    CCTS Component Types.

    UBL uses the Core Components Technical Specification (CCTS) to classify
    its components into three types.
    """

    ABIE = "ABIE"  # Aggregate Business Information Entity - complex container
    BBIE = "BBIE"  # Basic Business Information Entity - leaf data element
    ASBIE = "ASBIE"  # Association Business Information Entity - link to another ABIE

    @property
    def description(self) -> str:
        """Return a human-readable description of the component type."""
        descriptions = {
            "ABIE": "Aggregate Business Information Entity (complex container)",
            "BBIE": "Basic Business Information Entity (leaf data element)",
            "ASBIE": "Association Business Information Entity (reference to ABIE)",
        }
        return descriptions.get(self.value, "Unknown")


class Cardinality(str, Enum):
    """
    Element cardinality constraints.

    Defines how many times an element can appear within its parent.
    """

    ZERO_OR_ONE = "0..1"  # Optional, at most one
    EXACTLY_ONE = "1"  # Required, exactly one
    ZERO_OR_MORE = "0..n"  # Optional, unbounded
    ONE_OR_MORE = "1..n"  # Required, at least one

    @property
    def description(self) -> str:
        """Return a human-readable description of the cardinality."""
        descriptions = {
            "0..1": "Optional (zero or one)",
            "1": "Required (exactly one)",
            "0..n": "Optional (zero or more)",
            "1..n": "Required (one or more)",
        }
        return descriptions.get(self.value, "Unknown")

    @property
    def is_required(self) -> bool:
        """Check if this cardinality indicates a required element."""
        return self.value in ("1", "1..n")

    @property
    def is_multiple(self) -> bool:
        """Check if this cardinality allows multiple occurrences."""
        return self.value in ("0..n", "1..n")

    @property
    def min_occurs(self) -> int:
        """Return the minimum number of occurrences."""
        return 1 if self.is_required else 0

    @property
    def max_occurs(self) -> int | None:
        """Return the maximum number of occurrences (None for unbounded)."""
        if self.is_multiple:
            return None
        return 1

    @classmethod
    def from_min_max(cls, min_occurs: int, max_occurs: int | str | None) -> "Cardinality":
        """
        Create cardinality from XSD minOccurs/maxOccurs values.

        Args:
            min_occurs: Minimum occurrences (0 or 1)
            max_occurs: Maximum occurrences (1, number, or 'unbounded'/None)

        Returns:
            Appropriate Cardinality enum value
        """
        is_required = min_occurs >= 1
        is_unbounded = max_occurs is None or max_occurs == "unbounded" or (
            isinstance(max_occurs, int) and max_occurs > 1
        )

        if is_required and is_unbounded:
            return cls.ONE_OR_MORE
        elif is_required:
            return cls.EXACTLY_ONE
        elif is_unbounded:
            return cls.ZERO_OR_MORE
        else:
            return cls.ZERO_OR_ONE


class RepresentationTerm(str, Enum):
    """
    CCTS Representation Terms.

    Defines the primitive data types used in UBL based on UN/CEFACT CCTS.
    Each representation term maps to a specific XSD type pattern.
    """

    # Primary representation terms
    AMOUNT = "Amount"  # Monetary value with currency
    BINARY_OBJECT = "Binary Object"  # Binary data (base64)
    CODE = "Code"  # Coded value from a list
    DATE = "Date"  # Calendar date (YYYY-MM-DD)
    DATE_TIME = "Date Time"  # Date and time combined
    GRAPHIC = "Graphic"  # Graphical binary data
    IDENTIFIER = "Identifier"  # Unique identifier
    INDICATOR = "Indicator"  # Boolean true/false
    MEASURE = "Measure"  # Numeric with unit of measure
    NAME = "Name"  # Textual name
    NUMERIC = "Numeric"  # Plain number
    PERCENT = "Percent"  # Percentage value
    PICTURE = "Picture"  # Picture binary data
    QUANTITY = "Quantity"  # Counted quantity with unit
    RATE = "Rate"  # Rate value
    SOUND = "Sound"  # Audio binary data
    TEXT = "Text"  # Free-form text
    TIME = "Time"  # Time of day (HH:MM:SS)
    VALUE = "Value"  # Numeric value
    VIDEO = "Video"  # Video binary data

    @property
    def description(self) -> str:
        """Return a human-readable description of the representation term."""
        descriptions = {
            "Amount": "Monetary value with currency code",
            "Binary Object": "Binary data (base64 encoded)",
            "Code": "Coded value from a controlled vocabulary",
            "Date": "Calendar date (ISO 8601)",
            "Date Time": "Date and time (ISO 8601)",
            "Graphic": "Graphical image data",
            "Identifier": "Unique identifier string",
            "Indicator": "Boolean indicator (true/false)",
            "Measure": "Numeric value with unit of measure",
            "Name": "Textual name",
            "Numeric": "Plain numeric value",
            "Percent": "Percentage value",
            "Picture": "Picture/image data",
            "Quantity": "Counted quantity with unit",
            "Rate": "Rate or ratio value",
            "Sound": "Audio data",
            "Text": "Free-form text",
            "Time": "Time of day (ISO 8601)",
            "Value": "Numeric value",
            "Video": "Video data",
        }
        return descriptions.get(self.value, "Unknown")

    @property
    def xsd_base_type(self) -> str:
        """Return the corresponding XSD base type."""
        xsd_types = {
            "Amount": "xsd:decimal",
            "Binary Object": "xsd:base64Binary",
            "Code": "xsd:normalizedString",
            "Date": "xsd:date",
            "Date Time": "xsd:dateTime",
            "Graphic": "xsd:base64Binary",
            "Identifier": "xsd:normalizedString",
            "Indicator": "xsd:boolean",
            "Measure": "xsd:decimal",
            "Name": "xsd:string",
            "Numeric": "xsd:decimal",
            "Percent": "xsd:decimal",
            "Picture": "xsd:base64Binary",
            "Quantity": "xsd:decimal",
            "Rate": "xsd:decimal",
            "Sound": "xsd:base64Binary",
            "Text": "xsd:string",
            "Time": "xsd:time",
            "Value": "xsd:decimal",
            "Video": "xsd:base64Binary",
        }
        return xsd_types.get(self.value, "xsd:string")

    @property
    def is_binary(self) -> bool:
        """Check if this is a binary type."""
        return self.value in ("Binary Object", "Graphic", "Picture", "Sound", "Video")

    @property
    def is_numeric(self) -> bool:
        """Check if this is a numeric type."""
        return self.value in ("Amount", "Measure", "Numeric", "Percent", "Quantity", "Rate", "Value")

    @property
    def is_temporal(self) -> bool:
        """Check if this is a date/time type."""
        return self.value in ("Date", "Date Time", "Time")


class Namespace(str, Enum):
    """
    UBL 2.5 XML Namespaces.

    Standard namespace URIs used in UBL documents.
    """

    # UBL component namespaces
    CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
    EXT = "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
    SIG = "urn:oasis:names:specification:ubl:schema:xsd:CommonSignatureComponents-2"
    SAC = "urn:oasis:names:specification:ubl:schema:xsd:SignatureAggregateComponents-2"
    SBC = "urn:oasis:names:specification:ubl:schema:xsd:SignatureBasicComponents-2"

    # Data type namespaces
    QDT = "urn:oasis:names:specification:ubl:schema:xsd:QualifiedDataTypes-2"
    UDT = "urn:oasis:names:specification:bdndr:schema:xsd:UnqualifiedDataTypes-1"
    CCT = "urn:un:unece:uncefact:data:specification:CoreComponentTypeSchemaModule:2"

    # Documentation namespace
    CCTS = "urn:un:unece:uncefact:documentation:2"

    # XML Schema namespace
    XSD = "http://www.w3.org/2001/XMLSchema"

    @property
    def prefix(self) -> str:
        """Return the standard prefix for this namespace."""
        prefixes = {
            "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2": "cac",
            "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2": "cbc",
            "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2": "ext",
            "urn:oasis:names:specification:ubl:schema:xsd:CommonSignatureComponents-2": "sig",
            "urn:oasis:names:specification:ubl:schema:xsd:SignatureAggregateComponents-2": "sac",
            "urn:oasis:names:specification:ubl:schema:xsd:SignatureBasicComponents-2": "sbc",
            "urn:oasis:names:specification:ubl:schema:xsd:QualifiedDataTypes-2": "qdt",
            "urn:oasis:names:specification:bdndr:schema:xsd:UnqualifiedDataTypes-1": "udt",
            "urn:un:unece:uncefact:data:specification:CoreComponentTypeSchemaModule:2": "ccts-cct",
            "urn:un:unece:uncefact:documentation:2": "ccts",
            "http://www.w3.org/2001/XMLSchema": "xsd",
        }
        return prefixes.get(self.value, "")

    @classmethod
    def from_prefix(cls, prefix: str) -> "Namespace | None":
        """Look up namespace by prefix."""
        for ns in cls:
            if ns.prefix == prefix:
                return ns
        return None

    @classmethod
    def document_namespace(cls, document_type: str) -> str:
        """Generate namespace URI for a document type."""
        return f"urn:oasis:names:specification:ubl:schema:xsd:{document_type}-2"


# Standard namespace prefix map for XML serialization
NAMESPACE_PREFIXES: dict[str, str] = {
    Namespace.CAC.value: "cac",
    Namespace.CBC.value: "cbc",
    Namespace.EXT.value: "ext",
    Namespace.SIG.value: "sig",
    Namespace.SAC.value: "sac",
    Namespace.SBC.value: "sbc",
    Namespace.QDT.value: "qdt",
    Namespace.UDT.value: "udt",
    Namespace.CCT.value: "ccts-cct",
    Namespace.CCTS.value: "ccts",
    Namespace.XSD.value: "xsd",
}
