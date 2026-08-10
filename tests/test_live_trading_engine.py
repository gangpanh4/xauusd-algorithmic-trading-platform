from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.live_trading.config import LiveTradingConfig
from core.live_trading.engine import LiveTradingEngine
from core.regime_detector.models import MarketBar
from core.risk_manager.models import RiskDecision
from core.trading_pipeline.models import (
    PipelineDisposition,
    PipelineObservationAudit,
    PipelineStage,
)


def _market_bar() -> MarketBar:
    return MarketBar(
        timestamp=datetime.now(UTC),
        open=4000.0,
        high=4005.0,
        low=3998.0,
        close=4003.0,
        volume=1000,
    )


def _approved_pipeline_result() -> SimpleNamespace:
    trade_plan = SimpleNamespace(
        decision=RiskDecision.APPROVE,
        entry_price=4003.0,
        stop_loss=4001.0,
        take_profit=4007.0,
        position_size=0.01,
    )
    signal = SimpleNamespace(direction="BUY")
    return SimpleNamespace(
        signal=signal,
        trade_plan=trade_plan,
    )


def test_disabled_engine_processes_bars_without_initializing_mt5() -> None:
    engine = LiveTradingEngine(LiveTradingConfig())
    engine.executor.initialize = Mock(return_value=True)

    engine.start()

    assert engine.state.running is True
    engine.executor.initialize.assert_not_called()


def test_disabled_engine_never_executes_approved_trade() -> None:
    engine = LiveTradingEngine(LiveTradingConfig())
    pipeline_result = _approved_pipeline_result()

    engine.pipeline.process_bar = Mock(return_value=pipeline_result)
    engine.adapter.adapt = Mock()
    engine.executor.execute_order = Mock()

    engine.start()
    result = engine.process_bar(
        _market_bar(),
        account_balance=1000.0,
        stop_loss_distance=2.0,
        pip_value=1.0,
    )

    assert result.pipeline_result is pipeline_result
    assert result.execution_result is None
    assert result.trade_executed is False
    assert engine.state.executed_trades == 0
    assert engine.state.skipped_trades == 1
    engine.adapter.adapt.assert_not_called()
    engine.executor.execute_order.assert_not_called()


def test_disabled_engine_stop_does_not_shutdown_mt5() -> None:
    engine = LiveTradingEngine(LiveTradingConfig())
    engine.executor.shutdown = Mock()

    engine.start()
    engine.stop()

    assert engine.state.running is False
    engine.executor.shutdown.assert_not_called()


def test_enabled_engine_fails_closed_when_mt5_attachment_fails() -> None:
    config = LiveTradingConfig(live_execution_enabled=True)
    engine = LiveTradingEngine(config)
    engine.executor.attach = Mock(return_value=False)

    with pytest.raises(
        RuntimeError,
        match="Failed to attach MT5 execution",
    ):
        engine.start()

    assert engine.state.running is False
    assert engine.state.last_error == "Failed to attach MT5 execution."


def test_live_trading_engine_contract() -> None:
    engine = LiveTradingEngine(LiveTradingConfig())
    engine.start()

    bar = _market_bar()
    result = engine.process_bar(
        bar,
        account_balance=1000.0,
        stop_loss_distance=2.0,
        pip_value=1.0,
    )

    assert result is not None
    assert result.pipeline_result is not None

    trade_plan = result.pipeline_result.trade_plan

    assert trade_plan is not None
    assert hasattr(trade_plan, "entry_price")

    if trade_plan.decision.value == "APPROVE":
        assert trade_plan.entry_price == bar.close
        assert trade_plan.stop_loss != 0
        assert trade_plan.take_profit != 0
        assert trade_plan.position_size > 0
        assert result.trade_executed is False
    else:
        assert trade_plan.entry_price == 0.0
        assert trade_plan.stop_loss == 0.0
        assert trade_plan.take_profit == 0.0
        assert trade_plan.position_size == 0.0


def test_multi_timeframe_forwards_broker_volume_limits() -> None:
    engine = LiveTradingEngine(LiveTradingConfig())
    bar = _market_bar()
    snapshot = {
        timeframe: [bar]
        for timeframe in (
            __import__("core.multi_timeframe.enums", fromlist=["Timeframe"]).Timeframe.M5,
            __import__("core.multi_timeframe.enums", fromlist=["Timeframe"]).Timeframe.M15,
            __import__("core.multi_timeframe.enums", fromlist=["Timeframe"]).Timeframe.H1,
            __import__("core.multi_timeframe.enums", fromlist=["Timeframe"]).Timeframe.H4,
        )
    }
    mtf_result = SimpleNamespace(
        m5=SimpleNamespace(market_structure=SimpleNamespace())
    )
    engine.pipeline.multi_timeframe.process = Mock(return_value=mtf_result)
    engine.pipeline.confluence_engine.evaluate_multi_timeframe = Mock(
        return_value=None
    )
    pipeline_result = _approved_pipeline_result()
    engine.pipeline.process_bar = Mock(return_value=pipeline_result)

    engine.process_multi_timeframe(
        snapshot,
        account_balance=1000.0,
        stop_loss_distance=0.01,
        pip_value=0.1,
        tick_size=0.01,
        lot_step=0.01,
        minimum_lot=0.01,
        maximum_lot=25.0,
        warmup=True,
    )

    kwargs = engine.pipeline.process_bar.call_args.kwargs
    assert kwargs["minimum_lot"] == 0.01
    assert kwargs["maximum_lot"] == 25.0


