from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import core.live_trading.engine as live_engine_module
from core.live_trading.config import LiveTradingConfig
from core.live_trading.engine import LiveTradingEngine
from core.live_trading.partial_fill_store import (
    PartialFillStateError,
    PartialFillStateStore,
    PersistedPartialFill,
)


def _record(*, symbol: str = "XAUUSD") -> PersistedPartialFill:
    return PersistedPartialFill(
        symbol=symbol,
        ticket=123456,
        requested_volume=0.01,
        executed_volume=0.004,
        remaining_volume=0.006,
        created_at=datetime(2026, 7, 24, 8, 0, tzinfo=UTC),
    )


def _config(path: Path) -> LiveTradingConfig:
    return LiveTradingConfig(
        live_execution_enabled=True,
        partial_fill_state_path=path,
    )


def test_missing_state_file_is_safe(tmp_path: Path) -> None:
    store = PartialFillStateStore(tmp_path / "missing.json")

    assert store.load() is None


def test_store_round_trip_and_atomic_cleanup(tmp_path: Path) -> None:
    path = tmp_path / "partial.json"
    store = PartialFillStateStore(path)

    store.save(_record())

    assert store.load() == _record()
    assert list(tmp_path.glob("*.tmp")) == []
    assert list(tmp_path.glob(".partial.json.*.tmp")) == []


@pytest.mark.parametrize(
    "payload",
    [
        "{not-json",
        json.dumps({"version": 1}),
        json.dumps(
            {
                "version": 99,
                "symbol": "XAUUSD",
                "ticket": 123456,
                "requested_volume": 0.01,
                "executed_volume": 0.004,
                "remaining_volume": 0.006,
                "created_at": "2026-07-24T08:00:00+00:00",
            }
        ),
        json.dumps(
            {
                "version": 1,
                "symbol": "XAUUSD",
                "ticket": 123456,
                "requested_volume": 0.01,
                "executed_volume": 0.004,
                "remaining_volume": 0.005,
                "created_at": "2026-07-24T08:00:00+00:00",
            }
        ),
    ],
)
def test_malformed_state_never_falls_back(
    tmp_path: Path,
    payload: str,
) -> None:
    path = tmp_path / "partial.json"
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(PartialFillStateError):
        PartialFillStateStore(path).load()


def test_start_restores_before_attach_and_blocks_submission(
    tmp_path: Path,
) -> None:
    path = tmp_path / "partial.json"
    PartialFillStateStore(path).save(_record())
    engine = LiveTradingEngine(_config(path))
    engine.executor.attach = Mock(return_value=True)

    engine.start()

    assert engine.state.running is True
    assert engine.state.unresolved_partial_ticket == 123456
    assert engine.state.unresolved_requested_volume == pytest.approx(0.01)
    assert engine.state.unresolved_executed_volume == pytest.approx(0.004)
    assert engine.state.unresolved_remaining_volume == pytest.approx(0.006)
    assert engine.state.active_order_count == 1
    engine.executor.attach.assert_called_once_with()


def test_corrupt_state_prevents_attach(tmp_path: Path) -> None:
    path = tmp_path / "partial.json"
    path.write_text("{bad-json", encoding="utf-8")
    engine = LiveTradingEngine(_config(path))
    engine.executor.attach = Mock(return_value=True)

    with pytest.raises(PartialFillStateError):
        engine.start()

    assert engine.state.running is False
    assert engine.state.active_order_count == 1
    engine.executor.attach.assert_not_called()


def test_wrong_symbol_prevents_attach(tmp_path: Path) -> None:
    path = tmp_path / "partial.json"
    PartialFillStateStore(path).save(_record(symbol="EURUSD"))
    engine = LiveTradingEngine(_config(path))
    engine.executor.attach = Mock(return_value=True)

    with pytest.raises(PartialFillStateError, match="symbol"):
        engine.start()

    assert engine.state.active_order_count == 1
    engine.executor.attach.assert_not_called()


def test_restored_state_reconciles_later_fill_and_clears_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "partial.json"
    PartialFillStateStore(path).save(_record())
    engine = LiveTradingEngine(_config(path))
    engine.executor.attach = Mock(return_value=True)
    engine.start()

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
    assert not path.exists()


def test_restored_inactive_remainder_is_terminal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "partial.json"
    PartialFillStateStore(path).save(_record())
    engine = LiveTradingEngine(_config(path))
    engine.executor.attach = Mock(return_value=True)
    engine.start()

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
    assert (
        engine.state.last_partial_fill_resolution
        == "REMAINDER_CANCELLED_OR_REJECTED"
    )
    assert engine.state.executed_trades == 0
    assert not path.exists()


def test_clear_failure_preserves_unresolved_guard(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "partial.json"
    PartialFillStateStore(path).save(_record())
    engine = LiveTradingEngine(_config(path))
    engine.executor.attach = Mock(return_value=True)
    engine.start()

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
    engine.partial_fill_store.clear = Mock(
        side_effect=PartialFillStateError("clear failed")
    )

    with pytest.raises(PartialFillStateError, match="clear failed"):
        engine.synchronize_active_orders()

    assert engine.state.active_order_count == 1
    assert engine.state.unresolved_partial_ticket == 123456
    assert engine.state.executed_trades == 0
    assert path.exists()
