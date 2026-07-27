from __future__ import annotations

import csv
import json
from datetime import UTC, datetime, timedelta

import pytest

from core.backtesting.methodology_observer import BacktestMethodologyObserver
from core.backtesting.methodology_outcome_integrity import (
    MethodologyOutcomeIntegrityAnalytics,
)
from core.backtesting.methodology_outcome_research import (
    MethodologyOutcomeEvaluation,
)
from core.data.models import MarketBar as ContextMarketBar
from core.market_structure.enums import MarketTrend
from core.market_structure.measurements import MarketStructureMeasurements
from core.market_structure.models import MarketStructureResult, StructureState
from core.multi_timeframe.enums import MarketBias, Timeframe
from core.multi_timeframe.models import MultiTimeframeResult, TimeframeState
from core.regime_detector.models import MarketBar
from core.strategies.context import StrategyContext
from core.strategies.methodology_models import (
    MethodologyDirection,
    MethodologyEvaluationStatus,
    MethodologyIdentifier,
)


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
        current_bar=ContextMarketBar(
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


def _bar(timestamp: datetime, close: float = 3300.0) -> MarketBar:
    return MarketBar(
        timestamp=timestamp,
        open=close,
        high=close + 1.0,
        low=close - 1.0,
        close=close,
        volume=100,
        tick_volume=100,
    )


def _evaluation(
    *,
    timestamp: datetime,
    methodology: MethodologyIdentifier,
    status: MethodologyEvaluationStatus,
    direction: MethodologyDirection,
    horizon: int,
    move: float,
    favorable: bool,
    mfe: float,
    mae: float,
) -> MethodologyOutcomeEvaluation:
    source_price = 3300.0
    terminal_price = (
        source_price + move
        if direction is MethodologyDirection.BULLISH
        else source_price - move
    )
    return MethodologyOutcomeEvaluation(
        observation_timestamp=timestamp,
        methodology=methodology,
        evaluation_status=status,
        direction=direction,
        horizon_bars=horizon,
        horizon_complete=True,
        source_price=source_price,
        terminal_timestamp=timestamp + timedelta(minutes=5 * horizon),
        terminal_price=terminal_price,
        directional_move=move,
        directional_return_pct=(move / source_price) * 100.0,
        maximum_favorable_excursion=mfe,
        maximum_adverse_excursion=mae,
        favorable_terminal_outcome=favorable,
        session_name="London",
        regime_name=None,
    )


def test_integrity_reports_exact_matches_and_unmatched_timestamps() -> None:
    first = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    observations = (
        _observation(first),
        _observation(first + timedelta(minutes=5)),
    )
    bars = (
        _bar(first),
        _bar(first + timedelta(minutes=10)),
    )
    evaluations = (
        _evaluation(
            timestamp=first,
            methodology=MethodologyIdentifier.SMC,
            status=MethodologyEvaluationStatus.CONFIRMED,
            direction=MethodologyDirection.BULLISH,
            horizon=1,
            move=1.0,
            favorable=True,
            mfe=2.0,
            mae=1.0,
        ),
        _evaluation(
            timestamp=first,
            methodology=MethodologyIdentifier.ICT,
            status=MethodologyEvaluationStatus.NOT_CONFIRMED,
            direction=MethodologyDirection.BEARISH,
            horizon=1,
            move=-1.0,
            favorable=False,
            mfe=1.0,
            mae=2.0,
        ),
        _evaluation(
            timestamp=first + timedelta(minutes=5),
            methodology=MethodologyIdentifier.SMC,
            status=MethodologyEvaluationStatus.NOT_CONFIRMED,
            direction=MethodologyDirection.BULLISH,
            horizon=1,
            move=0.5,
            favorable=True,
            mfe=1.0,
            mae=1.0,
        ),
        _evaluation(
            timestamp=first + timedelta(minutes=5),
            methodology=MethodologyIdentifier.ICT,
            status=MethodologyEvaluationStatus.NOT_CONFIRMED,
            direction=MethodologyDirection.BEARISH,
            horizon=1,
            move=0.5,
            favorable=True,
            mfe=1.0,
            mae=1.0,
        ),
    )

    payload = MethodologyOutcomeIntegrityAnalytics.calculate_integrity(
        observations,
        bars,
        evaluations,
        horizons=(1,),
    )

    assert payload["methodology_observation_count"] == 2
    assert payload["m5_bar_count"] == 2
    assert payload["exact_timestamp_match_count"] == 1
    assert payload["unmatched_observation_count"] == 1
    assert payload["actual_evaluation_count"] == 4
    assert payload["expected_evaluation_count"] == 4
    assert payload["evaluation_count_matches"] is True
    assert "UNMATCHED_OBSERVATION_TIMESTAMPS" in payload["warnings"]


def test_integrity_detects_evaluation_count_mismatch() -> None:
    timestamp = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    payload = MethodologyOutcomeIntegrityAnalytics.calculate_integrity(
        (_observation(timestamp),),
        (_bar(timestamp),),
        (),
        horizons=(1, 3),
    )

    assert payload["expected_evaluation_count"] == 4
    assert payload["actual_evaluation_count"] == 0
    assert payload["evaluation_count_matches"] is False
    assert "EVALUATION_COUNT_MISMATCH" in payload["warnings"]


def test_comparison_calculates_confirmed_minus_baseline_deltas() -> None:
    timestamp = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    analytics = MethodologyOutcomeIntegrityAnalytics(
        minimum_sample_size=1,
    )
    evaluations = (
        _evaluation(
            timestamp=timestamp,
            methodology=MethodologyIdentifier.SMC,
            status=MethodologyEvaluationStatus.CONFIRMED,
            direction=MethodologyDirection.BULLISH,
            horizon=3,
            move=3.3,
            favorable=True,
            mfe=4.0,
            mae=2.0,
        ),
        _evaluation(
            timestamp=timestamp + timedelta(minutes=5),
            methodology=MethodologyIdentifier.SMC,
            status=MethodologyEvaluationStatus.NOT_CONFIRMED,
            direction=MethodologyDirection.BULLISH,
            horizon=3,
            move=-1.65,
            favorable=False,
            mfe=1.0,
            mae=2.0,
        ),
    )

    rows = analytics.calculate_comparisons(evaluations)

    assert len(rows) == 1
    row = rows[0]
    assert row["Confirmed Sample Count"] == 1
    assert row["Baseline Sample Count"] == 1
    assert row["Confirmed Favorable Rate"] == 1.0
    assert row["Baseline Favorable Rate"] == 0.0
    assert row["Favorable Rate Delta"] == 1.0
    assert row["Confirmed Average Return Percent"] == pytest.approx(0.1)
    assert row["Baseline Average Return Percent"] == pytest.approx(-0.05)
    assert row["Average Return Delta Percent"] == pytest.approx(0.15)
    assert row["Confirmed MFE MAE Ratio"] == 2.0
    assert row["Baseline MFE MAE Ratio"] == 0.5
    assert row["Sample Warning"] == ""


def test_comparison_warns_when_confirmed_sample_is_too_small() -> None:
    timestamp = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    analytics = MethodologyOutcomeIntegrityAnalytics(
        minimum_sample_size=2,
    )

    rows = analytics.calculate_comparisons(
        (
            _evaluation(
                timestamp=timestamp,
                methodology=MethodologyIdentifier.ICT,
                status=MethodologyEvaluationStatus.CONFIRMED,
                direction=MethodologyDirection.BEARISH,
                horizon=1,
                move=1.0,
                favorable=True,
                mfe=2.0,
                mae=1.0,
            ),
            _evaluation(
                timestamp=timestamp + timedelta(minutes=5),
                methodology=MethodologyIdentifier.ICT,
                status=MethodologyEvaluationStatus.NOT_CONFIRMED,
                direction=MethodologyDirection.BEARISH,
                horizon=1,
                move=1.0,
                favorable=True,
                mfe=2.0,
                mae=1.0,
            ),
            _evaluation(
                timestamp=timestamp + timedelta(minutes=10),
                methodology=MethodologyIdentifier.ICT,
                status=MethodologyEvaluationStatus.NOT_CONFIRMED,
                direction=MethodologyDirection.BEARISH,
                horizon=1,
                move=1.0,
                favorable=True,
                mfe=2.0,
                mae=1.0,
            ),
        )
    )

    assert rows[0]["Sample Warning"] == (
        "INSUFFICIENT_CONFIRMED_SAMPLE"
    )


def test_export_writes_integrity_and_comparison_artifacts(tmp_path) -> None:
    timestamp = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    observation = _observation(timestamp)
    evaluations = (
        _evaluation(
            timestamp=timestamp,
            methodology=MethodologyIdentifier.SMC,
            status=MethodologyEvaluationStatus.CONFIRMED,
            direction=MethodologyDirection.BULLISH,
            horizon=1,
            move=1.0,
            favorable=True,
            mfe=2.0,
            mae=1.0,
        ),
        _evaluation(
            timestamp=timestamp,
            methodology=MethodologyIdentifier.ICT,
            status=MethodologyEvaluationStatus.NOT_CONFIRMED,
            direction=MethodologyDirection.BEARISH,
            horizon=1,
            move=-1.0,
            favorable=False,
            mfe=1.0,
            mae=2.0,
        ),
    )
    analytics = MethodologyOutcomeIntegrityAnalytics(
        tmp_path,
        minimum_sample_size=1,
    )

    integrity_path, csv_path, json_path = analytics.export(
        (observation,),
        (_bar(timestamp),),
        evaluations,
        horizons=(1,),
    )

    assert integrity_path.name == "methodology_outcome_integrity.json"
    assert csv_path.name == "methodology_outcome_comparison.csv"
    assert json_path.name == "methodology_outcome_comparison.json"

    integrity = json.loads(integrity_path.read_text(encoding="utf-8"))
    assert integrity["observational_only"] is True
    assert integrity["trade_authority"] is False
    assert integrity["future_information_used_for_research_only"] is True

    with csv_path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert rows

    comparison = json.loads(json_path.read_text(encoding="utf-8"))
    assert comparison["observational_only"] is True
    assert comparison["trade_authority"] is False


def test_empty_inputs_export_valid_artifacts(tmp_path) -> None:
    analytics = MethodologyOutcomeIntegrityAnalytics(tmp_path)

    integrity_path, csv_path, json_path = analytics.export(
        (),
        (),
        (),
        horizons=(1, 3),
    )

    integrity = json.loads(integrity_path.read_text(encoding="utf-8"))
    assert integrity["methodology_observation_count"] == 0
    assert integrity["expected_evaluation_count"] == 0
    assert integrity["evaluation_count_matches"] is True
    with csv_path.open(newline="", encoding="utf-8") as file:
        assert list(csv.DictReader(file)) == []
    comparison = json.loads(json_path.read_text(encoding="utf-8"))
    assert comparison["comparisons"] == []


def test_rejects_unknown_evaluation_horizon() -> None:
    timestamp = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    evaluation = _evaluation(
        timestamp=timestamp,
        methodology=MethodologyIdentifier.SMC,
        status=MethodologyEvaluationStatus.CONFIRMED,
        direction=MethodologyDirection.BULLISH,
        horizon=3,
        move=1.0,
        favorable=True,
        mfe=2.0,
        mae=1.0,
    )

    with pytest.raises(ValueError, match="configured horizons"):
        MethodologyOutcomeIntegrityAnalytics.calculate_integrity(
            (_observation(timestamp),),
            (_bar(timestamp),),
            (evaluation,),
            horizons=(1,),
        )
