from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import core.live_trading.engine as live_engine_module
from core.live_trading.config import LiveTradingConfig
from core.live_trading.engine import LiveTradingEngine
from core.mt5_execution.authority import _require_broker_mutation_authority
from core.mt5_execution.models import (
    AccountInfo,
    OrderRequest,
    OrderResult,
    OrderSide,
    OrderStatus,
    SymbolInfo,
)
from core.regime_detector.models import MarketBar
from core.risk_manager.models import RiskDecision


def _bar(*, seconds: int = 0) -> MarketBar:
    return MarketBar(
        timestamp=datetime.now(UTC) + timedelta(seconds=seconds),
        open=4000.0,
        high=4005.0,
        low=3998.0,
        close=4003.0,
        volume=1000,
    )


def _approved():
    return SimpleNamespace(
        signal=SimpleNamespace(direction="BUY"),
        trade_plan=SimpleNamespace(
            decision=RiskDecision.APPROVE,
            entry_price=4003.0,
            stop_loss=4001.0,
            take_profit=4007.0,
            position_size=0.01,
        ),
    )


def _pending_result() -> OrderResult:
    return OrderResult(
        timestamp=datetime.now(UTC),
        status=OrderStatus.PENDING,
        ticket=987654,
        executed_price=0.0,
        message="PLACED [10008]: accepted",
        retcode=10008,
    )


def _partial_result(*, volume: float = 0.004) -> OrderResult:
    return OrderResult(
        timestamp=datetime.now(UTC),
        status=OrderStatus.PARTIALLY_FILLED,
        ticket=123456,
        executed_price=4003.0,
        message="DONE_PARTIAL [10010]: partial",
        retcode=10010,
        executed_volume=volume,
    )


def _authorized_result(result: OrderResult) -> OrderResult:
    _require_broker_mutation_authority()
    return result


def _config(path: Path, *, enabled: bool = False) -> LiveTradingConfig:
    return LiveTradingConfig(
        live_execution_enabled=enabled,
        demo_execution_approved=enabled,
        execution_kill_switch_enabled=not enabled,
        approved_account_login=123456 if enabled else None,
        approved_account_server="MetaQuotes-Demo" if enabled else None,
        demo_authorization_path=path.with_name("demo_authorization.json"),
        partial_fill_state_path=path,
        execution_intent_state_path=path.with_name("execution_intent.json"),
    )


def _enabled_engine(path: Path) -> LiveTradingEngine:
    config = _config(path, enabled=True)
    now = datetime.now(UTC)
    config.demo_authorization_path.write_text(
        __import__("json").dumps(
            {
                "schema_version": 1,
                "authorization_id": "pending-order-guard-test",
                "issued_at": (now - timedelta(minutes=1)).isoformat(),
                "expires_at": (now + timedelta(minutes=4)).isoformat(),
                "account_login": 123456,
                "account_server": "MetaQuotes-Demo",
                "symbol": "XAUUSD",
                "maximum_volume": 0.01,
                "maximum_submissions": 1,
                "demo_only": True,
                "one_shot": True,
                "acknowledgement": "I AUTHORIZE ONE DEMO ORDER",
                "consumed_at": None,
                "consumed_intent_key": None,
            }
        ),
        encoding="utf-8",
    )
    live_engine_module.get_account_info = Mock(
        return_value=AccountInfo(
            login=123456,
            server="MetaQuotes-Demo",
            balance=10_000.0,
            equity=10_000.0,
            margin=0.0,
            free_margin=10_000.0,
            leverage=100,
            currency="USD",
            trade_mode=0,
        )
    )
    live_engine_module.get_open_positions = Mock(return_value=[])
    live_engine_module.get_active_order_count = Mock(return_value=0)
    live_engine_module.get_symbol_info = Mock(
        return_value=SymbolInfo(
            name="XAUUSD",
            digits=2,
            point=0.01,
            spread=10,
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
            trade_allowed=True,
        )
    )
    engine = LiveTradingEngine(config)
    engine.state.running = True
    engine.state.realized_deals_synchronized = True
    engine.record_clock_normalization_validated()
    engine.record_parity_validation_passed()
    engine.pipeline.process_bar = Mock(return_value=_approved())
    engine.executor.is_connected = Mock(return_value=True)
    engine.adapter.adapt = Mock(
        return_value=SimpleNamespace(
            order_request=OrderRequest(
                symbol="XAUUSD",
                side=OrderSide.BUY,
                volume=0.01,
                entry_price=4003.0,
                stop_loss=4001.0,
                take_profit=4007.0,
            ),
        )
    )
    return engine


