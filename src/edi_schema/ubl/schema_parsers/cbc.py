"""
CBC (Common Basic Components) Parser.

Parses UBL-CommonBasicComponents-2.5.xsd to extract basic element declarations and types.
"""

from pathlib import Path

from lxml import etree

from ..enums import Cardinality
from ..models import BBIE, CBCElement
from .base import (
    NSMAP,
    get_complex_types,
    get_elements,
    get_extension_base,
    parse_type_reference,
    parse_xsd,
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


def parse_cbc_elements(path: Path) -> dict[str, CBCElement]:
    """
    Parse CBC element declarations.

    Args:
        path: Path to UBL-CommonBasicComponents-2.5.xsd

    Returns:
        Dictionary mapping element names to CBCElement objects
    """
    root = parse_xsd(path)
    result: dict[str, CBCElement] = {}

    for elem in get_elements(root):
        name = elem.get("name", "")
        type_ref = elem.get("type", "")

        if not name or not type_ref:
            continue

        # Parse type reference to get local name
        _, type_local = parse_type_reference(type_ref)

        # Determine base data type (strip 'Type' suffix)
        data_type = type_local[:-4] if type_local.endswith("Type") else type_local

        cbc_elem = CBCElement(
            name=name,
            type_name=type_local,
            data_type=data_type,
        )
        result[name] = cbc_elem

    return result


def parse_cbc_types(path: Path) -> dict[str, BBIE]:
    """
    Parse CBC complex types as BBIE definitions.

    Each CBC element has an associated type that may extend a UDT/QDT.

    Args:
        path: Path to UBL-CommonBasicComponents-2.5.xsd

    Returns:
        Dictionary mapping type names to BBIE objects
    """
    root = parse_xsd(path)
    result: dict[str, BBIE] = {}

    for complex_type in get_complex_types(root):
        type_name = complex_type.get("name", "")
        if not type_name or not type_name.endswith("Type"):
            continue

        name = type_name[:-4]

        # Get base type from extension
        base_ref = get_extension_base(complex_type)
        if base_ref:
            prefix, base_local = parse_type_reference(base_ref)
            data_type = base_local[:-4] if base_local.endswith("Type") else base_local
        else:
            data_type = name

        # Infer representation term from name patterns
        representation_term = _infer_representation_term(name, data_type)

        bbie = BBIE(
            name=name,
            definition="",  # CBC types don't have embedded definitions
            cardinality=Cardinality.ZERO_OR_ONE,  # Default, overridden in context
            data_type=data_type,
            representation_term=representation_term,
        )
        result[name] = bbie

    return result


def _infer_representation_term(name: str, data_type: str) -> str:
    """
    Infer the CCTS representation term from element/type name.

    Args:
        name: Element or type name
        data_type: Base data type name

    Returns:
        Inferred representation term
    """
    # Check name suffixes
    suffixes = {
        "ID": "Identifier",
        "Code": "Code",
        "Date": "Date",
        "Time": "Time",
        "DateTime": "Date Time",
        "Indicator": "Indicator",
        "Amount": "Amount",
        "Quantity": "Quantity",
        "Measure": "Measure",
        "Percent": "Percent",
        "Rate": "Rate",
        "Numeric": "Numeric",
        "URI": "Identifier",
        "Name": "Name",
        "Value": "Value",
    }

    for suffix, term in suffixes.items():
        if name.endswith(suffix):
            return term

    # Fall back to data type
    if data_type in suffixes.values():
        return data_type

    return "Text"
