"""
Handler protocols, context, and utilities for the Builder Mapping Engine.

Provides the foundation for single-pass mapping using a Box dict accumulator.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from box import Box

if TYPE_CHECKING:
    from edi_schema.semantic.mapping.diagnostics import MappingMetrics, MappingTrace
    from edi_schema.semantic.mapping.errors import ErrorAccumulator
    from edi_schema.x12.ast import LoopInstance, ParsedSegment


# =============================================================================
# Handler Protocols
# =============================================================================


@runtime_checkable
class SegmentHandler(Protocol):
    """Protocol for handlers that process a single parsed segment."""

    def handle(
        self,
        segment: ParsedSegment,
        builder: Box,
        ctx: HandlerContext,
    ) -> None: ...


@runtime_checkable
class LoopHandler(Protocol):
    """Protocol for handlers that process a loop instance."""

    def handle(
        self,
        loop: LoopInstance,
        builder: Box,
        ctx: HandlerContext,
    ) -> None: ...


# =============================================================================
# Handler Context
# =============================================================================


@dataclass
class HandlerContext:
    """Shared context passed to every handler during a single to_semantic() call."""

    metrics: MappingMetrics | None
    trace: MappingTrace | None
    accumulator: ErrorAccumulator
    transaction_id: str = ""

    # Tracks append counters per list path (e.g. "delivery" -> 1 means next is [1])
    _list_indices: dict[str, int] = field(default_factory=dict)

    def next_index(self, list_path: str) -> int:
        """Return the next available index for a list path, then increment."""
        idx = self._list_indices.get(list_path, 0)
        self._list_indices[list_path] = idx + 1
        return idx

    def current_index(self, list_path: str) -> int:
        """Return the current index for a list path without incrementing."""
        return self._list_indices.get(list_path, 0)

    def peek_index(self, list_path: str) -> int:
        """Return the next index that would be returned by next_index, without consuming it."""
        return self._list_indices.get(list_path, 0)


# =============================================================================
# Box Path Utilities
# =============================================================================

# Regex to match path segments: either a name or [N]/[+]
_PATH_TOKEN_RE = re.compile(r"([^.\[\]]+)|\[(\d+|\+)\]")


def set_box_path(
    builder: Box,
    path: str,
    value: Any,
    ctx: HandlerContext | None = None,
) -> None:
    """
    Set a value in a Box dict at the given dot/bracket path.

    Handles:
    - Dot paths: "order_reference.id"
    - Indexed lists: "delivery[0].delivery_terms.code"
    - Append syntax: "delivery[+].delivery_party" (uses ctx.next_index)
    - Auto-vivification of intermediate dicts via Box

    Lists are created as Python lists (not Box auto-vivified dicts).
    """
    tokens = _tokenize_path(path)
    if not tokens:
        return

    current: Any = builder

    for i, token in enumerate(tokens[:-1]):
        current = _navigate_token(current, token, ctx, create=True)
        if current is None:
            return

    # Set the final value
    final = tokens[-1]
    _set_final_token(current, final, value, ctx)


def _tokenize_path(path: str) -> list[str]:
    """Split a path like 'delivery[0].party.name' into tokens."""
    tokens: list[str] = []
    for m in _PATH_TOKEN_RE.finditer(path):
        name, bracket = m.groups()
        if name is not None:
            tokens.append(name)
        elif bracket is not None:
            tokens.append(f"[{bracket}]")
    return tokens


def _navigate_token(
    current: Any,
    token: str,
    ctx: HandlerContext | None,
    *,
    create: bool = False,
) -> Any:
    """Navigate one token, optionally creating intermediates."""
    if token.startswith("["):
        # List index or append
        idx_str = token[1:-1]
        if idx_str == "+":
            # Append requires context
            if ctx is None:
                return None
            # The list should already exist as a Python list on the parent
            # This case shouldn't happen in navigation (only as final token)
            return None

        idx = int(idx_str)

        if isinstance(current, list):
            # Ensure list is long enough, padding with Box dicts
            while len(current) <= idx:
                current.append(Box(default_box=True))
            return current[idx]
        elif isinstance(current, Box):
            # Box auto-vivifies as dict; shouldn't happen for lists
            return None
        return None
    else:
        # Named attribute
        if isinstance(current, Box):
            if create:
                # Box auto-vivifies on attribute access
                return current[token]
            return current.get(token)
        elif isinstance(current, dict):
            if create and token not in current:
                current[token] = Box(default_box=True)
            return current.get(token)
        return None


def _set_final_token(
    current: Any,
    token: str,
    value: Any,
    ctx: HandlerContext | None,
) -> None:
    """Set the value at the final token of a path."""
    if token.startswith("["):
        idx_str = token[1:-1]
        if idx_str == "+":
            # Append to list
            if isinstance(current, list):
                current.append(value)
            return

        idx = int(idx_str)
        if isinstance(current, list):
            while len(current) <= idx:
                current.append(Box(default_box=True))
            current[idx] = value
    else:
        if isinstance(current, (Box, dict)):
            current[token] = value


def ensure_list(builder: Box, path: str) -> list:
    """
    Ensure a path in the builder points to a Python list.

    If the path doesn't exist or is a Box (auto-vivified dict), replace it
    with an empty list. Returns the list.
    """
    tokens = _tokenize_path(path)
    current: Any = builder

    for token in tokens[:-1]:
        current = _navigate_token(current, token, None, create=True)
        if current is None:
            return []

    final = tokens[-1]
    if isinstance(current, (Box, dict)):
        existing = current.get(final) if isinstance(current, dict) else current.get(final)
        if not isinstance(existing, list):
            current[final] = []
        return current[final]
    return []


# =============================================================================
# Box Cleanup Utilities
# =============================================================================


def strip_empty_boxes(d: Any) -> Any:
    """
    Recursively remove empty dicts/Boxes left by auto-vivification.

    Returns the cleaned structure, or None if the entire structure is empty.
    """
    if isinstance(d, (dict, Box)):
        cleaned = {}
        for k, v in d.items():
            result = strip_empty_boxes(v)
            if result is not None:
                cleaned[k] = result
        return cleaned if cleaned else None
    elif isinstance(d, list):
        cleaned_list = []
        for item in d:
            result = strip_empty_boxes(item)
            if result is not None:
                cleaned_list.append(result)
        return cleaned_list if cleaned_list else None
    else:
        # Leaf value (str, int, Decimal, date, etc.)
        return d
