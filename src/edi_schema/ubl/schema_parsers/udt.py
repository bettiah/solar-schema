"""
UDT (Unqualified Data Types) Parser.

Parses BDNDR-UnqualifiedDataTypes-1.1.xsd to extract the base CCTS data types.
"""

from pathlib import Path

from lxml import etree

from ..models import Attribute, UnqualifiedDataType
from .base import (
    NSMAP,
    get_attributes,
    get_complex_types,
    get_restriction_base,
    parse_xsd,
)


def _get_ccts_metadata(complex_type: etree._Element) -> dict[str, str]:
    """Extract CCTS metadata from annotation."""
    result: dict[str, str] = {}

    # Look in annotation/documentation for ccts: elements
    for elem in complex_type.xpath(
        "xsd:annotation/xsd:documentation/*",
        namespaces=NSMAP,
    ):
        tag = etree.QName(elem.tag).localname
        if elem.text:
            result[tag] = elem.text.strip()

    return result


def _parse_attribute(attr_elem: etree._Element) -> Attribute:
    """Parse an xsd:attribute element into an Attribute model."""
    name = attr_elem.get("name", "")
    xsd_type = attr_elem.get("type", "xsd:string")
    use = attr_elem.get("use", "optional")
    required = use == "required"

    # Get definition from annotation
    definition = ""
    deprecated = False
    definitions = attr_elem.xpath(
        "xsd:annotation/xsd:documentation/ccts:Definition/text()",
        namespaces=NSMAP,
    )
    if definitions:
        definition = definitions[0].strip()
        deprecated = "(Deprecated)" in definition

    return Attribute(
        name=name,
        xsd_type=xsd_type,
        required=required,
        definition=definition,
        deprecated=deprecated,
    )


def parse_udt(path: Path) -> dict[str, UnqualifiedDataType]:
    """
    Parse the UnqualifiedDataTypes XSD file.

    Args:
        path: Path to BDNDR-UnqualifiedDataTypes-1.1.xsd

    Returns:
        Dictionary mapping type names to UnqualifiedDataType objects
    """
    root = parse_xsd(path)
    result: dict[str, UnqualifiedDataType] = {}

    for complex_type in get_complex_types(root):
        type_name = complex_type.get("name", "")
        if not type_name or not type_name.endswith("Type"):
            continue

        # Extract name without 'Type' suffix
        name = type_name[:-4]

        # Get CCTS metadata
        meta = _get_ccts_metadata(complex_type)
        definition = meta.get("Definition", "")
        representation_term = meta.get("RepresentationTermName", name)
        primitive_type = meta.get("PrimitiveType", "string")

        # Get base type from restriction
        base_type = get_restriction_base(complex_type)
        xsd_base = base_type if base_type else "xsd:string"

        # Parse attributes
        attributes: list[Attribute] = []
        for attr_elem in get_attributes(complex_type):
            attr = _parse_attribute(attr_elem)
            attributes.append(attr)

        udt = UnqualifiedDataType(
            name=name,
            definition=definition,
            representation_term=representation_term,
            primitive_type=primitive_type,
            xsd_base=xsd_base,
            attributes=attributes,
        )
        result[name] = udt

    return result
