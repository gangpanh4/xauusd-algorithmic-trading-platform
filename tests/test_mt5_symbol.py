from __future__ import annotations

from types import SimpleNamespace

import pytest

import core.mt5_execution.symbols as symbols


def test_get_symbol_info_maps_broker_specification_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = SimpleNamespace(
        name="XAUUSD",
        digits=2,
        point=0.01,
        spread=20,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
        trade_mode=getattr(
            symbols.mt5,
            "SYMBOL_TRADE_MODE_FULL",
            4,
        ),
        trade_tick_size=0.01,
        trade_stops_level=10,
        filling_mode=1,
        trade_exemode=getattr(
            symbols.mt5,
            "SYMBOL_TRADE_EXECUTION_MARKET",
            2,
        ),
    )
    monkeypatch.setattr(
        symbols.mt5,
        "symbol_info",
        lambda name: raw,
    )

    symbol = symbols.get_symbol_info("XAUUSD")

    assert symbol.name == "XAUUSD"
    assert symbol.digits == 2
    assert symbol.point == pytest.approx(0.01)
    assert symbol.volume_min == pytest.approx(0.01)
    assert symbol.volume_max == pytest.approx(100.0)
    assert symbol.volume_step == pytest.approx(0.01)
    assert symbol.trade_allowed is True
