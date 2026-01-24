"""
Document Schema Parser.

Parses UBL maindoc/*.xsd files to extract document type definitions.
"""

from pathlib import Path

from lxml import etree

from ..models import ABIE, ASBIE, BBIE, DocumentType
from ..enums import Cardinality, Namespace
from .base import (
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


def _get_documentation(element: etree._Element) -> str:
    """Extract simple documentation text."""
    docs = element.xpath(
        "xsd:annotation/xsd:documentation/text()",
        namespaces=NSMAP,
    )
    if docs:
        return docs[0].strip()
    return ""


def _parse_cardinality(meta: dict[str, str], elem: etree._Element) -> Cardinality:
    """Determine cardinality from CCTS metadata or XSD attributes."""
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

    min_occurs = int(elem.get("minOccurs", "1"))
    max_occurs_str = elem.get("maxOccurs", "1")
    max_occurs: int | None = None if max_occurs_str == "unbounded" else int(max_occurs_str)

    return Cardinality.from_min_max(min_occurs, max_occurs)


def parse_document_schema(path: Path) -> DocumentType:
    """
    Parse a document schema file (e.g., UBL-Invoice-2.5.xsd).

    Args:
        path: Path to the document XSD file

    Returns:
        DocumentType with the root ABIE definition
    """
    root = parse_xsd(path)

    # Get target namespace
    namespace = root.get("targetNamespace", "")

    # Extract document name from namespace or filename
    if namespace:
        # urn:oasis:names:specification:ubl:schema:xsd:Invoice-2 -> Invoice
        parts = namespace.split(":")
        if parts:
            doc_name = parts[-1].replace("-2", "")
        else:
            doc_name = path.stem.replace("UBL-", "").replace("-2.5", "")
    else:
        doc_name = path.stem.replace("UBL-", "").replace("-2.5", "")

    # Find root element declaration
    root_element_name = ""
    definition = ""
    for elem in get_elements(root):
        name = elem.get("name", "")
        if name:
            root_element_name = name
            definition = _get_documentation(elem)
            break

    # Find and parse the root complexType
    root_abie: ABIE | None = None
    for complex_type in get_complex_types(root):
        type_name = complex_type.get("name", "")
        if not type_name:
            continue

        # The root type should match the document name
        expected_type = f"{doc_name}Type"
        if type_name != expected_type:
            continue

        meta = _get_ccts_metadata(complex_type)
        type_def = meta.get("Definition", definition)
        object_class = meta.get("ObjectClass", doc_name)

        # Parse child elements
        bbies: list[BBIE] = []
        asbies: list[ASBIE] = []

        for elem in get_sequence_elements(complex_type):
            ref = elem.get("ref", "")
            if not ref:
                continue

            prefix, local_name = parse_type_reference(ref)
            elem_meta = _get_ccts_metadata(elem)
            cardinality = _parse_cardinality(elem_meta, elem)

            # Skip extension elements
            if prefix == "ext":
                continue

            # Determine if BBIE or ASBIE
            if prefix == "cbc":
                bbie = BBIE(
                    name=local_name,
                    definition=elem_meta.get("Definition", ""),
                    cardinality=cardinality,
                    data_type=local_name,
                    representation_term=elem_meta.get("RepresentationTerm", "Text"),
                    property_term=elem_meta.get("PropertyTerm", ""),
                    object_class=object_class,
                    examples=_get_examples(elem_meta),
                    alternative_terms=_get_alternative_terms(elem_meta),
                )
                bbies.append(bbie)
            elif prefix == "cac":
                asbie = ASBIE(
                    name=local_name,
                    definition=elem_meta.get("Definition", ""),
                    cardinality=cardinality,
                    associated_abie=local_name,  # Will be resolved later
                    property_term=elem_meta.get("PropertyTerm", ""),
                    object_class=object_class,
                )
                asbies.append(asbie)

        root_abie = ABIE(
            name=doc_name,
            definition=type_def,
            object_class=object_class,
            bbies=bbies,
            asbies=asbies,
            namespace=namespace,
        )
        break

    if root_abie is None:
        # Create minimal ABIE if parsing failed
        root_abie = ABIE(
            name=doc_name,
            definition=definition,
            namespace=namespace,
        )

    return DocumentType(
        name=doc_name,
        namespace=namespace,
        definition=definition,
        root_element=root_element_name,
        root_abie=root_abie,
    )


def _get_examples(meta: dict[str, str]) -> list[str]:
    """Extract example values from CCTS metadata."""
    examples = meta.get("Examples", "")
    if examples:
        return [ex.strip() for ex in examples.split(",")]
    return []


def _get_alternative_terms(meta: dict[str, str]) -> list[str]:
    """Extract alternative business terms from CCTS metadata."""
    terms = meta.get("AlternativeBusinessTerms", "")
    if terms:
        return [t.strip() for t in terms.split(",")]
    return []


def list_document_schemas(maindoc_path: Path) -> list[str]:
    """
    List all available document schema names.

    Args:
        maindoc_path: Path to the maindoc/ directory

    Returns:
        List of document type names (e.g., ['Invoice', 'Order', ...])
    """
    names = []
    for xsd_file in sorted(maindoc_path.glob("UBL-*.xsd")):
        # UBL-Invoice-2.5.xsd -> Invoice
        name = xsd_file.stem.replace("UBL-", "").replace("-2.5", "")
        names.append(name)
    return names
