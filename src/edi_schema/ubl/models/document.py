"""
UBL Document Models.

Defines document-level schema structures:
- DocumentType - complete document schema definition
- UBLSchema - full schema with all resolved references
"""

from dataclasses import dataclass, field

from .component import ABIE, CACElement, CBCElement
from .data_type import QualifiedDataType, UnqualifiedDataType
from .code_list import CodeList


@dataclass
class DocumentType:
    """
    A UBL document type definition.

    Represents a complete document schema from maindoc/ (e.g., Invoice, Order).
    Each document type has its own namespace and root ABIE.

    Attributes:
        name: Document name (e.g., 'Invoice', 'Order', 'DespatchAdvice')
        namespace: Document-specific namespace URI
        definition: Human-readable description
        root_element: Name of the root element
        root_abie: The root ABIE definition
        version: UBL version (e.g., '2.5')
    """

    name: str
    namespace: str
    definition: str
    root_element: str
    root_abie: ABIE
    version: str = "2.5"

    @property
    def id(self) -> str:
        """Return unique identifier."""
        return self.name


@dataclass
class UBLSchema:
    """
    Complete UBL schema for a document type.

    Contains the document type definition along with all referenced
    components (ABIEs, data types, code lists) needed for parsing
    and validation.

    Attributes:
        document_type: The document type definition
        abies: All ABIE definitions used (keyed by name)
        cbc_elements: All CBC element declarations (keyed by name)
        cac_elements: All CAC element declarations (keyed by name)
        udt_types: Unqualified data types (keyed by name)
        qdt_types: Qualified data types (keyed by name)
        code_lists: Code lists for validation (keyed by id)
        version: UBL version
    """

    document_type: DocumentType
    abies: dict[str, ABIE] = field(default_factory=dict)
    cbc_elements: dict[str, CBCElement] = field(default_factory=dict)
    cac_elements: dict[str, CACElement] = field(default_factory=dict)
    udt_types: dict[str, UnqualifiedDataType] = field(default_factory=dict)
    qdt_types: dict[str, QualifiedDataType] = field(default_factory=dict)
    code_lists: dict[str, CodeList] = field(default_factory=dict)
    version: str = "2.5"

    @property
    def name(self) -> str:
        """Return the document type name."""
        return self.document_type.name

    @property
    def namespace(self) -> str:
        """Return the document namespace."""
        return self.document_type.namespace

    def get_abie(self, name: str) -> ABIE | None:
        """Look up an ABIE by name."""
        return self.abies.get(name)

    def get_cbc_element(self, name: str) -> CBCElement | None:
        """Look up a CBC element by name."""
        return self.cbc_elements.get(name)

    def get_cac_element(self, name: str) -> CACElement | None:
        """Look up a CAC element by name."""
        return self.cac_elements.get(name)

    def get_data_type(self, name: str) -> UnqualifiedDataType | QualifiedDataType | None:
        """Look up a data type by name (checks both UDT and QDT)."""
        # Check QDT first (more specific)
        if name in self.qdt_types:
            return self.qdt_types[name]
        return self.udt_types.get(name)

    def get_code_list(self, id: str) -> CodeList | None:
        """Look up a code list by identifier."""
        return self.code_lists.get(id)


# List of all 101 UBL 2.5 document types
UBL_DOCUMENT_TYPES: list[str] = [
    "ApplicationResponse",
    "AttachedDocument",
    "AwardedNotification",
    "BillOfLading",
    "BusinessCard",
    "BusinessInformation",
    "CallForTenders",
    "Catalogue",
    "CatalogueDeletion",
    "CatalogueItemSpecificationUpdate",
    "CataloguePricingUpdate",
    "CatalogueRequest",
    "CertificateOfOrigin",
    "CommonTransportationReport",
    "ContractAwardNotice",
    "ContractNotice",
    "CreditNote",
    "DebitNote",
    "DeliveryNote",
    "DespatchAdvice",
    "DigitalAgreement",
    "DigitalCapability",
    "DocumentStatus",
    "DocumentStatusRequest",
    "Enquiry",
    "EnquiryResponse",
    "ExceptionCriteria",
    "ExceptionNotification",
    "ExportCustomsDeclaration",
    "ExpressionOfInterestRequest",
    "ExpressionOfInterestResponse",
    "Forecast",
    "ForecastRevision",
    "ForwardingInstructions",
    "FreightInvoice",
    "FulfilmentCancellation",
    "GoodsCertificate",
    "GoodsItemItinerary",
    "GoodsItemPassport",
    "GuaranteeCertificate",
    "ImportCustomsDeclaration",
    "InstructionForReturns",
    "InventoryReport",
    "Invoice",
    "InvoiceStatusRequest",
    "InvoiceStatusResponse",
    "ItemInformationRequest",
    "Manifest",
    "Order",
    "OrderCancellation",
    "OrderChange",
    "OrderResponse",
    "OrderResponseSimple",
    "PackingList",
    "PriorInformationNotice",
    "ProcurementStatus",
    "ProcurementStatusRequest",
    "ProductActivity",
    "ProofOfReexportation",
    "ProofOfReexportationReminder",
    "ProofOfReexportationRequest",
    "PurchaseReceipt",
    "QualificationApplicationRequest",
    "QualificationApplicationResponse",
    "Quotation",
    "ReceiptAdvice",
    "Reminder",
    "RemittanceAdvice",
    "RequestForQuotation",
    "RetailEvent",
    "SelfBilledCreditNote",
    "SelfBilledInvoice",
    "Statement",
    "StockAvailabilityReport",
    "Tender",
    "TenderContract",
    "TenderReceipt",
    "TenderStatus",
    "TenderStatusRequest",
    "TenderWithdrawal",
    "TendererQualification",
    "TendererQualificationResponse",
    "TradeItemLocationProfile",
    "TransitCustomsDeclaration",
    "TransportExecutionPlan",
    "TransportExecutionPlanRequest",
    "TransportProgressStatus",
    "TransportProgressStatusRequest",
    "TransportServiceDescription",
    "TransportServiceDescriptionRequest",
    "TransportationStatus",
    "TransportationStatusRequest",
    "UnawardedNotification",
    "UnsubscribeFromProcedureRequest",
    "UnsubscribeFromProcedureResponse",
    "UtilityStatement",
    "WasteMovement",
    "WasteNotification",
    "Waybill",
    "WeightStatement",
    "WorkReport",
]
