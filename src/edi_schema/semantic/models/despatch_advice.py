"""
Semantic Despatch Advice Models.

Shipping notice/ASN representations.
"""

from datetime import date, time

from pydantic import Field

from .base import SemanticModel
from .delivery import Shipment
from .item import Item
from .party import CustomerParty, SupplierParty
from .primitives import Quantity
from .reference import DocumentReference, OrderLineReference, OrderReference


class DespatchLine(SemanticModel):
    """
    Line item in a despatch advice.

    Maps to:
    - UBL: cac:DespatchLine
    - X12: HL loop with I (Item) level
    - EDIFACT: LIN segment group in DESADV
    """

    # Identification
    id: str = Field(description="Line item number")
    uuid: str | None = Field(
        default=None,
        description="UUID for this line",
    )
    note: list[str] = Field(
        default_factory=list,
        description="Line notes",
    )

    # Status
    line_status_code: str | None = Field(
        default=None,
        description="Line status code",
    )

    # Quantity
    delivered_quantity: Quantity = Field(description="Delivered/shipped quantity")
    backorder_quantity: Quantity | None = Field(
        default=None,
        description="Backordered quantity",
    )
    backorder_reason: str | None = Field(
        default=None,
        description="Backorder reason",
    )
    outstanding_quantity: Quantity | None = Field(
        default=None,
        description="Outstanding quantity",
    )
    outstanding_reason: str | None = Field(
        default=None,
        description="Outstanding reason",
    )
    oversupply_quantity: Quantity | None = Field(
        default=None,
        description="Oversupply quantity",
    )

    # References
    order_line_reference: OrderLineReference | None = Field(
        default=None,
        description="Order line reference",
    )
    document_references: list[DocumentReference] = Field(
        default_factory=list,
        description="Document references",
    )

    # Item
    item: Item = Field(description="Item details")

    # Shipment
    shipment: list[Shipment] = Field(
        default_factory=list,
        description="Shipment details for this line",
    )

    def __str__(self) -> str:
        return f"Despatch Line {self.id}: {self.delivered_quantity} x {self.item}"


class DespatchAdvice(SemanticModel):
    """
    Semantic Despatch Advice (ASN/Ship Notice) model.

    Central document representing a shipping notice in format-agnostic form.

    Maps to:
    - X12: 856 ASN (Advance Ship Notice)
    - UBL: DespatchAdvice
    - EDIFACT: DESADV

    Example:
        >>> asn = DespatchAdvice(
        ...     id="ASN-001",
        ...     issue_date=date(2024, 1, 15),
        ...     despatch_supplier_party=SupplierParty(party=Party(...)),
        ...     delivery_customer_party=CustomerParty(party=Party(...)),
        ...     despatch_lines=[DespatchLine(...)]
        ... )
    """

    # Identification
    id: str = Field(description="Despatch advice number")
    uuid: str | None = Field(
        default=None,
        description="UUID for this despatch advice",
    )
    copy_indicator: bool | None = Field(
        default=None,
        description="Whether this is a copy",
    )
    customization_id: str | None = Field(
        default=None,
        description="Customization identifier",
    )
    profile_id: str | None = Field(
        default=None,
        description="Profile identifier",
    )
    profile_execution_id: str | None = Field(
        default=None,
        description="Profile execution identifier",
    )

    # Dates and times
    issue_date: date = Field(description="Issue date")
    issue_time: time | None = Field(
        default=None,
        description="Issue time",
    )

    # Type
    document_status_code: str | None = Field(
        default=None,
        description="Document status code",
    )
    despatch_advice_type_code: str | None = Field(
        default=None,
        description="Despatch advice type code",
    )

    # Notes
    note: list[str] = Field(
        default_factory=list,
        description="Notes",
    )

    # Line count
    line_count: int | None = Field(
        default=None,
        description="Number of line items",
    )

    # References
    order_references: list[OrderReference] = Field(
        default_factory=list,
        description="Order references",
    )
    additional_document_references: list[DocumentReference] = Field(
        default_factory=list,
        description="Additional document references",
    )

    # Parties
    despatch_supplier_party: SupplierParty | None = Field(
        default=None,
        description="Despatching party (shipper)",
    )
    delivery_customer_party: CustomerParty | None = Field(
        default=None,
        description="Receiving party (consignee)",
    )
    buyer_customer_party: CustomerParty | None = Field(
        default=None,
        description="Buyer party",
    )
    seller_supplier_party: SupplierParty | None = Field(
        default=None,
        description="Seller party",
    )
    originator_customer_party: CustomerParty | None = Field(
        default=None,
        description="Originator party",
    )

    # Shipment
    shipment: Shipment | None = Field(
        default=None,
        description="Shipment details",
    )

    # Lines
    despatch_lines: list[DespatchLine] = Field(
        default_factory=list,
        description="Despatch line items",
    )

    # Source tracking
    _source_format: str | None = None
    _source_version: str | None = None

    @property
    def calculated_line_count(self) -> int:
        """Actual number of despatch lines."""
        return len(self.despatch_lines)

    def __str__(self) -> str:
        return f"DespatchAdvice {self.id} ({len(self.despatch_lines)} lines)"


