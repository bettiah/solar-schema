"""
X12 850 Purchase Order Mapping Definition.

Declarative mapping from X12 850 Purchase Order to semantic Order model.
"""

from edi_schema.semantic.models import Order, OrderLine
from ..transforms import PARSE_DATE, PARSE_DECIMAL, TO_INT
from ..types import (
    FieldMapping,
    LoopMapping,
    PartyLoopMapping,
    QualifiedMapping,
    TransactionMapping,
    seg,
    sem,
)
from .shared.parties import ORDER_PARTY_QUALIFIERS
from .validations.order_rules import ORDER_VALIDATION_RULES


# =============================================================================
# 850 Field Mappings - Header Level
# =============================================================================


_HEADER_FIELD_MAPPINGS = [
    # BEG segment - Beginning Segment for Purchase Order
    FieldMapping(
        seg("BEG", 1),
        sem("document_purpose_code"),
        # 00=Original, 05=Replace, 01=Cancellation
    ),
    FieldMapping(
        seg("BEG", 2),
        sem("order_type_code"),
        # DS=Dropship, SA=Stand-Alone, NE=New, etc.
    ),
    FieldMapping(
        seg("BEG", 3),
        sem("id"),
        required=True,
    ),
    FieldMapping(
        seg("BEG", 4),
        sem("sales_order_id"),
        # Release Number (for blanket POs)
    ),
    FieldMapping(
        seg("BEG", 5),
        sem("issue_date"),
        to_semantic_transform=PARSE_DATE,
        required=True,
    ),
    FieldMapping(
        seg("BEG", 6),
        sem("contract_document_reference.id"),
        # Contract Number
    ),
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
        # Exchange Rate
    ),
    # FOB segment - Delivery Terms / Incoterms
    # FOB*01 maps to simple delivery_terms string on Order
    # FOB*02, FOB*03, FOB*05 are mapped to delivery[0].delivery_terms by MappingEngine
    # after party loops create the delivery object
    FieldMapping(
        seg("FOB", 1),
        sem("delivery_terms"),
        # PP=Prepaid, CC=Collect, etc.
    ),
    # TD5 segment - Carrier Details
    FieldMapping(
        seg("TD5", 2),
        sem("delivery[0].shipment.carrier_party.party_identifications[0].id.scheme_id"),
        # ID Code Qualifier: 2=SCAC
    ),
    FieldMapping(
        seg("TD5", 3),
        sem("delivery[0].shipment.carrier_party.party_identifications[0].id.value"),
        # Carrier ID (SCAC code)
    ),
    FieldMapping(
        seg("TD5", 4),
        sem("delivery[0].shipment.shipment_stages[0].transport_mode_code"),
        # Transport Method: A=Air, M=Motor, R=Rail, S=Ship, etc.
    ),
    FieldMapping(
        seg("TD5", 5),
        sem("delivery[0].shipment.shipment_stages[0].transit_direction_code"),
        # Routing description
    ),
    FieldMapping(
        seg("TD5", 12),
        sem("delivery[0].shipment.shipping_priority_level_code"),
        # Service Level Code: SG=Standard Ground, etc.
    ),
    # TD1 segment - Packaging / Lading
    FieldMapping(
        seg("TD1", 1),
        sem("delivery[0].shipment.transport_handling_units[0].transport_handling_unit_type_code"),
        # Packaging Code: CTN=Carton, PLT=Pallet, etc.
    ),
    FieldMapping(
        seg("TD1", 2),
        sem("delivery[0].shipment.total_transport_handling_unit_quantity"),
        to_semantic_transform=TO_INT,
        # Lading Quantity
    ),
    # TD1*06/07/08 = Weight qualifier/value/unit - handled separately
    # ITD segment - Payment Terms (first occurrence)
    FieldMapping(
        seg("ITD", 5),
        sem("payment_terms[0].settlement_discount_percent"),
        to_semantic_transform=PARSE_DECIMAL,
    ),
    FieldMapping(
        seg("ITD", 6),
        sem("payment_terms[0].settlement_period.end_date"),
        to_semantic_transform=PARSE_DATE,
        # Discount Due Date
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
    # CTT segment - Transaction Totals
    FieldMapping(
        seg("CTT", 1),
        sem("line_count"),
        to_semantic_transform=TO_INT,
    ),
    # AMT segment - Monetary Amount (total)
    FieldMapping(
        seg("AMT", 2, qualifier=(1, "TT")),
        sem("anticipated_monetary_total.payable_amount.value"),
        to_semantic_transform=PARSE_DECIMAL,
    ),
    # MSG segment - Notes
    FieldMapping(
        seg("MSG", 1),
        sem("note[0]"),
    ),
]


