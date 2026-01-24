"""
UBL Abstract Syntax Tree (AST) Types.

Defines the node types for representing parsed UBL documents:
- SourcePosition - location tracking for errors
- ParsedElement - parsed XML element with schema binding
- ParsedDocument - complete parsed document
- ParseError - error with position and context
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .models import ABIE, ASBIE, BBIE


class ErrorSeverity(str, Enum):
    """Error severity levels."""

    WARNING = "warning"
    ERROR = "error"
    FATAL = "fatal"


class ErrorCategory(str, Enum):
    """Error category for classification."""

    STRUCTURAL = "structural"  # XML well-formedness
    SCHEMA = "schema"  # Element presence/cardinality
    ELEMENT = "element"  # Data type/format
    CODE = "code"  # Code list validation
    BUSINESS = "business"  # Business rule validation


@dataclass
class SourcePosition:
    """
    Position in the source XML document.

    Attributes:
        line: Line number (1-indexed)
        column: Column number (1-indexed)
        xpath: XPath to the element
    """

    line: int
    column: int
    xpath: str = ""

    def __str__(self) -> str:
        if self.xpath:
            return f"line {self.line}, column {self.column} ({self.xpath})"
        return f"line {self.line}, column {self.column}"


@dataclass
class ParsedAttribute:
    """
    A parsed XML attribute.

    Attributes:
        name: Local name of the attribute
        value: Attribute value
        namespace: Namespace URI (if any)
    """

    name: str
    value: str
    namespace: str | None = None


@dataclass
class ParsedElement:
    """
    A parsed XML element with optional schema binding.

    Represents a single element in the parsed document tree.
    Can be a BBIE (leaf with text value) or an ABIE/ASBIE (with children).

    Attributes:
        tag: Local tag name
        namespace: Namespace URI
        value: Text content (for leaf elements)
        attributes: List of parsed attributes
        children: List of child elements
        position: Source position for error reporting
        schema_component: Bound schema component (ABIE, BBIE, or ASBIE)
    """

    tag: str
    namespace: str
    value: str | None = None
    attributes: list[ParsedAttribute] = field(default_factory=list)
    children: list["ParsedElement"] = field(default_factory=list)
    position: SourcePosition | None = None
    schema_component: ABIE | BBIE | ASBIE | None = None

    @property
    def qualified_name(self) -> str:
        """Return the namespace-qualified name."""
        if self.namespace:
            return f"{{{self.namespace}}}{self.tag}"
        return self.tag

    def get_attribute(self, name: str) -> str | None:
        """Get an attribute value by name."""
        for attr in self.attributes:
            if attr.name == name:
                return attr.value
        return None

    def find_child(self, tag: str) -> "ParsedElement | None":
        """Find first child with the given tag."""
        for child in self.children:
            if child.tag == tag:
                return child
        return None

    def find_all_children(self, tag: str) -> list["ParsedElement"]:
        """Find all children with the given tag."""
        return [child for child in self.children if child.tag == tag]

    def get_text(self) -> str:
        """
        Get the text content of this element.

        Returns:
            The value if set, or concatenated text of all children.
        """
        if self.value is not None:
            return self.value
        # For complex elements, concatenate child values
        texts = []
        for child in self.children:
            text = child.get_text()
            if text:
                texts.append(text)
        return " ".join(texts)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to a dictionary representation.

        Returns:
            Dictionary with element data.
        """
        result: dict[str, Any] = {"tag": self.tag}

        if self.value is not None:
            result["value"] = self.value

        if self.attributes:
            result["attributes"] = {
                attr.name: attr.value for attr in self.attributes
            }

        if self.children:
            result["children"] = [child.to_dict() for child in self.children]

        return result


@dataclass
class ParsedDocument:
    """
    A complete parsed UBL document.

    Attributes:
        document_type: Document type name (e.g., 'Invoice')
        version: UBL version (e.g., '2.5')
        root: Root element of the parsed tree
        namespaces: Namespace prefix mappings
    """

    document_type: str
    version: str
    root: ParsedElement
    namespaces: dict[str, str] = field(default_factory=dict)

    def get_value(self, xpath: str) -> str | None:
        """
        Get a value using a simplified XPath-like syntax.

        Supports: 'Element', 'Element/Child', 'Element/Child/@attr'

        Args:
            xpath: Path to the value

        Returns:
            The value, or None if not found
        """
        parts = xpath.split("/")
        current: ParsedElement | None = self.root

        for part in parts:
            if current is None:
                return None

            if part.startswith("@"):
                # Attribute lookup
                attr_name = part[1:]
                return current.get_attribute(attr_name)
            else:
                # Child element lookup
                current = current.find_child(part)

        return current.get_text() if current else None


@dataclass
class ParseError:
    """
    An error encountered during parsing or validation.

    Attributes:
        code: Error code for categorization
        message: Human-readable error message
        severity: Error severity level
        category: Error category
        position: Source position where error occurred
        xpath: XPath to the problematic element
        expected: What was expected (optional)
        actual: What was found (optional)
    """

    code: str
    message: str
    severity: ErrorSeverity = ErrorSeverity.ERROR
    category: ErrorCategory = ErrorCategory.SCHEMA
    position: SourcePosition | None = None
    xpath: str | None = None
    expected: str | None = None
    actual: str | None = None

    def __str__(self) -> str:
        parts = [f"[{self.code}] {self.message}"]
        if self.position:
            parts.append(f" at {self.position}")
        elif self.xpath:
            parts.append(f" at {self.xpath}")
        return "".join(parts)


@dataclass
class ParseResult:
    """
    Result of parsing a UBL document.

    Attributes:
        document: The parsed document (if successful)
        errors: List of errors encountered
        warnings: List of warnings encountered
    """

    document: ParsedDocument | None = None
    errors: list[ParseError] = field(default_factory=list)
    warnings: list[ParseError] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Check if parsing succeeded without errors."""
        return self.document is not None and len(self.errors) == 0

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return len(self.warnings) > 0

    def add_error(self, error: ParseError) -> None:
        """Add an error to the result."""
        if error.severity == ErrorSeverity.WARNING:
            self.warnings.append(error)
        else:
            self.errors.append(error)


@dataclass
class ParseStatistics:
    """
    Statistics about a parsed document.

    Attributes:
        element_count: Total number of elements
        attribute_count: Total number of attributes
        depth: Maximum nesting depth
        document_type: Document type name
    """

    element_count: int = 0
    attribute_count: int = 0
    depth: int = 0
    document_type: str = ""

    @classmethod
    def from_document(cls, doc: ParsedDocument) -> "ParseStatistics":
        """Create statistics from a parsed document."""
        stats = cls(document_type=doc.document_type)
        stats._count_elements(doc.root, 0)
        return stats

    def _count_elements(self, elem: ParsedElement, depth: int) -> None:
        """Recursively count elements and track depth."""
        self.element_count += 1
        self.attribute_count += len(elem.attributes)
        self.depth = max(self.depth, depth)

        for child in elem.children:
            self._count_elements(child, depth + 1)
