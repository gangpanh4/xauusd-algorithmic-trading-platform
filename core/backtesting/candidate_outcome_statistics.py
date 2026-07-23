"""Aggregate statistics for observational candidate outcomes."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import fmean, median

from .candidate_outcome_models import (
    CandidateOutcome,
    CandidateOutcomeEvaluation,
)


@dataclass(slots=True, frozen=True)
class CandidateOutcomeStatistics:
    """Immutable aggregate validation metrics for candidate evaluations."""

    total_candidates: int
    resolved_candidates: int
    target_reached_count: int
    stop_reached_count: int
    ambiguous_same_bar_count: int
    unresolved_count: int
    target_hit_rate: float
    stop_rate: float
    ambiguous_same_bar_rate: float
    unresolved_rate: float
    average_mfe_r: float
    median_mfe_r: float
    average_mae_r: float
    median_mae_r: float
    average_bars_evaluated: float
    average_bars_to_terminal_outcome: float
    target_index_hit_counts: tuple[tuple[int, int], ...]


class CandidateOutcomeStatisticsCalculator:
    """Calculate deterministic research metrics from finalized outcomes."""

    @classmethod
    def calculate(
        cls,
        evaluations: Sequence[CandidateOutcomeEvaluation],
    ) -> CandidateOutcomeStatistics:
        validated = cls._validate(evaluations)
        total = len(validated)

        outcome_counts = Counter(
            evaluation.outcome
            for evaluation in validated
        )
        target_count = outcome_counts[CandidateOutcome.TARGET_REACHED]
        stop_count = outcome_counts[CandidateOutcome.STOP_REACHED]
        ambiguous_count = outcome_counts[
            CandidateOutcome.AMBIGUOUS_SAME_BAR
        ]
        unresolved_count = outcome_counts[CandidateOutcome.UNRESOLVED]
        resolved_count = total - unresolved_count

        mfe_values = [
            evaluation.maximum_favorable_r_multiple
            for evaluation in validated
        ]
        mae_values = [
            evaluation.maximum_adverse_r_multiple
            for evaluation in validated
        ]
        bars_values = [
            evaluation.bars_evaluated
            for evaluation in validated
        ]
        terminal_bars = [
            evaluation.bars_evaluated
            for evaluation in validated
            if evaluation.outcome is not CandidateOutcome.UNRESOLVED
        ]

        target_index_counts = Counter(
            evaluation.highest_target_index_reached
            for evaluation in validated
            if evaluation.highest_target_index_reached is not None
        )

        return CandidateOutcomeStatistics(
            total_candidates=total,
            resolved_candidates=resolved_count,
            target_reached_count=target_count,
            stop_reached_count=stop_count,
            ambiguous_same_bar_count=ambiguous_count,
            unresolved_count=unresolved_count,
            target_hit_rate=cls._rate(target_count, total),
            stop_rate=cls._rate(stop_count, total),
            ambiguous_same_bar_rate=cls._rate(
                ambiguous_count,
                total,
            ),
            unresolved_rate=cls._rate(unresolved_count, total),
            average_mfe_r=cls._mean(mfe_values),
            median_mfe_r=cls._median(mfe_values),
            average_mae_r=cls._mean(mae_values),
            median_mae_r=cls._median(mae_values),
            average_bars_evaluated=cls._mean(bars_values),
            average_bars_to_terminal_outcome=cls._mean(
                terminal_bars
            ),
            target_index_hit_counts=tuple(
                sorted(target_index_counts.items())
            ),
        )

    @staticmethod
    def _validate(
        evaluations: Sequence[CandidateOutcomeEvaluation],
    ) -> tuple[CandidateOutcomeEvaluation, ...]:
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
        return validated

    @staticmethod
    def _rate(count: int, total: int) -> float:
        return count / total if total else 0.0

    @staticmethod
    def _mean(values: Sequence[float | int]) -> float:
        return float(fmean(values)) if values else 0.0

    @staticmethod
    def _median(values: Sequence[float | int]) -> float:
        return float(median(values)) if values else 0.0
