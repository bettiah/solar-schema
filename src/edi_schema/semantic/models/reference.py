"""
Semantic Reference Models.

Document and line references for cross-document linking.
"""

from datetime import date, time

from pydantic import Field

from .base import SemanticModel
from .primitives import Period


class Attachment(SemanticModel):
    """
    Document attachment.

    Maps to:
    - UBL: cac:Attachment
    - X12: BIN segment
    - EDIFACT: EFI segment
    """

    embedded_document_binary_object: bytes | None = Field(
        default=None,
        description="Embedded binary content",
    )
    embedded_document: str | None = Field(
        default=None,
        description="Embedded text content",
    )
    external_reference_uri: str | None = Field(
        default=None,
        description="External document URI",
    )
    filename: str | None = Field(
        default=None,
        description="Filename",
    )
    mime_code: str | None = Field(
        default=None,
        description="MIME type",
    )
    encoding_code: str | None = Field(
        default=None,
        description="Encoding (e.g., base64)",
    )
    character_set_code: str | None = Field(
        default=None,
        description="Character set",
    )

    def __str__(self) -> str:
        return self.filename or self.external_reference_uri or "attachment"


class DocumentReference(SemanticModel):
    """
    Reference to another document.

    Maps to:
    - UBL: cac:*DocumentReference
    - X12: REF segment
    - EDIFACT: RFF segment
    """

    id: str = Field(description="Document identifier")
    copy_indicator: bool | None = Field(
        default=None,
        description="Whether this is a copy",
    )
    uuid: str | None = Field(
        default=None,
        description="UUID of referenced document",
    )
    issue_date: date | None = Field(
        default=None,
        description="Document issue date",
    )
    issue_time: time | None = Field(
        default=None,
        description="Document issue time",
    )
    document_type_code: str | None = Field(
        default=None,
        description="Document type code",
    )
    document_type: str | None = Field(
        default=None,
        description="Document type description",
    )
    xpath: str | None = Field(
        default=None,
        description="XPath to specific part",
    )
    language_id: str | None = Field(
        default=None,
        description="Document language",
    )
    locale_code: str | None = Field(
        default=None,
        description="Document locale",
    )
    version_id: str | None = Field(
        default=None,
        description="Document version",
    )
    document_status_code: str | None = Field(
        default=None,
        description="Document status",
    )
    document_description: str | None = Field(
        default=None,
        description="Document description",
    )
    validity_period: Period | None = Field(
        default=None,
        description="Document validity period",
    )
    attachment: Attachment | None = Field(
        default=None,
        description="Document attachment",
    )

    def __str__(self) -> str:
        if self.document_type:
            return f"{self.document_type} {self.id}"
        return self.id


class OrderReference(SemanticModel):
    """
    Reference to a purchase order.

    Maps to:
    - UBL: cac:OrderReference
    - X12: BIG*03/04 (PO date/number), REF*PO
    - EDIFACT: RFF+ON
    """

    id: str = Field(description="Purchase order number")
    sales_order_id: str | None = Field(
        default=None,
        description="Seller's sales order number",
    )
    copy_indicator: bool | None = Field(
        default=None,
        description="Whether this is a copy",
    )
    uuid: str | None = Field(
        default=None,
        description="UUID of referenced order",
    )
    issue_date: date | None = Field(
        default=None,
        description="Order issue date",
    )
    issue_time: time | None = Field(
        default=None,
        description="Order issue time",
    )
    customer_reference: str | None = Field(
        default=None,
        description="Customer's reference",
    )
    order_type_code: str | None = Field(
        default=None,
        description="Order type code",
    )

    def __str__(self) -> str:
        return f"Order {self.id}"


class LineReference(SemanticModel):
    """
    Reference to a specific line in another document.

    Maps to:
    - UBL: cac:LineReference
    - X12: Line-level REF segments
    - EDIFACT: RFF at line level
    """

    line_id: str = Field(description="Line identifier")
    uuid: str | None = Field(
        default=None,
        description="UUID of the line",
    )
    line_status_code: str | None = Field(
        default=None,
        description="Line status",
    )
    document_reference: DocumentReference | None = Field(
        default=None,
        description="Parent document reference",
    )

    def __str__(self) -> str:
        return f"Line {self.line_id}"


