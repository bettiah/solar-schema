"""
Base XSD Parsing Utilities.

Common utilities for parsing UBL XSD schema files using lxml.
"""

from pathlib import Path
from typing import Iterator

from lxml import etree

# XML namespaces used in UBL XSD files
XSD_NS = "http://www.w3.org/2001/XMLSchema"
CCTS_NS = "urn:un:unece:uncefact:documentation:2"
UDT_NS = "urn:oasis:names:specification:bdndr:schema:xsd:UnqualifiedDataTypes-1"
QDT_NS = "urn:oasis:names:specification:ubl:schema:xsd:QualifiedDataTypes-2"
CBC_NS = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
CAC_NS = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
EXT_NS = "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
CCT_NS = "urn:un:unece:uncefact:data:specification:CoreComponentTypeSchemaModule:2"

# Namespace map for XPath queries
NSMAP = {
    "xsd": XSD_NS,
    "ccts": CCTS_NS,
    "udt": UDT_NS,
    "qdt": QDT_NS,
    "cbc": CBC_NS,
    "cac": CAC_NS,
    "ext": EXT_NS,
    "ccts-cct": CCT_NS,
}


def parse_xsd(path: Path) -> etree._Element:
    """
    Parse an XSD file and return the root element.

    Args:
        path: Path to the XSD file

    Returns:
        The root xsd:schema element

    Raises:
        FileNotFoundError: If the file doesn't exist
        etree.XMLSyntaxError: If the XML is malformed
    """
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(str(path), parser)
    return tree.getroot()


def get_complex_types(root: etree._Element) -> Iterator[etree._Element]:
    """
    Iterate over all xsd:complexType elements.

    Args:
        root: The schema root element

    Yields:
        Each complexType element
    """
    yield from root.xpath("xsd:complexType", namespaces=NSMAP)


def get_elements(root: etree._Element) -> Iterator[etree._Element]:
    """
    Iterate over all top-level xsd:element declarations.

    Args:
        root: The schema root element

    Yields:
        Each element declaration
    """
    yield from root.xpath("xsd:element", namespaces=NSMAP)


def get_ccts_component(element: etree._Element) -> dict[str, str]:
    """
    Extract CCTS component metadata from an element's annotation.

    UBL schemas include CCTS metadata in xsd:annotation/xsd:documentation
    elements with ccts:Component children.

    Args:
        element: An XSD element with potential CCTS annotation

    Returns:
        Dictionary of CCTS metadata (ComponentType, Definition, Cardinality, etc.)
    """
    result: dict[str, str] = {}

    # Find annotation/documentation/Component
    component = element.xpath(
        "xsd:annotation/xsd:documentation/ccts:Component",
        namespaces=NSMAP,
    )
    if not component:
        return result

    comp = component[0]
    for child in comp:
        # Extract local name (without namespace prefix)
        tag = etree.QName(child.tag).localname
        if child.text:
            result[tag] = child.text.strip()

    return result


def get_documentation(element: etree._Element) -> str:
    """
    Extract documentation text from an element's annotation.

    Args:
        element: An XSD element

    Returns:
        Documentation text, or empty string if none
    """
    docs = element.xpath(
        "xsd:annotation/xsd:documentation/text()",
        namespaces=NSMAP,
    )
    if docs:
        return docs[0].strip()
    return ""


def get_attribute(element: etree._Element, name: str, default: str = "") -> str:
    """
    Get an attribute value from an element.

    Args:
        element: The XML element
        name: Attribute name
        default: Default value if not found

    Returns:
        The attribute value or default
    """
    return element.get(name, default)


def parse_type_reference(type_ref: str) -> tuple[str | None, str]:
    """
    Parse a type reference into namespace prefix and local name.

    Args:
        type_ref: Type reference like "udt:CodeType" or "CodeType"

    Returns:
        Tuple of (prefix or None, local_name)
    """
    if ":" in type_ref:
        prefix, local = type_ref.split(":", 1)
        return prefix, local
    return None, type_ref


def strip_type_suffix(name: str) -> str:
    """
    Remove 'Type' suffix from a type name.

    Args:
        name: Type name like "InvoiceType"

    Returns:
        Name without suffix like "Invoice"
    """
    if name.endswith("Type"):
        return name[:-4]
    return name


def get_sequence_elements(complex_type: etree._Element) -> Iterator[etree._Element]:
    """
    Get all xsd:element children of a complexType's sequence.

    Args:
        complex_type: A complexType element

    Yields:
        Each element in the sequence
    """
    # Direct sequence
    for elem in complex_type.xpath("xsd:sequence/xsd:element", namespaces=NSMAP):
        yield elem

    # Sequence inside complexContent/extension
    for elem in complex_type.xpath(
        "xsd:complexContent/xsd:extension/xsd:sequence/xsd:element",
        namespaces=NSMAP,
    ):
        yield elem


def get_attributes(complex_type: etree._Element) -> Iterator[etree._Element]:
    """
    Get all xsd:attribute elements from a complexType.

    Args:
        complex_type: A complexType element

    Yields:
        Each attribute element
    """
    # Direct attributes
    yield from complex_type.xpath("xsd:attribute", namespaces=NSMAP)

    # Attributes in simpleContent/restriction
    yield from complex_type.xpath(
        "xsd:simpleContent/xsd:restriction/xsd:attribute",
        namespaces=NSMAP,
    )

    # Attributes in simpleContent/extension
    yield from complex_type.xpath(
        "xsd:simpleContent/xsd:extension/xsd:attribute",
        namespaces=NSMAP,
    )


def get_restriction_base(complex_type: etree._Element) -> str | None:
    """
    Get the base type from a simpleContent restriction.

    Args:
        complex_type: A complexType element

    Returns:
        The base type reference, or None
    """
    restriction = complex_type.xpath(
        "xsd:simpleContent/xsd:restriction/@base",
        namespaces=NSMAP,
    )
    if restriction:
        return restriction[0]
    return None


def get_extension_base(complex_type: etree._Element) -> str | None:
    """
    Get the base type from a simpleContent extension.

    Args:
        complex_type: A complexType element

    Returns:
        The base type reference, or None
    """
    extension = complex_type.xpath(
        "xsd:simpleContent/xsd:extension/@base",
        namespaces=NSMAP,
    )
    if extension:
        return extension[0]
    return None
