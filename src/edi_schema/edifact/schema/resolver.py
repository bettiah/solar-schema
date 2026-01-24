"""
EDIFACT Schema Resolver.

Resolves cross-references between schema components:
- Links data elements to composites
- Links composites and elements to segments
- Links segments to message structures
"""

from ..models import (
    Composite,
    DataElement,
    MessageSpec,
    ResolvedMessageSpec,
    Segment,
    SegmentGroup,
    SegmentRef,
)
from .registry import EdifactRegistry


class EdifactResolver:
    """
    Resolves cross-references between EDIFACT schema components.

    Takes a registry with parsed components and resolves all references
    to create fully-linked schemas.
    """

    def __init__(self, registry: EdifactRegistry) -> None:
        """
        Initialize resolver with a registry.

        Args:
            registry: Registry containing parsed components
        """
        self.registry = registry

    def resolve_all(self) -> None:
        """
        Resolve all cross-references in the registry.

        This resolves:
        1. Element references in composites
        2. Composite/element references in segments
        """
        self._resolve_composites()
        self._resolve_segments()

    def _resolve_composites(self) -> None:
        """Resolve element references in composites."""
        for composite in self.registry.composites.values():
            for component in composite.components:
                component.element = self.registry.get_element(component.element_tag)

    def _resolve_segments(self) -> None:
        """Resolve composite/element references in segments."""
        for segment in self.registry.segments.values():
            for element in segment.elements:
                if element.is_composite:
                    element.resolved = self.registry.get_composite(element.tag)
                else:
                    element.resolved = self.registry.get_element(element.tag)

    def resolve_message(self, message: MessageSpec) -> ResolvedMessageSpec:
        """
        Create a fully resolved message specification.

        Resolves all segment references in the message structure
        and collects all referenced components.

        Args:
            message: Message specification to resolve

        Returns:
            ResolvedMessageSpec with all references linked and
            dictionaries of used components
        """
        # Collect all used components
        used_segments: dict[str, Segment] = {}
        used_composites: dict[str, Composite] = {}
        used_elements: dict[str, DataElement] = {}

        # Resolve structure and collect used components
        self._resolve_structure(
            message.structure,
            used_segments,
            used_composites,
            used_elements,
        )

        return ResolvedMessageSpec(
            spec=message,
            segments=used_segments,
            composites=used_composites,
            elements=used_elements,
        )

    def _resolve_structure(
        self,
        items: list[SegmentRef | SegmentGroup],
        used_segments: dict[str, Segment],
        used_composites: dict[str, Composite],
        used_elements: dict[str, DataElement],
    ) -> None:
        """
        Recursively resolve segment references in a structure.

        Modifies items in place to link segment references
        and collects all used components.
        """
        for item in items:
            if isinstance(item, SegmentRef):
                # Resolve segment reference
                segment = self.registry.get_segment(item.segment_tag)
                item.segment = segment

                if segment:
                    self._collect_segment_components(
                        segment,
                        used_segments,
                        used_composites,
                        used_elements,
                    )

            elif isinstance(item, SegmentGroup):
                # Recursively resolve children
                self._resolve_structure(
                    item.children,
                    used_segments,
                    used_composites,
                    used_elements,
                )

    def _collect_segment_components(
        self,
        segment: Segment,
        used_segments: dict[str, Segment],
        used_composites: dict[str, Composite],
        used_elements: dict[str, DataElement],
    ) -> None:
        """
        Collect all components used by a segment.

        Adds the segment and all its elements/composites to the
        appropriate dictionaries.
        """
        if segment.tag in used_segments:
            return  # Already processed

        used_segments[segment.tag] = segment

        for seg_element in segment.elements:
            if seg_element.is_composite:
                composite = self.registry.get_composite(seg_element.tag)
                if composite and composite.tag not in used_composites:
                    used_composites[composite.tag] = composite

                    # Collect elements within the composite
                    for component in composite.components:
                        element = self.registry.get_element(component.element_tag)
                        if element and element.tag not in used_elements:
                            used_elements[element.tag] = element
            else:
                element = self.registry.get_element(seg_element.tag)
                if element and element.tag not in used_elements:
                    used_elements[element.tag] = element


def collect_segment_tags(
    structure: list[SegmentRef | SegmentGroup],
) -> set[str]:
    """
    Collect all segment tags referenced in a message structure.

    Args:
        structure: Message structure (list of SegmentRef and SegmentGroup)

    Returns:
        Set of segment tags
    """
    tags = set()

    def _collect(items: list[SegmentRef | SegmentGroup]) -> None:
        for item in items:
            if isinstance(item, SegmentRef):
                tags.add(item.segment_tag)
            elif isinstance(item, SegmentGroup):
                _collect(item.children)

    _collect(structure)
    return tags
