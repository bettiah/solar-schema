"""
Transform Registry for Declarative Mappings.

Transforms convert values between X12 format and semantic model format.
"""

from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal, InvalidOperation
from typing import Any, Callable


@dataclass
class Transform:
    """
    A bidirectional data transform.

    Transforms define how to convert values between X12 and semantic formats.
    Each transform has a forward function (to_semantic) and optionally a
    reverse function (from_semantic).
    """

    name: str
    to_semantic_fn: Callable[[Any], Any]
    from_semantic_fn: Callable[[Any], Any] | None = None
    description: str = ""

    def to_semantic(self, value: Any) -> Any:
        """Convert X12 value to semantic format."""
        if value is None or value == "":
            return None
        return self.to_semantic_fn(value)

    def from_semantic(self, value: Any) -> Any:
        """Convert semantic value back to X12 format."""
        if value is None:
            return ""
        if self.from_semantic_fn:
            return self.from_semantic_fn(value)
        return str(value)

    def __str__(self) -> str:
        return f"Transform({self.name})"


# =============================================================================
# Date/Time Transforms
# =============================================================================


def _parse_date_ccyymmdd(value: str) -> date | None:
    """Parse CCYYMMDD date format."""
    if not value or len(value) != 8:
        return None
    try:
        return date(int(value[0:4]), int(value[4:6]), int(value[6:8]))
    except (ValueError, IndexError):
        return None


def _parse_date_yymmdd(value: str) -> date | None:
    """Parse YYMMDD date format (assumes 2000s for 00-50, 1900s for 51-99)."""
    if not value or len(value) != 6:
        return None
    try:
        year = int(value[0:2])
        if year <= 50:
            year += 2000
        else:
            year += 1900
        return date(year, int(value[2:4]), int(value[4:6]))
    except (ValueError, IndexError):
        return None


def _parse_date(value: str) -> date | None:
    """Parse X12 date in either CCYYMMDD or YYMMDD format."""
    if not value:
        return None
    if len(value) == 8:
        return _parse_date_ccyymmdd(value)
    elif len(value) == 6:
        return _parse_date_yymmdd(value)
    return None


def _format_date_ccyymmdd(d: date) -> str:
    """Format date as CCYYMMDD."""
    return d.strftime("%Y%m%d")


def _format_date_yymmdd(d: date) -> str:
    """Format date as YYMMDD."""
    return d.strftime("%y%m%d")


def _parse_time(value: str) -> time | None:
    """Parse X12 time in HHMM or HHMMSS format."""
    if not value:
        return None
    try:
        hour = int(value[0:2])
        minute = int(value[2:4])
        second = 0
        microsecond = 0

        if len(value) >= 6:
            second = int(value[4:6])
        if len(value) >= 7:
            microsecond = int(value[6]) * 100000

        return time(hour, minute, second, microsecond)
    except (ValueError, IndexError):
        return None


def _format_time(t: time) -> str:
    """Format time as HHMM."""
    return t.strftime("%H%M")


# =============================================================================
# Numeric Transforms
# =============================================================================


def _parse_decimal(value: str) -> Decimal | None:
    """Parse string to Decimal."""
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def _format_decimal(d: Decimal) -> str:
    """Format Decimal to string."""
    return str(d)


def _parse_int(value: str) -> int | None:
    """Parse string to int."""
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _format_int(i: int) -> str:
    """Format int to string."""
    return str(i)


def _parse_amount_cents(value: str) -> Decimal | None:
    """Parse amount with implied 2 decimal places (cents)."""
    if not value:
        return None
    try:
        return Decimal(value) / 100
    except InvalidOperation:
        return None


def _format_amount_cents(d: Decimal) -> str:
    """Format Decimal as cents (implied 2 decimals)."""
    return str(int(d * 100))


# =============================================================================
# Code Map Transform Factory
# =============================================================================


def create_code_map_transform(
    name: str,
    code_map: dict[str, str],
    reverse_map: dict[str, str] | None = None,
    description: str = "",
) -> Transform:
    """
    Create a transform that maps codes between X12 and semantic values.

    Args:
        name: Transform name
        code_map: X12 code → semantic value mapping
        reverse_map: Optional semantic → X12 mapping (auto-generated if not provided)
        description: Human-readable description

    Returns:
        Transform instance
    """
    if reverse_map is None:
        reverse_map = {v: k for k, v in code_map.items()}

    def to_semantic(value: str) -> str | None:
        return code_map.get(value, value)

    def from_semantic(value: str) -> str:
        return reverse_map.get(value, value)

    return Transform(
        name=name,
        to_semantic_fn=to_semantic,
        from_semantic_fn=from_semantic,
        description=description,
    )


