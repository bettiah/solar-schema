"""
Schema Validator.

Validates document structure and cardinality against UBL schema.
"""

from collections import Counter

from ..ast import ErrorCategory, ParsedElement, SourcePosition
from ..enums import Cardinality
from ..models import ABIE, ASBIE, BBIE
from .core import ValidationContext


def validate_structure(element: ParsedElement, context: ValidationContext) -> None:
    """
    Validate element structure against schema.

    Checks that all elements match schema definitions.

    Args:
        element: The element to validate
        context: Validation context
    """
    component = element.schema_component

    # If no schema component bound, element is unknown
    if component is None and context.current_path:
        # Root element checked separately
        context.add_error(
            code="UNKNOWN_ELEMENT",
            message=f"Unknown element '{element.tag}'",
            category=ErrorCategory.SCHEMA,
            position=element.position,
            element=element.tag,
        )
        return

    # For ABIE elements, check that all children are valid
    if isinstance(component, ABIE):
        valid_bbie_names = {b.name for b in component.bbies}
        valid_asbie_names = {a.name for a in component.asbies}
        valid_names = valid_bbie_names | valid_asbie_names

        for child in element.children:
            if child.tag not in valid_names and child.schema_component is None:
                context.add_error(
                    code="UNEXPECTED_ELEMENT",
                    message=f"Unexpected element '{child.tag}' in '{element.tag}'",
                    category=ErrorCategory.SCHEMA,
                    position=child.position,
                    parent=element.tag,
                    child=child.tag,
                )


def validate_cardinality(element: ParsedElement, context: ValidationContext) -> None:
    """
    Validate element cardinality constraints.

    Checks that required elements are present and element counts
    are within allowed bounds.

    Args:
        element: The element to validate
        context: Validation context
    """
    component = element.schema_component

    if not isinstance(component, ABIE):
        return

    # Count child element occurrences
    child_counts = Counter(child.tag for child in element.children)

    # Check BBIEs
    for bbie in component.bbies:
        count = child_counts.get(bbie.name, 0)
        _check_cardinality(
            element_name=bbie.name,
            cardinality=bbie.cardinality,
            count=count,
            parent=element,
            context=context,
        )

    # Check ASBIEs
    for asbie in component.asbies:
        count = child_counts.get(asbie.name, 0)
        _check_cardinality(
            element_name=asbie.name,
            cardinality=asbie.cardinality,
            count=count,
            parent=element,
            context=context,
        )


def _check_cardinality(
    element_name: str,
    cardinality: Cardinality,
    count: int,
    parent: ParsedElement,
    context: ValidationContext,
) -> None:
    """
    Check if element count satisfies cardinality constraint.

    Args:
        element_name: Name of the element being checked
        cardinality: The cardinality constraint
        count: Actual count of elements
        parent: Parent element (for position reporting)
        context: Validation context
    """
    min_occurs = cardinality.min_occurs
    max_occurs = cardinality.max_occurs

    if count < min_occurs:
        context.add_error(
            code="MISSING_REQUIRED_ELEMENT",
            message=f"Required element '{element_name}' is missing in '{parent.tag}'",
            category=ErrorCategory.SCHEMA,
            position=parent.position,
            element=element_name,
            parent=parent.tag,
            min_occurs=min_occurs,
            actual_count=count,
        )

    if max_occurs is not None and count > max_occurs:
        context.add_error(
            code="TOO_MANY_ELEMENTS",
            message=f"Element '{element_name}' appears {count} times in '{parent.tag}', maximum is {max_occurs}",
            category=ErrorCategory.SCHEMA,
            position=parent.position,
            element=element_name,
            parent=parent.tag,
            max_occurs=max_occurs,
            actual_count=count,
        )


def validate_element_order(element: ParsedElement, context: ValidationContext) -> None:
    """
    Validate element order against schema.

    In strict mode, checks that elements appear in schema-defined order.
    Note: UBL generally uses xs:all, which doesn't require specific order.

    Args:
        element: The element to validate
        context: Validation context
    """
    # UBL typically uses xs:all, so order is not strictly enforced
    # This validator is provided for future use or strict validation modes
    pass


def get_missing_required_elements(
    element: ParsedElement,
    schema: ABIE,
) -> list[str]:
    """
    Get list of missing required elements.

    Args:
        element: The parsed element to check
        schema: The ABIE schema

    Returns:
        List of missing required element names
    """
    child_names = {child.tag for child in element.children}
    missing = []

    for bbie in schema.bbies:
        if bbie.cardinality.is_required and bbie.name not in child_names:
            missing.append(bbie.name)

    for asbie in schema.asbies:
        if asbie.cardinality.is_required and asbie.name not in child_names:
            missing.append(asbie.name)

    return missing


def get_unexpected_elements(
    element: ParsedElement,
    schema: ABIE,
) -> list[str]:
    """
    Get list of unexpected elements not in schema.

    Args:
        element: The parsed element to check
        schema: The ABIE schema

    Returns:
        List of unexpected element names
    """
    valid_names = {b.name for b in schema.bbies} | {a.name for a in schema.asbies}
    unexpected = []

    for child in element.children:
        if child.tag not in valid_names:
            unexpected.append(child.tag)

    return unexpected
