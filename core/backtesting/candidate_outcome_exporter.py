"""Export observational candidate outcome research artifacts."""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from pathlib import Path

from .candidate_outcome_models import CandidateOutcomeEvaluation
from .candidate_outcome_segmentation import (
    CandidateOutcomeSegmentation,
    CandidateOutcomeSegment,
)
from .candidate_outcome_statistics import CandidateOutcomeStatistics


class CandidateOutcomeExporter:
    """Write deterministic candidate-outcome research files."""

    def __init__(
        self,
        output_directory: str | Path = "output/backtests",
    ) -> None:
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    def export_summary(
        self,
        summary: Mapping[str, int],
    ) -> Path:
        """Export ``candidate_outcome_summary.json``."""

        if not isinstance(summary, Mapping):
            raise TypeError("summary must be a mapping")

        payload: dict[str, int] = {}
        for key, value in summary.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError(
                    "summary keys must be non-empty strings"
                )
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError("summary values must be integers")
            if value < 0:
                raise ValueError("summary values cannot be negative")
            payload[key.strip()] = value

        path = (
            self.output_directory
            / "candidate_outcome_summary.json"
        )
        self._write_json(path, dict(sorted(payload.items())))
        return path

    def export_statistics(
        self,
        statistics: CandidateOutcomeStatistics,
    ) -> Path:
        """Export ``candidate_outcome_statistics.json``."""

        if not isinstance(statistics, CandidateOutcomeStatistics):
            raise TypeError(
                "statistics must be CandidateOutcomeStatistics"
            )

        payload = self._statistics_payload(statistics)

        path = (
            self.output_directory
            / "candidate_outcome_statistics.json"
        )
        self._write_json(path, payload)
        return path

    def export_segments(
        self,
        segmentation: CandidateOutcomeSegmentation,
    ) -> Path:
        """Export ``candidate_outcome_segments.json``."""

        if not isinstance(segmentation, CandidateOutcomeSegmentation):
            raise TypeError(
                "segmentation must be CandidateOutcomeSegmentation"
            )

        payload = {
            "by_strategy_id": self._segments_payload(
                segmentation.by_strategy_id
            ),
            "by_direction": self._segments_payload(
                segmentation.by_direction
            ),
            "by_setup_timeframe": self._segments_payload(
                segmentation.by_setup_timeframe
            ),
            "by_trigger_timeframe": self._segments_payload(
                segmentation.by_trigger_timeframe
            ),
            "by_trigger_reason": self._segments_payload(
                segmentation.by_trigger_reason
            ),
        }

        path = (
            self.output_directory
            / "candidate_outcome_segments.json"
        )
        self._write_json(path, payload)
        return path

    def export_evaluations(
        self,
        evaluations: Sequence[CandidateOutcomeEvaluation],
    ) -> Path:
        """Export one row per candidate to ``candidate_outcomes.csv``."""

        if isinstance(evaluations, (str, bytes, bytearray)) or not isinstance(
            evaluations,
            Sequence,
        ):
            raise TypeError("evaluations must be a sequence")

        validated = tuple(evaluations)
        if any(
            not isinstance(item, CandidateOutcomeEvaluation)
            for item in validated
        ):
            raise TypeError(
                "evaluations must contain CandidateOutcomeEvaluation values"
            )

        path = self.output_directory / "candidate_outcomes.csv"
        fieldnames = (
            "Candidate Number",
            "Setup ID",
            "Candidate Created At",
            "Evaluated Through",
            "Outcome",
            "Outcome Timestamp",
            "Entry Price",
            "Stop Loss Price",
            "Take Profit Prices",
            "Highest Target Index Reached",
            "Bars Evaluated",
            "Maximum Favorable Excursion",
            "Maximum Adverse Excursion",
            "Maximum Favorable R Multiple",
            "Maximum Adverse R Multiple",
        )

        with path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=list(fieldnames),
                extrasaction="raise",
            )
            writer.writeheader()

            for index, evaluation in enumerate(
                validated,
                start=1,
            ):
                writer.writerow(
                    {
                        "Candidate Number": index,
                        "Setup ID": str(evaluation.setup_id),
                        "Candidate Created At": (
                            evaluation.candidate_created_at.isoformat()
                        ),
                        "Evaluated Through": (
                            evaluation.evaluated_through.isoformat()
                        ),
                        "Outcome": evaluation.outcome.value,
                        "Outcome Timestamp": (
                            evaluation.outcome_timestamp.isoformat()
                            if evaluation.outcome_timestamp is not None
                            else ""
                        ),
                        "Entry Price": evaluation.entry_price,
                        "Stop Loss Price": evaluation.stop_loss_price,
                        "Take Profit Prices": json.dumps(
                            list(evaluation.take_profit_prices),
                            separators=(",", ":"),
                        ),
                        "Highest Target Index Reached": (
                            evaluation.highest_target_index_reached
                            if evaluation.highest_target_index_reached
                            is not None
                            else ""
                        ),
                        "Bars Evaluated": evaluation.bars_evaluated,
                        "Maximum Favorable Excursion": (
                            evaluation.maximum_favorable_excursion
                        ),
                        "Maximum Adverse Excursion": (
                            evaluation.maximum_adverse_excursion
                        ),
                        "Maximum Favorable R Multiple": (
                            evaluation.maximum_favorable_r_multiple
                        ),
                        "Maximum Adverse R Multiple": (
                            evaluation.maximum_adverse_r_multiple
                        ),
                    }
                )

        return path

    @classmethod
    def _segments_payload(
        cls,
        segments: tuple[CandidateOutcomeSegment, ...],
    ) -> dict[str, dict[str, object]]:
        return {
            segment.key: cls._statistics_payload(segment.statistics)
            for segment in segments
        }

    @staticmethod
    def _statistics_payload(
        statistics: CandidateOutcomeStatistics,
    ) -> dict[str, object]:
        payload = asdict(statistics)
        payload["target_index_hit_counts"] = {
            str(index): count
            for index, count in statistics.target_index_hit_counts
        }
        return payload

    @staticmethod
    def _write_json(path: Path, payload: object) -> None:
        with path.open("w", encoding="utf-8") as file:
            json.dump(
                payload,
                file,
                indent=4,
                ensure_ascii=False,
                sort_keys=True,
                allow_nan=False,
            )
