from __future__ import annotations

from types import SimpleNamespace

import pytest

import core.mt5_execution.positions as positions
from core.mt5_execution.models import OrderSide


def test_get_open_positions_raises_when_mt5_query_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        positions.mt5,
        "positions_get",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        positions.mt5,
        "last_error",
        lambda: (-10004, "No IPC connection"),
    )

    with pytest.raises(
        RuntimeError,
        match="Unable to retrieve open MT5 positions",
    ):
        positions.get_open_positions("XAUUSD")


def test_get_open_positions_returns_empty_only_for_successful_empty_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        positions.mt5,
        "positions_get",
        lambda **kwargs: (),
    )

    assert positions.get_open_positions("XAUUSD") == []


def test_get_position_raises_when_mt5_query_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        positions.mt5,
        "positions_get",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        positions.mt5,
        "last_error",
        lambda: (-10004, "No IPC connection"),
    )

    with pytest.raises(
        RuntimeError,
        match="Unable to retrieve MT5 position 123456",
    ):
        positions.get_position(123456)


def test_get_position_returns_none_only_when_ticket_is_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        positions.mt5,
        "positions_get",
        lambda **kwargs: (),
    )

    assert positions.get_position(123456) is None


def test_position_conversion_preserves_broker_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = SimpleNamespace(
        ticket=123456,
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

    result = positions.get_position(123456)

    assert result is not None
    assert result.ticket == 123456
    assert result.symbol == "XAUUSD"
    assert result.side is OrderSide.BUY
    assert result.volume == pytest.approx(0.01)
    assert result.open_price == pytest.approx(3300.0)
    assert result.stop_loss == pytest.approx(3295.0)
    assert result.take_profit == pytest.approx(3310.0)
    assert result.profit == pytest.approx(25.0)
