"""
Mapping Validation and Coverage Report Generation.

Tools for analyzing mapping completeness against schema definitions.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from .types import (
    FieldMapping,
    LoopMapping,
    PartyLoopMapping,
    QualifiedMapping,
    SegmentPath,
    TransactionMapping,
)

if TYPE_CHECKING:
    pass


# =============================================================================
# Coverage Analysis Types
# =============================================================================


@dataclass
class FieldCoverage:
    """Coverage status for a single field."""

    path: str
    is_mapped: bool
    source_path: str | None = None
    required: bool = False
    has_transform: bool = False
    notes: str | None = None


@dataclass
class SegmentCoverage:
    """Coverage status for a segment."""

    segment_id: str
    elements_total: int = 0
    elements_mapped: int = 0
    is_used: bool = False
    notes: str | None = None


@dataclass
class MappingCoverageReport:
    """Complete coverage report for a mapping."""

    transaction_id: str
    semantic_type: str

    # Semantic model coverage
    semantic_fields_total: int = 0
    semantic_fields_mapped: int = 0
    unmapped_semantic_fields: list[str] = field(default_factory=list)

    # X12 segment coverage
    segments_total: int = 0
    segments_used: int = 0
    unused_segments: list[str] = field(default_factory=list)

    # Detailed coverage
    field_coverage: list[FieldCoverage] = field(default_factory=list)
    segment_coverage: list[SegmentCoverage] = field(default_factory=list)

    # Mapping statistics
    direct_mappings: int = 0
    qualified_mappings: int = 0
    loop_mappings: int = 0
    party_mappings: int = 0
    transforms_used: int = 0

    @property
    def semantic_coverage_percent(self) -> float:
        """Percentage of semantic fields that are mapped."""
        if self.semantic_fields_total == 0:
            return 100.0
        return (self.semantic_fields_mapped / self.semantic_fields_total) * 100

    @property
    def segment_coverage_percent(self) -> float:
        """Percentage of segments that are used."""
        if self.segments_total == 0:
            return 100.0
        return (self.segments_used / self.segments_total) * 100

    def to_report(self) -> str:
        """Generate human-readable report."""
        lines = [
            f"Mapping Coverage Report: {self.transaction_id} -> {self.semantic_type}",
            "=" * 60,
            "",
            f"Semantic Model Coverage: {self.semantic_coverage_percent:.1f}%",
            f"  Mapped: {self.semantic_fields_mapped}/{self.semantic_fields_total}",
        ]

        if self.unmapped_semantic_fields:
            lines.append("  Unmapped fields:")
            for path in self.unmapped_semantic_fields[:20]:  # Limit output
                lines.append(f"    - {path}")
            if len(self.unmapped_semantic_fields) > 20:
                lines.append(f"    ... and {len(self.unmapped_semantic_fields) - 20} more")

        lines.extend([
            "",
            f"X12 Segment Coverage: {self.segment_coverage_percent:.1f}%",
            f"  Used: {self.segments_used}/{self.segments_total}",
        ])

        if self.unused_segments:
            lines.append("  Unused segments:")
            for seg in self.unused_segments[:20]:
                lines.append(f"    - {seg}")

        lines.extend([
            "",
            "Mapping Statistics:",
            f"  Direct field mappings: {self.direct_mappings}",
            f"  Qualified mappings: {self.qualified_mappings}",
            f"  Loop mappings: {self.loop_mappings}",
            f"  Party mappings: {self.party_mappings}",
            f"  Transforms used: {self.transforms_used}",
        ])

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "transaction_id": self.transaction_id,
            "semantic_type": self.semantic_type,
            "semantic_coverage": {
                "total": self.semantic_fields_total,
                "mapped": self.semantic_fields_mapped,
                "percent": self.semantic_coverage_percent,
                "unmapped": self.unmapped_semantic_fields,
            },
            "segment_coverage": {
                "total": self.segments_total,
                "used": self.segments_used,
                "percent": self.segment_coverage_percent,
                "unused": self.unused_segments,
            },
            "statistics": {
                "direct_mappings": self.direct_mappings,
                "qualified_mappings": self.qualified_mappings,
                "loop_mappings": self.loop_mappings,
                "party_mappings": self.party_mappings,
                "transforms_used": self.transforms_used,
            },
        }


# =============================================================================
# Mapping Validator
# =============================================================================


class MappingValidator:
    """
    Validates mapping definitions and generates coverage reports.

    Can analyze:
    - Which semantic model fields are mapped vs unmapped
    - Which X12 segments/elements are used
    - Transform usage
    - Validation rule coverage
    """

    def validate(
        self,
        mapping: TransactionMapping,
        x12_schema: Any = None,
    ) -> MappingCoverageReport:
        """
        Validate a mapping and generate a coverage report.

        Args:
            mapping: The TransactionMapping to analyze
            x12_schema: Optional X12 schema for segment coverage analysis

        Returns:
            MappingCoverageReport with coverage statistics
        """
        report = MappingCoverageReport(
            transaction_id=mapping.transaction_id,
            semantic_type=mapping.semantic_type.__name__,
        )

        # Analyze semantic model coverage
        self._analyze_semantic_coverage(mapping, report)

        # Analyze mapping statistics
        self._analyze_mapping_statistics(mapping, report)

        # Analyze X12 segment coverage (if schema provided)
        if x12_schema:
            self._analyze_segment_coverage(mapping, x12_schema, report)

        return report

    def _analyze_semantic_coverage(
        self,
        mapping: TransactionMapping,
        report: MappingCoverageReport,
    ) -> None:
        """Analyze which semantic model fields are mapped."""
        # Get all fields from the semantic model
        semantic_fields = self._get_model_fields(mapping.semantic_type)
        report.semantic_fields_total = len(semantic_fields)

        # Collect all mapped semantic paths
        mapped_paths = set()

        # From direct field mappings
        for fm in mapping.field_mappings:
            mapped_paths.add(self._normalize_path(fm.semantic.path))

        # From envelope mappings
        for fm in mapping.envelope_mappings:
            mapped_paths.add(self._normalize_path(fm.semantic.path))

        # From context mappings
        for fm in mapping.context_mappings:
            mapped_paths.add(self._normalize_path(fm.semantic.path))

        # From qualified mappings
        for qm in mapping.qualified_mappings:
            for field_mappings in qm.mappings.values():
                for fm in field_mappings:
                    mapped_paths.add(self._normalize_path(fm.semantic.path))

        # From loop mappings
        for lm in mapping.loop_mappings:
            self._collect_loop_mapped_paths(lm, mapped_paths)

        # From party mappings (these map to party subfields)
        for pm in mapping.party_mappings:
            for target in pm.party_field_map.values():
                mapped_paths.add(self._normalize_path(target.path))

        # Calculate coverage
        for field_path in semantic_fields:
            normalized = self._normalize_path(field_path)
            is_mapped = normalized in mapped_paths or any(
                normalized.startswith(mp + ".") or mp.startswith(normalized + ".")
                for mp in mapped_paths
            )

            report.field_coverage.append(
                FieldCoverage(
                    path=field_path,
                    is_mapped=is_mapped,
                )
            )

            if is_mapped:
                report.semantic_fields_mapped += 1
            else:
                report.unmapped_semantic_fields.append(field_path)

    def _collect_loop_mapped_paths(
        self,
        loop_mapping: LoopMapping,
        mapped_paths: set[str],
    ) -> None:
        """Collect mapped paths from a loop mapping."""
        # Add the loop target itself
        mapped_paths.add(self._normalize_path(loop_mapping.semantic_path.path))

        # Add field mappings (they're relative to loop items)
        base_path = loop_mapping.semantic_path.path
        for fm in loop_mapping.field_mappings:
            full_path = f"{base_path}[].{fm.semantic.path}"
            mapped_paths.add(self._normalize_path(full_path))

        # Add qualified mappings
        for qm in loop_mapping.qualified_mappings:
            for field_mappings in qm.mappings.values():
                for fm in field_mappings:
                    full_path = f"{base_path}[].{fm.semantic.path}"
                    mapped_paths.add(self._normalize_path(full_path))

        # Recurse into nested loops
        for nested in loop_mapping.nested_loops:
            self._collect_loop_mapped_paths(nested, mapped_paths)

    def _analyze_mapping_statistics(
        self,
        mapping: TransactionMapping,
        report: MappingCoverageReport,
    ) -> None:
        """Count mapping types and transform usage."""
        # Count direct mappings
        report.direct_mappings = (
            len(mapping.field_mappings) + len(mapping.envelope_mappings) + len(mapping.context_mappings)
        )

        # Count qualified mappings
        for qm in mapping.qualified_mappings:
            for field_mappings in qm.mappings.values():
                report.qualified_mappings += len(field_mappings)

        # Count loop mappings
        report.loop_mappings = len(mapping.loop_mappings)

        # Count party mappings
        report.party_mappings = len(mapping.party_mappings)

        # Count transforms
        transforms = 0
        for fm in mapping.field_mappings:
            if fm.to_semantic_transform:
                transforms += 1
        for fm in mapping.envelope_mappings:
            if fm.to_semantic_transform:
                transforms += 1
        for qm in mapping.qualified_mappings:
            for field_mappings in qm.mappings.values():
                for fm in field_mappings:
                    if fm.to_semantic_transform:
                        transforms += 1
        for lm in mapping.loop_mappings:
            for fm in lm.field_mappings:
                if fm.to_semantic_transform:
                    transforms += 1
        report.transforms_used = transforms

    def _analyze_segment_coverage(
        self,
        mapping: TransactionMapping,
        x12_schema: Any,
        report: MappingCoverageReport,
    ) -> None:
        """Analyze which X12 segments are used (requires schema)."""
        # This would require access to the X12 schema to know all available segments
        # For now, just collect which segments are referenced in the mapping
        used_segments: set[str] = set()

        # From field mappings
        for fm in mapping.field_mappings:
            if isinstance(fm.x12, SegmentPath):
                used_segments.add(fm.x12.segment)

        # From qualified mappings
        for qm in mapping.qualified_mappings:
            used_segments.add(qm.qualifier_path.segment)

        # From loop mappings
        for lm in mapping.loop_mappings:
            used_segments.add(lm.loop_id)
            for fm in lm.field_mappings:
                if isinstance(fm.x12, SegmentPath):
                    used_segments.add(fm.x12.segment)

        # From party mappings
        for pm in mapping.party_mappings:
            used_segments.add(pm.loop_id)
            # N1 loops typically use N1, N2, N3, N4, PER
            used_segments.update({"N1", "N2", "N3", "N4", "PER"})

        report.segments_used = len(used_segments)

    def _get_model_fields(
        self,
        model_class: type,
        prefix: str = "",
        max_depth: int = 3,
    ) -> list[str]:
        """Get all field paths from a Pydantic model."""
        fields: list[str] = []

        if max_depth <= 0:
            return fields

        if not hasattr(model_class, "model_fields"):
            return fields

        for name, field_info in model_class.model_fields.items():
            full_path = f"{prefix}.{name}" if prefix else name
            fields.append(full_path)

            # Check if it's a nested model
            annotation = field_info.annotation
            if annotation is None:
                continue

            # Handle Optional, List, etc.
            origin = getattr(annotation, "__origin__", None)
            args = getattr(annotation, "__args__", ())

            # Get the inner type
            inner_type = None
            if origin is list and args:
                inner_type = args[0]
            elif args:
                # Optional or Union - find non-None type
                for arg in args:
                    if arg is not type(None):
                        inner_type = arg
                        break
            else:
                inner_type = annotation

            # Recurse into nested models
            if inner_type and hasattr(inner_type, "model_fields"):
                if origin is list:
                    nested_prefix = f"{full_path}[]"
                else:
                    nested_prefix = full_path
                fields.extend(
                    self._get_model_fields(inner_type, nested_prefix, max_depth - 1)
                )

        return fields

    def _normalize_path(self, path: str) -> str:
        """Normalize a path for comparison (remove indices, etc.)."""
        # Remove specific indices, keep [] for lists
        import re

        normalized = re.sub(r"\[\d+\]", "[]", path)
        normalized = re.sub(r"\[\+\]", "[]", normalized)
        return normalized


# =============================================================================
# Convenience Functions
# =============================================================================


def generate_coverage_report(
    mapping: TransactionMapping,
    x12_schema: Any = None,
) -> MappingCoverageReport:
    """Generate a coverage report for a mapping."""
    validator = MappingValidator()
    return validator.validate(mapping, x12_schema)


def print_coverage_report(mapping: TransactionMapping) -> None:
    """Print a coverage report to stdout."""
    report = generate_coverage_report(mapping)
    print(report.to_report())
