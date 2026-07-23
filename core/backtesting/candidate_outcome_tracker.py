"""Incremental research tracker for observational candidate outcomes."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from uuid import UUID

from core.data.models import MarketBar
from core.strategies import CandidateTrade

from .candidate_outcome_evaluator import CandidateOutcomeEvaluator
from .candidate_outcome_models import (
    CandidateOutcome,
    CandidateOutcomeEvaluation,
)


@dataclass(slots=True)
class _PendingCandidate:
    candidate: CandidateTrade
    bars: list[MarketBar] = field(default_factory=list)


class CandidateOutcomeTracker:
    """Advance candidate research outcomes one completed bar at a time."""

    _TERMINAL_OUTCOMES = {
        CandidateOutcome.TARGET_REACHED,
        CandidateOutcome.STOP_REACHED,
        CandidateOutcome.AMBIGUOUS_SAME_BAR,
    }

    def __init__(
        self,
        evaluator: CandidateOutcomeEvaluator | None = None,
    ) -> None:
        self._evaluator = evaluator or CandidateOutcomeEvaluator()
        self._pending: dict[UUID, _PendingCandidate] = {}
        self._evaluations: list[CandidateOutcomeEvaluation] = []

    def reset(self) -> None:
        self._pending.clear()
        self._evaluations.clear()

    def register(self, candidate: CandidateTrade) -> None:
        if not isinstance(candidate, CandidateTrade):
            raise TypeError("candidate must be CandidateTrade")
        setup_id = candidate.setup.setup_id
        if setup_id in self._pending or any(
            item.setup_id == setup_id for item in self._evaluations
        ):
            raise ValueError("candidate setup_id is already registered")
        self._pending[setup_id] = _PendingCandidate(candidate=candidate)

    def process_bar(self, bar: MarketBar) -> None:
        if not isinstance(bar, MarketBar):
            raise TypeError("bar must be MarketBar")

        completed: list[UUID] = []
        for setup_id, pending in tuple(self._pending.items()):
            if bar.timestamp <= pending.candidate.created_at:
                continue
            if pending.bars and bar.timestamp <= pending.bars[-1].timestamp:
                raise ValueError(
                    "candidate outcome bars must be strictly increasing"
                )

            pending.bars.append(bar)
            evaluation = self._evaluator.evaluate(
                pending.candidate,
                tuple(pending.bars),
            )
            if evaluation.outcome in self._TERMINAL_OUTCOMES:
                self._evaluations.append(evaluation)
                completed.append(setup_id)

        for setup_id in completed:
            del self._pending[setup_id]

    def finalize(self) -> tuple[CandidateOutcomeEvaluation, ...]:
        for setup_id, pending in tuple(self._pending.items()):
            evaluation = self._evaluator.evaluate(
                pending.candidate,
                tuple(pending.bars),
            )
            self._evaluations.append(evaluation)
            del self._pending[setup_id]
        return self.evaluations

    @property
    def evaluations(self) -> tuple[CandidateOutcomeEvaluation, ...]:
        return tuple(self._evaluations)

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    def summary(self) -> dict[str, int]:
        counts = Counter(
            evaluation.outcome.value
            for evaluation in self._evaluations
        )
        return {
            outcome.value: counts.get(outcome.value, 0)
            for outcome in CandidateOutcome
        }
