from __future__ import annotations

from datetime import UTC, datetime

import pytest

from core.backtesting.engine import BacktestingEngine
from core.backtesting.models import BacktestTrade, TradeOutcome


def _trade(profit: float, outcome: TradeOutcome) -> BacktestTrade:
    timestamp = datetime(2025, 1, 1, tzinfo=UTC)
    return BacktestTrade(
        entry_time=timestamp,
        exit_time=timestamp,
        direction="BUY",
        entry_price=100.0,
        exit_price=100.0,
        position_size=0.01,
        net_profit=profit,
        outcome=outcome,
    )


def test_result_statistics_populate_summary_fields() -> None:
    trades = [
        _trade(5.0, TradeOutcome.WIN),
        _trade(5.0, TradeOutcome.WIN),
        _trade(-2.0, TradeOutcome.LOSS),
        _trade(0.0, TradeOutcome.BREAKEVEN),
        _trade(-4.0, TradeOutcome.LOSS),
        _trade(-2.0, TradeOutcome.LOSS),
    ]

    values = BacktestingEngine._calculate_result_statistics(trades)

    assert values["expectancy"] == pytest.approx(2.0 / 6.0)
    assert values["average_win"] == 5.0
    assert values["average_loss"] == pytest.approx(8.0 / 3.0)
    assert values["largest_win"] == 5.0
    assert values["largest_loss"] == 4.0
    assert values["consecutive_wins"] == 2
    assert values["consecutive_losses"] == 2


def test_result_statistics_are_zero_for_empty_trade_set() -> None:
    values = BacktestingEngine._calculate_result_statistics([])

    assert all(value == 0 for value in values.values())