def _set_partial_state(engine: LiveTradingEngine) -> None:
    engine.state.unresolved_partial_ticket = 123456
    engine.state.unresolved_requested_volume = 0.01
    engine.state.unresolved_executed_volume = 0.004
    engine.state.unresolved_remaining_volume = 0.006
    engine.state.unresolved_partial_created_at = datetime.now(UTC)
    engine.state.active_order_count = 1


def test_pending_result_blocks_future_execution(tmp_path: Path) -> None:
    engine = _enabled_engine(tmp_path / "partial.json")
    engine.executor.execute_order = Mock(
        side_effect=lambda request: _authorized_result(_pending_result())
    )

    result = engine.process_bar(
        _bar(),
        account_balance=10_000.0,
        stop_loss_distance=2.0,
        pip_value=1.0,
    )

    assert result.trade_executed is False
    assert result.execution_result.status is OrderStatus.PENDING
    assert engine.state.active_order_count == 1
    assert engine.state.last_ticket == 987654


def test_active_order_guard_prevents_duplicate_submission(
    tmp_path: Path,
) -> None:
    engine = _enabled_engine(tmp_path / "partial.json")
    engine.state.active_order_count = 1
    engine.executor.execute_order = Mock()

    result = engine.process_bar(
        _bar(),
        account_balance=10_000.0,
        stop_loss_distance=2.0,
        pip_value=1.0,
    )

    assert result.trade_executed is False
    assert result.execution_result is None
    engine.executor.execute_order.assert_not_called()


