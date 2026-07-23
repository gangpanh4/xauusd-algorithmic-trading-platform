from __future__ import annotations

from types import SimpleNamespace

import pytest

import core.mt5_execution.positions as positions
from core.mt5_execution.models import OrderSide


def test_get_position_returns_broker_position_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = SimpleNamespace(
        ticket=123456789,
        symbol="XAUUSD",
        type=positions.mt5.POSITION_TYPE_BUY,
        volume=0.01,
        price_open=3300.0,
        sl=3295.0,
        tp=3310.0,
        profit=25.0,
    )
    monkeypatch.setattr(
        positions.mt5,
        "positions_get",
        lambda **kwargs: (raw,),
    )

    result = positions.get_position(123456789)

    assert result is not None
    assert result.ticket == 123456789
    assert result.symbol == "XAUUSD"
    assert result.side is OrderSide.BUY
    assert result.volume == pytest.approx(0.01)


def test_get_position_returns_none_when_ticket_is_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        positions.mt5,
        "positions_get",
        lambda **kwargs: (),
    )

    assert positions.get_position(123456789) is None
