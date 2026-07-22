from __future__ import annotations

import csv
import json
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path

import pytest

from core.backtesting.exporter import BacktestExporter
from core.backtesting.models import (
    BacktestResult,
    BacktestTrade,
    ExitReason,
    TradeOutcome,
)


class ExampleEvidence(Enum):
    CONFIRMED = "CONFIRMED"


def _trade(*, metadata: dict | None = None) -> BacktestTrade:
    return BacktestTrade(
        entry_time=datetime(2025, 1, 2, 10, 15, tzinfo=UTC),
        exit_time=datetime(2025, 1, 2, 11, 0, tzinfo=UTC),
        direction="BUY",
        entry_price=2650.25,
        exit_price=2655.25,
        position_size=0.10,
        spread_cost=0.15,
        commission=0.05,
        gross_profit=50.0,
        net_profit=49.80,
        outcome=TradeOutcome.WIN,
        exit_reason=ExitReason.TAKE_PROFIT,
        holding_bars=3,
        holding_time=timedelta(minutes=45),
        risk_reward=2.0,
        max_favorable_excursion=5.5,
        max_adverse_excursion=0.8,
        highest_price=2655.75,
        lowest_price=2649.45,
        breakeven_triggered=True,
        lifecycle_events=("ENTRY", "BREAKEVEN", "TAKE_PROFIT"),
        metadata=metadata or {},
    )


def _result(trades: list[BacktestTrade]) -> BacktestResult:
    return BacktestResult(
        total_trades=len(trades),
        winning_trades=len(trades),
        losing_trades=0,
        breakeven_trades=0,
        net_profit=sum(trade.net_profit for trade in trades),
        win_rate=100.0 if trades else 0.0,
        max_drawdown=0.0,
        gross_profit=sum(trade.gross_profit for trade in trades),
        gross_loss=0.0,
        profit_factor=float("inf") if False else 0.0,
        expectancy=49.8 if trades else 0.0,
        average_win=49.8 if trades else 0.0,
        average_probability=0.67,
        average_confidence=0.68,
        average_feature_count=25.0,
        average_trade_quality=76.0,
        average_trade_quality_confidence=0.95,
        high_quality_trades=len(trades),
        trades=trades,
    )


def test_trade_log_exports_research_evidence_and_dynamic_metadata(
    tmp_path: Path,
) -> None:
    metadata = {
        "probability": 0.71,
        "confidence": 0.66,
        "trade_quality_score": 78.5,
        "trade_quality_confidence": 0.93,
        "trade_quality_level": "HIGH",
        "bos_present": True,
        "bos_direction": "BULLISH",
        "bos_break_distance": 1.25,
        "tick_size": 0.01,
        "tick_value_per_lot": 1.0,
        "spread_points": 1.5,
        "slippage_points": 0.5,
        "gross_r_multiple": 2.0,
        "net_r_multiple": 1.992,
        "custom": {
            "evidence": ExampleEvidence.CONFIRMED,
            "values": [1, 2, 3],
        },
    }
    exporter = BacktestExporter(tmp_path)

    path = exporter.export_trade_log(_result([_trade(metadata=metadata)]))

    with path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 1
    row = rows[0]
    assert row["Trade Number"] == "1"
    assert row["Outcome"] == "WIN"
    assert row["Exit Reason"] == "TAKE_PROFIT"
    assert row["Maximum Favorable Excursion"] == "5.5"
    assert row["Maximum Adverse Excursion"] == "0.8"
    assert row["Probability"] == "0.71"
    assert row["Trade Quality Level"] == "HIGH"
    assert row["BOS Present"] == "True"
    assert row["Gross R Multiple"] == "2.0"
    assert row["Metadata:custom.evidence"] == "CONFIRMED"
    assert row["Metadata:custom.values"] == "[1,2,3]"

    metadata_json = json.loads(row["Metadata JSON"])
    assert metadata_json["custom"]["evidence"] == "CONFIRMED"
    assert metadata_json["custom"]["values"] == [1, 2, 3]


def test_missing_evidence_is_blank_not_fabricated_zero(tmp_path: Path) -> None:
    exporter = BacktestExporter(tmp_path)

    path = exporter.export_trade_log(_result([_trade()]))

    with path.open(newline="", encoding="utf-8") as file:
        row = next(csv.DictReader(file))

    assert row["Probability"] == ""
    assert row["Probability Accepted"] == ""
    assert row["BOS Present"] == ""
    assert row["CHOCH Present"] == ""
    assert row["Liquidity Present"] == ""
    assert row["Confluence Score"] == ""


def test_summary_exports_complete_observability_metrics(tmp_path: Path) -> None:
    exporter = BacktestExporter(tmp_path)

    path = exporter.export_summary(_result([_trade()]))
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["expectancy"] == 49.8
    assert payload["average_probability"] == 0.67
    assert payload["average_confidence"] == 0.68
    assert payload["average_trade_quality"] == 76.0
    assert payload["average_trade_quality_confidence"] == 0.95
    assert payload["high_quality_trades"] == 1
    assert "rejected_quality_trades" in payload


def test_equity_curve_preserves_existing_two_column_schema(tmp_path: Path) -> None:
    exporter = BacktestExporter(tmp_path)

    path = exporter.export_equity_curve(
        _result([_trade()]),
        initial_balance=10_000.0,
    )

    with path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.reader(file))

    assert rows[0] == ["Trade", "Balance"]
    assert rows[1] == ["0", "10000.0"]
    assert rows[2] == ["1", "10049.8"]


def test_statistics_serializes_datetime_enum_and_timedelta(tmp_path: Path) -> None:
    exporter = BacktestExporter(tmp_path)

    path = exporter.export_statistics(
        {
            "timestamp": datetime(2025, 1, 2, tzinfo=UTC),
            "state": ExampleEvidence.CONFIRMED,
            "duration": timedelta(minutes=15),
        }
    )
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload == {
        "duration": 900.0,
        "state": "CONFIRMED",
        "timestamp": "2025-01-02T00:00:00+00:00",
    }


def test_non_finite_metadata_fails_closed(tmp_path: Path) -> None:
    exporter = BacktestExporter(tmp_path)

    with pytest.raises(ValueError, match="NaN"):
        exporter.export_trade_log(
            _result([_trade(metadata={"probability": float("nan")})])
        )
