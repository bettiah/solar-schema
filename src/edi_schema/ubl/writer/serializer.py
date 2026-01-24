"""
UBL XML Serializer.

Serializes ParsedDocument/ParsedElement to XML with proper namespace handling.
"""

from typing import TextIO

from lxml import etree

from ..ast import ParsedDocument, ParsedElement
from ..enums import NAMESPACE_PREFIXES


class XMLSerializer:
    """
    Serializes UBL documents to XML.

    Handles namespace prefixes, indentation, and XML declarations.

    Usage:
        serializer = XMLSerializer()
        xml_string = serializer.serialize(document)
        serializer.serialize_to_file(document, "output.xml")
    """

    def __init__(
        self,
        pretty: bool = True,
        indent: int = 2,
        xml_declaration: bool = True,
        encoding: str = "UTF-8",
    ):
        """
        Initialize the serializer.

        Args:
            pretty: Whether to format output with indentation
            indent: Number of spaces for indentation (if pretty=True)
            xml_declaration: Whether to include XML declaration
            encoding: Character encoding for output
        """
        self.pretty = pretty
        self.indent = indent
        self.xml_declaration = xml_declaration
        self.encoding = encoding

    def serialize(self, document: ParsedDocument) -> str:
        """
        Serialize a document to an XML string.

        Args:
            document: The document to serialize

        Returns:
            XML string
        """
        root = self._build_lxml_tree(document)
        return self._to_string(root)

    def serialize_bytes(self, document: ParsedDocument) -> bytes:
        """
        Serialize a document to XML bytes.

        Args:
            document: The document to serialize

        Returns:
            XML as bytes
        """
        root = self._build_lxml_tree(document)
        return etree.tostring(
            root,
            pretty_print=self.pretty,
            xml_declaration=self.xml_declaration,
            encoding=self.encoding,
        )

    def serialize_to_file(
        self,
        document: ParsedDocument,
        path: str,
    ) -> None:
        """
        Serialize a document to a file.

        Args:
            document: The document to serialize
            path: Output file path
        """
        xml_bytes = self.serialize_bytes(document)
        with open(path, "wb") as f:
            f.write(xml_bytes)

    def serialize_to_stream(
        self,
        document: ParsedDocument,
        stream: TextIO,
    ) -> None:
        """
        Serialize a document to a text stream.

        Args:
            document: The document to serialize
            stream: Output stream
        """
        xml_string = self.serialize(document)
        stream.write(xml_string)

    def serialize_element(self, element: ParsedElement) -> str:
        """
        Serialize a single element to XML string.

        Args:
            element: The element to serialize

        Returns:
            XML string (without declaration)
        """
        nsmap = self._build_nsmap({})
        lxml_elem = self._element_to_lxml(element, nsmap)
        return etree.tostring(
            lxml_elem,
            pretty_print=self.pretty,
            encoding="unicode",
        )

    def _build_lxml_tree(self, document: ParsedDocument) -> etree._Element:
        """Build lxml element tree from document."""
        nsmap = self._build_nsmap(document.namespaces)
        return self._element_to_lxml(document.root, nsmap)

    def _build_nsmap(self, namespaces: dict[str, str]) -> dict[str | None, str]:
        """
        Build namespace map for lxml.

        Args:
            namespaces: Document namespace mappings

        Returns:
            Namespace map compatible with lxml
        """
        nsmap: dict[str | None, str] = {}

        # Add standard UBL namespaces
        for uri, prefix in NAMESPACE_PREFIXES.items():
            if prefix:  # Skip empty prefix
                nsmap[prefix] = uri

        # Add document namespaces (may override standards)
        for prefix, uri in namespaces.items():
            if prefix == "":
                nsmap[None] = uri  # Default namespace
            else:
                nsmap[prefix] = uri

        return nsmap

    def _element_to_lxml(
        self,
        element: ParsedElement,
        nsmap: dict[str | None, str],
    ) -> etree._Element:
        """
        Convert ParsedElement to lxml element.

        Args:
            element: The element to convert
            nsmap: Namespace map

        Returns:
            lxml Element
        """
        # Determine qualified tag name
        if element.namespace:
            qname = etree.QName(element.namespace, element.tag)
        else:
            qname = element.tag

        # Create element with namespace map (only on root)
        if element.namespace and element.namespace in [ns for ns in nsmap.values()]:
            lxml_elem = etree.Element(qname, nsmap=nsmap)
        else:
            lxml_elem = etree.Element(qname)

        # Add attributes
        for attr in element.attributes:
            if attr.namespace:
                attr_qname = etree.QName(attr.namespace, attr.name)
                lxml_elem.set(attr_qname, attr.value)
            else:
                lxml_elem.set(attr.name, attr.value)

        # Set text value
        if element.value is not None:
            lxml_elem.text = element.value

        # Add children
        for child in element.children:
            child_elem = self._element_to_lxml_child(child, nsmap)
            lxml_elem.append(child_elem)

        return lxml_elem

    def _element_to_lxml_child(
        self,
        element: ParsedElement,
        nsmap: dict[str | None, str],
    ) -> etree._Element:
        """
        Convert child ParsedElement to lxml element.

        Args:
            element: The element to convert
            nsmap: Namespace map (not applied to children)

        Returns:
            lxml Element
        """
        # Determine qualified tag name
        if element.namespace:
            qname = etree.QName(element.namespace, element.tag)
        else:
            qname = element.tag

        lxml_elem = etree.Element(qname)

        # Add attributes
        for attr in element.attributes:
            if attr.namespace:
                attr_qname = etree.QName(attr.namespace, attr.name)
                lxml_elem.set(attr_qname, attr.value)
            else:
                lxml_elem.set(attr.name, attr.value)

        # Set text value
        if element.value is not None:
            lxml_elem.text = element.value

        # Add children
        for child in element.children:
            child_elem = self._element_to_lxml_child(child, nsmap)
            lxml_elem.append(child_elem)

        return lxml_elem

    def _to_string(self, element: etree._Element) -> str:
        """Convert lxml element to string."""
        if self.xml_declaration:
            return etree.tostring(
                element,
                pretty_print=self.pretty,
                xml_declaration=True,
                encoding=self.encoding,
            ).decode(self.encoding)
        else:
            return etree.tostring(
                element,
                pretty_print=self.pretty,
                encoding="unicode",
            )


def serialize(
    document: ParsedDocument,
    pretty: bool = True,
    xml_declaration: bool = True,
) -> str:
    """
    Convenience function to serialize a document.

    Args:
        document: The document to serialize
        pretty: Whether to format output
        xml_declaration: Whether to include XML declaration

    Returns:
        XML string
    """
    serializer = XMLSerializer(pretty=pretty, xml_declaration=xml_declaration)
    return serializer.serialize(document)


def serialize_to_file(
    document: ParsedDocument,
    path: str,
    pretty: bool = True,
) -> None:
    """
    Convenience function to serialize a document to a file.

    Args:
        document: The document to serialize
        path: Output file path
        pretty: Whether to format output
    """
    serializer = XMLSerializer(pretty=pretty)
    serializer.serialize_to_file(document, path)
