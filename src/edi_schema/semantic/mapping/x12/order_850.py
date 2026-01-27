"""
X12 850 Purchase Order Mapping Definition.

Declarative mapping from X12 850 Purchase Order to semantic Order model.
"""

from decimal import Decimal

from edi_schema.semantic.models import Item, Order, OrderLine
from ..transforms import PARSE_DATE, PARSE_DECIMAL, TO_INT, Transform
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
# Custom Transforms for 850
# =============================================================================


def _build_item_from_po1_elements(po1_data: dict) -> Item:
    """Build Item from PO1 product ID qualifier/value pairs."""
    from ....models import Identifier, ItemIdentification

    item = Item()

    # Process product ID pairs
    for i in range(6, 26, 2):
        qualifier = po1_data.get(f"elem_{i}")
        value = po1_data.get(f"elem_{i + 1}")

        if qualifier and value:
            field_type, scheme = _map_product_id_qualifier(qualifier)
            item_id = ItemIdentification(id=Identifier(value=value, scheme_id=scheme))

            if field_type == "standard":
                item.standard_item_identification = item_id
            elif field_type == "sellers":
                item.sellers_item_identification = item_id
            elif field_type == "buyers":
                item.buyers_item_identification = item_id
            elif field_type == "manufacturers":
                item.manufacturers_item_identification = item_id
            else:
                item.additional_item_identifications.append(item_id)

    return item


def _map_product_id_qualifier(qualifier: str) -> tuple[str, str | None]:
    """Map X12 product ID qualifier to (field_type, scheme)."""
    qualifier_map = {
        "UP": ("standard", "UPC"),
        "EN": ("standard", "EAN"),
        "UK": ("standard", "UCC/EAN-128"),
        "VP": ("sellers", None),
        "BP": ("buyers", None),
        "MG": ("manufacturers", None),
        "SK": ("sellers", None),
        "IN": ("buyers", None),
        "MN": ("manufacturers", None),
        "SN": ("additional", "Serial"),
    }
    return qualifier_map.get(qualifier, ("additional", None))


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
        seg("BEG", 5),
        sem("issue_date"),
        to_semantic_transform=PARSE_DATE,
        required=True,
    ),
    # CUR segment - Currency
    FieldMapping(
        seg("CUR", 2),
        sem("document_currency_code"),
        default="USD",
    ),
    # FOB segment - Delivery Terms / Incoterms
    FieldMapping(
        seg("FOB", 1),
        sem("delivery_terms"),
        # PP=Prepaid, CC=Collect, etc.
    ),
    # ITD segment - Payment Terms (first occurrence)
    FieldMapping(
        seg("ITD", 5),
        sem("payment_terms[0].settlement_discount_percent"),
        to_semantic_transform=PARSE_DECIMAL,
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
        # PO1*05 = Basis of Unit Price (not commonly used)
        # PO1*06-25 = Product ID qualifier/value pairs (handled separately)
        # For now, map the most common first pair
        FieldMapping(
            seg("PO1", 7),
            sem("item.sellers_item_identification.id.value"),
            # This is simplistic - real implementation needs to check qualifier
        ),
        # PID segment - Product Description
        FieldMapping(
            seg("PID", 5),
            sem("item.description"),
        ),
        # Line-level SAC (allowances/charges)
        # These require special handling for the loop
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
            },
        ),
    ],
)


# =============================================================================
# Complete 850 Mapping Definition
# =============================================================================


ORDER_850_MAPPING = TransactionMapping(
    transaction_id="850",
    semantic_type=Order,
    # Header-level field mappings
    field_mappings=_HEADER_FIELD_MAPPINGS,
    # Qualified mappings (DTM, REF with qualifiers)
    qualified_mappings=[
        _DTM_QUALIFIED_MAPPINGS,
        _REF_QUALIFIED_MAPPINGS,
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
