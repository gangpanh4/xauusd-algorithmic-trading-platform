"""Composite output for one completed historical backtest run."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from .candidate_outcome_models import CandidateOutcomeEvaluation
from .models import BacktestResult
from .strategy_comparison import BacktestStrategyComparison


@dataclass(slots=True, frozen=True)
class BacktestRunOutput:
    """Bundle execution and observational research results from one run.

    ``BacktestResult`` remains unchanged. Candidate outcome fields are additive
    and default to empty values so existing two-argument construction remains
    backward compatible.
    """

    result: BacktestResult
    strategy_comparison: BacktestStrategyComparison
    candidate_outcome_evaluations: tuple[
        CandidateOutcomeEvaluation,
        ...,
    ] = ()
    candidate_outcome_summary: Mapping[str, int] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not isinstance(self.result, BacktestResult):
            raise TypeError("result must be BacktestResult")
        if not isinstance(
            self.strategy_comparison,
            BacktestStrategyComparison,
        ):
            raise TypeError(
                "strategy_comparison must be BacktestStrategyComparison"
            )

        evaluations = tuple(self.candidate_outcome_evaluations)
        if any(
            not isinstance(item, CandidateOutcomeEvaluation)
            for item in evaluations
        ):
            raise TypeError(
                "candidate_outcome_evaluations must contain "
                "CandidateOutcomeEvaluation values"
            )
        object.__setattr__(
            self,
            "candidate_outcome_evaluations",
            evaluations,
        )

        if not isinstance(self.candidate_outcome_summary, Mapping):
            raise TypeError("candidate_outcome_summary must be a mapping")

        normalized_summary: dict[str, int] = {}
        for key, value in self.candidate_outcome_summary.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError(
                    "candidate outcome summary keys must be non-empty strings"
                )
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(
                    "candidate outcome summary values must be integers"
                )
            if value < 0:
                raise ValueError(
                    "candidate outcome summary values cannot be negative"
                )
            normalized_summary[key.strip()] = value

        object.__setattr__(
            self,
            "candidate_outcome_summary",
            MappingProxyType(dict(sorted(normalized_summary.items()))),
        )
