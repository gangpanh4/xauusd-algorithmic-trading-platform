"""Research-only SMC and ICT methodology observation for backtesting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from core.strategies.context import StrategyContext
from core.strategies.ict_methodology import ICTMethodologyEvaluator
from core.strategies.methodology_models import (
    MethodologyEvaluationStatus,
    MethodologyIdentifier,
    MethodologyResult,
)
from core.strategies.smc_ict_context import SMCICTContext
from core.strategies.smc_ict_context_builder import SMCICTContextBuilder
from core.strategies.smc_methodology import SMCMethodologyEvaluator


@dataclass(frozen=True, slots=True)
class MethodologyObservation:
    """Immutable research record for one completed strategy candle."""

    timestamp: datetime
    context: SMCICTContext
    smc: MethodologyResult
    ict: MethodologyResult

    def __post_init__(self) -> None:
        if not isinstance(self.timestamp, datetime):
            raise TypeError("timestamp must be a datetime")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        normalized = self.timestamp.astimezone(UTC)
        object.__setattr__(self, "timestamp", normalized)

        if not isinstance(self.context, SMCICTContext):
            raise TypeError("context must be SMCICTContext")
        if not isinstance(self.smc, MethodologyResult):
            raise TypeError("smc must be MethodologyResult")
        if not isinstance(self.ict, MethodologyResult):
            raise TypeError("ict must be MethodologyResult")
        if self.smc.methodology is not MethodologyIdentifier.SMC:
            raise ValueError("smc result must use MethodologyIdentifier.SMC")
        if self.ict.methodology is not MethodologyIdentifier.ICT:
            raise ValueError("ict result must use MethodologyIdentifier.ICT")

        timestamps = (
            self.context.timestamp,
            self.smc.timestamp,
            self.ict.timestamp,
        )
        if any(value.astimezone(UTC) != normalized for value in timestamps):
            raise ValueError(
                "context and methodology result timestamps must match observation"
            )


class BacktestMethodologyObserver:
    """Evaluate and retain methodology diagnostics without trade authority."""

    def __init__(
        self,
        *,
        context_builder: SMCICTContextBuilder | None = None,
        smc_evaluator: SMCMethodologyEvaluator | None = None,
        ict_evaluator: ICTMethodologyEvaluator | None = None,
    ) -> None:
        self.context_builder = context_builder or SMCICTContextBuilder()
        self.smc_evaluator = smc_evaluator or SMCMethodologyEvaluator()
        self.ict_evaluator = ict_evaluator or ICTMethodologyEvaluator()
        self._observations: list[MethodologyObservation] = []
        self._last_timestamp: datetime | None = None

    def reset(self) -> None:
        """Clear stored diagnostics and chronology."""

        self._observations.clear()
        self._last_timestamp = None

    def observe(self, context: StrategyContext) -> MethodologyObservation:
        """Evaluate one completed strategy context deterministically."""

        if not isinstance(context, StrategyContext):
            raise TypeError("context must be StrategyContext")

        timestamp = context.current_bar.timestamp.astimezone(UTC)
        if self._last_timestamp is not None and timestamp <= self._last_timestamp:
            raise ValueError(
                "methodology observation timestamps must be strictly increasing"
            )

        shared_context = self.context_builder.build(context)
        smc_result = self.smc_evaluator.evaluate(shared_context)
        ict_result = self.ict_evaluator.evaluate(shared_context)
        observation = MethodologyObservation(
            timestamp=timestamp,
            context=shared_context,
            smc=smc_result,
            ict=ict_result,
        )
        self._observations.append(observation)
        self._last_timestamp = timestamp
        return observation

    @property
    def observations(self) -> tuple[MethodologyObservation, ...]:
        """Return immutable chronological methodology observations."""

        return tuple(self._observations)

    def summary(self) -> dict[str, int]:
        """Return deterministic counts by methodology and evaluation status."""

        summary: dict[str, int] = {}
        for observation in self._observations:
            for result in (observation.smc, observation.ict):
                key = (
                    f"{result.methodology.value}:"
                    f"{result.evaluation_status.value}"
                )
                summary[key] = summary.get(key, 0) + 1
        return dict(sorted(summary.items()))

    def status_count(
        self,
        methodology: MethodologyIdentifier,
        status: MethodologyEvaluationStatus,
    ) -> int:
        """Return one explicit methodology/status count."""

        if not isinstance(methodology, MethodologyIdentifier):
            raise TypeError("methodology must be MethodologyIdentifier")
        if not isinstance(status, MethodologyEvaluationStatus):
            raise TypeError("status must be MethodologyEvaluationStatus")
        return sum(
            result.evaluation_status is status
            for observation in self._observations
            for result in (
                observation.smc
                if methodology is MethodologyIdentifier.SMC
                else observation.ict,
            )
        )
