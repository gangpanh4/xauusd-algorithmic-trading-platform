from __future__ import annotations

from datetime import UTC, datetime, timedelta

from core.backtesting.methodology_variant_b_shadow_exception_monitor import (
    MethodologyVariantBShadowExceptionMonitor,
)

from .test_methodology_variant_b_probability_subset import (
    _audit,
    _bars,
    _observation,
)


def test_monitors_only_frozen_probability_band() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    first = _observation(start + timedelta(minutes=100))
    second = _observation(start + timedelta(minutes=110))
    monitor = MethodologyVariantBShadowExceptionMonitor()

    payload, rows = monitor.calculate(
        (first, second),
        (
            _audit(first.timestamp, 0.55),
            _audit(second.timestamp, 0.45),
        ),
        _bars(start),
    )

    assert payload["counts"]["monitored_trade_count"] == 1
    assert len(rows) == 1
    assert rows[0]["Probability Band"] == "[0.5,0.6)"


def test_reports_chronological_cumulative_drawdown() -> None:
    monitor = MethodologyVariantBShadowExceptionMonitor()
    rows = monitor._monitor_rows(
        (
            {
                "Variant": monitor.VARIANT,
                "Observation Timestamp": "2026-01-01T00:00:00+00:00",
                "Entry Timestamp": "2026-01-01T00:05:00+00:00",
                "Exit Timestamp": "2026-01-01T00:10:00+00:00",
                "Probability Value": 0.55,
                "Probability Band": "[0.5,0.6)",
                "Gross Result R": 2.0,
                "Net R Zero Cost": 2.0,
                "Net R Low Cost": 1.9,
                "Net R Medium Cost": 1.75,
                "Net R High Cost": 1.5,
                "Exit Reason": "TARGET",
                "Holding Bars": 1,
                "Session": "London",
                "Regime": "RANGING",
                "Requested End Time": None,
                "M5 Window First Timestamp": None,
                "M5 Window Last Timestamp": None,
            },
            {
                "Variant": monitor.VARIANT,
                "Observation Timestamp": "2026-01-01T00:15:00+00:00",
                "Entry Timestamp": "2026-01-01T00:20:00+00:00",
                "Exit Timestamp": "2026-01-01T00:25:00+00:00",
                "Probability Value": 0.56,
                "Probability Band": "[0.5,0.6)",
                "Gross Result R": -1.0,
                "Net R Zero Cost": -1.0,
                "Net R Low Cost": -1.1,
                "Net R Medium Cost": -1.25,
                "Net R High Cost": -1.5,
                "Exit Reason": "STOP",
                "Holding Bars": 1,
                "Session": "London",
                "Regime": "RANGING",
                "Requested End Time": None,
                "M5 Window First Timestamp": None,
                "M5 Window Last Timestamp": None,
            },
        )
    )

    assert rows[-1]["Cumulative Gross R"] == 1.0
    assert rows[-1]["Gross Drawdown R"] == 1.0
    assert rows[-1]["Maximum Gross Drawdown To Date R"] == 1.0


def test_exports_monitor_files(tmp_path) -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    observation = _observation(start + timedelta(minutes=100))
    monitor = MethodologyVariantBShadowExceptionMonitor(tmp_path)

    csv_path, json_path = monitor.export(
        (observation,),
        (_audit(observation.timestamp, 0.55),),
        _bars(start),
    )

    assert csv_path.exists()
    assert json_path.exists()
    assert "Cumulative Gross R" in csv_path.read_text(
        encoding="utf-8"
    )


def test_monitor_has_no_active_authority() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    monitor = MethodologyVariantBShadowExceptionMonitor()
    payload, _ = monitor.calculate((), (), _bars(start))

    assert payload["observational_only"] is True
    assert payload["trade_authority"] is False
    assert payload["signal_authority"] is False
    assert payload["approval_authority"] is False
    assert payload["position_sizing_authority"] is False
    assert payload["order_creation_authority"] is False
    assert payload["active_pipeline_modified"] is False
    assert payload["probability_threshold_modified"] is False
    assert payload["shadow_exception_approved"] is False
