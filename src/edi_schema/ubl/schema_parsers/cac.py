"""
CAC (Common Aggregate Components) Parser.

Parses UBL-CommonAggregateComponents-2.5.xsd to extract ABIE definitions
and element declarations.
"""

from pathlib import Path

from lxml import etree

from ..models import ABIE, ASBIE, BBIE, CACElement
from ..enums import Cardinality
from .base import (
    CAC_NS,
    CBC_NS,
    EXT_NS,
    NSMAP,
    get_attribute,
    get_complex_types,
    get_elements,
    get_sequence_elements,
    parse_type_reference,
    parse_xsd,
    strip_type_suffix,
)


def _get_ccts_metadata(element: etree._Element) -> dict[str, str]:
    """Extract CCTS component metadata from annotation."""
    result: dict[str, str] = {}

    component = element.xpath(
        "xsd:annotation/xsd:documentation/ccts:Component",
        namespaces=NSMAP,
    )
    if not component:
        return result

    for child in component[0]:
        tag = etree.QName(child.tag).localname
        if child.text:
            result[tag] = child.text.strip()

    return result


def _parse_cardinality(meta: dict[str, str], elem: etree._Element) -> Cardinality:
    """
    Determine cardinality from CCTS metadata or XSD attributes.

    Args:
        meta: CCTS metadata dictionary
        elem: XSD element

    Returns:
        Appropriate Cardinality enum value
    """
    # Check CCTS Cardinality first
    ccts_card = meta.get("Cardinality", "")
    if ccts_card:
        if ccts_card in ("1", "1..1"):
            return Cardinality.EXACTLY_ONE
        elif ccts_card in ("0..1",):
            return Cardinality.ZERO_OR_ONE
        elif ccts_card in ("0..n", "0..unbounded"):
            return Cardinality.ZERO_OR_MORE
        elif ccts_card in ("1..n", "1..unbounded"):
            return Cardinality.ONE_OR_MORE

    # Fall back to XSD minOccurs/maxOccurs
    min_occurs = int(elem.get("minOccurs", "1"))
    max_occurs_str = elem.get("maxOccurs", "1")
    max_occurs: int | None = None if max_occurs_str == "unbounded" else int(max_occurs_str)

    return Cardinality.from_min_max(min_occurs, max_occurs)


def parse_cac_elements(path: Path) -> dict[str, CACElement]:
    """
    Parse CAC element declarations.

    These are global elements that map to ABIE types.

    Args:
        path: Path to UBL-CommonAggregateComponents-2.5.xsd

    Returns:
        Dictionary mapping element names to CACElement objects
    """
    root = parse_xsd(path)
    result: dict[str, CACElement] = {}

    for elem in get_elements(root):
        name = elem.get("name", "")
        type_ref = elem.get("type", "")

        if not name or not type_ref:
            continue

        # Parse type reference
        _, type_local = parse_type_reference(type_ref)

        cac_elem = CACElement(
            name=name,
            type_name=type_local,
        )
        result[name] = cac_elem

    return result


def parse_cac_types(path: Path) -> dict[str, ABIE]:
    """
    Parse CAC complex types as ABIE definitions.

    Args:
        path: Path to UBL-CommonAggregateComponents-2.5.xsd

    Returns:
        Dictionary mapping type names to ABIE objects
    """
    root = parse_xsd(path)
    result: dict[str, ABIE] = {}

    for complex_type in get_complex_types(root):
        type_name = complex_type.get("name", "")
        if not type_name or not type_name.endswith("Type"):
            continue

        name = strip_type_suffix(type_name)

        # Get CCTS metadata
        meta = _get_ccts_metadata(complex_type)
        definition = meta.get("Definition", "")
        object_class = meta.get("ObjectClass", name)

        # Parse child elements
        bbies: list[BBIE] = []
        asbies: list[ASBIE] = []

        for elem in get_sequence_elements(complex_type):
            ref = elem.get("ref", "")
            if not ref:
                continue

            # Determine namespace and parse accordingly
            prefix, local_name = parse_type_reference(ref)
            elem_meta = _get_ccts_metadata(elem)
            cardinality = _parse_cardinality(elem_meta, elem)

            # Determine if this is a CBC (BBIE) or CAC (ASBIE) reference
            if prefix == "cbc" or (prefix is None and _is_cbc_element(ref)):
                bbie = BBIE(
                    name=local_name,
                    definition=elem_meta.get("Definition", ""),
                    cardinality=cardinality,
                    data_type=local_name,
                    representation_term=elem_meta.get("RepresentationTerm", "Text"),
                    property_term=elem_meta.get("PropertyTerm", ""),
                    object_class=object_class,
                )
                bbies.append(bbie)
            elif prefix == "cac" or prefix is None:
                # Skip ext: elements
                if prefix == "ext" or ref.startswith("ext:"):
                    continue

                asbie = ASBIE(
                    name=local_name,
                    definition=elem_meta.get("Definition", ""),
                    cardinality=cardinality,
                    associated_abie=_guess_abie_type(local_name, elem),
                    property_term=elem_meta.get("PropertyTerm", ""),
                    object_class=object_class,
                )
                asbies.append(asbie)

        abie = ABIE(
            name=name,
            definition=definition,
            object_class=object_class,
            bbies=bbies,
            asbies=asbies,
            namespace=CAC_NS,
        )
        result[name] = abie

    return result


def _is_cbc_element(ref: str) -> bool:
    """Check if reference is to a CBC element based on naming conventions."""
    # CBC elements typically end with specific suffixes
    cbc_suffixes = (
        "ID", "Code", "Date", "Time", "Indicator", "Amount", "Quantity",
        "Measure", "Percent", "Rate", "Numeric", "Text", "Name", "URI",
        "Value", "Description", "Note",
    )
    return any(ref.endswith(suffix) for suffix in cbc_suffixes)


def _guess_abie_type(element_name: str, elem: etree._Element) -> str:
    """
    Guess the associated ABIE type from element name or reference.

    Args:
        element_name: The element name (e.g., 'AccountingSupplierParty')
        elem: The XSD element for additional context

    Returns:
        Guessed ABIE type name (e.g., 'SupplierParty')
    """
    # Common patterns: element names often include the type
    # e.g., AccountingSupplierParty -> SupplierPartyType
    # e.g., BuyerCustomerParty -> CustomerPartyType

    # Check for common prefix patterns
    prefixes_to_strip = [
        "Accounting", "Buyer", "Seller", "Originator", "Delivery", "Despatch",
        "Payee", "Receiver", "Consignee", "Consignor", "Carrier", "Freight",
        "Notify", "Final", "Original", "Substitute", "Additional", "Applicable",
    ]

    result = element_name
    for prefix in prefixes_to_strip:
        if element_name.startswith(prefix) and len(element_name) > len(prefix):
            # Check if remainder is a valid ABIE name (capitalized)
            remainder = element_name[len(prefix):]
            if remainder[0].isupper():
                result = remainder
                break

    return result
