from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import core.live_trading.engine as live_engine_module
from core.live_trading.config import LiveTradingConfig
from core.live_trading.demo_execution_authorization import (
    load_demo_execution_authorization,
)
from core.live_trading.engine import LiveTradingEngine
from core.live_trading.execution_intent_store import build_execution_intent
from core.live_trading.partial_fill_store import PersistedPartialFill
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


def _account(*, login: int = 123456) -> AccountInfo:
    return AccountInfo(
        login=login,
        server="MetaQuotes-Demo",
        balance=10_000.0,
        equity=10_000.0,
        margin=0.0,
        free_margin=10_000.0,
        leverage=100,
        currency="USD",
        trade_mode=0,
    )


def _symbol() -> SymbolInfo:
    return SymbolInfo(
        name="XAUUSD",
        digits=2,
        point=0.01,
        spread=10,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
        trade_allowed=True,
    )


def _request() -> OrderRequest:
    return OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=0.01,
        entry_price=4003.0,
        stop_loss=4001.0,
        take_profit=4007.0,
    )


def _approved() -> SimpleNamespace:
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


def _bar(index: int = 0) -> MarketBar:
    return MarketBar(
        timestamp=datetime.now(UTC) + timedelta(minutes=index),
        open=4000.0,
        high=4005.0,
        low=3998.0,
        close=4003.0,
        volume=1000,
    )


def _write_authorization(
    path: Path,
    *,
    authorization_id: str,
) -> None:
    now = datetime.now(UTC)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "authorization_id": authorization_id,
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
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _enabled_engine(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    maximum_submissions: int = 1,
    maximum_failures: int = 1,
) -> LiveTradingEngine:
    config = LiveTradingConfig(
        live_execution_enabled=True,
        demo_execution_approved=True,
        execution_kill_switch_enabled=False,
        approved_account_login=123456,
        approved_account_server="MetaQuotes-Demo",
        maximum_order_submissions_per_session=maximum_submissions,
        maximum_consecutive_execution_failures=maximum_failures,
        demo_authorization_path=tmp_path / "authorization.json",
        partial_fill_state_path=tmp_path / "partial.json",
        execution_intent_state_path=tmp_path / "intent.json",
        execution_reconciliation_audit_path=tmp_path / "audit.jsonl",
    )
    _write_authorization(
        config.demo_authorization_path,
        authorization_id="phase-5-authorization-1",
    )
    monkeypatch.setattr(live_engine_module, "get_account_info", _account)
    monkeypatch.setattr(
        live_engine_module,
        "get_open_positions",
        lambda symbol: [],
    )
    monkeypatch.setattr(
        live_engine_module,
        "get_active_order_count",
        lambda symbol: 0,
    )
    monkeypatch.setattr(
        live_engine_module,
        "get_symbol_info",
        lambda symbol: _symbol(),
    )

    engine = LiveTradingEngine(config)
    engine.state.running = True
    engine.state.realized_deals_synchronized = True
    engine.state.execution_intent_reconciliation_status = "NO_INTENT"
    engine.record_clock_normalization_validated()
    engine.record_parity_validation_passed()
    engine.pipeline.process_bar = Mock(return_value=_approved())
    engine.pipeline.register_position_opened = Mock()
    engine.executor.is_connected = Mock(return_value=True)
    engine.adapter.adapt = Mock(
        return_value=SimpleNamespace(order_request=_request())
    )
    return engine


def _execution_result(
    status: OrderStatus,
    *,
    retcode: int | None,
) -> OrderResult:
    return OrderResult(
        timestamp=datetime.now(UTC),
        status=status,
        ticket=None if status is OrderStatus.REJECTED else 987654,
        executed_price=4003.0,
        message=f"{status.value} test result",
        retcode=retcode,
        executed_volume=(
            0.01
            if status in {OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED}
            else 0.0
        ),
    )


def _mock_execution(
    engine: LiveTradingEngine,
    result: OrderResult,
) -> Mock:
    def execute(request: OrderRequest) -> OrderResult:
        _require_broker_mutation_authority()
        return replace(result, timestamp=datetime.now(UTC))

    mocked = Mock(side_effect=execute)
    engine.executor.execute_order = mocked
    return mocked


