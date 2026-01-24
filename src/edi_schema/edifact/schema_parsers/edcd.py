"""
EDIFACT Composite Element Parser (EDCD).

Parses the EDCD (Element Composite Data) file which contains composite
element definitions. Each composite groups related data elements.

File format:
       C001 TRANSPORT MEANS

       Desc: Code and/or name identifying the type of means of
             transport.

010    8179  Transport means description code          C      an..8
020    1131  Code list identification code             C      an..17
030    3055  Code list responsible agency code         C      an..3
040    8178  Transport means description               C      an..17

----------------------------------------------------------------------
"""

import re
from pathlib import Path

from ..models import Component, Composite
from .base import (
    clean_text,
    is_section_separator,
    parse_mandatory_indicator,
    read_file_lines,
    strip_change_indicator,
)

# Pattern for composite header line
# Example: "       C001 TRANSPORT MEANS"
COMPOSITE_HEADER_PATTERN = re.compile(r"^[*#|+X\s]\s{5,6}(C\d{3})\s+(.+)$")

# Pattern for component line
# Example: "010    8179  Transport means description code          C      an..8"
# Fields: position, element_tag, name, mandatory (M/C), repr
COMPONENT_PATTERN = re.compile(r"^(\d{3})\s+(\d{4})\s+(.+?)\s+([MC])\s+(an?|n)(\.\.)?\d+\s*$")

# Pattern for component line continuation (when name spans multiple lines)
# Example: "             identifier                                C      an..256"
COMPONENT_CONTINUATION_PATTERN = re.compile(r"^\s{13,}(.+?)\s+([MC])\s+(an?|n)(\.\.)?\d+\s*$")

# Pattern for Desc: line
DESC_PATTERN = re.compile(r"^\s+Desc:\s*(.*)$")


def parse_edcd(path: Path) -> dict[str, Composite]:
    """
    Parse an EDCD (composite element directory) file.

    Args:
        path: Path to the EDCD file (e.g., EDCD.22B)

    Returns:
        Dictionary mapping composite tags to Composite objects.

        Example:
            {
                'C001': Composite(
                    tag='C001',
                    name='TRANSPORT MEANS',
                    description='Code and/or name identifying...',
                    components=[
                        Component(position=10, element_tag='8179', mandatory=False),
                        Component(position=20, element_tag='1131', mandatory=False),
                        ...
                    ]
                ),
                ...
            }
    """
    lines = read_file_lines(path)
    result: dict[str, Composite] = {}

    current_tag: str | None = None
    current_name: str | None = None
    current_desc_parts: list[str] = []
    current_components: list[Component] = []
    in_header = True
    in_description = False
    pending_position: int | None = None
    pending_element: str | None = None
    pending_name_parts: list[str] = []

    for line in lines:
        # Skip section separators and save previous composite
        if is_section_separator(line):
            in_header = False
            # Save any pending component
            if pending_position is not None and pending_element is not None:
                _save_pending_component(
                    current_components,
                    pending_position,
                    pending_element,
                    pending_name_parts,
                )
            # Save previous composite
            if current_tag is not None:
                _save_composite(
                    result,
                    current_tag,
                    current_name or "",
                    current_desc_parts,
                    current_components,
                )
            # Reset for next composite
            current_tag = None
            current_name = None
            current_desc_parts = []
            current_components = []
            in_description = False
            pending_position = None
            pending_element = None
            pending_name_parts = []
            continue

        if in_header:
            continue

        # Normalize change indicators
        normalized = strip_change_indicator(line)

        # Check for composite header
        header_match = COMPOSITE_HEADER_PATTERN.match(normalized)
        if header_match:
            current_tag = header_match.group(1)
            current_name = header_match.group(2).strip()
            in_description = False
            continue

        # Check for Desc: line
        desc_match = DESC_PATTERN.match(normalized)
        if desc_match:
            in_description = True
            desc_text = desc_match.group(1).strip()
            if desc_text:
                current_desc_parts.append(desc_text)
            continue

        # Check for component line
        component_match = COMPONENT_PATTERN.match(normalized)
        if component_match:
            in_description = False
            # Save any pending component
            if pending_position is not None and pending_element is not None:
                _save_pending_component(
                    current_components,
                    pending_position,
                    pending_element,
                    pending_name_parts,
                )

            # Start new component
            pending_position = int(component_match.group(1))
            pending_element = component_match.group(2)
            mandatory = parse_mandatory_indicator(component_match.group(4))
            pending_name_parts = [component_match.group(3).strip()]

            # Create component immediately since we have all info
            current_components.append(
                Component(
                    position=pending_position,
                    element_tag=pending_element,
                    mandatory=mandatory,
                )
            )
            pending_position = None
            pending_element = None
            pending_name_parts = []
            continue

        # Check for component continuation line (name spans multiple lines)
        cont_match = COMPONENT_CONTINUATION_PATTERN.match(normalized)
        if cont_match:
            in_description = False
            # This is a continuation with the M/C and repr
            # We need to handle multi-line component names
            # Save any pending from before
            if pending_position is not None and pending_element is not None:
                # Complete the pending component
                mandatory = parse_mandatory_indicator(cont_match.group(2))
                pending_name_parts.append(cont_match.group(1).strip())
                current_components.append(
                    Component(
                        position=pending_position,
                        element_tag=pending_element,
                        mandatory=mandatory,
                    )
                )
                pending_position = None
                pending_element = None
                pending_name_parts = []
            continue

        # Check for partial component line (position and element, name continues)
        partial_match = re.match(r"^(\d{3})\s+(\d{4})\s+(.+?)$", normalized)
        if partial_match:
            in_description = False
            # Save any pending
            if pending_position is not None and pending_element is not None:
                _save_pending_component(
                    current_components,
                    pending_position,
                    pending_element,
                    pending_name_parts,
                )

            # Start pending component
            pending_position = int(partial_match.group(1))
            pending_element = partial_match.group(2)
            pending_name_parts = [partial_match.group(3).strip()]
            continue

        # Description continuation
        stripped = normalized.strip()
        if in_description and stripped and not stripped.startswith("Note:"):
            current_desc_parts.append(stripped)

    # Save final pending component
    if pending_position is not None and pending_element is not None:
        _save_pending_component(
            current_components,
            pending_position,
            pending_element,
            pending_name_parts,
        )

    # Save final composite
    if current_tag is not None:
        _save_composite(
            result,
            current_tag,
            current_name or "",
            current_desc_parts,
            current_components,
        )

    return result


def _save_pending_component(
    components: list[Component],
    position: int,
    element_tag: str,
    name_parts: list[str],
) -> None:
    """Save a pending component (when we only have position and element)."""
    # This shouldn't happen normally since we always have M/C indicator
    components.append(
        Component(
            position=position,
            element_tag=element_tag,
            mandatory=False,  # Default to conditional if unknown
        )
    )


def _save_composite(
    result: dict[str, Composite],
    tag: str,
    name: str,
    desc_parts: list[str],
    components: list[Component],
) -> None:
    """Create and save a Composite to the result dictionary."""
    description = clean_text(" ".join(desc_parts)) if desc_parts else ""
    composite = Composite(
        tag=tag,
        name=name,
        description=description,
        components=sorted(components, key=lambda c: c.position),
    )
    result[tag] = composite