# =============================================================================
# Built-in Transform Instances
# =============================================================================


PARSE_DATE = Transform(
    name="PARSE_DATE",
    to_semantic_fn=_parse_date,
    from_semantic_fn=_format_date_ccyymmdd,
    description="Parse X12 date (CCYYMMDD or YYMMDD) to date object",
)

PARSE_DATE_YYMMDD = Transform(
    name="PARSE_DATE_YYMMDD",
    to_semantic_fn=_parse_date_yymmdd,
    from_semantic_fn=_format_date_yymmdd,
    description="Parse YYMMDD date format",
)

PARSE_TIME = Transform(
    name="PARSE_TIME",
    to_semantic_fn=_parse_time,
    from_semantic_fn=_format_time,
    description="Parse X12 time (HHMM or HHMMSS) to time object",
)

PARSE_DECIMAL = Transform(
    name="PARSE_DECIMAL",
    to_semantic_fn=_parse_decimal,
    from_semantic_fn=_format_decimal,
    description="Parse string to Decimal",
)

TO_INT = Transform(
    name="TO_INT",
    to_semantic_fn=_parse_int,
    from_semantic_fn=_format_int,
    description="Parse string to integer",
)

PARSE_AMOUNT_CENTS = Transform(
    name="PARSE_AMOUNT_CENTS",
    to_semantic_fn=_parse_amount_cents,
    from_semantic_fn=_format_amount_cents,
    description="Parse amount with implied 2 decimal places",
)

# Invoice type code mapping (X12 BIG*07 -> UBL InvoiceTypeCode)
INVOICE_TYPE_MAP = {
    "": "380",
    "CN": "381",
    "CR": "381",
    "DI": "383",
    "DR": "383",
    "RU": "381",
    "SU": "385",
}

MAP_INVOICE_TYPE = create_code_map_transform(
    name="MAP_INVOICE_TYPE",
    code_map=INVOICE_TYPE_MAP,
    description="Map X12 invoice type codes to UBL InvoiceTypeCode",
)

# Identity transform (no conversion)
IDENTITY = Transform(
    name="IDENTITY",
    to_semantic_fn=lambda x: x,
    from_semantic_fn=lambda x: str(x) if x is not None else "",
    description="No conversion (pass-through)",
)

# Strip whitespace
STRIP = Transform(
    name="STRIP",
    to_semantic_fn=lambda x: x.strip() if isinstance(x, str) else x,
    from_semantic_fn=lambda x: str(x).strip() if x is not None else "",
    description="Strip leading/trailing whitespace",
)

# Boolean from "Y"/"N" or "1"/"0"
PARSE_BOOLEAN = Transform(
    name="PARSE_BOOLEAN",
    to_semantic_fn=lambda x: x in ("Y", "1", "true", "True") if x else None,
    from_semantic_fn=lambda x: "Y" if x else "N",
    description="Parse Y/N or 1/0 to boolean",
)


# =============================================================================
# Transform Registry
# =============================================================================


class TransformRegistry:
    """
    Registry of available transforms.

    Allows looking up transforms by name and registering custom transforms.
    """

    def __init__(self) -> None:
        self._transforms: dict[str, Transform] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        """Register built-in transforms."""
        for transform in [
            PARSE_DATE,
            PARSE_DATE_YYMMDD,
            PARSE_TIME,
            PARSE_DECIMAL,
            TO_INT,
            PARSE_AMOUNT_CENTS,
            MAP_INVOICE_TYPE,
            IDENTITY,
            STRIP,
            PARSE_BOOLEAN,
        ]:
            self.register(transform)

    def register(self, transform: Transform) -> None:
        """Register a transform."""
        self._transforms[transform.name] = transform

    def get(self, name: str) -> Transform | None:
        """Get a transform by name."""
        return self._transforms.get(name)

    def __getitem__(self, name: str) -> Transform:
        """Get a transform by name, raising KeyError if not found."""
        transform = self.get(name)
        if transform is None:
            raise KeyError(f"Transform not found: {name}")
        return transform

    def __contains__(self, name: str) -> bool:
        """Check if a transform is registered."""
        return name in self._transforms

    def list_transforms(self) -> list[str]:
        """List all registered transform names."""
        return list(self._transforms.keys())


# Global registry instance
_registry = TransformRegistry()


def get_transform(name: str) -> Transform | None:
    """Get a transform from the global registry."""
    return _registry.get(name)


def register_transform(transform: Transform) -> None:
    """Register a transform in the global registry."""
    _registry.register(transform)
