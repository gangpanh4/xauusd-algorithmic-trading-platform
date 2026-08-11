from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.live_trading.config import LiveTradingConfig
from core.live_trading.engine import LiveTradingEngine
from core.risk_manager.models import RiskDecision

NOW = datetime(2026, 8, 11, 4, 0, tzinfo=UTC)


def _approved_result():
    return SimpleNamespace(
        signal=SimpleNamespace(direction=SimpleNamespace(name="BUY")),
        trade_plan=SimpleNamespace(decision=RiskDecision.APPROVE),
    )


def test_precomputed_execution_requires_active_execution() -> None:
    engine = LiveTradingEngine(LiveTradingConfig())
    bar = SimpleNamespace(timestamp=NOW)

    with pytest.raises(RuntimeError, match="requires live execution"):
        engine.execute_precomputed_approved_observation(
            observation_bar=bar,  # type: ignore[arg-type]
            pipeline_result=_approved_result(),  # type: ignore[arg-type]
        )


def test_precomputed_execution_rejects_nonapproved_result() -> None:
    engine = LiveTradingEngine(
        LiveTradingConfig(
            live_execution_enabled=True,
            demo_execution_approved=True,
            execution_kill_switch_enabled=False,
        )
    )
    bar = SimpleNamespace(timestamp=NOW)
    result = _approved_result()
    result.trade_plan.decision = RiskDecision.SKIP

    with pytest.raises(ValueError, match="RiskDecision.APPROVE"):
        engine.execute_precomputed_approved_observation(
            observation_bar=bar,  # type: ignore[arg-type]
            pipeline_result=result,  # type: ignore[arg-type]
        )


def test_precomputed_approved_result_does_not_rerun_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = LiveTradingEngine(
        LiveTradingConfig(
            live_execution_enabled=True,
            demo_execution_approved=True,
            execution_kill_switch_enabled=False,
        )
    )
    bar = SimpleNamespace(timestamp=NOW)
    pipeline_result = _approved_result()
    finalize = Mock(return_value=object())
    process_bar = Mock()
    monkeypatch.setattr(engine, "_finalize_observation", finalize)
    monkeypatch.setattr(engine.pipeline, "process_bar", process_bar)

    returned = engine.execute_precomputed_approved_observation(
        observation_bar=bar,  # type: ignore[arg-type]
        pipeline_result=pipeline_result,  # type: ignore[arg-type]
    )

    assert returned is finalize.return_value
    process_bar.assert_not_called()
    finalize.assert_called_once_with(
        observation_bar=bar,
        pipeline_result=pipeline_result,
        warmup=False,
        parity_context=None,
    )