def _process(engine: LiveTradingEngine, index: int = 0):
    return engine.process_bar(
        _bar(index),
        account_balance=10_000.0,
        stop_loss_distance=2.0,
        pip_value=1.0,
    )


def test_readiness_pass_allows_authoritative_submission(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine = _enabled_engine(monkeypatch, tmp_path)
    execute = _mock_execution(
        engine,
        _execution_result(OrderStatus.FILLED, retcode=10009),
    )

    result = _process(engine)

    assert result.trade_executed is True
    assert engine.state.order_submissions_this_session == 1
    assert load_demo_execution_authorization(
        engine.config.demo_authorization_path
    ).consumed is True
    execute.assert_called_once()


def test_competing_engine_cannot_reach_mutation_and_owner_keeps_counters(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    owner_engine = _enabled_engine(
        monkeypatch,
        tmp_path,
        maximum_submissions=2,
        maximum_failures=2,
    )
    contender_engine = _enabled_engine(
        monkeypatch,
        tmp_path,
        maximum_submissions=2,
        maximum_failures=2,
    )
    owner_execute = _mock_execution(
        owner_engine,
        _execution_result(OrderStatus.FILLED, retcode=10009),
    )
    contender_engine.executor.execute_order = Mock()

    owner = owner_engine._execution_submission_lock.acquire()
    try:
        blocked = _process(contender_engine)
    finally:
        owner_engine._execution_submission_lock.release(owner)

    assert blocked.execution_result is None
    assert "ownership is already held or stale" in contender_engine.state.last_error
    assert contender_engine.state.order_submissions_this_session == 0
    assert contender_engine.execution_intent_store.load() is None
    assert load_demo_execution_authorization(
        contender_engine.config.demo_authorization_path
    ).consumed is False
    contender_engine.executor.execute_order.assert_not_called()

    successful = _process(owner_engine)

    assert successful.trade_executed is True
    assert owner_engine.state.order_submissions_this_session == 1
    assert owner_engine.state.consecutive_execution_failures == 0
    owner_execute.assert_called_once()


def test_readiness_failure_blocks_before_intent_or_authorization_consumption(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine = _enabled_engine(monkeypatch, tmp_path)
    engine.state.parity_validation_passed = False
    engine.executor.execute_order = Mock()

    result = _process(engine)

    assert result.execution_result is None
    assert "parity validation" in engine.state.last_error
    assert engine.state.order_submissions_this_session == 0
    assert engine.execution_intent_store.load() is None
    assert load_demo_execution_authorization(
        engine.config.demo_authorization_path
    ).consumed is False
    engine.executor.execute_order.assert_not_called()


def test_session_limit_counts_authorized_executor_invocations_and_blocks_new_auth(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine = _enabled_engine(
        monkeypatch,
        tmp_path,
        maximum_submissions=2,
        maximum_failures=5,
    )
    execute = _mock_execution(
        engine,
        _execution_result(OrderStatus.REJECTED, retcode=None),
    )

    assert _process(engine, 0).execution_result is not None
    _write_authorization(
        engine.config.demo_authorization_path,
        authorization_id="phase-5-authorization-2",
    )
    assert _process(engine, 1).execution_result is not None
    assert engine.state.order_submissions_this_session == 2

    _write_authorization(
        engine.config.demo_authorization_path,
        authorization_id="phase-5-authorization-3",
    )
    blocked = _process(engine, 2)

    assert blocked.execution_result is None
    assert "submission limit" in engine.state.last_error
    assert engine.state.order_submissions_this_session == 2
    assert load_demo_execution_authorization(
        engine.config.demo_authorization_path
    ).consumed is False
    assert execute.call_count == 2


def test_start_resets_process_session_safety_state() -> None:
    engine = LiveTradingEngine(LiveTradingConfig())
    engine.state.order_submissions_this_session = 3
    engine.state.consecutive_execution_failures = 2
    engine.record_clock_normalization_validated()
    engine.record_parity_validation_passed()

    engine.start()

    assert engine.state.order_submissions_this_session == 0
    assert engine.state.consecutive_execution_failures == 0
    assert engine.state.clock_normalization_validated is False
    assert engine.state.parity_validation_passed is False


def test_confirmed_broker_failure_opens_breaker_before_next_submission(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine = _enabled_engine(
        monkeypatch,
        tmp_path,
        maximum_submissions=5,
        maximum_failures=2,
    )
    engine.state.consecutive_execution_failures = 1
    execute = _mock_execution(
        engine,
        _execution_result(OrderStatus.REJECTED, retcode=10006),
    )

    assert _process(engine, 0).execution_result is not None
    assert engine.state.consecutive_execution_failures == 2

    _write_authorization(
        engine.config.demo_authorization_path,
        authorization_id="phase-5-breaker-2",
    )
    blocked = _process(engine, 1)

    assert blocked.execution_result is None
    assert "circuit breaker" in engine.state.last_error
    assert load_demo_execution_authorization(
        engine.config.demo_authorization_path
    ).consumed is False
    execute.assert_called_once()


@pytest.mark.parametrize(
    ("status", "retcode", "expected_failures"),
    [
        (OrderStatus.FILLED, 10009, 0),
        (OrderStatus.PENDING, 10008, 0),
        (OrderStatus.REJECTED, None, 1),
        (OrderStatus.PENDING, 10009, 1),
    ],
)
def test_failure_counter_distinguishes_success_local_rejection_and_ambiguity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    status: OrderStatus,
    retcode: int | None,
    expected_failures: int,
) -> None:
    engine = _enabled_engine(
        monkeypatch,
        tmp_path,
        maximum_submissions=5,
        maximum_failures=2,
    )
    engine.state.consecutive_execution_failures = 1
    _mock_execution(
        engine,
        _execution_result(status, retcode=retcode),
    )

    _process(engine)

    assert engine.state.consecutive_execution_failures == expected_failures


@pytest.mark.parametrize(
    "changed_fact",
    [
        "account",
        "active_order",
        "open_position",
        "partial_fill",
        "execution_intent",
        "session_counter",
        "runtime_readiness",
    ],
)
def test_final_canary_recheck_blocks_changed_state_before_consumption(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    changed_fact: str,
) -> None:
    engine = _enabled_engine(
        monkeypatch,
        tmp_path,
        maximum_submissions=2,
        maximum_failures=2,
    )
    engine.executor.execute_order = Mock()

    if changed_fact == "account":
        monkeypatch.setattr(
            live_engine_module,
            "get_account_info",
            Mock(side_effect=[_account(), _account(login=999999)]),
        )
    elif changed_fact == "active_order":
        monkeypatch.setattr(
            live_engine_module,
            "get_active_order_count",
            Mock(side_effect=[0, 1]),
        )
    elif changed_fact == "open_position":
        monkeypatch.setattr(
            live_engine_module,
            "get_open_positions",
            Mock(side_effect=[[], [SimpleNamespace(ticket=123)]]),
        )
    else:
        calls = 0

        def read_positions(symbol: str):
            nonlocal calls
            calls += 1
            if calls == 2:
                if changed_fact == "partial_fill":
                    engine.partial_fill_store.save(
                        PersistedPartialFill(
                            symbol="XAUUSD",
                            ticket=444,
                            requested_volume=0.01,
                            executed_volume=0.004,
                            remaining_volume=0.006,
                            created_at=datetime.now(UTC),
                        )
                    )
                elif changed_fact == "execution_intent":
                    engine.execution_intent_store.save(
                        build_execution_intent(
                            observation_timestamp=datetime.now(UTC),
                            request=_request(),
                            magic_number=engine.config.execution.magic_number,
                        )
                    )
                elif changed_fact == "session_counter":
                    engine.state.order_submissions_this_session = 1
                elif changed_fact == "runtime_readiness":
                    engine.state.parity_validation_passed = False
            return []

        monkeypatch.setattr(
            live_engine_module,
            "get_open_positions",
            read_positions,
        )

    result = _process(engine)

    assert result.execution_result is None
    assert load_demo_execution_authorization(
        engine.config.demo_authorization_path
    ).consumed is False
    engine.executor.execute_order.assert_not_called()
