from __future__ import annotations

import csv
from datetime import UTC, datetime

from core.backtesting.exporter import BacktestExporter
from core.backtesting.models import BacktestResult, BacktestTrade


def test_exporter_writes_structure_atr_and_freshness_columns(tmp_path) -> None:
    timestamp = datetime(2025, 1, 1, tzinfo=UTC)
    trade = BacktestTrade(
        entry_time=timestamp,
        exit_time=timestamp,
        direction="BUY",
        entry_price=100.0,
        exit_price=101.0,
        position_size=0.01,
        metadata={
            "structure_confidence": 0.3,
            "bos_break_atr_multiple": 0.5,
            "bos_freshness": 0.75,
            "choch_break_atr_multiple": None,
            "choch_freshness": None,
            "liquidity_freshness": 0.4,
        },
    )
    result = BacktestResult(
        total_trades=1,
        winning_trades=0,
        losing_trades=0,
        breakeven_trades=1,
        net_profit=0.0,
        win_rate=0.0,
        max_drawdown=0.0,
        trades=[trade],
    )

    path = BacktestExporter(tmp_path).export_trade_log(result)
    with path.open(newline="", encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))

    assert row["Structure Confidence"] == "0.3"
    assert row["BOS Break ATR Multiple"] == "0.5"
    assert row["BOS Freshness"] == "0.75"
    assert row["CHOCH Freshness"] == ""
    assert row["Liquidity Freshness"] == "0.4"
