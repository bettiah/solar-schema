"""
Error Types for Declarative Mapping.

Defines error codes, severities, and the error accumulator for collecting
errors during mapping operations.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MappingErrorSeverity(Enum):
    """Severity level for mapping errors."""

    WARNING = "warning"  # Non-fatal, mapping continues
    ERROR = "error"  # Fatal for this field, but mapping continues
    FATAL = "fatal"  # Stops mapping entirely


class MappingErrorCode(Enum):
    """Category codes for mapping errors."""

    # Source errors
    SEGMENT_NOT_FOUND = "segment_not_found"
    ELEMENT_NOT_FOUND = "element_not_found"
    REQUIRED_FIELD_MISSING = "required_field_missing"
    INVALID_VALUE = "invalid_value"
    LOOP_NOT_FOUND = "loop_not_found"

    # Transform errors
    TRANSFORM_FAILED = "transform_failed"
    DATE_PARSE_ERROR = "date_parse_error"
    DECIMAL_PARSE_ERROR = "decimal_parse_error"
    CODE_MAP_UNKNOWN = "code_map_unknown"

    # Target errors
    TARGET_PATH_INVALID = "target_path_invalid"
    TYPE_MISMATCH = "type_mismatch"
    CANNOT_SET_FIELD = "cannot_set_field"

    # Validation errors
    CONSTRAINT_VIOLATED = "constraint_violated"
    CROSS_FIELD_VALIDATION_FAILED = "cross_field_validation_failed"

    # Unmapped data warnings
    UNMAPPED_SEGMENT = "unmapped_segment"
    UNMAPPED_QUALIFIER = "unmapped_qualifier"
    UNMAPPED_ELEMENT = "unmapped_element"

    # General
    UNKNOWN_ERROR = "unknown_error"


class ErrorHandlingMode(Enum):
    """How to handle errors during mapping."""

    STRICT = "strict"  # Stop on first error
    LENIENT = "lenient"  # Continue, collect all errors
    BEST_EFFORT = "best_effort"  # Continue, ignore errors, map what's possible


@dataclass
class MappingError:
    """
    A mapping error with full context.

    Contains all information needed to understand what went wrong,
    where it happened, and potentially how to fix it.
    """

    code: MappingErrorCode
    severity: MappingErrorSeverity
    message: str
    source_path: str | None = None  # e.g., "BEG/03" or "ISA/06"
    target_path: str | None = None  # e.g., "id" or "buyer_customer_party.party.name"
    value: Any = None  # The problematic value
    context: dict[str, Any] = field(default_factory=dict)  # Additional context

    def __str__(self) -> str:
        parts = [f"[{self.severity.value}] {self.code.name}: {self.message}"]
        if self.source_path:
            parts.append(f" (source: {self.source_path})")
        if self.target_path:
            parts.append(f" (target: {self.target_path})")
        if self.value is not None:
            parts.append(f" (value: {self.value!r})")
        return "".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "code": self.code.value,
            "severity": self.severity.value,
            "message": self.message,
            "source_path": self.source_path,
            "target_path": self.target_path,
            "value": str(self.value) if self.value is not None else None,
            "context": self.context,
        }


class MappingException(Exception):
    """Exception raised when mapping fails fatally."""

    def __init__(self, error: MappingError) -> None:
        self.error = error
        super().__init__(str(error))


class ErrorAccumulator:
    """
    Collects errors during mapping with context tracking.

    Supports nested context (e.g., loop iterations) and different
    error handling modes.
    """

    def __init__(self, mode: ErrorHandlingMode = ErrorHandlingMode.LENIENT) -> None:
        self.mode = mode
        self.errors: list[MappingError] = []
        self._context_stack: list[dict[str, Any]] = []

    def push_context(self, **ctx: Any) -> None:
        """
        Push context for nested operations.

        Example:
            with accumulator.context(loop="PO1", iteration=1):
                # Errors here will include loop context
        """
        self._context_stack.append(ctx)

    def pop_context(self) -> dict[str, Any] | None:
        """Pop context when leaving nested operation."""
        if self._context_stack:
            return self._context_stack.pop()
        return None

    @property
    def current_context(self) -> dict[str, Any]:
        """Get merged context from all levels."""
        result: dict[str, Any] = {}
        for ctx in self._context_stack:
            result.update(ctx)
        return result

    def add_error(self, error: MappingError) -> None:
        """
        Add error with current context.

        Raises MappingException in STRICT mode for fatal errors.
        """
        # Merge current context into error
        if self._context_stack:
            error.context = {**error.context, **self.current_context}

        self.errors.append(error)

        # In strict mode, raise on any error
        if self.mode == ErrorHandlingMode.STRICT:
            if error.severity in (MappingErrorSeverity.ERROR, MappingErrorSeverity.FATAL):
                raise MappingException(error)

    def add(
        self,
        code: MappingErrorCode,
        message: str,
        *,
        severity: MappingErrorSeverity = MappingErrorSeverity.ERROR,
        source_path: str | None = None,
        target_path: str | None = None,
        value: Any = None,
        **extra_context: Any,
    ) -> None:
        """Convenience method to add an error with parameters."""
        error = MappingError(
            code=code,
            severity=severity,
            message=message,
            source_path=source_path,
            target_path=target_path,
            value=value,
            context=extra_context,
        )
        self.add_error(error)

    def add_warning(
        self,
        code: MappingErrorCode,
        message: str,
        **kwargs: Any,
    ) -> None:
        """Add a warning-level error."""
        self.add(code, message, severity=MappingErrorSeverity.WARNING, **kwargs)

    def add_fatal(
        self,
        code: MappingErrorCode,
        message: str,
        **kwargs: Any,
    ) -> None:
        """Add a fatal error (stops mapping in any mode)."""
        error = MappingError(
            code=code,
            severity=MappingErrorSeverity.FATAL,
            message=message,
            **kwargs,
        )
        self.add_error(error)
        raise MappingException(error)

    @property
    def has_errors(self) -> bool:
        """Check if any errors (not warnings) were collected."""
        return any(
            e.severity in (MappingErrorSeverity.ERROR, MappingErrorSeverity.FATAL)
            for e in self.errors
        )

    @property
    def has_fatal_errors(self) -> bool:
        """Check if any fatal errors were collected."""
        return any(e.severity == MappingErrorSeverity.FATAL for e in self.errors)

    @property
    def has_warnings(self) -> bool:
        """Check if any warnings were collected."""
        return any(e.severity == MappingErrorSeverity.WARNING for e in self.errors)

    @property
    def warnings(self) -> list[MappingError]:
        """Get only warning-level errors."""
        return [e for e in self.errors if e.severity == MappingErrorSeverity.WARNING]

    @property
    def error_count(self) -> int:
        """Count of errors (excluding warnings)."""
        return sum(
            1
            for e in self.errors
            if e.severity in (MappingErrorSeverity.ERROR, MappingErrorSeverity.FATAL)
        )

    def clear(self) -> None:
        """Clear all errors and context."""
        self.errors.clear()
        self._context_stack.clear()


class ErrorContext:
    """Context manager for nested error context."""

    def __init__(self, accumulator: ErrorAccumulator, **context: Any) -> None:
        self.accumulator = accumulator
        self.context = context

    def __enter__(self) -> "ErrorContext":
        self.accumulator.push_context(**self.context)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.accumulator.pop_context()
