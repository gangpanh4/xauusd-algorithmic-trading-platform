"""Research-only post-expiry trigger geometry and outcome tracking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from core.data.models import MarketBar
from core.strategies.context import StrategyContext
from core.strategies.models import CandidateTrade, TradingSetup
from core.strategies.xauusd_bos_choch import XAUUSDBOSCHOCHStrategy

from .candidate_outcome_evaluator import CandidateOutcomeEvaluator
from .candidate_outcome_models import CandidateOutcome


@dataclass(slots=True, frozen=True)
class PostExpiryTriggerRecord:
    setup_id: str
    strategy_id: str
    direction: str
    expired_at: datetime
    maximum_bars: int
    bars_observed: int
    trigger_found: bool
    first_trigger_at: datetime | None
    bars_after_expiry: int | None
    trigger_type: str | None
    window_complete: bool
    geometry_valid: bool | None
    entry_price: float | None
    stop_loss_price: float | None
    take_profit_prices: tuple[float, ...]
    reward_risk: float | None
    outcome: str | None
    outcome_timestamp: datetime | None
    outcome_bars_evaluated: int
    maximum_favorable_r_multiple: float | None
    maximum_adverse_r_multiple: float | None
    outcome_window_complete: bool


@dataclass(slots=True)
class _PendingExpiredSetup:
    setup: TradingSetup
    expired_at: datetime
    bars_observed: int = 0
    trigger_found: bool = False
    first_trigger_at: datetime | None = None
    bars_after_expiry: int | None = None
    trigger_type: str | None = None
    window_complete: bool = False
    geometry_valid: bool | None = None
    candidate: CandidateTrade | None = None
    outcome_bars: list[MarketBar] | None = None
    outcome: str | None = None
    outcome_timestamp: datetime | None = None
    outcome_bars_evaluated: int = 0
    maximum_favorable_r_multiple: float | None = None
    maximum_adverse_r_multiple: float | None = None
    outcome_window_complete: bool = False


class PostExpiryTriggerTracker:
    """Observe late triggers and evaluate hypothetical candidate outcomes."""

    def __init__(
        self,
        maximum_bars: int = 8,
        outcome_maximum_bars: int = 24,
        *,
        outcome_evaluator: Any | None = None,
    ) -> None:
        for value, name in (
            (maximum_bars, "maximum_bars"),
            (outcome_maximum_bars, "outcome_maximum_bars"),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer")
            if value <= 0:
                raise ValueError(f"{name} must be positive")

        self.maximum_bars = maximum_bars
        self.outcome_maximum_bars = outcome_maximum_bars
        self._pending: dict[str, _PendingExpiredSetup] = {}
        self._completed: list[_PendingExpiredSetup] = []
        self._outcome_evaluator = (
            outcome_evaluator or CandidateOutcomeEvaluator()
        )

    def reset(self) -> None:
        self._pending.clear()
        self._completed.clear()

    def register(self, setup: TradingSetup, *, expired_at: datetime) -> None:
        setup_id = str(setup.setup_id)
        if setup_id in self._pending or any(
            str(item.setup.setup_id) == setup_id for item in self._completed
        ):
            return
        self._pending[setup_id] = _PendingExpiredSetup(
            setup=setup,
            expired_at=expired_at,
        )

    def observe(
        self,
        *,
        strategy: XAUUSDBOSCHOCHStrategy,
        context: StrategyContext,
    ) -> None:
        completed_ids: list[str] = []

        for setup_id, pending in tuple(self._pending.items()):
            if pending.candidate is not None:
                self._observe_outcome_bar(pending, context.current_bar)
                if pending.outcome_window_complete:
                    completed_ids.append(setup_id)
                continue

            pending.bars_observed += 1
            trigger, _, _ = strategy._entry_trigger_diagnostic(
                pending.setup,
                context,
            )
            if trigger is None:
                if pending.bars_observed >= self.maximum_bars:
                    pending.window_complete = True
                    pending.outcome_window_complete = True
                    completed_ids.append(setup_id)
                continue

            pending.trigger_found = True
            pending.first_trigger_at = context.current_bar.timestamp
            pending.bars_after_expiry = pending.bars_observed
            pending.trigger_type = trigger.trigger_type.value
            pending.window_complete = True

            candidate = strategy._candidate_trade(
                setup=pending.setup,
                trigger=trigger,
            )
            pending.geometry_valid = candidate is not None
            pending.candidate = candidate
            pending.outcome_bars = []

            if candidate is None:
                pending.outcome_window_complete = True
                completed_ids.append(setup_id)

        for setup_id in completed_ids:
            self._completed.append(self._pending.pop(setup_id))

    def _observe_outcome_bar(
        self,
        pending: _PendingExpiredSetup,
        bar: MarketBar,
    ) -> None:
        candidate = pending.candidate
        if candidate is None:
            return

        assert pending.outcome_bars is not None
        pending.outcome_bars.append(bar)
        evaluation = self._outcome_evaluator.evaluate(
            candidate,
            tuple(pending.outcome_bars),
            maximum_bars=self.outcome_maximum_bars,
        )
        pending.outcome = evaluation.outcome.value
        pending.outcome_timestamp = evaluation.outcome_timestamp
        pending.outcome_bars_evaluated = evaluation.bars_evaluated
        pending.maximum_favorable_r_multiple = (
            evaluation.maximum_favorable_r_multiple
        )
        pending.maximum_adverse_r_multiple = (
            evaluation.maximum_adverse_r_multiple
        )

        terminal = evaluation.outcome is not CandidateOutcome.UNRESOLVED
        horizon_complete = (
            evaluation.bars_evaluated >= self.outcome_maximum_bars
        )
        pending.outcome_window_complete = terminal or horizon_complete

    @property
    def records(self) -> tuple[PostExpiryTriggerRecord, ...]:
        values = [*self._completed, *self._pending.values()]
        values.sort(key=lambda item: (item.expired_at, str(item.setup.setup_id)))

        records: list[PostExpiryTriggerRecord] = []
        for item in values:
            candidate = item.candidate
            reward_risk = None
            if candidate is not None:
                nearest_reward = min(
                    abs(target - candidate.entry_price)
                    for target in candidate.take_profit_prices
                )
                reward_risk = nearest_reward / candidate.initial_risk_distance

            records.append(
                PostExpiryTriggerRecord(
                    setup_id=str(item.setup.setup_id),
                    strategy_id=item.setup.strategy_id,
                    direction=item.setup.direction.value,
                    expired_at=item.expired_at,
                    maximum_bars=self.maximum_bars,
                    bars_observed=item.bars_observed,
                    trigger_found=item.trigger_found,
                    first_trigger_at=item.first_trigger_at,
                    bars_after_expiry=item.bars_after_expiry,
                    trigger_type=item.trigger_type,
                    window_complete=item.window_complete,
                    geometry_valid=item.geometry_valid,
                    entry_price=(
                        candidate.entry_price if candidate is not None else None
                    ),
                    stop_loss_price=(
                        candidate.stop_loss_price
                        if candidate is not None
                        else None
                    ),
                    take_profit_prices=(
                        candidate.take_profit_prices
                        if candidate is not None
                        else ()
                    ),
                    reward_risk=reward_risk,
                    outcome=item.outcome,
                    outcome_timestamp=item.outcome_timestamp,
                    outcome_bars_evaluated=item.outcome_bars_evaluated,
                    maximum_favorable_r_multiple=(
                        item.maximum_favorable_r_multiple
                    ),
                    maximum_adverse_r_multiple=(
                        item.maximum_adverse_r_multiple
                    ),
                    outcome_window_complete=item.outcome_window_complete,
                )
            )
        return tuple(records)
