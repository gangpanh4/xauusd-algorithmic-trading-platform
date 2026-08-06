from __future__ import annotations

from datetime import UTC, datetime

import pytest

from core.live_trading.config import LiveTradingConfig
from core.live_trading.connected_reconciliation_probe import (
    ConnectedReconciliationProbeError,
    run_connected_demo_read_only_probe,
)
from core.mt5_execution.models import AccountInfo

NOW = datetime(2026, 8, 7, 4, 0, tzinfo=UTC)


def _demo_account() -> AccountInfo:
    return AccountInfo(
        login=123456,
        server="Demo-Server",
        balance=10000.0,
        equity=10000.0,
        margin=0.0,
        free_margin=10000.0,
        leverage=100,
        currency="USD",
        trade_mode=0,
    )


def test_probe_without_persisted_intent_is_read_only(tmp_path) -> None:
    config = LiveTradingConfig(
        execution_intent_state_path=tmp_path / "missing.json",
        live_execution_enabled=False,
    )
    result = run_connected_demo_read_only_probe(
        config=config,
        as_of=NOW,
        account_reader=_demo_account,
        active_order_reader=lambda symbol: (),
        historical_order_reader=lambda **kwargs: (),
        deal_reader=lambda **kwargs: (),
        position_reader=lambda symbol: (),
    )

    assert result.validation_passed is True
    assert result.reconciliation_disposition == "NO_PERSISTED_INTENT"
    assert result.order_submission_attempted is False
    assert result.trade_executed is False
    assert result.live_execution_enabled is False
    assert result.shadow_only is True


def test_probe_rejects_live_execution_configuration(tmp_path) -> None:
    config = LiveTradingConfig(
        execution_intent_state_path=tmp_path / "missing.json",
        live_execution_enabled=True,
    )
    with pytest.raises(
        ConnectedReconciliationProbeError,
        match="live_execution_enabled=False",
    ):
        run_connected_demo_read_only_probe(
            config=config,
            as_of=NOW,
            account_reader=_demo_account,
            active_order_reader=lambda symbol: (),
            historical_order_reader=lambda **kwargs: (),
            deal_reader=lambda **kwargs: (),
            position_reader=lambda symbol: (),
        )


def test_probe_rejects_non_demo_account(tmp_path) -> None:
    config = LiveTradingConfig(
        execution_intent_state_path=tmp_path / "missing.json",
        live_execution_enabled=False,
    )
    real_account = AccountInfo(
        **{
            **_demo_account().__dict__,
            "trade_mode": 2,
        }
    )
    with pytest.raises(
        ConnectedReconciliationProbeError,
        match="not confirmed as an MT5 demo account",
    ):
        run_connected_demo_read_only_probe(
            config=config,
            as_of=NOW,
            account_reader=lambda: real_account,
            active_order_reader=lambda symbol: (),
            historical_order_reader=lambda **kwargs: (),
            deal_reader=lambda **kwargs: (),
            position_reader=lambda symbol: (),
        )
