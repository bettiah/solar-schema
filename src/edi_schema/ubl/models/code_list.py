"""
UBL Code List Models.

Defines code list structures for controlled vocabularies used in UBL.
Code lists are stored in Genericode (.gc) format.
"""

from dataclasses import dataclass, field


@dataclass
class CodeValue:
    """
    A single code value in a code list.

    Attributes:
        code: The code value (e.g., 'USD', 'US', 'EA')
        name: Human-readable name (e.g., 'US Dollar', 'United States')
        description: Extended description (optional)
        metadata: Additional columns from the code list
    """

    code: str
    name: str
    description: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class CodeListColumn:
    """
    A column definition in a Genericode code list.

    Attributes:
        id: Column identifier (e.g., 'code', 'name')
        short_name: Display name
        data_type: XSD data type
        required: Whether this column is required for each row
        lang: Language code if applicable
    """

    id: str
    short_name: str
    data_type: str = "string"
    required: bool = False
    lang: str | None = None


@dataclass
class CodeList:
    """
    A controlled vocabulary (code list) from Genericode.

    Represents a complete code list with metadata and values.
    Used for validation of coded elements in UBL documents.

    Attributes:
        id: Unique identifier (e.g., 'CurrencyCode-2.4')
        short_name: Short name (e.g., 'CurrencyCode')
        long_name: Full name (e.g., 'Currency Code')
        version: Version identifier
        canonical_uri: Canonical URI for the code list
        agency_name: Maintaining agency (e.g., 'ISO', 'UNECE')
        agency_id: Agency identifier
        columns: Column definitions
        values: List of code values
    """

    id: str
    short_name: str
    long_name: str = ""
    version: str = ""
    canonical_uri: str = ""
    agency_name: str = ""
    agency_id: str = ""
    columns: list[CodeListColumn] = field(default_factory=list)
    values: list[CodeValue] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Build code lookup index."""
        self._code_index: dict[str, CodeValue] = {}
        for value in self.values:
            # Store first occurrence of each code
            if value.code not in self._code_index:
                self._code_index[value.code] = value

    def contains(self, code: str) -> bool:
        """Check if a code exists in this list."""
        return code in self._code_index

    def get(self, code: str) -> CodeValue | None:
        """Look up a code value."""
        return self._code_index.get(code)

    def get_name(self, code: str) -> str | None:
        """Look up the name for a code."""
        value = self._code_index.get(code)
        return value.name if value else None

    @property
    def codes(self) -> list[str]:
        """Return all unique code values."""
        return list(self._code_index.keys())

    def validate(self, code: str) -> bool:
        """
        Validate that a code exists in this list.

        Args:
            code: The code value to validate

        Returns:
            True if valid, False otherwise
        """
        return self.contains(code)


# Standard UBL 2.5 code lists
STANDARD_CODE_LISTS: dict[str, str] = {
    "CurrencyCode": "CurrencyCode-2.4.gc",
    "CountryIdentificationCode": "CountryIdentificationCode-2.4.gc",
    "LanguageCode": "LanguageCode-2.4.gc",
    "UnitOfMeasureCode": "UnitOfMeasureCode-2.4.gc",
    "PaymentMeansCode": "PaymentMeansCode-2.4.gc",
    "TransportModeCode": "TransportModeCode-2.4.gc",
    "AllowanceChargeReasonCode": "AllowanceChargeReasonCode-2.4.gc",
    "PackagingTypeCode": "PackagingTypeCode-2.4.gc",
    "ChannelCode": "ChannelCode-2.4.gc",
    "TransportEquipmentTypeCode": "TransportEquipmentTypeCode-2.4.gc",
    "BinaryObjectMimeCode": "BinaryObjectMimeCode-2.4.gc",
    "HandlingCode": "HandlingCode-2.4.gc",
    "PortCode": "PortCode-2.4.gc",
    "LocationTypeCode": "LocationTypeCode-2.4.gc",
}
