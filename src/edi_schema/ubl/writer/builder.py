"""
UBL Document Builder.

Provides a fluent interface for constructing UBL documents.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Self

from ..ast import ParsedAttribute, ParsedDocument, ParsedElement
from ..enums import Namespace


@dataclass
class ElementBuilder:
    """
    Builder for a single XML element.

    Supports fluent API for adding children, attributes, and values.
    """

    tag: str
    namespace: str = ""
    value: str | None = None
    attributes: list[ParsedAttribute] = field(default_factory=list)
    children: list["ElementBuilder"] = field(default_factory=list)

    def set_value(self, value: str | None) -> Self:
        """Set the text value of this element."""
        self.value = value
        return self

    def add_attribute(
        self,
        name: str,
        value: str,
        namespace: str | None = None,
    ) -> Self:
        """Add an attribute to this element."""
        self.attributes.append(ParsedAttribute(
            name=name,
            value=value,
            namespace=namespace,
        ))
        return self

    def add_child(self, child: "ElementBuilder") -> Self:
        """Add a child element."""
        self.children.append(child)
        return self

    def add_element(
        self,
        tag: str,
        value: str | None = None,
        namespace: str = "",
        **attrs,
    ) -> Self:
        """
        Add a simple child element.

        Args:
            tag: Element tag name
            value: Text value (optional)
            namespace: Namespace URI (optional)
            **attrs: Additional attributes

        Returns:
            Self for chaining
        """
        child = ElementBuilder(tag=tag, namespace=namespace, value=value)
        for name, attr_value in attrs.items():
            child.add_attribute(name, str(attr_value))
        self.children.append(child)
        return self

    def with_child(
        self,
        tag: str,
        configure: Callable[["ElementBuilder"], None],
        namespace: str = "",
    ) -> Self:
        """
        Add a child element with configuration callback.

        Args:
            tag: Element tag name
            configure: Function to configure the child builder
            namespace: Namespace URI (optional)

        Returns:
            Self for chaining
        """
        child = ElementBuilder(tag=tag, namespace=namespace)
        configure(child)
        self.children.append(child)
        return self

    def build(self) -> ParsedElement:
        """Build the ParsedElement tree."""
        return ParsedElement(
            tag=self.tag,
            namespace=self.namespace,
            value=self.value,
            attributes=list(self.attributes),
            children=[child.build() for child in self.children],
        )


class DocumentBuilder:
    """
    Builder for UBL documents.

    Provides high-level methods for common document structures.

    Usage:
        doc = (
            DocumentBuilder("Invoice")
            .id("INV-001")
            .issue_date("2024-01-15")
            .supplier_party(lambda p: p.name("Supplier Corp"))
            .build()
        )
    """

    def __init__(
        self,
        document_type: str,
        version: str = "2.5",
    ):
        """
        Initialize the document builder.

        Args:
            document_type: Document type name (e.g., 'Invoice')
            version: UBL version
        """
        self.document_type = document_type
        self.version = version
        self.namespace = Namespace.document_namespace(document_type)

        self._root = ElementBuilder(
            tag=document_type,
            namespace=self.namespace,
        )
        self._namespaces: dict[str, str] = {
            "": self.namespace,
            "cac": Namespace.CAC.value,
            "cbc": Namespace.CBC.value,
            "ext": Namespace.EXT.value,
        }

    def add_namespace(self, prefix: str, uri: str) -> Self:
        """Add a namespace to the document."""
        self._namespaces[prefix] = uri
        return self

    # Common CBC elements

    def ubl_version_id(self, value: str = "2.5") -> Self:
        """Set UBLVersionID."""
        self._add_cbc("UBLVersionID", value)
        return self

    def customization_id(self, value: str) -> Self:
        """Set CustomizationID."""
        self._add_cbc("CustomizationID", value)
        return self

    def profile_id(self, value: str) -> Self:
        """Set ProfileID."""
        self._add_cbc("ProfileID", value)
        return self

    def id(self, value: str, **attrs) -> Self:
        """Set document ID."""
        self._add_cbc("ID", value, **attrs)
        return self

    def copy_indicator(self, value: bool) -> Self:
        """Set CopyIndicator."""
        self._add_cbc("CopyIndicator", "true" if value else "false")
        return self

    def uuid(self, value: str) -> Self:
        """Set UUID."""
        self._add_cbc("UUID", value)
        return self

    def issue_date(self, value: str) -> Self:
        """Set IssueDate (YYYY-MM-DD format)."""
        self._add_cbc("IssueDate", value)
        return self

    def issue_time(self, value: str) -> Self:
        """Set IssueTime (HH:MM:SS format)."""
        self._add_cbc("IssueTime", value)
        return self

    def due_date(self, value: str) -> Self:
        """Set DueDate."""
        self._add_cbc("DueDate", value)
        return self

    def note(self, value: str, language_id: str | None = None) -> Self:
        """Add a Note element."""
        attrs = {}
        if language_id:
            attrs["languageID"] = language_id
        self._add_cbc("Note", value, **attrs)
        return self

    def document_currency_code(self, value: str) -> Self:
        """Set DocumentCurrencyCode."""
        self._add_cbc("DocumentCurrencyCode", value)
        return self

    def tax_currency_code(self, value: str) -> Self:
        """Set TaxCurrencyCode."""
        self._add_cbc("TaxCurrencyCode", value)
        return self

    # Common CAC elements

    def accounting_supplier_party(
        self,
        configure: Callable[[ElementBuilder], None],
    ) -> Self:
        """Add AccountingSupplierParty."""
        self._add_cac("AccountingSupplierParty", configure)
        return self

    def accounting_customer_party(
        self,
        configure: Callable[[ElementBuilder], None],
    ) -> Self:
        """Add AccountingCustomerParty."""
        self._add_cac("AccountingCustomerParty", configure)
        return self

    def supplier_party(
        self,
        configure: Callable[[ElementBuilder], None],
    ) -> Self:
        """Add SupplierParty (alias for AccountingSupplierParty)."""
        return self.accounting_supplier_party(configure)

    def customer_party(
        self,
        configure: Callable[[ElementBuilder], None],
    ) -> Self:
        """Add CustomerParty (alias for AccountingCustomerParty)."""
        return self.accounting_customer_party(configure)

    def buyer_customer_party(
        self,
        configure: Callable[[ElementBuilder], None],
    ) -> Self:
        """Add BuyerCustomerParty."""
        self._add_cac("BuyerCustomerParty", configure)
        return self

    def seller_supplier_party(
        self,
        configure: Callable[[ElementBuilder], None],
    ) -> Self:
        """Add SellerSupplierParty."""
        self._add_cac("SellerSupplierParty", configure)
        return self

    def delivery(
        self,
        configure: Callable[[ElementBuilder], None],
    ) -> Self:
        """Add Delivery."""
        self._add_cac("Delivery", configure)
        return self

    def payment_means(
        self,
        configure: Callable[[ElementBuilder], None],
    ) -> Self:
        """Add PaymentMeans."""
        self._add_cac("PaymentMeans", configure)
        return self

    def payment_terms(
        self,
        configure: Callable[[ElementBuilder], None],
    ) -> Self:
        """Add PaymentTerms."""
        self._add_cac("PaymentTerms", configure)
        return self

    def allowance_charge(
        self,
        configure: Callable[[ElementBuilder], None],
    ) -> Self:
        """Add AllowanceCharge."""
        self._add_cac("AllowanceCharge", configure)
        return self

    def tax_total(
        self,
        configure: Callable[[ElementBuilder], None],
    ) -> Self:
        """Add TaxTotal."""
        self._add_cac("TaxTotal", configure)
        return self

    def legal_monetary_total(
        self,
        configure: Callable[[ElementBuilder], None],
    ) -> Self:
        """Add LegalMonetaryTotal."""
        self._add_cac("LegalMonetaryTotal", configure)
        return self

    def invoice_line(
        self,
        configure: Callable[[ElementBuilder], None],
    ) -> Self:
        """Add InvoiceLine."""
        self._add_cac("InvoiceLine", configure)
        return self

    def credit_note_line(
        self,
        configure: Callable[[ElementBuilder], None],
    ) -> Self:
        """Add CreditNoteLine."""
        self._add_cac("CreditNoteLine", configure)
        return self

    def order_line(
        self,
        configure: Callable[[ElementBuilder], None],
    ) -> Self:
        """Add OrderLine."""
        self._add_cac("OrderLine", configure)
        return self

    def despatch_line(
        self,
        configure: Callable[[ElementBuilder], None],
    ) -> Self:
        """Add DespatchLine."""
        self._add_cac("DespatchLine", configure)
        return self

    def receipt_line(
        self,
        configure: Callable[[ElementBuilder], None],
    ) -> Self:
        """Add ReceiptLine."""
        self._add_cac("ReceiptLine", configure)
        return self

    # Generic methods

    def add_cbc(self, tag: str, value: str, **attrs) -> Self:
        """Add a CBC (basic) element."""
        self._add_cbc(tag, value, **attrs)
        return self

    def add_cac(
        self,
        tag: str,
        configure: Callable[[ElementBuilder], None],
    ) -> Self:
        """Add a CAC (aggregate) element."""
        self._add_cac(tag, configure)
        return self

    def add_raw(self, element: ElementBuilder) -> Self:
        """Add a raw element builder."""
        self._root.add_child(element)
        return self

    # Build methods

    def build(self) -> ParsedDocument:
        """
        Build the document.

        Returns:
            ParsedDocument ready for serialization
        """
        root = self._root.build()
        return ParsedDocument(
            document_type=self.document_type,
            version=self.version,
            root=root,
            namespaces=self._namespaces,
        )

    def build_element(self) -> ParsedElement:
        """Build just the root element."""
        return self._root.build()

    # Internal helpers

    def _add_cbc(self, tag: str, value: str, **attrs) -> None:
        """Add a CBC element."""
        elem = ElementBuilder(
            tag=tag,
            namespace=Namespace.CBC.value,
            value=value,
        )
        for name, attr_value in attrs.items():
            elem.add_attribute(name, str(attr_value))
        self._root.add_child(elem)

    def _add_cac(
        self,
        tag: str,
        configure: Callable[[ElementBuilder], None],
    ) -> None:
        """Add a CAC element."""
        elem = ElementBuilder(
            tag=tag,
            namespace=Namespace.CAC.value,
        )
        configure(elem)
        self._root.add_child(elem)


class PartyBuilder:
    """
    Builder for Party structures.

    Helper for building common party elements.
    """

    def __init__(self, parent: ElementBuilder):
        """Initialize with parent element."""
        self.parent = parent
        self._party = ElementBuilder(tag="Party", namespace=Namespace.CAC.value)
        parent.add_child(self._party)

    def endpoint_id(self, value: str, scheme_id: str | None = None) -> Self:
        """Set EndpointID."""
        elem = ElementBuilder(
            tag="EndpointID",
            namespace=Namespace.CBC.value,
            value=value,
        )
        if scheme_id:
            elem.add_attribute("schemeID", scheme_id)
        self._party.add_child(elem)
        return self

    def party_identification(self, value: str, scheme_id: str | None = None) -> Self:
        """Add PartyIdentification."""
        ident = ElementBuilder(tag="PartyIdentification", namespace=Namespace.CAC.value)
        id_elem = ElementBuilder(
            tag="ID",
            namespace=Namespace.CBC.value,
            value=value,
        )
        if scheme_id:
            id_elem.add_attribute("schemeID", scheme_id)
        ident.add_child(id_elem)
        self._party.add_child(ident)
        return self

    def name(self, value: str) -> Self:
        """Set PartyName/Name."""
        party_name = ElementBuilder(tag="PartyName", namespace=Namespace.CAC.value)
        party_name.add_element("Name", value, namespace=Namespace.CBC.value)
        self._party.add_child(party_name)
        return self

    def postal_address(
        self,
        street: str | None = None,
        city: str | None = None,
        postal_zone: str | None = None,
        country: str | None = None,
    ) -> Self:
        """Set PostalAddress."""
        address = ElementBuilder(tag="PostalAddress", namespace=Namespace.CAC.value)
        if street:
            address.add_element("StreetName", street, namespace=Namespace.CBC.value)
        if city:
            address.add_element("CityName", city, namespace=Namespace.CBC.value)
        if postal_zone:
            address.add_element("PostalZone", postal_zone, namespace=Namespace.CBC.value)
        if country:
            country_elem = ElementBuilder(tag="Country", namespace=Namespace.CAC.value)
            country_elem.add_element("IdentificationCode", country, namespace=Namespace.CBC.value)
            address.add_child(country_elem)
        self._party.add_child(address)
        return self

    def tax_scheme(self, company_id: str, scheme_id: str = "VAT") -> Self:
        """Set PartyTaxScheme."""
        tax = ElementBuilder(tag="PartyTaxScheme", namespace=Namespace.CAC.value)
        tax.add_element("CompanyID", company_id, namespace=Namespace.CBC.value)
        tax_scheme = ElementBuilder(tag="TaxScheme", namespace=Namespace.CAC.value)
        tax_scheme.add_element("ID", scheme_id, namespace=Namespace.CBC.value)
        tax.add_child(tax_scheme)
        self._party.add_child(tax)
        return self

    def legal_entity(self, registration_name: str, company_id: str | None = None) -> Self:
        """Set PartyLegalEntity."""
        legal = ElementBuilder(tag="PartyLegalEntity", namespace=Namespace.CAC.value)
        legal.add_element("RegistrationName", registration_name, namespace=Namespace.CBC.value)
        if company_id:
            legal.add_element("CompanyID", company_id, namespace=Namespace.CBC.value)
        self._party.add_child(legal)
        return self

    def contact(
        self,
        name: str | None = None,
        phone: str | None = None,
        email: str | None = None,
    ) -> Self:
        """Set Contact."""
        contact = ElementBuilder(tag="Contact", namespace=Namespace.CAC.value)
        if name:
            contact.add_element("Name", name, namespace=Namespace.CBC.value)
        if phone:
            contact.add_element("Telephone", phone, namespace=Namespace.CBC.value)
        if email:
            contact.add_element("ElectronicMail", email, namespace=Namespace.CBC.value)
        self._party.add_child(contact)
        return self


def party(parent: ElementBuilder) -> PartyBuilder:
    """Create a PartyBuilder for the parent element."""
    return PartyBuilder(parent)
