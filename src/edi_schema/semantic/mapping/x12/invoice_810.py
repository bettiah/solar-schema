"""
X12 810 Invoice Mapping Definition.

Declarative mapping from X12 810 Invoice to semantic Invoice model.
"""

from edi_schema.semantic.models import Invoice, InvoiceLine

from ..transforms import MAP_INVOICE_TYPE, PARSE_AMOUNT_CENTS, PARSE_DATE, PARSE_DECIMAL, TO_INT
from ..types import (
    FieldMapping,
    LoopMapping,
    PartyLoopMapping,
    QualifiedMapping,
    TransactionMapping,
    seg,
    sem,
)
from .shared.parties import INVOICE_PARTY_QUALIFIERS
from .validations.invoice_rules import INVOICE_VALIDATION_RULES


# =============================================================================
# 810 Field Mappings - Header Level
# =============================================================================


_HEADER_FIELD_MAPPINGS = [
    # BIG segment - Beginning Segment for Invoice
    FieldMapping(
        seg("BIG", 1),
        sem("issue_date"),
        to_semantic_transform=PARSE_DATE,
        required=True,
    ),
    FieldMapping(
        seg("BIG", 2),
        sem("id"),
        required=True,
    ),
    FieldMapping(
        seg("BIG", 3),
        sem("order_reference.issue_date"),
        to_semantic_transform=PARSE_DATE,
    ),
    FieldMapping(
        seg("BIG", 4),
        sem("order_reference.id"),
    ),
    FieldMapping(
        seg("BIG", 5),
        sem("order_reference.sales_order_id"),
        # Release Number (for blanket POs)
    ),
    FieldMapping(
        seg("BIG", 7),
        sem("invoice_type_code"),
        to_semantic_transform=MAP_INVOICE_TYPE,
    ),
    # BIG*08 = Transaction Set Purpose Code - not mapped (structural)
    # BIG*10 = Prior Invoice Number - handled separately for billing references

    # CUR segment - Currency
    FieldMapping(
        seg("CUR", 2),
        sem("document_currency_code"),
        default="USD",
    ),
    FieldMapping(
        seg("CUR", 3),
        sem("pricing_exchange_rate"),
        to_semantic_transform=PARSE_DECIMAL,
    ),

    # FOB segment - Delivery Terms / Incoterms
    # FOB*01 maps to simple delivery_terms string
    # FOB*02, FOB*03, FOB*04 are mapped to delivery[0].delivery_terms by BuilderMappingEngine
    FieldMapping(
        seg("FOB", 1),
        sem("delivery[0].delivery_terms.id"),
        # PP=Prepaid, CC=Collect, etc.
    ),

    # ITD segment - Payment Terms (first occurrence)
    FieldMapping(
        seg("ITD", 3),
        sem("payment_terms[0].settlement_discount_percent"),
        to_semantic_transform=PARSE_DECIMAL,
    ),
    FieldMapping(
        seg("ITD", 6),
        sem("due_date"),
        to_semantic_transform=PARSE_DATE,
        # Net Due Date
    ),
    FieldMapping(
        seg("ITD", 7),
        sem("payment_terms[0].settlement_period_days"),
        to_semantic_transform=TO_INT,
    ),
    FieldMapping(
        seg("ITD", 12),
        sem("payment_terms[0].note"),
    ),

    # CTT segment - Transaction Totals (X12 control segment, not mapped to semantic model)
    # CTT*01 = Line Count, CTT*02 = Hash Total - validation only

    # TDS segment - Total Monetary Value Summary
    # Handled by BuilderMappingEngine._map_tds_totals() which converts cents to decimal
    # TDS*01 = Total Invoice Amount (in cents)

    # CAD segment - Carrier Detail
    # Handled by BuilderMappingEngine._map_cad_to_shipment()

    # ISS segment - Invoice Shipment Summary
    FieldMapping(
        seg("ISS", 1),
        sem("delivery[0].quantity.value"),
        to_semantic_transform=PARSE_DECIMAL,
    ),
    FieldMapping(
        seg("ISS", 2),
        sem("delivery[0].quantity.unit_code"),
    ),

    # NTE segment - Notes
    # Handled by BuilderMappingEngine._map_nte_notes()

    # MSG segment - Notes
    # Handled by BuilderMappingEngine._map_msg_notes()
]


# =============================================================================
# 810 Qualified Mappings - DTM Segments
# =============================================================================


_DTM_QUALIFIED_MAPPINGS = QualifiedMapping(
    qualifier_path=seg("DTM", 1),
    mappings={
        "003": [
            FieldMapping(
                seg("DTM", 2),
                sem("issue_date"),
                to_semantic_transform=PARSE_DATE,
                # Invoice date (alternate to BIG*01)
            ),
        ],
        "011": [
            FieldMapping(
                seg("DTM", 2),
                sem("delivery[0].actual_delivery_date"),
                to_semantic_transform=PARSE_DATE,
                # Shipped date
            ),
        ],
        "017": [
            FieldMapping(
                seg("DTM", 2),
                sem("delivery[0].requested_delivery_period.end_date"),
                to_semantic_transform=PARSE_DATE,
                # Estimated delivery date
            ),
        ],
        "035": [
            FieldMapping(
                seg("DTM", 2),
                sem("delivery[0].actual_delivery_date"),
                to_semantic_transform=PARSE_DATE,
                # Delivered date
            ),
        ],
        "050": [
            FieldMapping(
                seg("DTM", 2),
                sem("receipt_document_reference.issue_date"),
                to_semantic_transform=PARSE_DATE,
                # Received date
            ),
        ],
    },
)


