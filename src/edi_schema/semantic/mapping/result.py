"""
Mapping Result Types.

Contains the result of a mapping operation with success status,
the mapped model, errors, and optional diagnostics.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from .errors import MappingError, MappingErrorSeverity

if TYPE_CHECKING:
    from .diagnostics import MappingMetrics, MappingTrace

T = TypeVar("T")


@dataclass
class MappingResult(Generic[T]):
    """
    Result of a mapping operation.

    Contains the mapped model (if successful), all errors encountered,
    and optional diagnostics (trace, metrics).
    """

    success: bool
    model: T | None = None
    errors: list[MappingError] = field(default_factory=list)

    # Optional diagnostics (populated when debug_mode or collect_metrics enabled)
    trace: "MappingTrace | None" = None
    metrics: "MappingMetrics | None" = None

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors (not just warnings)."""
        return any(
            e.severity in (MappingErrorSeverity.ERROR, MappingErrorSeverity.FATAL)
            for e in self.errors
        )

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return any(e.severity == MappingErrorSeverity.WARNING for e in self.errors)

    @property
    def warnings(self) -> list[MappingError]:
        """Get only warnings."""
        return [e for e in self.errors if e.severity == MappingErrorSeverity.WARNING]

    @property
    def fatal_errors(self) -> list[MappingError]:
        """Get only fatal errors."""
        return [e for e in self.errors if e.severity == MappingErrorSeverity.FATAL]

    @property
    def non_fatal_errors(self) -> list[MappingError]:
        """Get non-fatal errors (excluding warnings)."""
        return [e for e in self.errors if e.severity == MappingErrorSeverity.ERROR]

    @property
    def error_count(self) -> int:
        """Count of errors (excluding warnings)."""
        return sum(
            1
            for e in self.errors
            if e.severity in (MappingErrorSeverity.ERROR, MappingErrorSeverity.FATAL)
        )

    def get_model(self) -> T:
        """
        Get the mapped model, raising if not successful.

        Raises:
            ValueError: If mapping was not successful
        """
        if not self.success or self.model is None:
            error_msg = "; ".join(str(e) for e in self.errors[:3])
            raise ValueError(f"Mapping failed: {error_msg}")
        return self.model

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "success": self.success,
            "error_count": len(self.errors),
            "errors": [e.to_dict() for e in self.errors],
        }

        if self.model is not None:
            # If model has a to_dict or model_dump method, use it
            if hasattr(self.model, "model_dump"):
                result["model"] = self.model.model_dump(exclude_none=True)
            elif hasattr(self.model, "to_dict"):
                result["model"] = self.model.to_dict()

        if self.metrics:
            result["metrics"] = self.metrics.to_dict()

        return result

    def __str__(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        return f"MappingResult({status}, {len(self.errors)} errors)"


@dataclass
class BatchMappingResult(Generic[T]):
    """
    Result of mapping multiple transactions.

    Contains individual results and aggregate statistics.
    """

    results: list[MappingResult[T]] = field(default_factory=list)

    @property
    def successful_count(self) -> int:
        """Count of successful mappings."""
        return sum(1 for r in self.results if r.success)

    @property
    def failed_count(self) -> int:
        """Count of failed mappings."""
        return sum(1 for r in self.results if not r.success)

    @property
    def total_count(self) -> int:
        """Total number of mappings."""
        return len(self.results)

    @property
    def success_rate(self) -> float:
        """Success rate as a fraction (0.0 to 1.0)."""
        if not self.results:
            return 1.0
        return self.successful_count / len(self.results)

    @property
    def all_successful(self) -> bool:
        """Check if all mappings were successful."""
        return all(r.success for r in self.results)

    @property
    def successful_models(self) -> list[T]:
        """Get all successfully mapped models."""
        return [r.model for r in self.results if r.success and r.model is not None]

    @property
    def all_errors(self) -> list[MappingError]:
        """Get all errors from all results."""
        errors: list[MappingError] = []
        for result in self.results:
            errors.extend(result.errors)
        return errors

    def __str__(self) -> str:
        return f"BatchMappingResult({self.successful_count}/{self.total_count} successful)"
