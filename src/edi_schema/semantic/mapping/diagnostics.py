"""
Runtime Diagnostics for Declarative Mapping.

Provides logging, metrics collection, and tracing for mapping operations.
"""

import logging
import time
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generator

from .errors import MappingError, MappingErrorSeverity

if TYPE_CHECKING:
    from .context import MessageContext

logger = logging.getLogger("edi_schema.mapping")


# =============================================================================
# Metrics Collection
# =============================================================================


@dataclass
class MappingMetrics:
    """Metrics for a single mapping operation."""

    # Timing
    start_time: float = 0.0
    end_time: float = 0.0
    field_mapping_time: float = 0.0
    loop_mapping_time: float = 0.0
    validation_time: float = 0.0

    # Counts
    fields_mapped: int = 0
    fields_skipped: int = 0
    fields_defaulted: int = 0
    loops_processed: int = 0
    loop_iterations: int = 0
    transforms_applied: int = 0
    validation_rules_run: int = 0

    # Errors by category
    errors_by_code: Counter = field(default_factory=Counter)
    errors_by_severity: Counter = field(default_factory=Counter)

    @property
    def total_time(self) -> float:
        """Total elapsed time."""
        return self.end_time - self.start_time

    @property
    def mapping_success_rate(self) -> float:
        """Rate of successfully mapped fields."""
        total = self.fields_mapped + self.fields_skipped
        return self.fields_mapped / total if total > 0 else 1.0

    def record_error(self, error: MappingError) -> None:
        """Record an error in metrics."""
        self.errors_by_code[error.code.name] += 1
        self.errors_by_severity[error.severity.name] += 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_time_ms": self.total_time * 1000,
            "field_mapping_time_ms": self.field_mapping_time * 1000,
            "loop_mapping_time_ms": self.loop_mapping_time * 1000,
            "validation_time_ms": self.validation_time * 1000,
            "fields_mapped": self.fields_mapped,
            "fields_skipped": self.fields_skipped,
            "fields_defaulted": self.fields_defaulted,
            "loops_processed": self.loops_processed,
            "loop_iterations": self.loop_iterations,
            "transforms_applied": self.transforms_applied,
            "validation_rules_run": self.validation_rules_run,
            "mapping_success_rate": self.mapping_success_rate,
            "errors_by_code": dict(self.errors_by_code),
            "errors_by_severity": dict(self.errors_by_severity),
        }


@dataclass
class AggregateMetrics:
    """Aggregate metrics across multiple mapping operations."""

    total_mappings: int = 0
    successful_mappings: int = 0
    failed_mappings: int = 0
    total_time: float = 0.0
    total_fields_mapped: int = 0
    total_errors: int = 0

    # Per-transaction-type metrics
    by_transaction: dict[str, MappingMetrics] = field(default_factory=dict)

    def add(self, transaction_id: str, metrics: MappingMetrics, success: bool) -> None:
        """Add metrics from a single mapping operation."""
        self.total_mappings += 1
        self.total_time += metrics.total_time
        self.total_fields_mapped += metrics.fields_mapped
        self.total_errors += sum(metrics.errors_by_code.values())

        if success:
            self.successful_mappings += 1
        else:
            self.failed_mappings += 1

        # Aggregate by transaction type
        if transaction_id not in self.by_transaction:
            self.by_transaction[transaction_id] = MappingMetrics()

        agg = self.by_transaction[transaction_id]
        agg.fields_mapped += metrics.fields_mapped
        agg.fields_skipped += metrics.fields_skipped
        agg.loops_processed += metrics.loops_processed
        agg.loop_iterations += metrics.loop_iterations
        agg.errors_by_code += metrics.errors_by_code
        agg.errors_by_severity += metrics.errors_by_severity

    @property
    def success_rate(self) -> float:
        """Overall success rate."""
        if self.total_mappings == 0:
            return 1.0
        return self.successful_mappings / self.total_mappings

    @property
    def avg_time_per_mapping(self) -> float:
        """Average time per mapping operation."""
        if self.total_mappings == 0:
            return 0.0
        return self.total_time / self.total_mappings

    def reset(self) -> None:
        """Reset all metrics."""
        self.total_mappings = 0
        self.successful_mappings = 0
        self.failed_mappings = 0
        self.total_time = 0.0
        self.total_fields_mapped = 0
        self.total_errors = 0
        self.by_transaction.clear()


# =============================================================================
# Tracing
# =============================================================================


@dataclass
class MappingStep:
    """Single step in a mapping trace."""

    step_type: str  # "field", "loop_start", "loop_item", "transform", "validation", "error"
    source_path: str | None = None
    target_path: str | None = None
    value_before: Any = None
    value_after: Any = None
    transform: str | None = None
    error: MappingError | None = None
    timestamp: float = field(default_factory=time.perf_counter)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.step_type,
            "source": self.source_path,
            "target": self.target_path,
            "value_before": str(self.value_before) if self.value_before is not None else None,
            "value_after": str(self.value_after) if self.value_after is not None else None,
            "transform": self.transform,
            "error": self.error.code.name if self.error else None,
        }

    def __str__(self) -> str:
        if self.step_type == "field":
            return f"FIELD {self.source_path} -> {self.target_path}: {self.value_after!r}"
        elif self.step_type == "transform":
            return f"TRANSFORM {self.transform}: {self.value_before!r} -> {self.value_after!r}"
        elif self.step_type == "loop_start":
            return f"LOOP START {self.source_path}"
        elif self.step_type == "loop_item":
            return f"LOOP ITEM {self.source_path}"
        elif self.step_type == "validation":
            status = "PASS" if not self.error else "FAIL"
            return f"VALIDATE {self.source_path}: {status}"
        elif self.step_type == "error":
            return f"ERROR {self.error.code.name if self.error else 'UNKNOWN'}: {self.error.message if self.error else ''}"
        return f"{self.step_type}: {self.source_path}"