# =============================================================================
# 850 Qualified Mappings - DTM Segments
# =============================================================================


_DTM_QUALIFIED_MAPPINGS = QualifiedMapping(
    qualifier_path=seg("DTM", 1),
    mappings={
        # Various date qualifiers
        "002": [
            FieldMapping(
                seg("DTM", 2),
                sem("delivery[0].requested_delivery_period.start_date"),
                to_semantic_transform=PARSE_DATE,
            ),
        ],
        "010": [
            FieldMapping(
                seg("DTM", 2),
                sem("delivery[0].despatch.requested_despatch_date"),
                to_semantic_transform=PARSE_DATE,
            ),
        ],
        "037": [
            FieldMapping(
                seg("DTM", 2),
                sem("delivery[0].despatch.earliest_despatch_date"),
                to_semantic_transform=PARSE_DATE,
            ),
        ],
        "038": [
            FieldMapping(
                seg("DTM", 2),
                sem("delivery[0].latest_delivery_date"),
                to_semantic_transform=PARSE_DATE,
            ),
        ],
        "063": [
            FieldMapping(
                seg("DTM", 2),
                sem("delivery[0].latest_delivery_date"),
                to_semantic_transform=PARSE_DATE,
            ),
        ],
        "064": [
            FieldMapping(
                seg("DTM", 2),
                sem("validity_period.start_date"),
                to_semantic_transform=PARSE_DATE,
            ),
        ],
        "065": [
            FieldMapping(
                seg("DTM", 2),
                sem("validity_period.end_date"),
                to_semantic_transform=PARSE_DATE,
            ),
        ],
    },
)


# =============================================================================
# 850 Qualified Mappings - REF Segments
# =============================================================================


