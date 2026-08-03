from __future__ import annotations

from core.backtesting.methodology_variant_b_shadow_exception_stability import (
    MethodologyVariantBShadowExceptionStability,
)


def test_series_summary_tracks_drawdown_and_loss_streak() -> None:
    study = MethodologyVariantBShadowExceptionStability()
    summary = study._series_summary((2.0, -1.0, -1.0, -1.0, 2.0))
    assert summary["maximum_drawdown_r"] == 3.0
    assert summary["longest_drawdown_duration_trades"] == 4
    assert summary["maximum_consecutive_losses"] == 3


def test_deterioration_flags_negative_window() -> None:
    study = MethodologyVariantBShadowExceptionStability()
    flags = study._deterioration_flags(
        study._summary((-1.0,) * 10, (-1.1,) * 10)
    )
    assert "NON_POSITIVE_EXPECTANCY" in flags
    assert "PROFIT_FACTOR_BELOW_ONE" in flags
    assert "NON_POSITIVE_HIGH_COST_EXPECTANCY" in flags
    assert "EXPECTANCY_BELOW_HALF_REFERENCE" in flags


def test_rolling_rows_use_frozen_ten_trade_window() -> None:
    study = MethodologyVariantBShadowExceptionStability()
    rows = tuple(
        {
            "Observation Timestamp": f"2026-01-{i + 1:02d}T00:00:00+00:00",
            "Gross Result R": 1.0,
            "Net R High Cost": 0.5,
        }
        for i in range(12)
    )
    rolling = study._rolling_rows(rows)
    assert len(rolling) == 12
    assert rolling[-1]["Trade Count"] == 10
    assert rolling[-1]["Total Gross R"] == 10.0


def test_calendar_rows_separate_month_and_quarter() -> None:
    study = MethodologyVariantBShadowExceptionStability()
    rows = (
        {"Observation Timestamp": "2026-01-10T00:00:00+00:00",
         "Gross Result R": 2.0, "Net R High Cost": 1.5},
        {"Observation Timestamp": "2026-04-10T00:00:00+00:00",
         "Gross Result R": -1.0, "Net R High Cost": -1.5},
    )
    assert [r["Window Label"] for r in study._calendar_rows(rows, "MONTH")] == [
        "2026-01", "2026-04"
    ]
    assert [r["Window Label"] for r in study._calendar_rows(rows, "QUARTER")] == [
        "2026-Q1", "2026-Q2"
    ]


def test_stability_has_no_active_authority() -> None:
    payload, rows = MethodologyVariantBShadowExceptionStability().calculate(
        (), (), ()
    )
    assert rows == []
    assert payload["observational_only"] is True
    assert payload["trade_authority"] is False
    assert payload["signal_authority"] is False
    assert payload["approval_authority"] is False
    assert payload["position_sizing_authority"] is False
    assert payload["order_creation_authority"] is False
    assert payload["active_pipeline_modified"] is False
    assert payload["probability_threshold_modified"] is False
    assert payload["shadow_exception_approved"] is False
