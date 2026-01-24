"""
XML Parser for UBL Documents.

Low-level XML parsing with namespace handling and position tracking.
"""

from pathlib import Path
from typing import IO

from lxml import etree

from ..ast import ParsedAttribute, ParsedElement, SourcePosition
from ..enums import Namespace


class XMLParseError(Exception):
    """Exception raised for XML parsing errors."""

    def __init__(self, message: str, line: int = 0, column: int = 0):
        super().__init__(message)
        self.line = line
        self.column = column


def parse_xml(
    source: str | bytes | Path | IO[bytes],
    recover: bool = True,
) -> tuple[ParsedElement, dict[str, str]]:
    """
    Parse an XML document into a ParsedElement tree.

    Args:
        source: XML content (string, bytes, file path, or file object)
        recover: Whether to attempt recovery from errors

    Returns:
        Tuple of (root ParsedElement, namespace prefix map)

    Raises:
        XMLParseError: If the XML is malformed and recovery fails
    """
    parser = etree.XMLParser(
        remove_blank_text=True,
        recover=recover,
        remove_comments=True,
    )

    try:
        if isinstance(source, Path):
            tree = etree.parse(str(source), parser)
            root = tree.getroot()
        elif isinstance(source, (str, bytes)):
            if isinstance(source, str):
                source = source.encode("utf-8")
            root = etree.fromstring(source, parser)
        else:
            # File-like object
            tree = etree.parse(source, parser)
            root = tree.getroot()
    except etree.XMLSyntaxError as e:
        raise XMLParseError(str(e), getattr(e, "lineno", 0), getattr(e, "offset", 0))

    # Extract namespace map from root
    nsmap = _extract_namespaces(root)

    # Convert to ParsedElement tree
    parsed_root = _convert_element(root, nsmap)

    return parsed_root, nsmap


def _extract_namespaces(root: etree._Element) -> dict[str, str]:
    """
    Extract namespace prefix mappings from the document.

    Args:
        root: The root lxml element

    Returns:
        Dictionary mapping prefixes to namespace URIs
    """
    nsmap: dict[str, str] = {}

    # Get all namespace declarations from root and ancestors
    for prefix, uri in root.nsmap.items():
        if prefix is not None:
            nsmap[prefix] = uri

    # Add standard UBL prefixes if not present
    standard_prefixes = {
        "cac": Namespace.CAC.value,
        "cbc": Namespace.CBC.value,
        "ext": Namespace.EXT.value,
    }
    for prefix, uri in standard_prefixes.items():
        if prefix not in nsmap:
            nsmap[prefix] = uri

    return nsmap


def _convert_element(
    elem: etree._Element,
    nsmap: dict[str, str],
    xpath_parts: list[str] | None = None,
) -> ParsedElement:
    """
    Convert an lxml element to a ParsedElement.

    Args:
        elem: The lxml element
        nsmap: Namespace prefix map
        xpath_parts: Current XPath path components

    Returns:
        ParsedElement representation
    """
    if xpath_parts is None:
        xpath_parts = []

    # Extract namespace and local name
    qname = etree.QName(elem.tag)
    namespace = qname.namespace or ""
    local_name = qname.localname

    # Build XPath
    current_xpath = xpath_parts + [local_name]
    xpath_str = "/" + "/".join(current_xpath)

    # Get source position
    position = SourcePosition(
        line=elem.sourceline or 0,
        column=0,  # lxml doesn't provide column info
        xpath=xpath_str,
    )

    # Parse attributes
    attributes: list[ParsedAttribute] = []
    for attr_name, attr_value in elem.attrib.items():
        # Handle namespaced attributes
        if isinstance(attr_name, str) and attr_name.startswith("{"):
            attr_qname = etree.QName(attr_name)
            attr_local = attr_qname.localname
            attr_ns = attr_qname.namespace
        else:
            attr_local = attr_name
            attr_ns = None

        attributes.append(ParsedAttribute(
            name=attr_local,
            value=attr_value,
            namespace=attr_ns,
        ))

    # Get text content
    value = None
    if elem.text and elem.text.strip():
        value = elem.text.strip()

    # Convert children
    children: list[ParsedElement] = []
    for child in elem:
        if isinstance(child.tag, str):  # Skip comments, etc.
            child_elem = _convert_element(child, nsmap, current_xpath)
            children.append(child_elem)

    return ParsedElement(
        tag=local_name,
        namespace=namespace,
        value=value,
        attributes=attributes,
        children=children,
        position=position,
    )


def get_document_type(root: ParsedElement) -> str:
    """
    Determine the document type from the root element.

    Args:
        root: Root ParsedElement

    Returns:
        Document type name (e.g., 'Invoice')
    """
    return root.tag


def get_ubl_version(root: ParsedElement) -> str:
    """
    Extract the UBL version from the document.

    Looks for cbc:UBLVersionID element.

    Args:
        root: Root ParsedElement

    Returns:
        UBL version string, or '2.5' as default
    """
    version_elem = root.find_child("UBLVersionID")
    if version_elem and version_elem.value:
        return version_elem.value
    return "2.5"