def test_duplicate_timestamp_is_rejected_before_pipeline_mutation() -> None:
    engine = LiveTradingEngine(LiveTradingConfig())
    bar = _market_bar()
    engine.pipeline.process_bar = Mock(
        return_value=_approved_pipeline_result()
    )

    engine.process_bar(
        bar,
        account_balance=1000.0,
        stop_loss_distance=2.0,
        pip_value=1.0,
        warmup=True,
    )

    with pytest.raises(ValueError, match="increase strictly"):
        engine.process_bar(
            bar,
            account_balance=1000.0,
            stop_loss_distance=2.0,
            pip_value=1.0,
            warmup=True,
        )

    assert engine.pipeline.process_bar.call_count == 1


def test_analysis_only_engine_records_append_only_shadow_observation(
    tmp_path,
) -> None:
    path = tmp_path / "shadow.jsonl"
    engine = LiveTradingEngine(
        LiveTradingConfig(
            shadow_recording_enabled=True,
            shadow_observation_path=path,
        )
    )
    pipeline_result = _approved_pipeline_result()
    pipeline_result.trade_plan.risk_reward_ratio = 2.0
    pipeline_result.trade_plan.reason = "approved test"
    engine.pipeline.process_bar = Mock(return_value=pipeline_result)
    bar = _market_bar()
    engine.pipeline._last_observation_audit = PipelineObservationAudit(
        timestamp=bar.timestamp,
        disposition=PipelineDisposition.ACCEPTED,
        stage_reached=PipelineStage.APPROVED,
        regime_confirmed=True,
        bos_present=True,
        feature_count=6,
        probability_calculated=True,
        probability_accepted=True,
        probability_value=0.75,
        trade_quality_calculated=True,
        trade_quality_approved=True,
        trade_quality_score=0.8,
        confluence_available=True,
        confluence_approved=True,
        confluence_score=0.7,
        signal_generated=True,
        risk_approved=True,
    )
    engine.adapter.adapt = Mock()
    engine.executor.execute_order = Mock()

    result = engine.process_bar(
        bar,
        account_balance=1000.0,
        stop_loss_distance=2.0,
        pip_value=1.0,
    )

    assert result.trade_executed is False
    assert engine.state.shadow_observations_recorded == 1
    engine.adapter.adapt.assert_not_called()
    engine.executor.execute_order.assert_not_called()

    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 1
    assert rows[0]["timestamp"] == bar.timestamp.isoformat()
    assert datetime.fromisoformat(rows[0]["recorded_at"]) >= bar.timestamp
    assert rows[0]["session_id"] == engine.state.shadow_session_id
    assert rows[0]["session_id"]
    assert rows[0]["session_started_at"] == (
        engine.state.shadow_session_started_at.isoformat()
    )
    assert rows[0]["symbol"] == "XAUUSD"
    assert rows[0]["live_execution_enabled"] is False
    assert rows[0]["shadow_only"] is True
    assert rows[0]["decision"] == "APPROVE"
    assert rows[0]["entry_price"] == pytest.approx(4003.0)
    assert rows[0]["stop_loss"] == pytest.approx(4001.0)
    assert rows[0]["take_profit"] == pytest.approx(4007.0)
    assert rows[0]["position_size"] == pytest.approx(0.01)
    assert rows[0]["trade_executed"] is False
    assert rows[0]["pipeline_disposition"] == "ACCEPTED"
    assert rows[0]["pipeline_stage_reached"] == "APPROVED"
    assert rows[0]["pipeline_rejection_stage"] is None
    assert rows[0]["pipeline_reason_code"] is None
    assert rows[0]["regime_confirmed"] is True
    assert rows[0]["bos_present"] is True
    assert rows[0]["feature_count"] == 6
    assert rows[0]["probability_value"] == pytest.approx(0.75)
    assert rows[0]["trade_quality_score"] == pytest.approx(0.8)
    assert rows[0]["confluence_score"] == pytest.approx(0.7)
    assert rows[0]["signal_generated"] is True
    assert rows[0]["risk_approved"] is True


def test_warmup_does_not_write_shadow_observation(tmp_path) -> None:
    path = tmp_path / "shadow.jsonl"
    engine = LiveTradingEngine(
        LiveTradingConfig(
            shadow_recording_enabled=True,
            shadow_observation_path=path,
        )
    )
    engine.pipeline.process_bar = Mock(
        return_value=_approved_pipeline_result()
    )

    engine.process_bar(
        _market_bar(),
        account_balance=1000.0,
        stop_loss_distance=2.0,
        pip_value=1.0,
        warmup=True,
    )

    assert engine.state.shadow_observations_recorded == 0
    assert not path.exists()


