from __future__ import annotations

import csv
import json
from datetime import UTC, datetime, timedelta

import pytest

from core.backtesting.methodology_condition_analytics import (
    MethodologyConditionAnalytics,
)
from core.backtesting.methodology_observer import BacktestMethodologyObserver
from core.data.models import MarketBar
from core.market_structure.enums import MarketTrend
from core.market_structure.measurements import MarketStructureMeasurements
from core.market_structure.models import MarketStructureResult, StructureState
from core.multi_timeframe.enums import MarketBias, Timeframe
from core.multi_timeframe.models import MultiTimeframeResult, TimeframeState
from core.regime_detector.models import MarketRegime, RegimeLabel
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


def _observation(
    timestamp: datetime,
    *,
    regime: RegimeLabel | None = None,
):
    mtf = MultiTimeframeResult(
        weekly=_state(Timeframe.WEEKLY, timestamp),
        daily=_state(Timeframe.DAILY, timestamp),
        h4=_state(Timeframe.H4, timestamp),
        h1=_state(Timeframe.H1, timestamp),
        m15=_state(Timeframe.M15, timestamp),
        m5=_state(Timeframe.M5, timestamp),
        timestamp=timestamp,
    )
    market_regime = (
        MarketRegime(
            primary_regime=regime,
            confidence=0.80,
            observation_timestamp=timestamp,
            computation_timestamp=timestamp,
        )
        if regime is not None
        else None
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
        market_regime=market_regime,
    )
    return BacktestMethodologyObserver().observe(context)


def test_exports_condition_csv_and_json(tmp_path) -> None:
    first = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    observations = (
        _observation(first, regime=RegimeLabel.TRENDING_BULL),
        _observation(first + timedelta(hours=10)),
    )
    analytics = MethodologyConditionAnalytics(tmp_path)

    csv_path, json_path = analytics.export(observations)

    assert csv_path == tmp_path / "methodology_condition_summary.csv"
    assert json_path == tmp_path / "methodology_condition_summary.json"

    with csv_path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert rows
    assert {row["Methodology"] for row in rows} == {"SMC", "ICT"}
    htf_rows = [
        row for row in rows if row["Condition Code"] == "HTF_BIAS_ALIGNED"
    ]
    assert len(htf_rows) == 2
    assert all(row["Total Evaluations"] == "2" for row in htf_rows)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["total_observations"] == 2
    assert payload["observational_only"] is True
    assert payload["trade_authority"] is False
    assert sum(payload["status_overlap"].values()) == 2
    assert payload["confirmation_by_session"]["London"]["total_observations"] == 1
    assert payload["confirmation_by_session"]["OFF_SESSION"]["total_observations"] == 1
    assert payload["confirmation_by_regime"]["TRENDING_BULL"]["total_observations"] == 1
    assert payload["confirmation_by_regime"]["MISSING"]["total_observations"] == 1


def test_condition_state_counts_are_complete() -> None:
    timestamp = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    payload, rows = MethodologyConditionAnalytics.calculate(
        (_observation(timestamp),)
    )

    assert payload["total_observations"] == 1
    assert rows
    for row in rows:
        assert (
            row["Satisfied Count"]
            + row["Failed Count"]
            + row["Unavailable Count"]
            == row["Total Evaluations"]
        )
        assert row["Total Evaluations"] == 1


def test_direction_and_overlap_counts_are_deterministic() -> None:
    first = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    payload, _ = MethodologyConditionAnalytics.calculate(
        (
            _observation(first),
            _observation(first + timedelta(minutes=5)),
        )
    )

    assert sum(payload["direction_counts"]["SMC"].values()) == 2
    assert sum(payload["direction_counts"]["ICT"].values()) == 2
    assert sum(payload["status_overlap"].values()) == 2


def test_empty_observations_export_valid_empty_artifacts(tmp_path) -> None:
    analytics = MethodologyConditionAnalytics(tmp_path)

    csv_path, json_path = analytics.export(())

    with csv_path.open(newline="", encoding="utf-8") as file:
        assert list(csv.DictReader(file)) == []
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["total_observations"] == 0
    assert payload["condition_counts"] == {"ICT": {}, "SMC": {}}
    assert payload["confirmation_by_session"] == {}
    assert payload["confirmation_by_regime"] == {}


def test_rejects_duplicate_timestamps() -> None:
    timestamp = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    observation = _observation(timestamp)

    with pytest.raises(ValueError, match="timestamps must be unique"):
        MethodologyConditionAnalytics.calculate((observation, observation))


def test_rejects_invalid_observation_type() -> None:
    with pytest.raises(TypeError, match="MethodologyObservation"):
        MethodologyConditionAnalytics.calculate((object(),))
