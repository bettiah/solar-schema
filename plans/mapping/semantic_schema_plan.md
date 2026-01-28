# Semantic Pydantic Schemas for Cross-Format Translation

## Executive Summary

Build a canonical semantic business model layer using Pydantic that enables bidirectional translation between X12 ↔ UBL ↔ EDIFACT formats. The approach uses UBL's CCTS-based component library as the semantic foundation, since it's the most richly typed and has explicit business definitions.

---

## Why This Is Feasible

### 1. Conceptual Alignment Already Exists

The three formats represent the same business concepts:

| Business Concept | X12 | UBL | EDIFACT |
|------------------|-----|-----|---------|
| Purchase Order | 850 | Order | ORDERS |
| Order Response | 855 | OrderResponse | ORDRSP |
| Ship Notice | 856 | DespatchAdvice | DESADV |
| Invoice | 810 | Invoice | INVOIC |
| Credit Memo | 812 | CreditNote | CREMUL |
| Remittance | 820 | RemittanceAdvice | REMADV |
| Acknowledgment | 997 | ApplicationResponse | CONTRL |

### 2. UBL's CCTS Model Is The Natural Canonical Form

UBL is built on UN/CEFACT CCTS (Core Component Technical Specification), which provides:
- **200+ reusable ABIEs** (Party, Address, Item, Price, TaxTotal, etc.)
- **Semantic definitions** for each component
- **14 code lists** aligned with ISO/UN standards
- **Clear cardinality** (0..1, 1, 0..n, 1..n)

X12 and EDIFACT segments can be decomposed into these same semantic concepts.

### 3. Existing Mappings Prove The Path

The `x12_ubl_mapping.md` documents field-level mappings for 850/856/810, demonstrating that:
- ~80% of fields have direct equivalents
- Remaining ~20% require transformation rules or are optional
- Structural differences (HL hierarchy vs nested ABIEs) are addressable

---

## Architecture

```
                    ┌─────────────────────────────────────┐
                    │     Semantic Business Models        │
                    │        (Pydantic + CCTS)            │
                    │                                     │
                    │  Order, Invoice, DespatchAdvice,    │
                    │  Party, Address, Item, Price, ...   │
                    └─────────────────────────────────────┘
                              ▲           ▲
                              │           │
              ┌───────────────┼───────────┼───────────────┐
              │               │           │               │
              ▼               ▼           ▼               ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   X12 Mapper    │ │   UBL Mapper    │ │ EDIFACT Mapper  │
│                 │ │                 │ │                 │
│ 850 → Order     │ │ Order → Order   │ │ ORDERS → Order  │
│ Order → 850     │ │ (1:1 mapping)   │ │ Order → ORDERS  │
└─────────────────┘ └─────────────────┘ └─────────────────┘
        ▲                   ▲                   ▲
        │                   │                   │
        ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   X12 Parser    │ │   UBL Parser    │ │ EDIFACT Parser  │
│   (existing)    │ │   (existing)    │ │   (existing)    │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

---

## Semantic Model Design

### Core Principles

1. **UBL-aligned naming**: Use UBL's ABIE names (Party, Address, Item) since they're industry standard
2. **Pydantic models**: Runtime validation, serialization, IDE support
3. **Optional-by-default**: Accommodate different format completeness levels
4. **Extensible**: Allow format-specific metadata without polluting the core model
5. **Bidirectional**: Every model supports both ingestion and generation

### Pydantic Model Structure

```python
# src/edi_schema/semantic/models/base.py
from pydantic import BaseModel, Field
from typing import Annotated
from decimal import Decimal
from datetime import date, time, datetime
from enum import Enum

class SemanticModel(BaseModel):
    """Base class for all semantic models."""

    class Config:
        # Allow extra fields for format-specific data
        extra = "allow"
        # Use enum values in serialization
        use_enum_values = True
        # Validate on assignment
        validate_assignment = True


# src/edi_schema/semantic/models/primitives.py
class Amount(SemanticModel):
    """Monetary amount with currency."""
    value: Decimal
    currency: str = Field(pattern=r"^[A-Z]{3}$")  # ISO 4217


class Quantity(SemanticModel):
    """Numeric quantity with unit."""
    value: Decimal
    unit_code: str  # UNECE Rec 20


class Identifier(SemanticModel):
    """Identifier with optional scheme."""
    value: str
    scheme_id: str | None = None
    scheme_agency_id: str | None = None


class Period(SemanticModel):
    """Date/time period."""
    start_date: date | None = None
    end_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None


# src/edi_schema/semantic/models/party.py
class Address(SemanticModel):
    """Physical or postal address."""
    street_name: str | None = None
    additional_street_name: str | None = None
    building_number: str | None = None
    city_name: str | None = None
    postal_zone: str | None = None
    country_subentity: str | None = None  # State/Province
    country_code: str | None = Field(None, pattern=r"^[A-Z]{2}$")  # ISO 3166


class Contact(SemanticModel):
    """Contact information."""
    name: str | None = None
    telephone: str | None = None
    electronic_mail: str | None = None
    telefax: str | None = None


class PartyIdentification(SemanticModel):
    """Party identifier (DUNS, GLN, etc.)."""
    id: Identifier


class PartyName(SemanticModel):
    """Party name."""
    name: str


