from __future__ import annotations

from unittest.mock import Mock

import pytest

import core.live_trading.engine as live_engine_module
from core.live_trading.config import LiveTradingConfig
from core.live_trading.engine import LiveTradingEngine


def test_synchronize_open_positions_uses_configured_symbol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = LiveTradingEngine(
        LiveTradingConfig(symbol="XAUUSD.a")
    )
    captured: dict[str, object] = {}

    def fake_get_open_positions(symbol: str):
        captured["symbol"] = symbol
        return [object(), object()]

    monkeypatch.setattr(
        live_engine_module,
        "get_open_positions",
        fake_get_open_positions,
    )
    engine.pipeline.set_open_position_count = Mock()

    count = engine.synchronize_open_positions()

    assert count == 2
    assert captured["symbol"] == "XAUUSD.a"
    engine.pipeline.set_open_position_count.assert_called_once_with(2)


def test_synchronize_open_positions_sets_zero_only_after_successful_empty_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = LiveTradingEngine(LiveTradingConfig())
    monkeypatch.setattr(
        live_engine_module,
        "get_open_positions",
        lambda symbol: [],
    )
    engine.pipeline.set_open_position_count = Mock()

    count = engine.synchronize_open_positions()

    assert count == 0
    engine.pipeline.set_open_position_count.assert_called_once_with(0)


def test_position_query_failure_does_not_overwrite_risk_exposure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = LiveTradingEngine(LiveTradingConfig())
    engine.pipeline.set_open_position_count = Mock()

    def fail_query(symbol: str):
        raise RuntimeError("Unable to retrieve open MT5 positions")

    monkeypatch.setattr(
        live_engine_module,
        "get_open_positions",
        fail_query,
    )

    with pytest.raises(
        RuntimeError,
        match="Unable to retrieve open MT5 positions",
    ):
        engine.synchronize_open_positions()

    engine.pipeline.set_open_position_count.assert_not_called()


def test_repeated_position_synchronization_uses_latest_broker_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = LiveTradingEngine(LiveTradingConfig())
    responses = iter(
        [
            [object()],
            [object()],
            [],
        ]
    )
    monkeypatch.setattr(
        live_engine_module,
        "get_open_positions",
        lambda symbol: next(responses),
    )
    engine.pipeline.set_open_position_count = Mock()

    assert engine.synchronize_open_positions() == 1
    assert engine.synchronize_open_positions() == 1
    assert engine.synchronize_open_positions() == 0

    assert engine.pipeline.set_open_position_count.call_args_list == [
        ((1,),),
        ((1,),),
        ((0,),),
    ]
