from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

import core.live_trading.engine as live_engine_module
from core.live_trading.config import LiveTradingConfig
from core.live_trading.engine import LiveTradingEngine
from core.mt5_execution.deal_history import RealizedDeal


def _deal(
    *,
    ticket: int,
    timestamp: datetime,
    net_pnl: float,
) -> RealizedDeal:
    return RealizedDeal(
        ticket=ticket,
        position_id=1000 + ticket,
        timestamp=timestamp,
        symbol="XAUUSD",
        entry=1,
        profit=net_pnl,
        commission=0.0,
        swap=0.0,
        fee=0.0,
    )


def test_startup_baseline_records_tickets_without_applying_pnl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = LiveTradingEngine(LiveTradingConfig())
    as_of = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
    deals = [
        _deal(ticket=11, timestamp=as_of, net_pnl=50.0),
        _deal(ticket=12, timestamp=as_of, net_pnl=-20.0),
    ]

    monkeypatch.setattr(
        live_engine_module,
        "get_realized_deals",
        lambda **kwargs: deals,
    )
    engine.pipeline.register_realized_pnl = Mock()
    engine.pipeline.synchronize_account_balance = Mock()

    processed = engine.reconcile_realized_deals(
        account_balance=10_000.0,
        as_of=as_of,
        initialize_only=True,
    )

    assert processed == 2
    assert engine.state.processed_deal_tickets == {11, 12}
    assert engine.state.last_deal_reconciliation_time == as_of
    engine.pipeline.register_realized_pnl.assert_not_called()
    engine.pipeline.synchronize_account_balance.assert_not_called()


def test_new_deal_is_applied_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = LiveTradingEngine(LiveTradingConfig())
    first_time = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
    second_time = datetime(2026, 7, 22, 12, 5, tzinfo=UTC)
    deal = _deal(ticket=21, timestamp=first_time, net_pnl=75.0)

    monkeypatch.setattr(
        live_engine_module,
        "get_realized_deals",
        lambda **kwargs: [deal],
    )
    engine.pipeline.register_realized_pnl = Mock()
    engine.pipeline.synchronize_account_balance = Mock()

    first_count = engine.reconcile_realized_deals(
        account_balance=10_075.0,
        as_of=first_time,
    )
    second_count = engine.reconcile_realized_deals(
        account_balance=10_075.0,
        as_of=second_time,
    )

    assert first_count == 1
    assert second_count == 0
    engine.pipeline.register_realized_pnl.assert_called_once_with(
        75.0,
        timestamp=first_time,
    )
    assert engine.pipeline.synchronize_account_balance.call_count == 2


def test_reconciliation_uses_configured_symbol_and_overlap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = LiveTradingEngine(LiveTradingConfig(symbol="XAUUSD.a"))
    previous = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
    current = datetime(2026, 7, 22, 12, 10, tzinfo=UTC)
    engine.state.last_deal_reconciliation_time = previous

    captured: dict[str, object] = {}

    def fake_get_realized_deals(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(
        live_engine_module,
        "get_realized_deals",
        fake_get_realized_deals,
    )
    engine.pipeline.synchronize_account_balance = Mock()

    engine.reconcile_realized_deals(
        account_balance=10_000.0,
        as_of=current,
    )

    assert captured["symbol"] == "XAUUSD.a"
    assert captured["date_from"] == datetime(
        2026, 7, 22, 11, 55, tzinfo=UTC
    )
    assert captured["date_to"] == current


def test_partial_close_updates_pnl_without_completed_trade_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = LiveTradingEngine(LiveTradingConfig())
    opened_at = datetime(2026, 7, 22, 8, 0, tzinfo=UTC)
    closed_at = datetime(2026, 7, 22, 9, 0, tzinfo=UTC)

    engine.pipeline.synchronize_account_balance(
        10_000.0,
        timestamp=opened_at,
    )

    partial_close = _deal(
        ticket=31,
        timestamp=closed_at,
        net_pnl=-300.0,
    )
    monkeypatch.setattr(
        live_engine_module,
        "get_realized_deals",
        lambda **kwargs: [partial_close],
    )

    processed = engine.reconcile_realized_deals(
        account_balance=9_700.0,
        as_of=closed_at,
    )

    risk_state = engine.pipeline.risk_manager.state

    assert processed == 1
    assert risk_state.virtual_balance == pytest.approx(9_700.0)
    assert risk_state.daily_loss == pytest.approx(300.0)
    assert risk_state.daily_drawdown == pytest.approx(300.0)
    assert risk_state.daily_drawdown_fraction == pytest.approx(0.03)
    assert risk_state.daily_loss_limit_hit is True
    assert risk_state.completed_trade_count == 0


def test_realized_pnl_failure_does_not_mark_ticket_processed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = LiveTradingEngine(LiveTradingConfig())
    as_of = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
    deal = _deal(ticket=41, timestamp=as_of, net_pnl=-10.0)

    monkeypatch.setattr(
        live_engine_module,
        "get_realized_deals",
        lambda **kwargs: [deal],
    )
    engine.pipeline.register_realized_pnl = Mock(
        side_effect=RuntimeError("risk state unavailable")
    )

    with pytest.raises(RuntimeError, match="risk state unavailable"):
        engine.reconcile_realized_deals(
            account_balance=9_990.0,
            as_of=as_of,
        )

    # A failed risk-state update must remain retryable.
    assert 41 not in engine.state.processed_deal_tickets
    assert engine.state.last_deal_reconciliation_time is None
