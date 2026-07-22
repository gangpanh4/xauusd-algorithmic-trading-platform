from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


# ==============================================================================
# ENUMS
# ==============================================================================


class ExperimentStatus(str, Enum):
    """Current lifecycle state of an experiment."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PromotionDecision(str, Enum):
    """Final decision after evaluating an experiment."""

    PROMOTE = "PROMOTE"
    REJECT = "REJECT"
    REVIEW = "REVIEW"


# ==============================================================================
# EXPERIMENT
# ==============================================================================


@dataclass(slots=True)
class Experiment:
    """
    Describes one research experiment.

    Examples
    --------
    Baseline

    H4 Bias Enabled

    Liquidity Filter Enabled

    Confluence Enabled
    """

    experiment_id: str
    name: str
    profile: str

    symbol: str
    timeframe: str

    description: str = ""

    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    metadata: dict[str, Any] = field(default_factory=dict)


# ==============================================================================
# BACKTEST RESULT
# ==============================================================================


@dataclass(slots=True)
class ExperimentResult:
    """
    Stores performance statistics for one experiment.
    """

    experiment_id: str

    trades: int = 0

    wins: int = 0
    losses: int = 0
    breakeven: int = 0

    win_rate: float = 0.0

    net_profit: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0

    profit_factor: float = 0.0
    expectancy: float = 0.0

    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0

    max_drawdown: float = 0.0

    average_trade: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0

    largest_win: float = 0.0
    largest_loss: float = 0.0

    metadata: dict[str, Any] = field(default_factory=dict)


# ==============================================================================
# COMPARISON
# ==============================================================================


@dataclass(slots=True)
class ExperimentComparison:
    """
    Compare two experiment results.
    """

    baseline: ExperimentResult
    candidate: ExperimentResult

    delta_net_profit: float
    delta_profit_factor: float
    delta_expectancy: float
    delta_drawdown: float

    better_experiment: str


# ==============================================================================
# PROMOTION REPORT
# ==============================================================================


@dataclass(slots=True)
class PromotionReport:
    """
    Final evaluation report.
    """

    experiment_id: str

    decision: PromotionDecision

    score: float

    approved: bool

    reasons: list[str] = field(default_factory=list)

    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )


# ==============================================================================
# RESEARCH SUMMARY
# ==============================================================================


@dataclass(slots=True)
class ResearchSummary:
    """
    Collection of completed experiments.
    """

    experiments: list[Experiment] = field(default_factory=list)

    results: list[ExperimentResult] = field(default_factory=list)

    promotion_reports: list[PromotionReport] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_experiments(self) -> int:
        return len(self.experiments)

    @property
    def completed_experiments(self) -> int:
        return len(self.results)

    @property
    def promoted_experiments(self) -> int:
        return sum(
            report.approved
            for report in self.promotion_reports
        )