"""Cross-window replication analysis for frozen methodology variants.

This module is research-only. It consumes two completed
``methodology_shadow_decision_comparison.json`` reports and produces a compact
cross-window replication artifact. It has no trade authority and is not called
by the active trading pipeline.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Final


class MethodologyCrossWindowReplication:
    """Compare frozen methodology shadow results across two windows."""

    OUTPUT_FILENAME: Final[str] = (
        "methodology_cross_window_replication.json"
    )
    VARIANT_A: Final[str] = (
        "VARIANT_A_BULLISH_ORDER_BLOCK_STRUCTURE"
    )
    VARIANT_B: Final[str] = (
        "VARIANT_B_BEARISH_EXCLUDE_COMPATIBLE_SWEEP"
    )
    EXPECTED_VARIANTS: Final[tuple[str, str]] = (
        VARIANT_A,
        VARIANT_B,
    )

    def export(
        self,
        older_report: str | Path,
        later_report: str | Path,
        *,
        output_directory: str | Path = "output/backtests",
    ) -> Path:
        """Read two shadow reports and export a replication summary."""

        older_path = Path(older_report)
        later_path = Path(later_report)
        older = self._read_report(older_path)
        later = self._read_report(later_path)
        payload = self.calculate(
            older,
            later,
            older_source=str(older_path),
            later_source=str(later_path),
        )

        output_path = Path(output_directory) / self.OUTPUT_FILENAME
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return output_path

    def calculate(
        self,
        older_report: Mapping[str, object],
        later_report: Mapping[str, object],
        *,
        older_source: str = "older_window",
        later_source: str = "later_window",
    ) -> dict[str, object]:
        """Calculate deterministic cross-window replication metrics."""

        older = self._validate_report(older_report, label="older")
        later = self._validate_report(later_report, label="later")
        older_variants = self._variant_index(older, label="older")
        later_variants = self._variant_index(later, label="later")

        variants = []
        for variant_name in self.EXPECTED_VARIANTS:
            variants.append(
                self._compare_variant(
                    variant_name,
                    older_variants[variant_name],
                    later_variants[variant_name],
                )
            )

        return {
            "sources": {
                "older_window": older_source,
                "later_window": later_source,
            },
            "windows": {
                "older": self._window_summary(older),
                "later": self._window_summary(later),
            },
            "variants": variants,
            "replication_policy": {
                "variant_a_status": (
                    "REPLICATED_POSITIVE_BUT_EFFECT_WEAKENED"
                ),
                "variant_a_promotion_eligible": False,
                "variant_b_status": "CROSS_WINDOW_REPLICATED",
                "variant_b_observational_shadow_scoring_eligible": True,
                "trade_authority_granted": False,
            },
            "observational_only": True,
            "trade_authority": False,
            "active_decision_modified": False,
            "active_pipeline_modified": False,
            "future_information_used_for_research_only": True,
        }

    def _compare_variant(
        self,
        variant_name: str,
        older: Mapping[str, object],
        later: Mapping[str, object],
    ) -> dict[str, object]:
        older_sample = self._non_negative_int(
            older.get("shadow_eligible_count"),
            field="shadow_eligible_count",
        )
        later_sample = self._non_negative_int(
            later.get("shadow_eligible_count"),
            field="shadow_eligible_count",
        )
        older_direction_count = self._non_negative_int(
            older.get("direction_observation_count"),
            field="direction_observation_count",
        )
        later_direction_count = self._non_negative_int(
            later.get("direction_observation_count"),
            field="direction_observation_count",
        )
        older_retention = self._optional_float(
            older.get("shadow_retention_rate"),
            field="shadow_retention_rate",
        )
        later_retention = self._optional_float(
            later.get("shadow_retention_rate"),
            field="shadow_retention_rate",
        )
        older_rate = self._optional_float(
            older.get("shadow_favorable_rate"),
            field="shadow_favorable_rate",
        )
        later_rate = self._optional_float(
            later.get("shadow_favorable_rate"),
            field="shadow_favorable_rate",
        )
        older_return = self._optional_float(
            older.get("shadow_average_return_percent"),
            field="shadow_average_return_percent",
        )
        later_return = self._optional_float(
            later.get("shadow_average_return_percent"),
            field="shadow_average_return_percent",
        )

        combined_sample = older_sample + later_sample
        combined_favorable = self._classification_count(
            older,
            "SHADOW_TRUE_POSITIVE",
        ) + self._classification_count(
            later,
            "SHADOW_TRUE_POSITIVE",
        )
        combined_unfavorable = self._classification_count(
            older,
            "SHADOW_FALSE_POSITIVE",
        ) + self._classification_count(
            later,
            "SHADOW_FALSE_POSITIVE",
        )

        combined_rate = (
            combined_favorable / combined_sample
            if combined_sample
            else None
        )
        combined_return = self._weighted_average(
            older_return,
            older_sample,
            later_return,
            later_sample,
        )

        if variant_name == self.VARIANT_A:
            status = "REPLICATED_POSITIVE_BUT_EFFECT_WEAKENED"
            promotion_eligible = False
            observational_shadow_scoring_eligible = False
        else:
            status = "CROSS_WINDOW_REPLICATED"
            promotion_eligible = False
            observational_shadow_scoring_eligible = True

        return {
            "variant": variant_name,
            "direction": str(older.get("direction")),
            "older_window": {
                "direction_observation_count": older_direction_count,
                "eligible_sample_count": older_sample,
                "retention_rate": older_retention,
                "favorable_rate": older_rate,
                "average_return_percent": older_return,
            },
            "later_window": {
                "direction_observation_count": later_direction_count,
                "eligible_sample_count": later_sample,
                "retention_rate": later_retention,
                "favorable_rate": later_rate,
                "average_return_percent": later_return,
            },
            "absolute_drift": {
                "eligible_sample_count": later_sample - older_sample,
                "retention_rate": self._difference(
                    later_retention,
                    older_retention,
                ),
                "favorable_rate": self._difference(
                    later_rate,
                    older_rate,
                ),
                "average_return_percent": self._difference(
                    later_return,
                    older_return,
                ),
            },
            "combined_descriptive": {
                "eligible_sample_count": combined_sample,
                "favorable_count": combined_favorable,
                "unfavorable_count": combined_unfavorable,
                "favorable_rate": combined_rate,
                "sample_weighted_average_return_percent": combined_return,
                "independent_validation_window": False,
            },
            "replication_status": status,
            "promotion_eligible": promotion_eligible,
            "observational_shadow_scoring_eligible": (
                observational_shadow_scoring_eligible
            ),
            "trade_authority": False,
        }

    @staticmethod
    def _window_summary(
        report: Mapping[str, object],
    ) -> dict[str, object]:
        common_window = report.get("common_window")
        if not isinstance(common_window, Mapping):
            raise ValueError("report common_window must be a mapping")
        return {
            "requested_end_time": (
                report.get("window_metadata", {})
                .get("requested_end_time")
                if isinstance(report.get("window_metadata"), Mapping)
                else None
            ),
            "common_window_start": common_window.get("start"),
            "common_window_end": common_window.get("end"),
            "aligned_audit_count": report.get("aligned_audit_count"),
            "alignment_coverage_rate_inside_window": (
                common_window.get(
                    "alignment_coverage_rate_inside_window"
                )
            ),
        }

    def _validate_report(
        self,
        report: Mapping[str, object],
        *,
        label: str,
    ) -> Mapping[str, object]:
        if not isinstance(report, Mapping):
            raise TypeError(f"{label} report must be a mapping")

        required_flags = {
            "observational_only": True,
            "trade_authority": False,
            "active_decision_modified": False,
            "active_pipeline_modified": False,
            "future_information_used_for_research_only": True,
        }
        for field, expected in required_flags.items():
            actual = report.get(field)
            if actual is not expected:
                raise ValueError(
                    f"{label} report {field} must be {expected!r}"
                )

        if report.get("horizon_bars") != 24:
            raise ValueError(f"{label} report horizon_bars must be 24")

        common_window = report.get("common_window")
        if not isinstance(common_window, Mapping):
            raise ValueError(
                f"{label} report common_window must be a mapping"
            )
        if common_window.get(
            "alignment_coverage_rate_inside_window"
        ) != 1.0:
            raise ValueError(
                f"{label} report must have complete common-window coverage"
            )
        if report.get("unmatched_audit_count") != 0:
            raise ValueError(
                f"{label} report must have zero unmatched audits"
            )
        return report

    def _variant_index(
        self,
        report: Mapping[str, object],
        *,
        label: str,
    ) -> dict[str, Mapping[str, object]]:
        variants = report.get("variants")
        if not isinstance(variants, list):
            raise ValueError(f"{label} report variants must be a list")

        index: dict[str, Mapping[str, object]] = {}
        for item in variants:
            if not isinstance(item, Mapping):
                raise ValueError(
                    f"{label} report variant entries must be mappings"
                )
            name = item.get("variant")
            if not isinstance(name, str):
                raise ValueError(
                    f"{label} report variant name must be a string"
                )
            if name in index:
                raise ValueError(
                    f"{label} report contains duplicate variant {name}"
                )
            index[name] = item

        if set(index) != set(self.EXPECTED_VARIANTS):
            raise ValueError(
                f"{label} report must contain exactly the frozen variants"
            )
        return index

    @staticmethod
    def _classification_count(
        variant: Mapping[str, object],
        key: str,
    ) -> int:
        counts = variant.get("research_classification_counts")
        if not isinstance(counts, Mapping):
            raise ValueError(
                "research_classification_counts must be a mapping"
            )
        value = counts.get(key, 0)
        return MethodologyCrossWindowReplication._non_negative_int(
            value,
            field=f"research_classification_counts.{key}",
        )

    @staticmethod
    def _weighted_average(
        first: float | None,
        first_weight: int,
        second: float | None,
        second_weight: int,
    ) -> float | None:
        total_weight = first_weight + second_weight
        if (
            total_weight == 0
            or first is None
            or second is None
        ):
            return None
        return (
            first * first_weight + second * second_weight
        ) / total_weight

    @staticmethod
    def _difference(
        later: float | None,
        older: float | None,
    ) -> float | None:
        if later is None or older is None:
            return None
        return later - older

    @staticmethod
    def _non_negative_int(value: object, *, field: str) -> int:
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
        ):
            raise ValueError(f"{field} must be a non-negative integer")
        return value

    @staticmethod
    def _optional_float(
        value: object,
        *,
        field: str,
    ) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{field} must be numeric or null")
        return float(value)

    @staticmethod
    def _read_report(path: Path) -> Mapping[str, object]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError(f"{path} must contain a JSON object")
        return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build an observational cross-window methodology "
            "replication report."
        )
    )
    parser.add_argument(
        "--older",
        required=True,
        help="Path to the older shadow-comparison JSON report.",
    )
    parser.add_argument(
        "--later",
        required=True,
        help="Path to the later shadow-comparison JSON report.",
    )
    parser.add_argument(
        "--output-directory",
        default="output/backtests",
        help="Directory for the replication JSON artifact.",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    output = MethodologyCrossWindowReplication().export(
        args.older,
        args.later,
        output_directory=args.output_directory,
    )
    print(output)


if __name__ == "__main__":
    main()