# =============================================================================
# 810 Qualified Mappings - REF Segments
# =============================================================================


_REF_QUALIFIED_MAPPINGS = QualifiedMapping(
    qualifier_path=seg("REF", 1),
    mappings={
        "BM": [
            FieldMapping(
                seg("REF", 2),
                sem("despatch_document_reference.id"),
                # Bill of Lading Number
            ),
        ],
        "CN": [
            FieldMapping(
                seg("REF", 2),
                sem("delivery[0].shipment.carrier_party.party_identifications[0].id.value"),
                # Carrier Number
            ),
        ],
        "CO": [
            FieldMapping(
                seg("REF", 2),
                sem("order_reference.id"),
                # Customer Order Number
            ),
        ],
        "CR": [
            FieldMapping(
                seg("REF", 2),
                sem("buyer_reference"),
                # Customer Reference Number
            ),
        ],
        "CT": [
            FieldMapping(
                seg("REF", 2),
                sem("contract_document_reference.id"),
                # Contract Number
            ),
        ],
        "DP": [
            FieldMapping(
                seg("REF", 2),
                sem("additional_document_references[+].id"),
                # Department Number
            ),
        ],
        "IA": [
            FieldMapping(
                seg("REF", 2),
                sem("additional_document_references[+].id"),
                # Internal Vendor Number
            ),
        ],
        "IL": [
            FieldMapping(
                seg("REF", 2),
                sem("originator_document_reference.id"),
                # Internal Order Number
            ),
        ],
        "IN": [
            FieldMapping(
                seg("REF", 2),
                sem("billing_references[0].invoice_document_reference.id"),
                # Invoice Number (prior)
            ),
        ],
        "IV": [
            FieldMapping(
                seg("REF", 2),
                sem("additional_document_references[+].id"),
                # Seller Invoice Number
            ),
        ],
        "ON": [
            FieldMapping(
                seg("REF", 2),
                sem("order_reference.id"),
                # Order Number
            ),
        ],
        "PO": [
            FieldMapping(
                seg("REF", 2),
                sem("order_reference.id"),
                # Purchase Order Number
            ),
        ],
        "SE": [
            FieldMapping(
                seg("REF", 2),
                sem("additional_document_references[+].id"),
                # Serial Number
            ),
        ],
        "SI": [
            FieldMapping(
                seg("REF", 2),
                sem("despatch_document_reference.id"),
                # Shipper's ID Number
            ),
        ],
        "TN": [
            FieldMapping(
                seg("REF", 2),
                sem("additional_document_references[+].id"),
                # Transaction Reference Number
            ),
        ],
        "VN": [
            FieldMapping(
                seg("REF", 2),
                sem("additional_document_references[+].id"),
                # Vendor Order Number
            ),
        ],
        "ZZ": [
            FieldMapping(
                seg("REF", 2),
                sem("additional_document_references[+].id"),
                # Mutually Defined
            ),
        ],
    },
)


# =============================================================================
# 810 Qualified Mappings - N9 Segments (Additional References)
# =============================================================================


_N9_QUALIFIED_MAPPINGS = QualifiedMapping(
    qualifier_path=seg("N9", 1),
    mappings={
        "AH": [
            FieldMapping(
                seg("N9", 2),
                sem("contract_document_reference.id"),
                # Agreement Number
            ),
        ],
        "CR": [
            FieldMapping(
                seg("N9", 2),
                sem("buyer_reference"),
                # Customer Reference Number
            ),
        ],
        "DO": [
            FieldMapping(
                seg("N9", 2),
                sem("despatch_document_reference.id"),
                # Delivery Order Number
            ),
        ],
        "LI": [
            FieldMapping(
                seg("N9", 2),
                sem("additional_document_references[+].id"),
                # Line Item Reference Number
            ),
        ],
        "OQ": [
            FieldMapping(
                seg("N9", 2),
                sem("order_reference.id"),
                # Order Number
            ),
        ],
        "PD": [
            FieldMapping(
                seg("N9", 2),
                sem("additional_document_references[+].id"),
                # Promotion/Deal Number
            ),
        ],
        "ZZ": [
            FieldMapping(
                seg("N9", 2),
                sem("additional_document_references[+].id"),
                # Mutually Defined
            ),
        ],
    },
)


# =============================================================================
# 810 Party Loop Mapping
# =============================================================================