@dataclass
class MappingTrace:
    """Detailed trace of a mapping operation for debugging."""

    transaction_id: str
    control_number: str
    context: "MessageContext | None" = None

    # Step-by-step trace
    steps: list[MappingStep] = field(default_factory=list)

    # Final state
    success: bool = False
    error_count: int = 0
    metrics: MappingMetrics | None = None

    def add_step(self, step: MappingStep) -> None:
        """Add a step to the trace."""
        self.steps.append(step)

    def add_field(
        self,
        source_path: str,
        target_path: str,
        value: Any,
        transform: str | None = None,
    ) -> None:
        """Add a field mapping step."""
        self.add_step(
            MappingStep(
                step_type="field",
                source_path=source_path,
                target_path=target_path,
                value_after=value,
                transform=transform,
            )
        )

    def add_transform(
        self,
        transform_name: str,
        value_before: Any,
        value_after: Any,
    ) -> None:
        """Add a transform step."""
        self.add_step(
            MappingStep(
                step_type="transform",
                transform=transform_name,
                value_before=value_before,
                value_after=value_after,
            )
        )

    def add_error(self, error: MappingError) -> None:
        """Add an error step."""
        self.add_step(
            MappingStep(
                step_type="error",
                source_path=error.source_path,
                target_path=error.target_path,
                error=error,
            )
        )

    def to_json(self) -> str:
        """Export trace as JSON for debugging."""
        import json

        return json.dumps(
            {
                "transaction_id": self.transaction_id,
                "control_number": self.control_number,
                "steps": [s.to_dict() for s in self.steps],
                "success": self.success,
                "error_count": self.error_count,
                "metrics": self.metrics.to_dict() if self.metrics else None,
            },
            indent=2,
        )

    def print_trace(self, max_steps: int = 100) -> None:
        """Print human-readable trace."""
        print(f"=== Mapping Trace: {self.transaction_id} ===")
        for i, step in enumerate(self.steps[:max_steps]):
            print(f"{i + 1:3d}. {step}")
        if len(self.steps) > max_steps:
            print(f"... ({len(self.steps) - max_steps} more steps)")
        print(f"\nResult: {'SUCCESS' if self.success else 'FAILED'}")
        print(f"Errors: {self.error_count}")
        if self.metrics:
            print(f"Time: {self.metrics.total_time * 1000:.2f}ms")
            print(f"Fields: {self.metrics.fields_mapped} mapped, {self.metrics.fields_skipped} skipped")


# =============================================================================
# Logger
# =============================================================================


class MappingLogger:
    """Structured logging for mapping operations."""

    def __init__(self, log_level: int = logging.DEBUG) -> None:
        self.log_level = log_level

    @contextmanager
    def mapping_context(
        self,
        transaction_id: str,
        control_number: str,
    ) -> Generator[None, None, None]:
        """Context manager for logging a mapping operation."""
        logger.info(f"Starting mapping: {transaction_id} (control: {control_number})")
        start_time = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start_time
            logger.info(f"Completed mapping: {transaction_id} in {elapsed:.3f}s")

    def log_field_mapping(
        self,
        source_path: str,
        target_path: str,
        value: Any,
        transformed_value: Any = None,
    ) -> None:
        """Log individual field mapping."""
        if transformed_value is not None and transformed_value != value:
            logger.log(
                self.log_level,
                f"  {source_path} -> {target_path}: {value!r} -> {transformed_value!r}",
            )
        else:
            logger.log(self.log_level, f"  {source_path} -> {target_path}: {value!r}")

    def log_loop_iteration(
        self,
        loop_id: str,
        iteration: int,
        segment_count: int,
    ) -> None:
        """Log loop iteration start."""
        logger.log(self.log_level, f"  Loop {loop_id}[{iteration}]: {segment_count} segments")

    def log_error(self, error: MappingError) -> None:
        """Log mapping error."""
        level = logging.WARNING if error.severity == MappingErrorSeverity.WARNING else logging.ERROR
        logger.log(
            level,
            f"  {error.code.name}: {error.message} (source={error.source_path}, target={error.target_path})",
        )

    def log_validation(
        self,
        rule_name: str,
        passed: bool,
        errors: list[MappingError] | None = None,
    ) -> None:
        """Log validation rule result."""
        if passed:
            logger.log(self.log_level, f"  [PASS] {rule_name}")
        else:
            error_count = len(errors) if errors else 0
            logger.warning(f"  [FAIL] {rule_name}: {error_count} errors")
