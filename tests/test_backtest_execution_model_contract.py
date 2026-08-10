from __future__ import annotations

import pytest

from core.backtesting.config import BacktestConfig, BacktestExecutionModel


def test_backtest_config_keeps_v1_as_compatibility_default() -> None:
    config = BacktestConfig()

    assert config.execution_model is BacktestExecutionModel.M15_COMPLETED_OHLC_V1


def test_v1_provenance_preserves_completed_m15_contract() -> None:
    provenance = BacktestExecutionModel.M15_COMPLETED_OHLC_V1.provenance()

    assert provenance == {
        "execution_model_id": "M15_COMPLETED_OHLC_V1",
        "decision_clock": "M5",
        "decision_available_after_minutes": 5,
        "entry_policy": "NEXT_M15_OPEN",
        "entry_clock": "M15",
        "lifecycle_clock": "M15_COMPLETED",
        "lifecycle_bar_minutes": 15,
        "closed_bar_consumption": "ONLY_AFTER_BAR_COMPLETES",
        "same_bar_entry_exit_evaluation": True,
        "intra_bar_ambiguity_policy": "CONSERVATIVE_STOP_FIRST",
        "gap_stop_policy": "BAR_OPEN_WITH_ADVERSE_SLIPPAGE",
        "gap_target_policy": "TARGET_PRICE_NO_FAVORABLE_GAP_IMPROVEMENT",
        "breakeven_activation_policy": (
            "PENDING_AFTER_TRIGGER_BAR_ACTIVE_NEXT_LIFECYCLE_BAR"
        ),
        "exit_timestamp_semantics": (
            "LIFECYCLE_BAR_OPEN_TIMESTAMP_INTRABAR_TIME_UNKNOWN"
        ),
        "comparable_with_unversioned_results": False,
    }


def test_v2_provenance_declares_causal_completed_m5_contract() -> None:
    provenance = BacktestExecutionModel.M5_COMPLETED_OHLC_V2.provenance()

    assert provenance["execution_model_id"] == "M5_COMPLETED_OHLC_V2"
    assert provenance["decision_clock"] == "M5"
    assert provenance["decision_available_after_minutes"] == 5
    assert provenance["entry_policy"] == "NEXT_AVAILABLE_M5_OPEN"
    assert provenance["entry_clock"] == "M5"
    assert provenance["lifecycle_clock"] == "M5_COMPLETED"
    assert provenance["lifecycle_bar_minutes"] == 5
    assert provenance["closed_bar_consumption"] == "ONLY_AFTER_BAR_COMPLETES"
    assert provenance["same_bar_entry_exit_evaluation"] is True
    assert provenance["comparable_with_unversioned_results"] is False


def test_v1_and_v2_are_not_silently_equivalent() -> None:
    v1 = BacktestExecutionModel.M15_COMPLETED_OHLC_V1.provenance()
    v2 = BacktestExecutionModel.M5_COMPLETED_OHLC_V2.provenance()

    assert v1["execution_model_id"] != v2["execution_model_id"]
    assert v1["entry_clock"] != v2["entry_clock"]
    assert v1["lifecycle_clock"] != v2["lifecycle_clock"]
    assert v1["lifecycle_bar_minutes"] != v2["lifecycle_bar_minutes"]
    assert v1["comparable_with_unversioned_results"] is False
    assert v2["comparable_with_unversioned_results"] is False


def test_invalid_execution_model_fails_closed() -> None:
    with pytest.raises(TypeError, match="BacktestExecutionModel"):
        BacktestConfig(execution_model="M5_COMPLETED_OHLC_V2")  # type: ignore[arg-type]
