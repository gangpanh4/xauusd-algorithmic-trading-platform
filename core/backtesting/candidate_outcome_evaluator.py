"""Forward-bar evaluator for observational candidate trades."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from core.data.models import MarketBar
from core.strategies import CandidateTrade, SetupDirection

from .candidate_outcome_models import (
    CandidateOutcome,
    CandidateOutcomeEvaluation,
)


class CandidateOutcomeEvaluator:
    """Measure candidate outcomes without creating simulated positions.

    Only bars strictly after ``candidate.created_at`` are considered. When a
    single OHLC bar touches both stop and target, intrabar order is unknowable;
    the result is explicitly marked ``AMBIGUOUS_SAME_BAR``.
    """

    def evaluate(
        self,
        candidate: CandidateTrade,
        future_bars: Sequence[MarketBar],
        *,
        maximum_bars: int | None = None,
    ) -> CandidateOutcomeEvaluation:
        if not isinstance(candidate, CandidateTrade):
            raise TypeError("candidate must be CandidateTrade")
        if isinstance(future_bars, (str, bytes, bytearray)) or not isinstance(
            future_bars,
            Sequence,
        ):
            raise TypeError("future_bars must be a sequence")
        if maximum_bars is not None:
            if isinstance(maximum_bars, bool) or not isinstance(
                maximum_bars,
                int,
            ):
                raise TypeError("maximum_bars must be an integer or None")
            if maximum_bars <= 0:
                raise ValueError("maximum_bars must be greater than zero")

        bars = self._prepare_bars(
            future_bars,
            created_at=candidate.created_at,
            maximum_bars=maximum_bars,
        )
        entry = candidate.entry_price
        stop = candidate.stop_loss_price
        targets = candidate.take_profit_prices
        risk = candidate.initial_risk_distance
        direction = candidate.setup.direction

        maximum_favorable = 0.0
        maximum_adverse = 0.0
        highest_target_index: int | None = None
        outcome = CandidateOutcome.UNRESOLVED
        outcome_timestamp: datetime | None = None

        for bar in bars:
            favorable, adverse = self._excursions(
                direction=direction,
                entry=entry,
                bar=bar,
            )
            maximum_favorable = max(maximum_favorable, favorable)
            maximum_adverse = max(maximum_adverse, adverse)

            reached_targets = self._reached_target_indexes(
                direction=direction,
                targets=targets,
                bar=bar,
            )
            if reached_targets:
                highest_target_index = max(
                    highest_target_index
                    if highest_target_index is not None
                    else -1,
                    max(reached_targets),
                )

            stop_reached = self._stop_reached(
                direction=direction,
                stop=stop,
                bar=bar,
            )
            target_reached = bool(reached_targets)

            if stop_reached and target_reached:
                outcome = CandidateOutcome.AMBIGUOUS_SAME_BAR
                outcome_timestamp = bar.timestamp.astimezone(UTC)
                break
            if stop_reached:
                outcome = CandidateOutcome.STOP_REACHED
                outcome_timestamp = bar.timestamp.astimezone(UTC)
                break
            if target_reached:
                outcome = CandidateOutcome.TARGET_REACHED
                outcome_timestamp = bar.timestamp.astimezone(UTC)
                break

        evaluated_through = (
            bars[-1].timestamp.astimezone(UTC)
            if bars
            else candidate.created_at
        )
        return CandidateOutcomeEvaluation(
            setup_id=candidate.setup.setup_id,
            candidate_created_at=candidate.created_at,
            evaluated_through=evaluated_through,
            outcome=outcome,
            outcome_timestamp=outcome_timestamp,
            entry_price=entry,
            stop_loss_price=stop,
            take_profit_prices=targets,
            highest_target_index_reached=highest_target_index,
            bars_evaluated=len(bars),
            maximum_favorable_excursion=maximum_favorable,
            maximum_adverse_excursion=maximum_adverse,
            maximum_favorable_r_multiple=maximum_favorable / risk,
            maximum_adverse_r_multiple=maximum_adverse / risk,
            strategy_id=candidate.setup.strategy_id,
            direction=candidate.setup.direction,
            setup_timeframe=candidate.setup.setup_timeframe,
            trigger_timeframe=candidate.trigger.timeframe,
            trigger_reason=candidate.trigger.reason,
            setup_metadata=candidate.setup.metadata,
            trigger_metadata=candidate.trigger.metadata,
            candidate_metadata=candidate.metadata,
        )

    @staticmethod
    def _prepare_bars(
        bars: Sequence[MarketBar],
        *,
        created_at: datetime,
        maximum_bars: int | None,
    ) -> tuple[MarketBar, ...]:
        selected: list[MarketBar] = []
        previous_timestamp: datetime | None = None
        created = created_at.astimezone(UTC)

        for bar in bars:
            if not isinstance(bar, MarketBar):
                raise TypeError(
                    "future_bars must contain MarketBar instances"
                )
            timestamp = bar.timestamp
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError("bar timestamps must be timezone-aware")
            timestamp = timestamp.astimezone(UTC)
            if (
                previous_timestamp is not None
                and timestamp <= previous_timestamp
            ):
                raise ValueError(
                    "future bar timestamps must be strictly increasing"
                )
            previous_timestamp = timestamp

            if timestamp <= created:
                continue
            selected.append(bar)
            if maximum_bars is not None and len(selected) >= maximum_bars:
                break

        return tuple(selected)

    @staticmethod
    def _excursions(
        *,
        direction: SetupDirection,
        entry: float,
        bar: MarketBar,
    ) -> tuple[float, float]:
        if direction is SetupDirection.BUY:
            return (
                max(0.0, bar.high - entry),
                max(0.0, entry - bar.low),
            )
        return (
            max(0.0, entry - bar.low),
            max(0.0, bar.high - entry),
        )

    @staticmethod
    def _stop_reached(
        *,
        direction: SetupDirection,
        stop: float,
        bar: MarketBar,
    ) -> bool:
        if direction is SetupDirection.BUY:
            return bar.low <= stop
        return bar.high >= stop

    @staticmethod
    def _reached_target_indexes(
        *,
        direction: SetupDirection,
        targets: tuple[float, ...],
        bar: MarketBar,
    ) -> tuple[int, ...]:
        if direction is SetupDirection.BUY:
            return tuple(
                index
                for index, target in enumerate(targets)
                if bar.high >= target
            )
        return tuple(
            index
            for index, target in enumerate(targets)
            if bar.low <= target
        )
