"""
Semantic Party Models.

Business party representations (buyer, seller, carrier, etc.) with
address and contact information.
"""

from pydantic import Field

from .base import SemanticModel
from .primitives import Identifier


class Address(SemanticModel):
    """
    Physical or postal address.

    Maps to:
    - UBL: cac:PostalAddress, cac:DeliveryAddress
    - X12: N3/N4 segments
    - EDIFACT: NAD segment address components
    """

    # Street address
    street_name: str | None = Field(
        default=None,
        description="Primary street address line",
    )
    additional_street_name: str | None = Field(
        default=None,
        description="Secondary street address line",
    )
    building_name: str | None = Field(
        default=None,
        description="Building or structure name",
    )
    building_number: str | None = Field(
        default=None,
        description="Building or house number",
    )
    department: str | None = Field(
        default=None,
        description="Department within organization",
    )
    floor: str | None = Field(
        default=None,
        description="Floor or level",
    )
    room: str | None = Field(
        default=None,
        description="Room or suite number",
    )

    # City/region
    city_name: str | None = Field(
        default=None,
        description="City or municipality name",
    )
    city_subdivision_name: str | None = Field(
        default=None,
        description="District or borough within city",
    )
    postal_zone: str | None = Field(
        default=None,
        description="Postal/ZIP code",
    )
    country_subentity: str | None = Field(
        default=None,
        description="State, province, or region",
    )
    country_subentity_code: str | None = Field(
        default=None,
        description="State/province code",
    )
    region: str | None = Field(
        default=None,
        description="Geographic region",
    )

    # Country
    country_code: str | None = Field(
        default=None,
        pattern=r"^[A-Z]{2}$",
        description="ISO 3166-1 alpha-2 country code",
    )
    country_name: str | None = Field(
        default=None,
        description="Country name",
    )

    # Address line format (alternative to structured)
    address_lines: list[str] = Field(
        default_factory=list,
        description="Unstructured address lines",
    )

    def __str__(self) -> str:
        parts = []
        if self.street_name:
            parts.append(self.street_name)
        if self.city_name:
            parts.append(self.city_name)
        if self.country_subentity:
            parts.append(self.country_subentity)
        if self.postal_zone:
            parts.append(self.postal_zone)
        if self.country_code:
            parts.append(self.country_code)
        return ", ".join(parts) if parts else "unspecified address"


class Contact(SemanticModel):
    """
    Contact information for a party.

    Maps to:
    - UBL: cac:Contact
    - X12: PER segment
    - EDIFACT: CTA/COM segments
    """

    id: str | None = Field(
        default=None,
        description="Contact identifier",
    )
    name: str | None = Field(
        default=None,
        description="Contact person name",
    )
    telephone: str | None = Field(
        default=None,
        description="Telephone number",
    )
    telefax: str | None = Field(
        default=None,
        description="Fax number",
    )
    electronic_mail: str | None = Field(
        default=None,
        description="Email address",
    )
    note: str | None = Field(
        default=None,
        description="Additional contact notes",
    )

    def __str__(self) -> str:
        if self.name:
            return self.name
        if self.electronic_mail:
            return self.electronic_mail
        return "unspecified contact"


class PartyIdentification(SemanticModel):
    """
    Party identifier (DUNS, GLN, tax ID, etc.).

    Maps to:
    - UBL: cac:PartyIdentification
    - X12: N1*03/04 (ID qualifier and value)
    - EDIFACT: NAD+*+identifier
    """

    id: Identifier = Field(description="The identifier")

    def __str__(self) -> str:
        return str(self.id)


class PartyName(SemanticModel):
    """
    Party name.

    Maps to:
    - UBL: cac:PartyName
    - X12: N1*02, N2
    - EDIFACT: NAD party name
    """

    name: str = Field(description="The party name")

    def __str__(self) -> str:
        return self.name


class PartyLegalEntity(SemanticModel):
    """
    Legal entity information for a party.

    Maps to:
    - UBL: cac:PartyLegalEntity
    - X12: Various reference segments
    - EDIFACT: RFF segments with legal IDs
    """

    registration_name: str | None = Field(
        default=None,
        description="Registered legal name",
    )
    company_id: Identifier | None = Field(
        default=None,
        description="Company registration number",
    )
    registration_date: str | None = Field(
        default=None,
        description="Date of registration",
    )
    registration_address: Address | None = Field(
        default=None,
        description="Registered address",
    )