class Party(SemanticModel):
    """Business party (buyer, seller, carrier, etc.)."""
    party_identifications: list[PartyIdentification] = Field(default_factory=list)
    party_names: list[PartyName] = Field(default_factory=list)
    postal_address: Address | None = None
    contact: Contact | None = None

    @property
    def primary_name(self) -> str | None:
        """Convenience accessor for first party name."""
        return self.party_names[0].name if self.party_names else None


class CustomerParty(SemanticModel):
    """Customer party wrapper (BuyerCustomerParty, AccountingCustomerParty)."""
    party: Party
    buyer_contact: Contact | None = None
    delivery_contact: Contact | None = None
    accounting_contact: Contact | None = None


class SupplierParty(SemanticModel):
    """Supplier party wrapper."""
    party: Party
    seller_contact: Contact | None = None
    shipping_contact: Contact | None = None
    accounting_contact: Contact | None = None


# src/edi_schema/semantic/models/item.py
class ItemIdentification(SemanticModel):
    """Item identifier (UPC, EAN, SKU, etc.)."""
    id: Identifier


class Item(SemanticModel):
    """Product or service item."""
    description: str | None = None
    name: str | None = None
    buyers_item_identification: ItemIdentification | None = None
    sellers_item_identification: ItemIdentification | None = None
    manufacturers_item_identification: ItemIdentification | None = None
    standard_item_identification: ItemIdentification | None = None  # UPC, EAN
    commodity_classification: list[str] = Field(default_factory=list)


class Price(SemanticModel):
    """Unit price."""
    price_amount: Amount
    base_quantity: Quantity | None = None


# src/edi_schema/semantic/models/tax.py
class TaxCategory(SemanticModel):
    """Tax category details."""
    id: str | None = None  # VAT, GST, etc.
    percent: Decimal | None = None
    tax_scheme: str | None = None


class TaxSubtotal(SemanticModel):
    """Tax subtotal for a category."""
    taxable_amount: Amount | None = None
    tax_amount: Amount
    tax_category: TaxCategory


class TaxTotal(SemanticModel):
    """Total tax for document/line."""
    tax_amount: Amount
    tax_subtotals: list[TaxSubtotal] = Field(default_factory=list)


# src/edi_schema/semantic/models/allowance_charge.py
class AllowanceCharge(SemanticModel):
    """Allowance or charge."""
    charge_indicator: bool  # True = charge, False = allowance
    reason: str | None = None
    reason_code: str | None = None
    amount: Amount
    percent: Decimal | None = None


# src/edi_schema/semantic/models/delivery.py
class Delivery(SemanticModel):
    """Delivery information."""
    delivery_location: Address | None = None
    delivery_party: Party | None = None
    requested_delivery_period: Period | None = None
    actual_delivery_date: date | None = None
    tracking_id: str | None = None


class Shipment(SemanticModel):
    """Shipment details."""
    id: str | None = None
    gross_weight: Quantity | None = None
    net_weight: Quantity | None = None
    total_transport_handling_unit_quantity: int | None = None
    carrier_party: Party | None = None
    delivery: Delivery | None = None
    shipper_party: Party | None = None


# src/edi_schema/semantic/models/reference.py
class DocumentReference(SemanticModel):
    """Reference to another document."""
    id: str
    document_type: str | None = None
    document_type_code: str | None = None
    issue_date: date | None = None


class OrderReference(SemanticModel):
    """Reference to a purchase order."""
    id: str
    sales_order_id: str | None = None
    issue_date: date | None = None


class OrderLineReference(SemanticModel):
    """Reference to an order line."""
    line_id: str
    order_reference: OrderReference | None = None
```

### Document Models

```python
# src/edi_schema/semantic/models/order.py
from .base import SemanticModel
from .party import CustomerParty, SupplierParty
from .item import Item, Price
from .delivery import Delivery
from .tax import TaxTotal
from .allowance_charge import AllowanceCharge
from .reference import DocumentReference

class OrderLine(SemanticModel):
    """Line item in an order."""
    id: str
    quantity: Quantity
    line_extension_amount: Amount | None = None
    item: Item
    price: Price | None = None
    delivery: list[Delivery] = Field(default_factory=list)
    allowance_charges: list[AllowanceCharge] = Field(default_factory=list)
    tax_total: TaxTotal | None = None


class MonetaryTotal(SemanticModel):
    """Document monetary totals."""
    line_extension_amount: Amount | None = None
    tax_exclusive_amount: Amount | None = None
    tax_inclusive_amount: Amount | None = None
    allowance_total_amount: Amount | None = None
    charge_total_amount: Amount | None = None
    payable_amount: Amount | None = None


class PaymentTerms(SemanticModel):
    """Payment terms."""
    note: str | None = None
    payment_due_date: date | None = None
    settlement_discount_percent: Decimal | None = None


