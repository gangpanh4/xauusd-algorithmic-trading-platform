from __future__ import annotations

import csv
import json
from datetime import UTC, datetime

import pytest

from core.backtesting.methodology_diagnostics_exporter import (
    MethodologyDiagnosticsExporter,
)
from core.backtesting.methodology_observer import BacktestMethodologyObserver
from core.data.models import MarketBar
from core.market_structure.enums import MarketTrend
from core.market_structure.measurements import MarketStructureMeasurements
from core.market_structure.models import MarketStructureResult, StructureState
from core.multi_timeframe.enums import MarketBias, Timeframe
from core.multi_timeframe.models import MultiTimeframeResult, TimeframeState
from core.strategies.context import StrategyContext


def _state(timeframe: Timeframe, timestamp: datetime) -> TimeframeState:
    structure = StructureState(
        timestamp=timestamp,
        current_bar_index=10,
        trend=MarketTrend.UNKNOWN,
    )
    result = MarketStructureResult(
        timestamp=timestamp,
        last_swing=None,
        last_bos=None,
        last_choch=None,
        last_liquidity=None,
        current_trend=MarketTrend.UNKNOWN,
        structure_confidence=0.0,
        measurements=MarketStructureMeasurements(),
        structure_state=structure,
    )
    return TimeframeState(
        timeframe=timeframe,
        timestamp=timestamp,
        bias=MarketBias.NEUTRAL,
        market_structure=result,
    )


def _observation(timestamp: datetime):
    mtf = MultiTimeframeResult(
        weekly=_state(Timeframe.WEEKLY, timestamp),
        daily=_state(Timeframe.DAILY, timestamp),
        h4=_state(Timeframe.H4, timestamp),
        h1=_state(Timeframe.H1, timestamp),
        m15=_state(Timeframe.M15, timestamp),
        m5=_state(Timeframe.M5, timestamp),
        timestamp=timestamp,
    )
    context = StrategyContext(
        multi_timeframe=mtf,
        current_bar=MarketBar(
            timestamp=timestamp,
            open=3300.0,
            high=3301.0,
            low=3299.0,
            close=3300.0,
            tick_volume=100,
        ),
        current_bar_index=10,
    )
    return BacktestMethodologyObserver().observe(context)


def test_exports_deterministic_observation_csv(tmp_path) -> None:
    timestamp = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    observation = _observation(timestamp)
    exporter = MethodologyDiagnosticsExporter(tmp_path)

    path = exporter.export_observations((observation,))

    assert path == tmp_path / "methodology_observations.csv"
    with path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 1
    row = rows[0]
    assert row["Observation Number"] == "1"
    assert row["Timestamp"] == timestamp.isoformat()
    assert row["SMC Status"] == "NOT_CONFIRMED"
    assert row["ICT Status"] == "NOT_CONFIRMED"
    assert row["Price Location"] == "UNKNOWN"
    assert "market_regime" in row["Missing Capabilities"]


def test_exports_empty_csv_with_header(tmp_path) -> None:
    exporter = MethodologyDiagnosticsExporter(tmp_path)

    path = exporter.export_observations(())

    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        assert reader.fieldnames is not None
        assert list(reader) == []


def test_exports_summary_json(tmp_path) -> None:
    exporter = MethodologyDiagnosticsExporter(tmp_path)

    path = exporter.export_summary(
        {
            "ICT:NOT_CONFIRMED": 2,
            "SMC:NOT_CONFIRMED": 2,
        },
        total_observations=2,
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload == {
        "methodologies": {
            "ICT": {
                "CONFIRMED": 0,
                "INCOMPLETE": 0,
                "NOT_CONFIRMED": 2,
            },
            "SMC": {
                "CONFIRMED": 0,
                "INCOMPLETE": 0,
                "NOT_CONFIRMED": 2,
            },
        },
        "observational_only": True,
        "status_counts": {
            "ICT:NOT_CONFIRMED": 2,
            "SMC:NOT_CONFIRMED": 2,
        },
        "total_observations": 2,
        "trade_authority": False,
    }


def test_summary_requires_each_methodology_count_to_match_total(tmp_path) -> None:
    exporter = MethodologyDiagnosticsExporter(tmp_path)

    with pytest.raises(ValueError, match="SMC summary count"):
        exporter.export_summary(
            {"SMC:NOT_CONFIRMED": 1},
            total_observations=2,
        )


def test_rejects_invalid_observation_sequence(tmp_path) -> None:
    exporter = MethodologyDiagnosticsExporter(tmp_path)

    with pytest.raises(TypeError, match="MethodologyObservation"):
        exporter.export_observations((object(),))


def test_rejects_unknown_summary_key(tmp_path) -> None:
    exporter = MethodologyDiagnosticsExporter(tmp_path)

    with pytest.raises(ValueError, match="unsupported"):
        exporter.export_summary(
            {"SMC:APPROVED": 0},
            total_observations=0,
        )