_REF_QUALIFIED_MAPPINGS = QualifiedMapping(
    qualifier_path=seg("REF", 1),
    mappings={
        "CT": [
            FieldMapping(
                seg("REF", 2),
                sem("contract_document_reference.id"),
            ),
        ],
        "PO": [
            FieldMapping(
                seg("REF", 2),
                sem("order_document_references[0].id"),
            ),
        ],
        "QQ": [
            FieldMapping(
                seg("REF", 2),
                sem("quotation_document_reference.id"),
            ),
        ],
        "VN": [
            FieldMapping(
                seg("REF", 2),
                sem("additional_document_references[0].id"),
            ),
        ],
        "BM": [
            FieldMapping(
                seg("REF", 2),
                sem("additional_document_references[+].id"),
                # Bill of Lading Number
            ),
        ],
        "IT": [
            FieldMapping(
                seg("REF", 2),
                sem("originator_document_reference.id"),
                # Internal Order Number
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
        "8M": [
            FieldMapping(
                seg("REF", 2),
                sem("additional_document_references[+].id"),
                # Related Vendor Order Number
            ),
        ],
        "IV": [
            FieldMapping(
                seg("REF", 2),
                sem("additional_document_references[+].id"),
                # Seller's Invoice Number
            ),
        ],
        "SI": [
            FieldMapping(
                seg("REF", 2),
                sem("additional_document_references[+].id"),
                # Shipper's Identifying Number
            ),
        ],
        "KK": [
            FieldMapping(
                seg("REF", 2),
                sem("additional_document_references[+].id"),
                # Customer Account Number
            ),
        ],
        "SE": [
            FieldMapping(
                seg("REF", 2),
                sem("additional_document_references[+].id"),
                # Serial Number
            ),
        ],
        "TN": [
            FieldMapping(
                seg("REF", 2),
                sem("additional_document_references[+].id"),
                # Transaction Reference Number
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
# 850 Qualified Mappings - N9 Segments (Additional References)
# =============================================================================


_N9_QUALIFIED_MAPPINGS = QualifiedMapping(
    qualifier_path=seg("N9", 1),
    mappings={
        "LI": [
            FieldMapping(
                seg("N9", 2),
                sem("additional_document_references[+].id"),
                # Line Item Reference Number
            ),
        ],
        "DO": [
            FieldMapping(
                seg("N9", 2),
                sem("additional_document_references[+].id"),
                # Delivery Order Number
            ),
        ],
        "CR": [
            FieldMapping(
                seg("N9", 2),
                sem("additional_document_references[+].id"),
                # Customer Reference Number
            ),
        ],
        "PD": [
            FieldMapping(
                seg("N9", 2),
                sem("additional_document_references[+].id"),
                # Promotion/Deal Number
            ),
        ],
        "AH": [
            FieldMapping(
                seg("N9", 2),
                sem("additional_document_references[+].id"),
                # Agreement Number
            ),
        ],
        "ZZ": [
            FieldMapping(
                seg("N9", 2),
                sem("additional_document_references[+].id"),
                # Mutually Defined
            ),
        ],
        "PD": [
            FieldMapping(
                seg("N9", 2),
                sem("additional_document_references[+].id"),
                # Promotion/Deal Number
            ),
        ],
        "L1": [
            FieldMapping(
                seg("N9", 2),
                sem("additional_document_references[+].id"),
                # Letters or Notes
            ),
        ],
        "OQ": [
            FieldMapping(
                seg("N9", 2),
                sem("additional_document_references[+].id"),
                # Order Number
            ),
        ],
    },
)


# =============================================================================
# 850 Party Loop Mapping
# =============================================================================


_PARTY_MAPPING = PartyLoopMapping(
    loop_id="N1",
    party_field_map=ORDER_PARTY_QUALIFIERS,
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
# 850 Line Item Loop Mapping (PO1)
# =============================================================================


_PO1_LOOP_MAPPING = LoopMapping(
    loop_id="PO1",
    semantic_path=sem("order_lines"),
    item_type=OrderLine,
    field_mappings=[
        # PO1 segment - Line item data
        FieldMapping(
            seg("PO1", 1),
            sem("id"),
        ),
        FieldMapping(
            seg("PO1", 2),
            sem("quantity.value"),
            to_semantic_transform=PARSE_DECIMAL,
        ),
        FieldMapping(
            seg("PO1", 3),
            sem("quantity.unit_code"),
            default="EA",
        ),
        FieldMapping(
            seg("PO1", 4),
            sem("price.price_amount.value"),
            to_semantic_transform=PARSE_DECIMAL,
        ),
        # PO1*05 = Basis of Unit Price Code
        FieldMapping(
            seg("PO1", 5),
            sem("price.base_quantity_unit_code"),
        ),
        # PO1*06-25 = Product ID qualifier/value pairs
        # These are handled by MappingEngine._extract_po1_product_ids()
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
        # REF segment within PO1 loop - line-level references
        FieldMapping(
            seg("REF", 2, qualifier=(1, "LI")),
            sem("document_references[0].id"),
            # Line Item Reference
        ),
        # MSG segment within PO1 loop - line-level notes
        FieldMapping(
            seg("MSG", 1),
            sem("note[0]"),
        ),
        # Line-level SAC, SCH handled by MappingEngine
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
                "010": [
                    FieldMapping(
                        seg("DTM", 2),
                        sem("delivery[0].despatch.requested_despatch_date"),
                        to_semantic_transform=PARSE_DATE,
                    ),
                ],
                "038": [
                    FieldMapping(
                        seg("DTM", 2),
                        sem("delivery[0].latest_delivery_date"),
                        to_semantic_transform=PARSE_DATE,
                    ),
                ],
                "063": [
                    FieldMapping(
                        seg("DTM", 2),
                        sem("delivery[0].latest_delivery_date"),
                        to_semantic_transform=PARSE_DATE,
                    ),
                ],
            },
        ),
    ],
    # Note: Line-level SAC and SCH handled by MappingEngine
)


# =============================================================================
# Complete 850 Mapping Definition
# =============================================================================


ORDER_850_MAPPING = TransactionMapping(
    transaction_id="850",
    semantic_type=Order,
    # Header-level field mappings
    field_mappings=_HEADER_FIELD_MAPPINGS,
    # Qualified mappings (DTM, REF, N9 with qualifiers)
    qualified_mappings=[
        _DTM_QUALIFIED_MAPPINGS,
        _REF_QUALIFIED_MAPPINGS,
        _N9_QUALIFIED_MAPPINGS,
    ],
    # Loop mappings (PO1 line items)
    loop_mappings=[
        _PO1_LOOP_MAPPING,
    ],
    # Party mappings (N1 loops)
    party_mappings=[
        _PARTY_MAPPING,
    ],
    # Envelope mappings (populated from context)
    envelope_mappings=[
        # These would map ISA/GS fields if the Order model had fields for them
        # For now, Order doesn't have envelope-related fields
    ],
    # Context mappings (external metadata)
    context_mappings=[
        # These would map filename, received_at, etc. if Order had those fields
    ],
    # Validation rules
    validation_rules=ORDER_VALIDATION_RULES,
    validate_on_map=True,
)