class Order(SemanticModel):
    """
    Semantic Order model.

    Maps to:
    - X12: 850 Purchase Order
    - UBL: Order
    - EDIFACT: ORDERS
    """
    # Identifiers
    id: str
    uuid: str | None = None
    issue_date: date
    issue_time: time | None = None

    # Type codes
    order_type_code: str | None = None

    # Currency
    document_currency_code: str = Field(pattern=r"^[A-Z]{3}$")

    # Notes
    notes: list[str] = Field(default_factory=list)

    # Validity
    validity_period: Period | None = None

    # References
    contract_document_reference: DocumentReference | None = None
    additional_document_references: list[DocumentReference] = Field(default_factory=list)

    # Parties
    buyer_customer_party: CustomerParty | None = None
    seller_supplier_party: SupplierParty | None = None

    # Delivery
    delivery: list[Delivery] = Field(default_factory=list)
    delivery_terms: str | None = None  # Incoterms

    # Payment
    payment_terms: list[PaymentTerms] = Field(default_factory=list)

    # Tax
    tax_total: list[TaxTotal] = Field(default_factory=list)

    # Totals
    anticipated_monetary_total: MonetaryTotal | None = None

    # Lines
    order_lines: list[OrderLine] = Field(default_factory=list)
    line_count: int | None = None

    # Source tracking (not part of business data)
    _source_format: str | None = None  # "x12", "ubl", "edifact"
    _source_version: str | None = None  # "005010", "2.5", "D96A"


# src/edi_schema/semantic/models/invoice.py
class InvoiceLine(SemanticModel):
    """Line item in an invoice."""
    id: str
    invoiced_quantity: Quantity
    line_extension_amount: Amount
    item: Item
    price: Price | None = None
    order_line_reference: OrderLineReference | None = None
    delivery: list[Delivery] = Field(default_factory=list)
    allowance_charges: list[AllowanceCharge] = Field(default_factory=list)
    tax_total: TaxTotal | None = None


class Invoice(SemanticModel):
    """
    Semantic Invoice model.

    Maps to:
    - X12: 810 Invoice
    - UBL: Invoice
    - EDIFACT: INVOIC
    """
    # Identifiers
    id: str
    uuid: str | None = None
    issue_date: date
    issue_time: time | None = None

    # Type
    invoice_type_code: str | None = None

    # Currency
    document_currency_code: str = Field(pattern=r"^[A-Z]{3}$")

    # Notes
    notes: list[str] = Field(default_factory=list)

    # References
    order_reference: OrderReference | None = None
    despatch_document_reference: DocumentReference | None = None
    additional_document_references: list[DocumentReference] = Field(default_factory=list)

    # Parties
    accounting_supplier_party: SupplierParty
    accounting_customer_party: CustomerParty
    payee_party: Party | None = None

    # Delivery
    delivery: list[Delivery] = Field(default_factory=list)

    # Payment
    payment_terms: list[PaymentTerms] = Field(default_factory=list)
    payment_means: list[PaymentMeans] = Field(default_factory=list)

    # Tax
    tax_total: list[TaxTotal] = Field(default_factory=list)

    # Totals
    legal_monetary_total: MonetaryTotal

    # Lines
    invoice_lines: list[InvoiceLine]
    line_count: int | None = None


# src/edi_schema/semantic/models/despatch_advice.py
class DespatchLine(SemanticModel):
    """Line item in a despatch advice."""
    id: str
    delivered_quantity: Quantity
    item: Item
    order_line_reference: OrderLineReference | None = None


class TransportHandlingUnit(SemanticModel):
    """Packaging unit (pallet, carton, etc.)."""
    id: str | None = None
    transport_handling_unit_type_code: str | None = None
    handling_unit_despatch_lines: list[DespatchLine] = Field(default_factory=list)


class DespatchAdvice(SemanticModel):
    """
    Semantic Despatch Advice (ASN) model.

    Maps to:
    - X12: 856 ASN
    - UBL: DespatchAdvice
    - EDIFACT: DESADV
    """
    # Identifiers
    id: str
    uuid: str | None = None
    issue_date: date
    issue_time: time | None = None

    # Notes
    notes: list[str] = Field(default_factory=list)

    # References
    order_reference: list[OrderReference] = Field(default_factory=list)

    # Parties
    despatch_supplier_party: SupplierParty | None = None
    delivery_customer_party: CustomerParty | None = None

    # Shipment
    shipment: Shipment | None = None

    # Lines
    despatch_lines: list[DespatchLine] = Field(default_factory=list)
```

---

## Mapper Design

### Base Mapper Protocol

```python
# src/edi_schema/semantic/mappers/base.py
from abc import ABC, abstractmethod
from typing import TypeVar, Generic
from ..models import SemanticModel

T = TypeVar("T", bound=SemanticModel)

class SemanticMapper(ABC, Generic[T]):
    """Base class for format-specific mappers."""

    @abstractmethod
    def to_semantic(self, source: any) -> T:
        """Convert format-specific model to semantic model."""
        ...

    @abstractmethod
    def from_semantic(self, model: T) -> any:
        """Convert semantic model to format-specific model."""
        ...

    @property
    @abstractmethod
    def semantic_type(self) -> type[T]:
        """Return the semantic model type this mapper handles."""
        ...

    @property
    @abstractmethod
    def source_format(self) -> str:
        """Return the source format identifier ('x12', 'ubl', 'edifact')."""
        ...
```

### X12 → Semantic Mappers

```python
# src/edi_schema/semantic/mappers/x12/order.py
from decimal import Decimal
from datetime import datetime
from ..base import SemanticMapper
from ...models import Order, OrderLine, CustomerParty, SupplierParty, Party, Address, Item, Price, Amount, Quantity

