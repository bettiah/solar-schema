"""
Declarative Mapping Type Definitions.

Core dataclasses for defining X12 ↔ Semantic mappings as data structures.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .transforms import Transform
    from .validation import ValidationRule


# =============================================================================
# Path Types - Addressing elements in source/target structures
# =============================================================================


@dataclass(frozen=True)
class SegmentPath:
    """
    Path to element in X12 transaction content.

    Examples:
        seg("BEG", 3)           -> BEG segment, element 3
        seg("DTM", 2, loop="N1") -> DTM within N1 loop, element 2
        seg("N1", 1, qualifier=(1, "BY")) -> N1 where element 1 == "BY"
    """

    segment: str  # Segment tag: "BEG", "N1", "PO1"
    element: int | None = None  # 1-indexed element position
    component: int | None = None  # For composite elements (1-indexed)
    loop: str | None = None  # Loop context: "N1", "PO1"
    qualifier: tuple[int, str] | None = None  # (element_idx, value) filter

    def __str__(self) -> str:
        parts = [self.segment]
        if self.element:
            parts.append(f"*{self.element:02d}")
        if self.component:
            parts.append(f":{self.component}")
        if self.loop:
            parts.append(f" (loop={self.loop})")
        if self.qualifier:
            parts.append(f" [*{self.qualifier[0]}={self.qualifier[1]}]")
        return "".join(parts)


@dataclass(frozen=True)
class EnvelopePath:
    """
    Path to element in ISA/GS envelope.

    Examples:
        env("ISA", 6)  -> ISA06 (Sender ID)
        env("GS", 8)   -> GS08 (Version)
    """

    segment: str  # "ISA" or "GS"
    element: int  # 1-indexed element position

    def __str__(self) -> str:
        return f"{self.segment}{self.element:02d}"


@dataclass(frozen=True)
class ContextPath:
    """
    Path to external context metadata.

    Examples:
        ctx("filename")         -> MessageContext.filename
        ctx("received_at")      -> MessageContext.received_at
        ctx("custom.my_key")    -> MessageContext.custom["my_key"]
    """

    key: str  # Dot-separated path: "filename", "custom.my_key"

    def __str__(self) -> str:
        return f"ctx.{self.key}"


@dataclass(frozen=True)
class SemanticPath:
    """
    Path to field in semantic model.

    Examples:
        sem("id")                                    -> Order.id
        sem("buyer_customer_party.party.name")       -> nested field
        sem("order_lines[]")                         -> list field
        sem("delivery[0].delivery_party")            -> indexed list
        sem("delivery[+].delivery_party")            -> append to list
    """

    path: str  # Dot-separated path with optional [] for lists

    def __str__(self) -> str:
        return self.path


# =============================================================================
# Path Helper Functions
# =============================================================================


def seg(
    segment: str,
    element: int | None = None,
    *,
    component: int | None = None,
    loop: str | None = None,
    qualifier: tuple[int, str] | None = None,
) -> SegmentPath:
    """Create a SegmentPath for transaction content."""
    return SegmentPath(
        segment=segment,
        element=element,
        component=component,
        loop=loop,
        qualifier=qualifier,
    )


def env(segment: str, element: int) -> EnvelopePath:
    """Create an EnvelopePath for ISA/GS envelope data."""
    return EnvelopePath(segment=segment, element=element)


def ctx(key: str) -> ContextPath:
    """Create a ContextPath for external metadata."""
    return ContextPath(key=key)


def sem(path: str) -> SemanticPath:
    """Create a SemanticPath for semantic model fields."""
    return SemanticPath(path=path)


# =============================================================================
# Mapping Types
# =============================================================================


@dataclass
class FieldMapping:
    """
    Maps a single source field to a semantic target field.

    Supports transforms for data conversion and error handling options.
    """

    x12: SegmentPath | EnvelopePath | ContextPath  # Source path
    semantic: SemanticPath  # Target path
    to_semantic_transform: "Transform | None" = None  # X12 → Semantic
    from_semantic_transform: "Transform | None" = None  # Semantic → X12
    required: bool = False  # Is this field required?
    default: Any = None  # Default value if missing

    # Error handling options
    fallback: Any = None  # Value to use if transform fails

    def __str__(self) -> str:
        return f"{self.x12} → {self.semantic}"


@dataclass
class QualifiedMapping:
    """
    Maps qualified segments (like DTM, REF) where first element determines target.

    The qualifier element value routes to different semantic paths.

    Example:
        DTM*002*20241206 → delivery[0].requested_delivery_period.start_date
        DTM*010*20241206 → delivery[0].despatch.requested_despatch_date
    """

    qualifier_path: SegmentPath  # Path to qualifier element (e.g., seg("DTM", 1))
    mappings: dict[str, list[FieldMapping]]  # Qualifier value → field mappings
    loop: str | None = None  # Optional loop context

    def __str__(self) -> str:
        qualifiers = ", ".join(self.mappings.keys())
        return f"Qualified({self.qualifier_path.segment}): [{qualifiers}]"


@dataclass
class LoopMapping:
    """
    Maps a repeating loop to a list in the semantic model.

    Each iteration of the loop creates one item in the list.
    """

    loop_id: str  # Loop identifier: "PO1", "N1"
    semantic_path: SemanticPath  # Target list path: "order_lines"
    item_type: type  # Type of items in list: OrderLine
    field_mappings: list[FieldMapping] = field(default_factory=list)
    qualified_mappings: list[QualifiedMapping] = field(default_factory=list)
    nested_loops: list["LoopMapping"] = field(default_factory=list)

    def __str__(self) -> str:
        return f"Loop({self.loop_id}) → {self.semantic_path}"


@dataclass
class PartyLoopMapping:
    """
    Maps N1-style party loops where a qualifier determines the target party field.

    The first element of N1 (entity identifier code) determines which party
    field to populate.
    """

    loop_id: str  # Usually "N1"
    party_field_map: dict[str, SemanticPath]  # Qualifier → semantic path
    field_mappings: list[FieldMapping] = field(default_factory=list)
    contact_mappings: list[FieldMapping] = field(default_factory=list)

    def __str__(self) -> str:
        parties = ", ".join(self.party_field_map.keys())
        return f"PartyLoop({self.loop_id}): [{parties}]"


@dataclass
class TransactionMapping:
    """
    Complete mapping definition for an X12 transaction type.

    Defines how to map an entire transaction (e.g., 850) to a semantic model.
    """

    transaction_id: str  # "850", "810", etc.
    semantic_type: type  # Target model class: Order, Invoice

    # Direct field mappings (header-level segments)
    field_mappings: list[FieldMapping] = field(default_factory=list)

    # Qualified mappings (DTM, REF with qualifiers)
    qualified_mappings: list[QualifiedMapping] = field(default_factory=list)

    # Loop mappings (PO1, IT1, etc.)
    loop_mappings: list[LoopMapping] = field(default_factory=list)

    # Party loop mappings (N1 with party qualifiers)
    party_mappings: list[PartyLoopMapping] = field(default_factory=list)

    # Envelope mappings (ISA/GS → semantic fields)
    envelope_mappings: list[FieldMapping] = field(default_factory=list)

    # Context mappings (external metadata → semantic fields)
    context_mappings: list[FieldMapping] = field(default_factory=list)

    # Validation rules to run after mapping
    validation_rules: list["ValidationRule"] = field(default_factory=list)

    # Whether to run validation automatically
    validate_on_map: bool = True

    def __str__(self) -> str:
        return f"TransactionMapping({self.transaction_id} → {self.semantic_type.__name__})"


# Type alias for source path types
SourcePath = SegmentPath | EnvelopePath | ContextPath