class OrderLineReference(SemanticModel):
    """
    Reference to a specific order line.

    Maps to:
    - UBL: cac:OrderLineReference
    - X12: PRF segment
    - EDIFACT: RFF+ON at line level
    """

    line_id: str = Field(description="Order line identifier")
    sales_order_line_id: str | None = Field(
        default=None,
        description="Seller's line identifier",
    )
    uuid: str | None = Field(
        default=None,
        description="UUID of the order line",
    )
    line_status_code: str | None = Field(
        default=None,
        description="Line status",
    )
    order_reference: OrderReference | None = Field(
        default=None,
        description="Parent order reference",
    )

    def __str__(self) -> str:
        if self.order_reference:
            return f"Order {self.order_reference.id} Line {self.line_id}"
        return f"Line {self.line_id}"


class DespatchLineReference(SemanticModel):
    """
    Reference to a despatch advice line.

    Maps to:
    - UBL: cac:DespatchLineReference
    - X12: BSN/HL references
    - EDIFACT: RFF in DESADV
    """

    line_id: str = Field(description="Despatch line identifier")
    uuid: str | None = Field(
        default=None,
        description="UUID of the line",
    )
    line_status_code: str | None = Field(
        default=None,
        description="Line status",
    )
    document_reference: DocumentReference | None = Field(
        default=None,
        description="Parent document reference",
    )

    def __str__(self) -> str:
        return f"Despatch Line {self.line_id}"


class ReceiptLineReference(SemanticModel):
    """
    Reference to a receipt line.

    Maps to:
    - UBL: cac:ReceiptLineReference
    - X12: Various receipt references
    - EDIFACT: RFF in receipt documents
    """

    line_id: str = Field(description="Receipt line identifier")
    uuid: str | None = Field(
        default=None,
        description="UUID of the line",
    )
    line_status_code: str | None = Field(
        default=None,
        description="Line status",
    )
    document_reference: DocumentReference | None = Field(
        default=None,
        description="Parent document reference",
    )

    def __str__(self) -> str:
        return f"Receipt Line {self.line_id}"


class BillingReference(SemanticModel):
    """
    Reference to billing documents.

    Maps to:
    - UBL: cac:BillingReference
    - X12: BIG*02 (invoice number), REF segments
    - EDIFACT: RFF+IV
    """

    invoice_document_reference: DocumentReference | None = Field(
        default=None,
        description="Referenced invoice",
    )
    self_billed_invoice_document_reference: DocumentReference | None = Field(
        default=None,
        description="Self-billed invoice reference",
    )
    credit_note_document_reference: DocumentReference | None = Field(
        default=None,
        description="Referenced credit note",
    )
    debit_note_document_reference: DocumentReference | None = Field(
        default=None,
        description="Referenced debit note",
    )
    reminder_document_reference: DocumentReference | None = Field(
        default=None,
        description="Referenced reminder",
    )
    additional_document_reference: DocumentReference | None = Field(
        default=None,
        description="Additional reference",
    )
    billing_reference_lines: list["BillingReferenceLine"] = Field(
        default_factory=list,
        description="Line-level billing references",
    )

    def __str__(self) -> str:
        if self.invoice_document_reference:
            return f"Billing ref: Invoice {self.invoice_document_reference.id}"
        return "billing reference"


class BillingReferenceLine(SemanticModel):
    """
    Line-level billing reference.

    Maps to:
    - UBL: cac:BillingReferenceLine
    - X12: Line-level invoice references
    - EDIFACT: Line-level RFF
    """

    id: str = Field(description="Reference line ID")
    amount: "Amount | None" = Field(
        default=None,
        description="Referenced amount",
    )
    allowance_charges: list["AllowanceCharge"] = Field(
        default_factory=list,
        description="Referenced allowances/charges",
    )

    def __str__(self) -> str:
        return f"Billing Line {self.id}"


# Forward references
from .allowance_charge import AllowanceCharge  # noqa: E402
from .primitives import Amount  # noqa: E402

BillingReferenceLine.model_rebuild()