class X12OrderMapper(SemanticMapper[Order]):
    """Maps X12 850 to/from semantic Order model."""

    @property
    def semantic_type(self) -> type[Order]:
        return Order

    @property
    def source_format(self) -> str:
        return "x12"

    def to_semantic(self, x12_doc: X12Document) -> Order:
        """Convert X12 850 to semantic Order."""
        order = Order(
            id=self._get_beg_po_number(x12_doc),
            issue_date=self._parse_date(self._get_beg_date(x12_doc)),
            document_currency_code=self._get_currency(x12_doc) or "USD",
            order_lines=[],
        )

        # Extract parties from N1 loops
        for n1_loop in x12_doc.get_loops("N1"):
            party_code = n1_loop.get_element("N1", "01")
            party = self._build_party(n1_loop)

            if party_code == "BY":
                order.buyer_customer_party = CustomerParty(party=party)
            elif party_code == "SE":
                order.seller_supplier_party = SupplierParty(party=party)
            elif party_code == "ST":
                order.delivery.append(Delivery(delivery_party=party))

        # Extract line items from PO1 loops
        for po1_loop in x12_doc.get_loops("PO1"):
            order.order_lines.append(self._build_order_line(po1_loop))

        order._source_format = "x12"
        order._source_version = x12_doc.version
        return order

    def from_semantic(self, order: Order) -> X12Document:
        """Convert semantic Order to X12 850."""
        doc = X12Document(transaction_set="850", version="005010")

        # BEG segment
        doc.add_segment("BEG", {
            "01": "00",  # Original
            "02": "SA",  # Standalone
            "03": order.id,
            "05": self._format_date(order.issue_date),
        })

        # CUR segment if non-USD
        if order.document_currency_code != "USD":
            doc.add_segment("CUR", {
                "01": "BY",
                "02": order.document_currency_code,
            })

        # N1 loops for parties
        if order.buyer_customer_party:
            self._add_party_loop(doc, "BY", order.buyer_customer_party.party)
        if order.seller_supplier_party:
            self._add_party_loop(doc, "SE", order.seller_supplier_party.party)

        # PO1 loops for line items
        for i, line in enumerate(order.order_lines, 1):
            self._add_line_loop(doc, str(i), line)

        # CTT segment
        doc.add_segment("CTT", {
            "01": str(len(order.order_lines)),
        })

        return doc

    def _build_party(self, n1_loop: Loop) -> Party:
        """Build Party from N1 loop."""
        party = Party()

        # N1 segment - name and identifier
        n1 = n1_loop.get_segment("N1")
        if n1:
            party.party_names.append(PartyName(name=n1.get_element("02")))
            if n1.get_element("04"):
                scheme = self._map_id_qualifier(n1.get_element("03"))
                party.party_identifications.append(
                    PartyIdentification(id=Identifier(
                        value=n1.get_element("04"),
                        scheme_id=scheme,
                    ))
                )

        # N3/N4 segments - address
        n3 = n1_loop.get_segment("N3")
        n4 = n1_loop.get_segment("N4")
        if n3 or n4:
            party.postal_address = Address(
                street_name=n3.get_element("01") if n3 else None,
                additional_street_name=n3.get_element("02") if n3 else None,
                city_name=n4.get_element("01") if n4 else None,
                country_subentity=n4.get_element("02") if n4 else None,
                postal_zone=n4.get_element("03") if n4 else None,
                country_code=n4.get_element("04") if n4 else None,
            )

        return party

    def _build_order_line(self, po1_loop: Loop) -> OrderLine:
        """Build OrderLine from PO1 loop."""
        po1 = po1_loop.get_segment("PO1")

        line = OrderLine(
            id=po1.get_element("01"),
            quantity=Quantity(
                value=Decimal(po1.get_element("02")),
                unit_code=po1.get_element("03"),
            ),
            item=self._build_item(po1_loop),
        )

        # Price
        if po1.get_element("04"):
            line.price = Price(
                price_amount=Amount(
                    value=Decimal(po1.get_element("04")),
                    currency=self._current_currency,
                ),
            )

        # SAC (allowances/charges)
        for sac in po1_loop.get_segments("SAC"):
            line.allowance_charges.append(self._build_allowance_charge(sac))

        return line

    def _build_item(self, po1_loop: Loop) -> Item:
        """Build Item from PO1 and PID segments."""
        po1 = po1_loop.get_segment("PO1")
        item = Item()

        # Product IDs come in pairs: qualifier (06, 08, 10...) + value (07, 09, 11...)
        for i in range(6, 26, 2):
            qual = po1.get_element(f"{i:02d}")
            val = po1.get_element(f"{i+1:02d}")
            if qual and val:
                item = self._set_item_id(item, qual, val)

        # PID segment - description
        pid = po1_loop.get_segment("PID")
        if pid:
            item.description = pid.get_element("05")

        return item

    def _set_item_id(self, item: Item, qualifier: str, value: str) -> Item:
        """Set item identifier based on X12 qualifier code."""
        id = ItemIdentification(id=Identifier(value=value))

        if qualifier == "UP":
            id.id.scheme_id = "UPC"
            item.standard_item_identification = id
        elif qualifier == "EN":
            id.id.scheme_id = "EAN"
            item.standard_item_identification = id
        elif qualifier in ("VP", "SK"):
            item.sellers_item_identification = id
        elif qualifier in ("BP", "IN"):
            item.buyers_item_identification = id
        elif qualifier == "MG":
            item.manufacturers_item_identification = id

        return item

    @staticmethod
    def _map_id_qualifier(x12_code: str) -> str:
        """Map X12 N103 ID qualifier to scheme ID."""
        mapping = {
            "1": "DUNS",
            "9": "DUNS+4",
            "12": "Phone",
            "91": "Assigned by Seller",
            "92": "Assigned by Buyer",
        }
        return mapping.get(x12_code, x12_code)