def test_restart_creates_new_shadow_session_metadata(tmp_path) -> None:
    path = tmp_path / "shadow.jsonl"
    config = LiveTradingConfig(
        shadow_recording_enabled=True,
        shadow_observation_path=path,
    )
    engine = LiveTradingEngine(config)
    engine.pipeline.process_bar = Mock(
        return_value=_approved_pipeline_result()
    )

    engine.start()
    first_session_id = engine.state.shadow_session_id
    first_started_at = engine.state.shadow_session_started_at
    first_bar = _market_bar()
    engine.process_bar(
        first_bar,
        account_balance=1000.0,
        stop_loss_distance=2.0,
        pip_value=1.0,
    )
    engine.stop()

    engine.start()
    second_session_id = engine.state.shadow_session_id
    second_started_at = engine.state.shadow_session_started_at
    second_bar = MarketBar(
        timestamp=first_bar.timestamp.replace(
            minute=(first_bar.timestamp.minute + 5) % 60
        ),
        open=4000.0,
        high=4005.0,
        low=3998.0,
        close=4003.0,
        volume=1000,
    )
    engine.process_bar(
        second_bar,
        account_balance=1000.0,
        stop_loss_distance=2.0,
        pip_value=1.0,
    )

    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 2
    assert first_session_id != second_session_id
    assert first_started_at is not None
    assert second_started_at is not None
    assert rows[0]["session_id"] == first_session_id
    assert rows[1]["session_id"] == second_session_id


def test_multi_timeframe_records_analysis_only_parity_evidence(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core.live_trading import engine as live_trading_engine_module
    from core.live_trading.parity_provenance import (
        CURRENT_PARITY_HISTORY_CONTRACT_VERSION,
        M5_ANALYTICAL_CONTRACT_V1,
        PARITY_EVIDENCE_SCHEMA_VERSION,
        ParityAnalyticalProvenance,
    )
    from core.multi_timeframe.enums import Timeframe

    source_commit = "a" * 40
    config_fingerprint = "b" * 64
    monkeypatch.setattr(
        live_trading_engine_module,
        "current_parity_provenance",
        lambda _config: ParityAnalyticalProvenance(
            analytical_contract_version=M5_ANALYTICAL_CONTRACT_V1,
            source_commit=source_commit,
            pipeline_config_fingerprint=config_fingerprint,
        ),
    )

    path = tmp_path / "parity.jsonl"
    engine = LiveTradingEngine(
        LiveTradingConfig(
            parity_recording_enabled=True,
            parity_evidence_path=path,
        )
    )
    bar = _market_bar()
    snapshot = {timeframe: [bar] for timeframe in Timeframe}
    mtf_result = SimpleNamespace(
        m5=SimpleNamespace(market_structure=SimpleNamespace())
    )
    engine.pipeline.multi_timeframe.process = Mock(return_value=mtf_result)
    engine.pipeline.confluence_engine.evaluate_multi_timeframe = Mock(
        return_value=None
    )
    pipeline_result = _approved_pipeline_result()
    engine.pipeline.process_bar = Mock(return_value=pipeline_result)
    engine.pipeline._last_observation_audit = PipelineObservationAudit(
        timestamp=bar.timestamp,
        disposition=PipelineDisposition.ACCEPTED,
        stage_reached=PipelineStage.APPROVED,
        regime_confirmed=True,
        probability_calculated=True,
        probability_accepted=True,
        probability_value=0.75,
        trade_quality_calculated=True,
        trade_quality_approved=True,
        trade_quality_score=0.8,
        signal_generated=True,
        risk_approved=True,
    )

    result = engine.process_multi_timeframe(
        snapshot,
        account_balance=10_000.0,
        stop_loss_distance=0.01,
        pip_value=0.1,
        tick_size=0.01,
        lot_step=0.01,
        minimum_lot=0.01,
        maximum_lot=100.0,
    )

    assert result.trade_executed is False
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == PARITY_EVIDENCE_SCHEMA_VERSION
    assert (
        payload["analytical_contract_version"]
        == M5_ANALYTICAL_CONTRACT_V1
    )
    assert payload["source_commit"] == source_commit
    assert payload["pipeline_config_fingerprint"] == config_fingerprint
    assert payload["history_contract_version"] == (
        CURRENT_PARITY_HISTORY_CONTRACT_VERSION
    )
    assert payload["observation_timestamp"] == bar.timestamp.isoformat()
    assert payload["live_execution_enabled"] is False
    assert payload["shadow_only"] is True
    assert payload["trade_executed"] is False
    assert set(payload["bars_by_timeframe"]) == {"M5", "M15", "H1", "H4"}