_PARTY_MAPPING = PartyLoopMapping(
    loop_id="N1",
    party_field_map=INVOICE_PARTY_QUALIFIERS,
    field_mappings=[
        FieldMapping(seg("N1", 2), sem("party.party_names[0].name")),
        FieldMapping(seg("N3", 1), sem("party.postal_address.street_name")),
        FieldMapping(seg("N3", 2), sem("party.postal_address.additional_street_name")),
        FieldMapping(seg("N4", 1), sem("party.postal_address.city_name")),
        FieldMapping(seg("N4", 2), sem("party.postal_address.country_subentity")),
        FieldMapping(seg("N4", 3), sem("party.postal_address.postal_zone")),
        FieldMapping(seg("N4", 4), sem("party.postal_address.country_code")),
    ],
    contact_mappings=[
        FieldMapping(seg("PER", 2), sem("party.contact.name")),
    ],
)


# =============================================================================
# 810 Line Item Loop Mapping (IT1)
# =============================================================================


_IT1_LOOP_MAPPING = LoopMapping(
    loop_id="IT1",
    semantic_path=sem("invoice_lines"),
    item_type=InvoiceLine,
    field_mappings=[
        # IT1 segment - Line item data
        FieldMapping(
            seg("IT1", 1),
            sem("id"),
        ),
        FieldMapping(
            seg("IT1", 2),
            sem("invoiced_quantity.value"),
            to_semantic_transform=PARSE_DECIMAL,
        ),
        FieldMapping(
            seg("IT1", 3),
            sem("invoiced_quantity.unit_code"),
            default="EA",
        ),
        FieldMapping(
            seg("IT1", 4),
            sem("price.price_amount.value"),
            to_semantic_transform=PARSE_DECIMAL,
        ),
        # IT1*05 = Basis of Unit Price Code
        FieldMapping(
            seg("IT1", 5),
            sem("price.base_quantity_unit_code"),
        ),
        # IT1*06-25 = Product ID qualifier/value pairs
        # These are handled by BuilderMappingEngine._extract_it1_product_ids()

        # PID segment - Product Description
        FieldMapping(
            seg("PID", 5),
            sem("item.description"),
        ),
        # PID*04 = Additional item property name
        FieldMapping(
            seg("PID", 4),
            sem("item.additional_item_properties[0].name"),
        ),

        # CTP segment - Pricing Information
        FieldMapping(
            seg("CTP", 2),
            sem("price.price_type_code"),
            # Price type: WS=Wholesale, RS=Retail, CT=Contract, etc.
        ),
        FieldMapping(
            seg("CTP", 3),
            sem("price.price_amount.value"),
            to_semantic_transform=PARSE_DECIMAL,
            # Alternate unit price
        ),

        # REF segment within IT1 loop - line-level references
        FieldMapping(
            seg("REF", 2, qualifier=(1, "LI")),
            sem("order_line_references[0].line_id"),
            # Line Item Reference
        ),
        FieldMapping(
            seg("REF", 2, qualifier=(1, "PO")),
            sem("order_line_references[0].order_reference.id"),
            # PO Reference
        ),

        # MSG segment within IT1 loop - line-level notes
        FieldMapping(
            seg("MSG", 1),
            sem("note[0]"),
        ),

        # Line-level SAC, TXI handled by BuilderMappingEngine
    ],
    qualified_mappings=[
        # Line-level DTM
        QualifiedMapping(
            qualifier_path=seg("DTM", 1),
            mappings={
                "002": [
                    FieldMapping(
                        seg("DTM", 2),
                        sem("delivery[0].requested_delivery_period.start_date"),
                        to_semantic_transform=PARSE_DATE,
                    ),
                ],
                "011": [
                    FieldMapping(
                        seg("DTM", 2),
                        sem("delivery[0].actual_delivery_date"),
                        to_semantic_transform=PARSE_DATE,
                    ),
                ],
                "017": [
                    FieldMapping(
                        seg("DTM", 2),
                        sem("delivery[0].requested_delivery_period.end_date"),
                        to_semantic_transform=PARSE_DATE,
                    ),
                ],
                "035": [
                    FieldMapping(
                        seg("DTM", 2),
                        sem("delivery[0].actual_delivery_date"),
                        to_semantic_transform=PARSE_DATE,
                    ),
                ],
            },
        ),
    ],
    # Note: Line-level SAC and TXI handled by BuilderMappingEngine
)


# =============================================================================
# Complete 810 Mapping Definition
# =============================================================================


INVOICE_810_MAPPING = TransactionMapping(
    transaction_id="810",
    semantic_type=Invoice,
    # Header-level field mappings
    field_mappings=_HEADER_FIELD_MAPPINGS,
    # Qualified mappings (DTM, REF, N9 with qualifiers)
    qualified_mappings=[
        _DTM_QUALIFIED_MAPPINGS,
        _REF_QUALIFIED_MAPPINGS,
        _N9_QUALIFIED_MAPPINGS,
    ],
    # Loop mappings (IT1 line items)
    loop_mappings=[
        _IT1_LOOP_MAPPING,
    ],
    # Party mappings (N1 loops)
    party_mappings=[
        _PARTY_MAPPING,
    ],
    # Envelope mappings (populated from context)
    envelope_mappings=[],
    # Context mappings (external metadata)
    context_mappings=[],
    # Validation rules
    validation_rules=INVOICE_VALIDATION_RULES,
    validate_on_map=True,
)