```

### UBL → Semantic Mappers

UBL mapping is simpler since the semantic model is based on UBL concepts:

```python
# src/edi_schema/semantic/mappers/ubl/order.py
class UBLOrderMapper(SemanticMapper[Order]):
    """Maps UBL Order to/from semantic Order model."""

    def to_semantic(self, ubl_doc: ParsedDocument) -> Order:
        """Convert UBL Order to semantic Order."""
        root = ubl_doc.root

        order = Order(
            id=self._get_text(root, "cbc:ID"),
            uuid=self._get_text(root, "cbc:UUID"),
            issue_date=self._parse_date(self._get_text(root, "cbc:IssueDate")),
            document_currency_code=self._get_text(root, "cbc:DocumentCurrencyCode"),
            order_lines=[],
        )

        # Parties - nearly 1:1 mapping
        buyer = root.find(".//cac:BuyerCustomerParty")
        if buyer is not None:
            order.buyer_customer_party = self._build_customer_party(buyer)

        seller = root.find(".//cac:SellerSupplierParty")
        if seller is not None:
            order.seller_supplier_party = self._build_supplier_party(seller)

        # Lines
        for line_elem in root.findall(".//cac:OrderLine"):
            order.order_lines.append(self._build_order_line(line_elem))

        order._source_format = "ubl"
        order._source_version = "2.5"
        return order

    def from_semantic(self, order: Order) -> UBLDocument:
        """Convert semantic Order to UBL Order."""
        # Build using existing UBLWriter
        from edi_schema.ubl.writer import UBLWriter

        writer = UBLWriter(version="2.5")
        builder = writer.order()

        builder.id(order.id)
        builder.issue_date(str(order.issue_date))
        builder.document_currency_code(order.document_currency_code)

        if order.buyer_customer_party:
            builder.buyer_customer_party(
                lambda p: self._build_ubl_party(p, order.buyer_customer_party)
            )

        # ... continue building

        return builder.build()
```

### EDIFACT → Semantic Mappers

```python
# src/edi_schema/semantic/mappers/edifact/order.py
class EDIFACTOrderMapper(SemanticMapper[Order]):
    """Maps EDIFACT ORDERS to/from semantic Order model."""

    def to_semantic(self, edifact_doc: EDIFACTMessage) -> Order:
        """Convert EDIFACT ORDERS to semantic Order."""
        order = Order(
            id=self._get_bgm_document_id(edifact_doc),
            issue_date=self._parse_dtm(edifact_doc, "137"),  # Document date
            document_currency_code=self._get_cux_currency(edifact_doc),
            order_lines=[],
        )

        # NAD segments for parties
        for nad in edifact_doc.get_segments("NAD"):
            party_code = nad.get_element("3035")
            party = self._build_party(nad)

            if party_code == "BY":  # Buyer
                order.buyer_customer_party = CustomerParty(party=party)
            elif party_code == "SU":  # Supplier
                order.seller_supplier_party = SupplierParty(party=party)
            elif party_code == "DP":  # Delivery party
                order.delivery.append(Delivery(delivery_party=party))

        # LIN segment groups for line items
        for lin_group in edifact_doc.get_segment_groups("SG26"):  # LIN group
            order.order_lines.append(self._build_order_line(lin_group))

        order._source_format = "edifact"
        order._source_version = edifact_doc.version
        return order

    def from_semantic(self, order: Order) -> EDIFACTMessage:
        """Convert semantic Order to EDIFACT ORDERS."""
        msg = EDIFACTMessage(message_type="ORDERS", version="D96A")

        # BGM segment
        msg.add_segment("BGM", {
            "C002.1001": "220",  # Order
            "C106.1004": order.id,
            "1225": "9",  # Original
        })

        # DTM segment
        msg.add_segment("DTM", {
            "C507.2005": "137",  # Document date
            "C507.2380": order.issue_date.strftime("%Y%m%d"),
            "C507.2379": "102",  # CCYYMMDD format
        })

        # CUX segment
        msg.add_segment("CUX", {
            "C504.6347": "2",  # Reference currency
            "C504.6345": order.document_currency_code,
        })

        # NAD segments for parties
        if order.buyer_customer_party:
            self._add_nad_segment(msg, "BY", order.buyer_customer_party.party)
        if order.seller_supplier_party:
            self._add_nad_segment(msg, "SU", order.seller_supplier_party.party)

        # LIN groups for line items
        for line in order.order_lines:
            self._add_lin_group(msg, line)

        return msg
