"""
Reusable N1 Party Loop Patterns.

Standard patterns for mapping X12 N1 loops to semantic party models.
"""

from ...types import FieldMapping, PartyLoopMapping, SemanticPath, seg, sem


# =============================================================================
# Standard Party Qualifier Maps
# =============================================================================


# Common party codes used across transaction types
STANDARD_PARTY_QUALIFIERS = {
    "BY": sem("buyer_customer_party"),  # Buying Party
    "SE": sem("seller_supplier_party"),  # Selling Party
    "ST": sem("delivery[+].delivery_party"),  # Ship To
    "SF": sem("originator_customer_party"),  # Ship From (or Originator)
    "BT": sem("accounting_customer_party"),  # Bill To
    "RI": sem("payee_party"),  # Remit To
    "CA": sem("freight_forwarder_party"),  # Carrier
    "VN": sem("seller_supplier_party"),  # Vendor (alternate for seller)
    "SU": sem("seller_supplier_party"),  # Supplier (alternate for seller)
    "OB": sem("originator_customer_party"),  # Ordered By
    "II": sem("issuer_party"),  # Issuer of Invoice
    "PR": sem("payer_party"),  # Payer
    "PE": sem("payee_party"),  # Payee
}


# Order-specific party qualifiers
ORDER_PARTY_QUALIFIERS = {
    "BY": sem("buyer_customer_party"),
    "SE": sem("seller_supplier_party"),
    "ST": sem("delivery[+].delivery_party"),
    "BT": sem("accounting_customer_party"),
    "OB": sem("originator_customer_party"),
    "SF": sem("delivery[0].despatch.despatch_party"),  # Ship From
    "CA": sem("freight_forwarder_party"),  # Carrier
    "RI": sem("payee_party"),  # Remit To
}


# Invoice-specific party qualifiers
INVOICE_PARTY_QUALIFIERS = {
    "BY": sem("buyer_customer_party"),
    "SE": sem("seller_supplier_party"),
    "ST": sem("delivery[0].delivery_party"),
    "BT": sem("accounting_customer_party"),
    "RI": sem("payee_party"),
    "II": sem("accounting_supplier_party"),
}


# Shipment/ASN party qualifiers
SHIPMENT_PARTY_QUALIFIERS = {
    "ST": sem("delivery[0].delivery_party"),
    "SF": sem("despatch.despatch_party"),
    "SE": sem("seller_supplier_party"),
    "BY": sem("buyer_customer_party"),
    "CA": sem("freight_forwarder_party"),
}


# =============================================================================
# Standard N1 Loop Field Mappings
# =============================================================================


# These are relative to the party.party object within CustomerParty/SupplierParty
N1_PARTY_FIELD_MAPPINGS = [
    # N1 segment - Party identification
    FieldMapping(seg("N1", 2), sem("party.party_names[0].name")),
    FieldMapping(seg("N1", 3), sem("party.party_identifications[0].id.scheme_id")),
    FieldMapping(seg("N1", 4), sem("party.party_identifications[0].id.value")),
    # N2 segment - Additional name
    FieldMapping(seg("N2", 1), sem("party.party_names[1].name")),
    # N3 segment - Address
    FieldMapping(seg("N3", 1), sem("party.postal_address.street_name")),
    FieldMapping(seg("N3", 2), sem("party.postal_address.additional_street_name")),
    # N4 segment - City, State, Zip, Country
    FieldMapping(seg("N4", 1), sem("party.postal_address.city_name")),
    FieldMapping(seg("N4", 2), sem("party.postal_address.country_subentity")),
    FieldMapping(seg("N4", 3), sem("party.postal_address.postal_zone")),
    FieldMapping(seg("N4", 4), sem("party.postal_address.country_code")),
]


N1_CONTACT_MAPPINGS = [
    # PER segment - Contact information
    # Note: PER segments use qualifier/value pairs for comm methods
    FieldMapping(seg("PER", 2), sem("party.contact.name")),
    # PER*03/04, *05/06, *07/08 are qualifier/value pairs handled specially
]


# =============================================================================
# Factory Functions
# =============================================================================


def create_standard_party_mapping(
    loop_id: str = "N1",
    party_qualifiers: dict[str, SemanticPath] | None = None,
) -> PartyLoopMapping:
    """
    Create a standard N1 party loop mapping.

    Args:
        loop_id: The loop identifier (usually "N1")
        party_qualifiers: Custom qualifier map, or uses STANDARD_PARTY_QUALIFIERS

    Returns:
        PartyLoopMapping configured for standard N1 handling
    """
    if party_qualifiers is None:
        party_qualifiers = STANDARD_PARTY_QUALIFIERS

    return PartyLoopMapping(
        loop_id=loop_id,
        party_field_map=party_qualifiers,
        field_mappings=N1_PARTY_FIELD_MAPPINGS,
        contact_mappings=N1_CONTACT_MAPPINGS,
    )


def create_order_party_mapping() -> PartyLoopMapping:
    """Create party mapping for 850 Purchase Order."""
    return create_standard_party_mapping(
        party_qualifiers=ORDER_PARTY_QUALIFIERS,
    )


def create_invoice_party_mapping() -> PartyLoopMapping:
    """Create party mapping for 810 Invoice."""
    return create_standard_party_mapping(
        party_qualifiers=INVOICE_PARTY_QUALIFIERS,
    )


def create_shipment_party_mapping() -> PartyLoopMapping:
    """Create party mapping for 856 ASN/Shipment."""
    return create_standard_party_mapping(
        party_qualifiers=SHIPMENT_PARTY_QUALIFIERS,
    )


# =============================================================================
# ID Qualifier Mappings
# =============================================================================


# Map X12 N1*03 ID qualifiers to semantic scheme names
ID_QUALIFIER_TO_SCHEME = {
    "1": "DUNS",
    "9": "DUNS+4",
    "12": "Phone",
    "14": "DUNS+4",
    "91": "SellerAssigned",
    "92": "BuyerAssigned",
    "ZZ": "MutuallyDefined",
}


# Reverse mapping for generating X12
SCHEME_TO_ID_QUALIFIER = {v: k for k, v in ID_QUALIFIER_TO_SCHEME.items()}


def map_id_qualifier_to_scheme(qualifier: str | None) -> str | None:
    """Map X12 N1*03 ID qualifier to semantic scheme name."""
    if not qualifier:
        return None
    return ID_QUALIFIER_TO_SCHEME.get(qualifier, qualifier)


def map_scheme_to_id_qualifier(scheme: str | None) -> str:
    """Map semantic scheme name to X12 N1*03 ID qualifier."""
    if not scheme:
        return "ZZ"
    return SCHEME_TO_ID_QUALIFIER.get(scheme, "ZZ")
