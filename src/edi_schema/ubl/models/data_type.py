"""
UBL Data Type Models.

Defines the CCTS-based data type hierarchy used in UBL:
- Unqualified Data Types (UDT) - base CCTS types
- Qualified Data Types (QDT) - constrained/restricted types
- Attributes for data types (currencyID, unitCode, etc.)
"""

from dataclasses import dataclass, field


@dataclass
class Attribute:
    """
    An attribute on a data type.

    UBL data types often have supplementary attributes that provide
    context (e.g., currencyID on Amount, unitCode on Measure).

    Attributes:
        name: Attribute name (e.g., 'currencyID', 'unitCode')
        xsd_type: XSD type (e.g., 'xsd:normalizedString', 'xsd:anyURI')
        required: Whether this attribute is required
        definition: Human-readable description
        deprecated: Whether this attribute is deprecated
    """

    name: str
    xsd_type: str
    required: bool = False
    definition: str = ""
    deprecated: bool = False


@dataclass
class UnqualifiedDataType:
    """
    A CCTS Unqualified Data Type (UDT).

    These are the base data types defined in BDNDR-UnqualifiedDataTypes-1.1.xsd.
    They correspond to CCTS Core Component Types.

    Attributes:
        name: Type name without 'Type' suffix (e.g., 'Amount', 'Code', 'Date')
        definition: Human-readable description
        representation_term: CCTS representation term
        primitive_type: Underlying XSD primitive type
        xsd_base: XSD base type or restriction base
        attributes: Supplementary component attributes
    """

    name: str
    definition: str
    representation_term: str
    primitive_type: str
    xsd_base: str
    attributes: list[Attribute] = field(default_factory=list)

    @property
    def id(self) -> str:
        """Return the type identifier."""
        return self.name

    @property
    def type_name(self) -> str:
        """Return the full type name with 'Type' suffix."""
        return f"{self.name}Type"

    def get_required_attributes(self) -> list[Attribute]:
        """Return list of required attributes."""
        return [attr for attr in self.attributes if attr.required]

    def get_optional_attributes(self) -> list[Attribute]:
        """Return list of optional attributes."""
        return [attr for attr in self.attributes if not attr.required]


@dataclass
class QualifiedDataType:
    """
    A UBL Qualified Data Type (QDT).

    These are constrained versions of UDTs defined in UBL-QualifiedDataTypes-2.5.xsd.
    They typically restrict the base type to specific code lists.

    Attributes:
        name: Type name without 'Type' suffix (e.g., 'CurrencyCode', 'CountryIdentificationCode')
        base_type: Reference to base UDT name (e.g., 'Code')
        code_list_id: Associated code list identifier (if applicable)
        definition: Human-readable description (optional)
    """

    name: str
    base_type: str
    code_list_id: str | None = None
    definition: str = ""

    @property
    def id(self) -> str:
        """Return the type identifier."""
        return self.name

    @property
    def type_name(self) -> str:
        """Return the full type name with 'Type' suffix."""
        return f"{self.name}Type"


# Standard UBL 2.5 Unqualified Data Types
STANDARD_UDT_TYPES: list[str] = [
    "Amount",
    "BinaryObject",
    "Code",
    "Date",
    "DateTime",
    "Graphic",
    "Identifier",
    "Indicator",
    "Measure",
    "Name",
    "Numeric",
    "Percent",
    "Picture",
    "Quantity",
    "Rate",
    "Sound",
    "Text",
    "Time",
    "Value",
    "Video",
]

# Standard UBL 2.5 Qualified Data Types
STANDARD_QDT_TYPES: list[str] = [
    "AllowanceChargeReasonCode",
    "ChannelCode",
    "ChipCode",
    "CountryIdentificationCode",
    "CurrencyCode",
    "DocumentStatusCode",
    "LanguageCode",
    "LatitudeDirectionCode",
    "LineStatusCode",
    "LongitudeDirectionCode",
    "OperatorCode",
    "PackagingTypeCode",
    "PaymentMeansCode",
    "ReceiptAdviceTypeCode",
    "SubstitutionStatusCode",
    "TransportEquipmentTypeCode",
    "TransportModeCode",
    "UnitOfMeasureCode",
    "WeekDayCode",
    "WeighingMethodCode",
]