```

---

## Translation Service

```python
# src/edi_schema/semantic/translator.py
from enum import Enum
from typing import TypeVar

from .models import Order, Invoice, DespatchAdvice, SemanticModel
from .mappers.x12 import X12OrderMapper, X12InvoiceMapper, X12DespatchAdviceMapper
from .mappers.ubl import UBLOrderMapper, UBLInvoiceMapper, UBLDespatchAdviceMapper
from .mappers.edifact import EDIFACTOrderMapper, EDIFACTInvoiceMapper, EDIFACTDespatchAdviceMapper


class Format(Enum):
    X12 = "x12"
    UBL = "ubl"
    EDIFACT = "edifact"


class DocumentType(Enum):
    ORDER = "order"
    INVOICE = "invoice"
    DESPATCH_ADVICE = "despatch_advice"
    # ... more


T = TypeVar("T", bound=SemanticModel)


class TranslationService:
    """
    Translate documents between X12, UBL, and EDIFACT formats.

    Usage:
        service = TranslationService()

        # X12 850 → UBL Order
        x12_doc = x12_parser.parse(raw_x12)
        order = service.to_semantic(x12_doc, Format.X12, DocumentType.ORDER)
        ubl_doc = service.from_semantic(order, Format.UBL)

        # Or directly
        ubl_doc = service.translate(x12_doc, Format.X12, Format.UBL, DocumentType.ORDER)
    """

    def __init__(self):
        # Register mappers
        self._mappers = {
            (Format.X12, DocumentType.ORDER): X12OrderMapper(),
            (Format.X12, DocumentType.INVOICE): X12InvoiceMapper(),
            (Format.X12, DocumentType.DESPATCH_ADVICE): X12DespatchAdviceMapper(),
            (Format.UBL, DocumentType.ORDER): UBLOrderMapper(),
            (Format.UBL, DocumentType.INVOICE): UBLInvoiceMapper(),
            (Format.UBL, DocumentType.DESPATCH_ADVICE): UBLDespatchAdviceMapper(),
            (Format.EDIFACT, DocumentType.ORDER): EDIFACTOrderMapper(),
            (Format.EDIFACT, DocumentType.INVOICE): EDIFACTInvoiceMapper(),
            (Format.EDIFACT, DocumentType.DESPATCH_ADVICE): EDIFACTDespatchAdviceMapper(),
        }

    def to_semantic(
        self,
        source: any,
        source_format: Format,
        doc_type: DocumentType
    ) -> SemanticModel:
        """Convert format-specific document to semantic model."""
        mapper = self._mappers.get((source_format, doc_type))
        if not mapper:
            raise ValueError(f"No mapper for {source_format}/{doc_type}")
        return mapper.to_semantic(source)

    def from_semantic(
        self,
        model: SemanticModel,
        target_format: Format
    ) -> any:
        """Convert semantic model to format-specific document."""
        # Infer document type from model type
        doc_type = self._infer_doc_type(model)
        mapper = self._mappers.get((target_format, doc_type))
        if not mapper:
            raise ValueError(f"No mapper for {target_format}/{doc_type}")
        return mapper.from_semantic(model)

    def translate(
        self,
        source: any,
        source_format: Format,
        target_format: Format,
        doc_type: DocumentType,
    ) -> any:
        """Translate document from one format to another."""
        semantic = self.to_semantic(source, source_format, doc_type)
        return self.from_semantic(semantic, target_format)

    def _infer_doc_type(self, model: SemanticModel) -> DocumentType:
        """Infer document type from semantic model class."""
        type_map = {
            Order: DocumentType.ORDER,
            Invoice: DocumentType.INVOICE,
            DespatchAdvice: DocumentType.DESPATCH_ADVICE,
        }
        return type_map.get(type(model))
```

---

## Code Lists & Value Mappings

```python
# src/edi_schema/semantic/codelists/party_role.py
"""Party role code mappings between formats."""

X12_TO_SEMANTIC = {
    "BY": "Buyer",
    "SE": "Seller",
    "ST": "ShipTo",
    "SF": "ShipFrom",
    "BT": "BillTo",
    "RI": "RemitTo",
    "CA": "Carrier",
    "VN": "Vendor",
}

EDIFACT_TO_SEMANTIC = {
    "BY": "Buyer",
    "SU": "Supplier",  # Note: different from X12
    "DP": "DeliveryParty",
    "UC": "UltimateConsignee",
    "IV": "InvoicingParty",
}

SEMANTIC_TO_UBL_XPATH = {
    "Buyer": "cac:BuyerCustomerParty",
    "Seller": "cac:SellerSupplierParty",
    "ShipTo": "cac:Delivery/cac:DeliveryParty",
    "ShipFrom": "cac:Shipment/cac:ShipperParty",
    "BillTo": "cac:AccountingCustomerParty",
    "RemitTo": "cac:PayeeParty",
    "Carrier": "cac:Shipment/cac:CarrierParty",
}


# src/edi_schema/semantic/codelists/product_id.py
"""Product identifier scheme mappings."""

