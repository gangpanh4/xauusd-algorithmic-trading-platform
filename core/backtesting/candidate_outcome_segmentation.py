"""Segmented validation statistics for observational candidate outcomes."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .candidate_outcome_models import CandidateOutcomeEvaluation
from .candidate_outcome_statistics import (
    CandidateOutcomeStatistics,
    CandidateOutcomeStatisticsCalculator,
)


@dataclass(slots=True, frozen=True)
class CandidateOutcomeSegment:
    """One deterministic candidate-outcome statistics group."""

    key: str
    statistics: CandidateOutcomeStatistics


@dataclass(slots=True, frozen=True)
class CandidateOutcomeSegmentation:
    """Candidate validation grouped by stable typed provenance fields."""

    by_strategy_id: tuple[CandidateOutcomeSegment, ...]
    by_direction: tuple[CandidateOutcomeSegment, ...]
    by_setup_timeframe: tuple[CandidateOutcomeSegment, ...]
    by_trigger_timeframe: tuple[CandidateOutcomeSegment, ...]
    by_trigger_reason: tuple[CandidateOutcomeSegment, ...]


class CandidateOutcomeSegmentationCalculator:
    """Build deterministic candidate validation segments."""

    @classmethod
    def calculate(
        cls,
        evaluations: Sequence[CandidateOutcomeEvaluation],
    ) -> CandidateOutcomeSegmentation:
        validated = cls._validate(evaluations)

        return CandidateOutcomeSegmentation(
            by_strategy_id=cls._group(
                validated,
                lambda item: item.strategy_id,
            ),
            by_direction=cls._group(
                validated,
                lambda item: (
                    item.direction.value
                    if item.direction is not None
                    else None
                ),
            ),
            by_setup_timeframe=cls._group(
                validated,
                lambda item: (
                    item.setup_timeframe.value
                    if item.setup_timeframe is not None
                    else None
                ),
            ),
            by_trigger_timeframe=cls._group(
                validated,
                lambda item: (
                    item.trigger_timeframe.value
                    if item.trigger_timeframe is not None
                    else None
                ),
            ),
            by_trigger_reason=cls._group(
                validated,
                lambda item: item.trigger_reason,
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
    def _group(
        evaluations: tuple[CandidateOutcomeEvaluation, ...],
        key_getter: Callable[[CandidateOutcomeEvaluation], str | None],
    ) -> tuple[CandidateOutcomeSegment, ...]:
        groups: dict[str, list[CandidateOutcomeEvaluation]] = defaultdict(list)

        for evaluation in evaluations:
            raw_key = key_getter(evaluation)
            key = raw_key.strip() if isinstance(raw_key, str) else ""
            groups[key or "UNKNOWN"].append(evaluation)

        return tuple(
            CandidateOutcomeSegment(
                key=key,
                statistics=CandidateOutcomeStatisticsCalculator.calculate(
                    tuple(groups[key])
                ),
            )
            for key in sorted(groups)
        )
