"""
Shared X12 mapping patterns.
"""

from .parties import (
    ID_QUALIFIER_TO_SCHEME,
    INVOICE_PARTY_QUALIFIERS,
    N1_CONTACT_MAPPINGS,
    N1_PARTY_FIELD_MAPPINGS,
    ORDER_PARTY_QUALIFIERS,
    SCHEME_TO_ID_QUALIFIER,
    SHIPMENT_PARTY_QUALIFIERS,
    STANDARD_PARTY_QUALIFIERS,
    create_invoice_party_mapping,
    create_order_party_mapping,
    create_shipment_party_mapping,
    create_standard_party_mapping,
    map_id_qualifier_to_scheme,
    map_scheme_to_id_qualifier,
)

__all__ = [
    # Qualifier maps
    "STANDARD_PARTY_QUALIFIERS",
    "ORDER_PARTY_QUALIFIERS",
    "INVOICE_PARTY_QUALIFIERS",
    "SHIPMENT_PARTY_QUALIFIERS",
    # Field mappings
    "N1_PARTY_FIELD_MAPPINGS",
    "N1_CONTACT_MAPPINGS",
    # Factory functions
    "create_standard_party_mapping",
    "create_order_party_mapping",
    "create_invoice_party_mapping",
    "create_shipment_party_mapping",
    # ID qualifier mappings
    "ID_QUALIFIER_TO_SCHEME",
    "SCHEME_TO_ID_QUALIFIER",
    "map_id_qualifier_to_scheme",
    "map_scheme_to_id_qualifier",
]