X12_QUALIFIER_TO_SCHEME = {
    "UP": ("UPC", "standard"),
    "EN": ("EAN", "standard"),
    "UK": ("UCC/EAN-128", "standard"),
    "VP": (None, "sellers"),
    "BP": (None, "buyers"),
    "MG": (None, "manufacturers"),
    "SK": (None, "sellers"),
    "IN": (None, "buyers"),
}

EDIFACT_QUALIFIER_TO_SCHEME = {
    "SRV": ("EAN", "standard"),
    "BP": (None, "buyers"),
    "VP": (None, "sellers"),
    "MF": (None, "manufacturers"),
}


# src/edi_schema/semantic/codelists/currency.py
"""Currency code mapping (all formats use ISO 4217, but X12 may need validation)."""

# X12 uses same codes as ISO 4217
# EDIFACT uses same codes as ISO 4217
# UBL uses same codes as ISO 4217

# Only issue: X12 amounts are often in cents (implied 2 decimals)
def x12_amount_to_decimal(value: str, element_id: str) -> Decimal:
    """Convert X12 amount (often in cents) to decimal."""
    # Check if this element uses implied decimals
    implied_decimal_elements = {"610", "782"}  # Amount elements

    if element_id in implied_decimal_elements:
        return Decimal(value) / 100
    return Decimal(value)
```

---

## Implementation Phases

### Phase 1: Semantic Models (2-3 weeks)

| Task | Description |
|------|-------------|
| Base models | SemanticModel, primitives (Amount, Quantity, Identifier, Period) |
| Party models | Party, Address, Contact, CustomerParty, SupplierParty |
| Item models | Item, ItemIdentification, Price |
| Tax models | TaxTotal, TaxSubtotal, TaxCategory |
| Other models | AllowanceCharge, Delivery, Shipment, DocumentReference |
| Document models | Order, Invoice, DespatchAdvice |
| Tests | Unit tests with Pydantic validation |

**Deliverable:** `src/edi_schema/semantic/models/` with full Pydantic model hierarchy

### Phase 2: X12 Mappers (2-3 weeks)

| Task | Description |
|------|-------------|
| 850 → Order | X12OrderMapper.to_semantic() |
| Order → 850 | X12OrderMapper.from_semantic() |
| 810 → Invoice | X12InvoiceMapper |
| 856 → DespatchAdvice | X12DespatchAdviceMapper |
| Code mappings | Party roles, product IDs, amounts |
| Tests | Round-trip tests, field coverage validation |

**Deliverable:** `src/edi_schema/semantic/mappers/x12/`

### Phase 3: UBL Mappers (1-2 weeks)

| Task | Description |
|------|-------------|
| Order ↔ Order | UBLOrderMapper (nearly 1:1) |
| Invoice ↔ Invoice | UBLInvoiceMapper |
| DespatchAdvice ↔ DespatchAdvice | UBLDespatchAdviceMapper |
| Tests | Integration with existing UBL parser/writer |

**Deliverable:** `src/edi_schema/semantic/mappers/ubl/`

### Phase 4: EDIFACT Mappers (2-3 weeks)

| Task | Description |
|------|-------------|
| ORDERS → Order | EDIFACTOrderMapper.to_semantic() |
| Order → ORDERS | EDIFACTOrderMapper.from_semantic() |
| INVOIC → Invoice | EDIFACTInvoiceMapper |
| DESADV → DespatchAdvice | EDIFACTDespatchAdviceMapper |
| Tests | Round-trip tests |

**Deliverable:** `src/edi_schema/semantic/mappers/edifact/`

### Phase 5: Translation Service (1 week)

| Task | Description |
|------|-------------|
| TranslationService | Unified API for format translation |
| CLI integration | `edi translate --from x12 --to ubl invoice.edi` |
| Validation hooks | Pre/post translation validation |
| Tests | End-to-end translation tests |

**Deliverable:** `src/edi_schema/semantic/translator.py`, CLI commands

### Phase 6: Additional Document Types (ongoing)

Extend to cover more of the 101 UBL types with X12/EDIFACT equivalents:

| Priority | UBL | X12 | EDIFACT | Status |
|----------|-----|-----|---------|--------|
| High | OrderResponse | 855 | ORDRSP | ✅ Complete |
| High | CreditNote | 812 | CREMUL | ✅ Complete |
| High | RemittanceAdvice | 820 | REMADV | ✅ Complete |
| Medium | Quotation | 843 | QUOTES | ✅ Complete |
| Medium | ReceiptAdvice | 861 | RECADV | ✅ Complete |
| Low | Catalogue | 832 | PRICAT | Deferred |

**Current Status:** Phase 6 complete (high + medium priority). Catalogue deferred for future work.

**Final Deliverable:** 24 mappers (3 formats × 8 document types) supporting:
- Order, OrderResponse, Quotation, Invoice, CreditNote, RemittanceAdvice, DespatchAdvice, ReceiptAdvice

---

## Testing Strategy

### 1. Unit Tests - Model Validation

```python
def test_order_validates_currency():
    """Currency must be ISO 4217."""
    with pytest.raises(ValidationError):
        Order(
            id="PO-001",
            issue_date=date.today(),
            document_currency_code="INVALID",
            order_lines=[],
        )

def test_amount_requires_currency():
    """Amount must have currency."""
    with pytest.raises(ValidationError):
        Amount(value=Decimal("100.00"))
