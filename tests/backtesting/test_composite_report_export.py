from __future__ import annotations

import csv
import json
from datetime import UTC, datetime

import pytest

from core.backtesting.exporter import BacktestExporter
from core.backtesting.models import BacktestResult
from core.backtesting.run_output import BacktestRunOutput
from core.backtesting.runner import BacktestRunner
from core.backtesting.strategy_comparison import (
    BacktestStrategyComparison,
    StrategyComparisonEvent,
)


def _result() -> BacktestResult:
    return BacktestResult(
        total_trades=1,
        winning_trades=1,
        losing_trades=0,
        breakeven_trades=0,
        net_profit=10.0,
        win_rate=100.0,
        max_drawdown=0.0,
    )


def _comparison() -> BacktestStrategyComparison:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    return BacktestStrategyComparison(
        pipeline_observation_count=4,
        pipeline_approval_count=1,
        executed_trade_count=1,
        strategy_observation_count=4,
        strategy_setup_count=1,
        strategy_candidate_count=1,
        pipeline_reason_counts=(
            ("APPROVED", 1),
            ("PROBABILITY_REJECTED", 3),
        ),
        strategy_reason_counts=(
            ("CANDIDATE_CREATED", 1),
            ("NO_SETUP", 2),
            ("SETUP_DETECTED", 1),
        ),
        events=(
            StrategyComparisonEvent(
                timestamp=timestamp,
                source="STRATEGY",
                event_type="SETUP_DETECTED",
                direction="BUY",
                identifier="setup-1",
            ),
            StrategyComparisonEvent(
                timestamp=timestamp,
                source="PIPELINE",
                event_type="APPROVED",
            ),
        ),
    )


def test_export_strategy_comparison_summary(tmp_path) -> None:
    exporter = BacktestExporter(tmp_path)

    path = exporter.export_strategy_comparison_summary(
        _comparison()
    )

    assert path.name == "strategy_comparison_summary.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["pipeline_observation_count"] == 4
    assert payload["pipeline_approval_count"] == 1
    assert payload["executed_trade_count"] == 1
    assert payload["strategy_setup_count"] == 1
    assert payload["strategy_candidate_count"] == 1
    assert payload["pipeline_reason_counts"] == {
        "APPROVED": 1,
        "PROBABILITY_REJECTED": 3,
    }


def test_export_strategy_comparison_events(tmp_path) -> None:
    exporter = BacktestExporter(tmp_path)

    path = exporter.export_strategy_comparison_events(
        _comparison()
    )

    assert path.name == "strategy_comparison_events.csv"
    with path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    assert rows == [
        {
            "Event Number": "1",
            "Timestamp": "2026-01-01T00:00:00+00:00",
            "Source": "STRATEGY",
            "Event Type": "SETUP_DETECTED",
            "Direction": "BUY",
            "Identifier": "setup-1",
        },
        {
            "Event Number": "2",
            "Timestamp": "2026-01-01T00:00:00+00:00",
            "Source": "PIPELINE",
            "Event Type": "APPROVED",
            "Direction": "",
            "Identifier": "",
        },
    ]


def test_generate_composite_reports_preserves_existing_reports() -> None:
    runner = object.__new__(BacktestRunner)
    result = _result()
    comparison = _comparison()
    output = BacktestRunOutput(
        result=result,
        strategy_comparison=comparison,
    )
    calls: list[tuple[str, object]] = []

    runner.generate_reports = lambda received: calls.append(
        ("existing", received)
    )
    runner.exporter = type(
        "ExporterSpy",
        (),
        {
            "export_strategy_comparison_summary": lambda self, value: (
                calls.append(("summary", value))
            ),
            "export_strategy_comparison_events": lambda self, value: (
                calls.append(("events", value))
            ),
        },
    )()

    runner.generate_composite_reports(output)

    assert calls == [
        ("existing", result),
        ("summary", comparison),
        ("events", comparison),
    ]


def test_comparison_export_rejects_wrong_type(tmp_path) -> None:
    exporter = BacktestExporter(tmp_path)

    with pytest.raises(TypeError, match="BacktestStrategyComparison"):
        exporter.export_strategy_comparison_summary(object())

    with pytest.raises(TypeError, match="BacktestStrategyComparison"):
        exporter.export_strategy_comparison_events(object())
