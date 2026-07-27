from __future__ import annotations

import csv
import json
from datetime import UTC, datetime, timedelta

import pytest

from core.backtesting.methodology_outcome_research import (
    MethodologyOutcomeEvaluation,
)
from core.backtesting.methodology_outcome_stability import (
    MethodologyOutcomeStabilityAnalytics,
)
from core.strategies.methodology_models import (
    MethodologyDirection,
    MethodologyEvaluationStatus,
    MethodologyIdentifier,
)


def _evaluation(
    *,
    timestamp: datetime,
    status: MethodologyEvaluationStatus,
    move: float,
    favorable: bool,
    methodology: MethodologyIdentifier = MethodologyIdentifier.SMC,
    direction: MethodologyDirection = MethodologyDirection.BULLISH,
    horizon: int = 12,
    session: str | None = "London",
    regime: str | None = "TRENDING_BULL",
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
        maximum_favorable_excursion=max(move, 1.0),
        maximum_adverse_excursion=1.0,
        favorable_terminal_outcome=favorable,
        session_name=session,
        regime_name=regime,
    )


def _paired_fold(
    timestamp: datetime,
    *,
    confirmed_move: float,
    baseline_move: float,
) -> tuple[MethodologyOutcomeEvaluation, ...]:
    return (
        _evaluation(
            timestamp=timestamp,
            status=MethodologyEvaluationStatus.CONFIRMED,
            move=confirmed_move,
            favorable=confirmed_move > 0.0,
        ),
        _evaluation(
            timestamp=timestamp,
            status=MethodologyEvaluationStatus.NOT_CONFIRMED,
            move=baseline_move,
            favorable=baseline_move > 0.0,
        ),
    )


def test_partitions_unique_timestamps_into_contiguous_folds() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    evaluations = tuple(
        item
        for index in range(10)
        for item in _paired_fold(
            start + timedelta(minutes=5 * index),
            confirmed_move=1.0,
            baseline_move=-1.0,
        )
    )
    analytics = MethodologyOutcomeStabilityAnalytics(
        fold_count=5,
        minimum_sample_size=1,
    )

    payload, rows = analytics.calculate(evaluations)

    assert payload["total_unique_observations"] == 10
    assert [fold["observation_count"] for fold in payload["folds"]] == [
        2,
        2,
        2,
        2,
        2,
    ]
    assert len(rows) == 5
    assert rows[0]["Fold Start Timestamp"] == start.isoformat()
    assert rows[-1]["Fold End Timestamp"] == (
        start + timedelta(minutes=45)
    ).isoformat()


def test_stability_summary_reports_consistent_positive_edge() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    evaluations = tuple(
        item
        for index in range(5)
        for item in _paired_fold(
            start + timedelta(minutes=5 * index),
            confirmed_move=2.0,
            baseline_move=-1.0,
        )
    )
    analytics = MethodologyOutcomeStabilityAnalytics(
        fold_count=5,
        minimum_sample_size=1,
    )

    payload, _ = analytics.calculate(evaluations)

    summary = payload["stability_summary"][0]
    assert summary["valid_fold_count"] == 5
    assert summary["positive_favorable_delta_folds"] == 5
    assert summary["positive_return_delta_folds"] == 5
    assert summary["warnings"] == []


def test_stability_summary_warns_when_delta_sign_changes() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    evaluations = tuple(
        item
        for index in range(5)
        for item in _paired_fold(
            start + timedelta(minutes=5 * index),
            confirmed_move=2.0 if index < 3 else -2.0,
            baseline_move=-1.0 if index < 3 else 1.0,
        )
    )
    analytics = MethodologyOutcomeStabilityAnalytics(
        fold_count=5,
        minimum_sample_size=1,
    )

    payload, _ = analytics.calculate(evaluations)

    warnings = payload["stability_summary"][0]["warnings"]
    assert "FAVORABLE_RATE_SIGN_UNSTABLE" in warnings
    assert "RETURN_SIGN_UNSTABLE" in warnings


def test_insufficient_fold_samples_are_excluded_from_stability() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    evaluations = tuple(
        item
        for index in range(5)
        for item in _paired_fold(
            start + timedelta(minutes=5 * index),
            confirmed_move=1.0,
            baseline_move=-1.0,
        )
    )
    analytics = MethodologyOutcomeStabilityAnalytics(
        fold_count=5,
        minimum_sample_size=2,
    )

    payload, rows = analytics.calculate(evaluations)

    assert all(
        "INSUFFICIENT_CONFIRMED_SAMPLE" in row["Sample Warning"]
        for row in rows
    )
    summary = payload["stability_summary"][0]
    assert summary["valid_fold_count"] == 0
    assert "INSUFFICIENT_VALID_FOLDS" in summary["warnings"]
    assert "NO_VALID_FOLDS" in summary["warnings"]


def test_fold_payload_reports_session_and_regime_distribution() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    evaluations = (
        *_paired_fold(
            start,
            confirmed_move=1.0,
            baseline_move=-1.0,
        ),
        _evaluation(
            timestamp=start + timedelta(minutes=5),
            status=MethodologyEvaluationStatus.CONFIRMED,
            move=1.0,
            favorable=True,
            session=None,
            regime=None,
        ),
        _evaluation(
            timestamp=start + timedelta(minutes=5),
            status=MethodologyEvaluationStatus.NOT_CONFIRMED,
            move=-1.0,
            favorable=False,
            session=None,
            regime=None,
        ),
    )
    analytics = MethodologyOutcomeStabilityAnalytics(
        fold_count=2,
        minimum_sample_size=1,
    )

    payload, _ = analytics.calculate(evaluations)

    assert payload["folds"][0]["session_counts"] == {"London": 1}
    assert payload["folds"][0]["regime_counts"] == {"TRENDING_BULL": 1}
    assert payload["folds"][1]["session_counts"] == {"OFF_SESSION": 1}
    assert payload["folds"][1]["regime_counts"] == {"MISSING": 1}


def test_export_writes_csv_and_json(tmp_path) -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    analytics = MethodologyOutcomeStabilityAnalytics(
        tmp_path,
        fold_count=2,
        minimum_sample_size=1,
    )

    csv_path, json_path = analytics.export(
        (
            *_paired_fold(
                timestamp,
                confirmed_move=1.0,
                baseline_move=-1.0,
            ),
            *_paired_fold(
                timestamp + timedelta(minutes=5),
                confirmed_move=1.0,
                baseline_move=-1.0,
            ),
        )
    )

    assert csv_path.name == "methodology_outcome_stability.csv"
    assert json_path.name == "methodology_outcome_stability.json"
    with csv_path.open(newline="", encoding="utf-8") as file:
        assert len(list(csv.DictReader(file))) == 2
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["fold_count"] == 2
    assert payload["observational_only"] is True
    assert payload["trade_authority"] is False
    assert payload["future_information_used_for_research_only"] is True


def test_empty_input_produces_empty_folds_and_rows(tmp_path) -> None:
    analytics = MethodologyOutcomeStabilityAnalytics(
        tmp_path,
        fold_count=5,
    )

    csv_path, json_path = analytics.export(())

    with csv_path.open(newline="", encoding="utf-8") as file:
        assert list(csv.DictReader(file)) == []
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["total_unique_observations"] == 0
    assert len(payload["folds"]) == 5
    assert all(fold["observation_count"] == 0 for fold in payload["folds"])
    assert payload["stability_summary"] == []


def test_rejects_invalid_evaluation_type() -> None:
    with pytest.raises(TypeError, match="MethodologyOutcomeEvaluation"):
        MethodologyOutcomeStabilityAnalytics().calculate((object(),))