```

### 2. Round-Trip Tests

```python
def test_x12_order_round_trip():
    """X12 850 → Semantic → X12 850 preserves data."""
    x12_doc = load_fixture("850_sample.edi")

    semantic = X12OrderMapper().to_semantic(x12_doc)
    x12_output = X12OrderMapper().from_semantic(semantic)

    assert_x12_equivalent(x12_doc, x12_output)

def test_cross_format_translation():
    """X12 850 → Semantic → UBL Order → Semantic → X12 850."""
    x12_doc = load_fixture("850_sample.edi")

    semantic1 = X12OrderMapper().to_semantic(x12_doc)
    ubl_doc = UBLOrderMapper().from_semantic(semantic1)
    semantic2 = UBLOrderMapper().to_semantic(ubl_doc)
    x12_output = X12OrderMapper().from_semantic(semantic2)

    # Allow minor differences (UUID, timestamps)
    assert_x12_mostly_equivalent(x12_doc, x12_output)
```

### 3. Real-World Sample Tests

Collect real-world samples from trading partners and validate:
- All fields preserved in round-trip
- Translation produces valid output
- No data loss for critical fields

### 4. Coverage Reports

Track which fields in each format have semantic mappings:

```
Order Field Coverage:
- X12 850: 45/52 fields mapped (87%)
- UBL Order: 78/78 fields mapped (100%)
- EDIFACT ORDERS: 41/48 fields mapped (85%)

Unmapped X12 fields:
- BEG08 (Acknowledgment Type) → Use OrderResponse instead
- REF (multiple reference qualifiers) → Need expansion
```

---

## Known Challenges & Mitigations

### 1. HL Hierarchy (X12 856)

**Challenge:** X12 856 uses flat HL segment hierarchy with parent-child codes.
**Mitigation:** During to_semantic(), build tree structure from HL codes, then flatten to DespatchLine list with nested TransportHandlingUnits.

### 2. Amount Encoding

**Challenge:** X12 amounts often in cents; UBL/EDIFACT use decimals.
**Mitigation:** Element-specific conversion rules in code list mappings.

### 3. Missing Fields

**Challenge:** Some fields exist in one format but not others.
**Mitigation:**
- Optional fields in semantic model
- `_source_format` tracking to know what was provided
- Validation warnings for missing required fields in target format

### 4. Code List Alignment

**Challenge:** Different code values across formats (e.g., X12 N101="SE" vs EDIFACT NAD="SU").
**Mitigation:** Explicit mapping tables for each code list; fall back to original value if no mapping.

### 5. Multi-Party Scenarios

**Challenge:** X12 N1 can have many party codes; UBL has specific party roles.
**Mitigation:** Map common codes (BY, SE, ST, SF, RI); store others in generic `additional_parties` list.

---

## Success Metrics

1. **Field Coverage:** ≥85% of commonly-used fields mapped for Order, Invoice, DespatchAdvice
2. **Round-Trip Fidelity:** ≥95% of test documents translate without data loss
3. **Validation:** All translated documents pass target format validation
4. **Performance:** Translation completes in <100ms for typical documents

---

## Directory Structure

```
src/edi_schema/
├── semantic/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py           # SemanticModel base class
│   │   ├── primitives.py     # Amount, Quantity, Identifier, Period
│   │   ├── party.py          # Party, Address, Contact, CustomerParty, SupplierParty
│   │   ├── item.py           # Item, ItemIdentification, Price
│   │   ├── tax.py            # TaxTotal, TaxSubtotal, TaxCategory
│   │   ├── allowance_charge.py
│   │   ├── delivery.py       # Delivery, Shipment
│   │   ├── reference.py      # DocumentReference, OrderReference
│   │   ├── order.py          # Order, OrderLine
│   │   ├── invoice.py        # Invoice, InvoiceLine
│   │   └── despatch_advice.py
│   ├── mappers/
│   │   ├── __init__.py
│   │   ├── base.py           # SemanticMapper protocol
│   │   ├── x12/
│   │   │   ├── __init__.py
│   │   │   ├── order.py      # X12OrderMapper
│   │   │   ├── invoice.py    # X12InvoiceMapper
│   │   │   └── despatch_advice.py
│   │   ├── ubl/
│   │   │   ├── __init__.py
│   │   │   ├── order.py
│   │   │   ├── invoice.py
│   │   │   └── despatch_advice.py
│   │   └── edifact/
│   │       ├── __init__.py
│   │       ├── order.py
│   │       ├── invoice.py
│   │       └── despatch_advice.py
│   ├── codelists/
│   │   ├── __init__.py
│   │   ├── party_role.py
│   │   ├── product_id.py
│   │   ├── currency.py
│   │   └── unit_of_measure.py
│   └── translator.py         # TranslationService
└── ...
```

---

## References

- [UN/CEFACT CCTS 2.01](http://www.unece.org/cefact/codesfortrade/ccts_index.html)
- [UBL 2.5 Specification](https://docs.oasis-open.org/ubl/UBL-2.5.html)
- [X12 005010 Standards](https://www.stedi.com/edi/x12-005010)
- [EDIFACT D96A](https://www.unece.org/trade/untdid/d96a/welcome.html)
- [Pydantic V2 Documentation](https://docs.pydantic.dev/latest/)
