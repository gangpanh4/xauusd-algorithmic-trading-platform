"""Research-only tracking for M5 triggers observed after setup expiry."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.strategies.context import StrategyContext
from core.strategies.models import TradingSetup
from core.strategies.xauusd_bos_choch import XAUUSDBOSCHOCHStrategy


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


class PostExpiryTriggerTracker:
    def __init__(self, maximum_bars: int = 8) -> None:
        if isinstance(maximum_bars, bool) or not isinstance(maximum_bars, int):
            raise TypeError("maximum_bars must be an integer")
        if maximum_bars <= 0:
            raise ValueError("maximum_bars must be positive")
        self.maximum_bars = maximum_bars
        self._pending: dict[str, _PendingExpiredSetup] = {}
        self._completed: list[_PendingExpiredSetup] = []

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
            pending.bars_observed += 1
            trigger, _, _ = strategy._entry_trigger_diagnostic(
                pending.setup,
                context,
            )
            if trigger is not None:
                pending.trigger_found = True
                pending.first_trigger_at = context.current_bar.timestamp
                pending.bars_after_expiry = pending.bars_observed
                pending.trigger_type = trigger.trigger_type.value
                pending.window_complete = True
                completed_ids.append(setup_id)
            elif pending.bars_observed >= self.maximum_bars:
                pending.window_complete = True
                completed_ids.append(setup_id)

        for setup_id in completed_ids:
            self._completed.append(self._pending.pop(setup_id))

    @property
    def records(self) -> tuple[PostExpiryTriggerRecord, ...]:
        values = [*self._completed, *self._pending.values()]
        values.sort(key=lambda item: (item.expired_at, str(item.setup.setup_id)))
        return tuple(
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
            )
            for item in values
        )