class ReceiptAdvice(SemanticModel):
    """
    Semantic Receipt Advice model.

    Confirmation of goods receipt.

    Maps to:
    - X12: 861 Receiving Advice
    - UBL: ReceiptAdvice
    - EDIFACT: RECADV
    """

    # Identification
    id: str = Field(description="Receipt advice number")
    uuid: str | None = Field(default=None)
    copy_indicator: bool | None = Field(default=None)
    customization_id: str | None = Field(default=None)
    profile_id: str | None = Field(default=None)

    # Dates
    issue_date: date = Field(description="Issue date")
    issue_time: time | None = Field(default=None)

    # Type
    document_status_code: str | None = Field(default=None)
    receipt_advice_type_code: str | None = Field(default=None)

    # Notes
    note: list[str] = Field(default_factory=list)

    # Line count
    line_count: int | None = Field(default=None)

    # References
    order_references: list[OrderReference] = Field(default_factory=list)
    despatch_document_references: list[DocumentReference] = Field(default_factory=list)
    additional_document_references: list[DocumentReference] = Field(default_factory=list)

    # Parties
    delivery_customer_party: CustomerParty | None = Field(default=None)
    despatch_supplier_party: SupplierParty | None = Field(default=None)
    buyer_customer_party: CustomerParty | None = Field(default=None)
    seller_supplier_party: SupplierParty | None = Field(default=None)

    # Shipment
    shipment: Shipment | None = Field(default=None)

    # Lines
    receipt_lines: list["ReceiptLine"] = Field(
        default_factory=list,
        description="Receipt line items",
    )

    # Source tracking
    _source_format: str | None = None
    _source_version: str | None = None

    def __str__(self) -> str:
        return f"ReceiptAdvice {self.id}"


class ReceiptLine(SemanticModel):
    """Receipt line item."""

    id: str = Field(description="Line number")
    uuid: str | None = Field(default=None)
    note: list[str] = Field(default_factory=list)
    line_status_code: str | None = Field(default=None)

    # Quantities
    received_quantity: Quantity = Field(description="Received quantity")
    short_quantity: Quantity | None = Field(default=None)
    shortage_action_code: str | None = Field(default=None)
    rejected_quantity: Quantity | None = Field(default=None)
    reject_reason_code: str | None = Field(default=None)
    reject_reason: str | None = Field(default=None)
    reject_action_code: str | None = Field(default=None)
    oversupply_quantity: Quantity | None = Field(default=None)
    received_date: date | None = Field(default=None)
    timing_complaint_code: str | None = Field(default=None)
    timing_complaint: str | None = Field(default=None)

    # References
    order_line_reference: OrderLineReference | None = Field(default=None)
    despatch_line_references: list["DespatchLineReference"] = Field(default_factory=list)
    document_references: list[DocumentReference] = Field(default_factory=list)

    # Item
    item: Item = Field(description="Item details")

    # Shipment
    shipment: list[Shipment] = Field(default_factory=list)

    def __str__(self) -> str:
        return f"ReceiptLine {self.id}: {self.received_quantity} x {self.item}"


# Forward reference
from .reference import DespatchLineReference  # noqa: E402

ReceiptLine.model_rebuild()