class PartyTaxScheme(SemanticModel):
    """
    Tax registration information for a party.

    Maps to:
    - UBL: cac:PartyTaxScheme
    - X12: REF segment with tax ID qualifier
    - EDIFACT: RFF+VA (VAT number)
    """

    registration_name: str | None = Field(
        default=None,
        description="Name registered for tax purposes",
    )
    company_id: str | None = Field(
        default=None,
        description="Tax registration number (e.g., VAT ID)",
    )
    tax_scheme_id: str | None = Field(
        default=None,
        description="Tax scheme identifier (e.g., VAT, GST)",
    )


class Party(SemanticModel):
    """
    Business party (buyer, seller, carrier, etc.).

    Central entity representing any business party involved in
    a transaction.

    Maps to:
    - UBL: cac:Party
    - X12: N1 loop (N1, N2, N3, N4, PER)
    - EDIFACT: NAD segment group
    """

    # Identifiers
    party_identifications: list[PartyIdentification] = Field(
        default_factory=list,
        description="Party identifiers (DUNS, GLN, etc.)",
    )

    # Names
    party_names: list[PartyName] = Field(
        default_factory=list,
        description="Party names",
    )

    # Address
    postal_address: Address | None = Field(
        default=None,
        description="Postal/mailing address",
    )
    physical_location: Address | None = Field(
        default=None,
        description="Physical location address",
    )

    # Contact
    contact: Contact | None = Field(
        default=None,
        description="Primary contact",
    )

    # Legal and tax
    party_legal_entity: PartyLegalEntity | None = Field(
        default=None,
        description="Legal entity information",
    )
    party_tax_schemes: list[PartyTaxScheme] = Field(
        default_factory=list,
        description="Tax registration information",
    )

    # Additional info
    endpoint_id: Identifier | None = Field(
        default=None,
        description="Electronic endpoint identifier",
    )
    industry_classification_code: str | None = Field(
        default=None,
        description="Industry classification (SIC, NAICS)",
    )

    @property
    def primary_name(self) -> str | None:
        """Get the first party name."""
        return self.party_names[0].name if self.party_names else None

    @property
    def primary_id(self) -> Identifier | None:
        """Get the first party identifier."""
        return self.party_identifications[0].id if self.party_identifications else None

    def __str__(self) -> str:
        return self.primary_name or "unnamed party"


class CustomerParty(SemanticModel):
    """
    Customer party wrapper with role-specific contacts.

    Maps to:
    - UBL: cac:BuyerCustomerParty, cac:AccountingCustomerParty
    - X12: N1 loop with BY/BT qualifier
    - EDIFACT: NAD+BY
    """

    party: Party = Field(description="The party details")
    buyer_contact: Contact | None = Field(
        default=None,
        description="Buyer/purchasing contact",
    )
    delivery_contact: Contact | None = Field(
        default=None,
        description="Delivery contact",
    )
    accounting_contact: Contact | None = Field(
        default=None,
        description="Accounts payable contact",
    )
    customer_assigned_account_id: str | None = Field(
        default=None,
        description="Customer's account ID for this party",
    )
    supplier_assigned_account_id: str | None = Field(
        default=None,
        description="Supplier's account ID for this party",
    )

    def __str__(self) -> str:
        return str(self.party)


class SupplierParty(SemanticModel):
    """
    Supplier party wrapper with role-specific contacts.

    Maps to:
    - UBL: cac:SellerSupplierParty, cac:AccountingSupplierParty
    - X12: N1 loop with SE/VN qualifier
    - EDIFACT: NAD+SU
    """

    party: Party = Field(description="The party details")
    seller_contact: Contact | None = Field(
        default=None,
        description="Sales contact",
    )
    shipping_contact: Contact | None = Field(
        default=None,
        description="Shipping contact",
    )
    accounting_contact: Contact | None = Field(
        default=None,
        description="Accounts receivable contact",
    )
    customer_assigned_account_id: str | None = Field(
        default=None,
        description="Customer's account ID for this supplier",
    )

    def __str__(self) -> str:
        return str(self.party)