def test_broker_reconciliation_clears_active_order_guard(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine = LiveTradingEngine(_config(tmp_path / "partial.json"))
    engine.state.active_order_count = 1
    monkeypatch.setattr(
        live_engine_module,
        "get_active_order_count",
        lambda symbol: 0,
    )

    assert engine.synchronize_active_orders() == 0
    assert engine.state.active_order_count == 0


def test_active_order_query_failure_preserves_existing_guard(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine = LiveTradingEngine(_config(tmp_path / "partial.json"))
    engine.state.active_order_count = 1

    def fail(symbol: str) -> int:
        raise RuntimeError("Unable to retrieve active MT5 orders")

    monkeypatch.setattr(
        live_engine_module,
        "get_active_order_count",
        fail,
    )

    with pytest.raises(
        RuntimeError,
        match="Unable to retrieve active MT5 orders",
    ):
        engine.synchronize_active_orders()

    assert engine.state.active_order_count == 1


def test_partial_fill_records_actual_and_remaining_volume(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "partial.json"
    engine = _enabled_engine(state_path)
    engine.pipeline.register_position_opened = Mock()
    engine.executor.execute_order = Mock(
        side_effect=lambda request: _authorized_result(
            _partial_result(volume=0.004)
        )
    )

    result = engine.process_bar(
        _bar(),
        account_balance=10_000.0,
        stop_loss_distance=2.0,
        pip_value=1.0,
    )

    assert result.trade_executed is True
    assert result.execution_result.status is OrderStatus.PARTIALLY_FILLED
    assert engine.state.unresolved_partial_ticket == 123456
    assert engine.state.unresolved_requested_volume == pytest.approx(0.01)
    assert engine.state.unresolved_executed_volume == pytest.approx(0.004)
    assert engine.state.unresolved_remaining_volume == pytest.approx(0.006)
    assert engine.state.unresolved_partial_created_at is not None
    assert engine.state.active_order_count == 1
    assert engine.state.executed_trades == 0
    assert state_path.exists()
    engine.pipeline.register_position_opened.assert_called_once_with()


def test_unresolved_partial_fill_blocks_new_submission(
    tmp_path: Path,
) -> None:
    engine = _enabled_engine(tmp_path / "partial.json")
    _set_partial_state(engine)
    engine.executor.execute_order = Mock()

    result = engine.process_bar(
        _bar(),
        account_balance=10_000.0,
        stop_loss_distance=2.0,
        pip_value=1.0,
    )

    assert result.trade_executed is False
    assert result.execution_result is None
    assert "remainder is unresolved" in engine.state.last_error
    engine.executor.execute_order.assert_not_called()


def test_partial_fill_reconciliation_tracks_later_fill(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "partial.json"
    engine = LiveTradingEngine(_config(state_path))
    _set_partial_state(engine)

    monkeypatch.setattr(
        live_engine_module,
        "get_active_order_count",
        lambda symbol: 1,
    )
    monkeypatch.setattr(
        live_engine_module,
        "get_open_positions",
        lambda symbol: [SimpleNamespace(volume=0.007)],
    )

    assert engine.synchronize_active_orders() == 1
    assert engine.state.unresolved_executed_volume == pytest.approx(0.007)
    assert engine.state.unresolved_remaining_volume == pytest.approx(0.003)
    assert engine.state.executed_trades == 0
    assert state_path.exists()


def test_partial_fill_completion_increments_counter_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "partial.json"
    engine = LiveTradingEngine(_config(state_path))
    _set_partial_state(engine)
    engine._persist_partial_fill_state()

    monkeypatch.setattr(
        live_engine_module,
        "get_active_order_count",
        lambda symbol: 0,
    )
    monkeypatch.setattr(
        live_engine_module,
        "get_open_positions",
        lambda symbol: [SimpleNamespace(volume=0.01)],
    )

    assert engine.synchronize_active_orders() == 0
    assert engine.state.executed_trades == 1
    assert engine.state.last_partial_fill_resolution == "FILLED"
    assert engine.state.unresolved_partial_ticket is None
    assert engine.state.unresolved_remaining_volume == 0.0
    assert not state_path.exists()

    assert engine.synchronize_active_orders() == 0
    assert engine.state.executed_trades == 1


def test_partial_fill_cancelled_remainder_preserves_actual_position(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "partial.json"
    engine = LiveTradingEngine(_config(state_path))
    _set_partial_state(engine)
    engine._persist_partial_fill_state()

    monkeypatch.setattr(
        live_engine_module,
        "get_active_order_count",
        lambda symbol: 0,
    )
    monkeypatch.setattr(
        live_engine_module,
        "get_open_positions",
        lambda symbol: [SimpleNamespace(volume=0.004)],
    )

    assert engine.synchronize_active_orders() == 0
    assert engine.state.executed_trades == 0
    assert (
        engine.state.last_partial_fill_resolution
        == "REMAINDER_CANCELLED_OR_REJECTED"
    )
    assert engine.state.unresolved_partial_ticket is None
    assert not state_path.exists()


@pytest.mark.parametrize("observed_volume", [0.003, 0.011])
def test_inconsistent_partial_reconciliation_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    observed_volume: float,
) -> None:
    state_path = tmp_path / "partial.json"
    engine = LiveTradingEngine(_config(state_path))
    _set_partial_state(engine)
    engine._persist_partial_fill_state()

    monkeypatch.setattr(
        live_engine_module,
        "get_active_order_count",
        lambda symbol: 0,
    )
    monkeypatch.setattr(
        live_engine_module,
        "get_open_positions",
        lambda symbol: [SimpleNamespace(volume=observed_volume)],
    )

    assert engine.synchronize_active_orders() == 1
    assert engine.state.unresolved_partial_ticket == 123456
    assert engine.state.last_error
    assert engine.state.executed_trades == 0
    assert state_path.exists()
