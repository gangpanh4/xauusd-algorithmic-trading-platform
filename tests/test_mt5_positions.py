from __future__ import annotations

from types import SimpleNamespace

import pytest

import core.mt5_execution.positions as positions
from core.mt5_execution.models import OrderSide


def test_get_open_positions_maps_multiple_positions_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_positions = (
        SimpleNamespace(
            ticket=1,
            symbol="XAUUSD",
            type=positions.mt5.POSITION_TYPE_BUY,
            volume=0.01,
            price_open=3300.0,
            sl=3295.0,
            tp=3310.0,
            profit=10.0,
        ),
        SimpleNamespace(
            ticket=2,
            symbol="XAUUSD",
            type=positions.mt5.POSITION_TYPE_SELL,
            volume=0.02,
            price_open=3310.0,
            sl=3315.0,
            tp=3300.0,
            profit=-5.0,
        ),
    )
    captured: dict[str, object] = {}

    def fake_positions_get(**kwargs):
        captured.update(kwargs)
        return raw_positions

    monkeypatch.setattr(
        positions.mt5,
        "positions_get",
        fake_positions_get,
    )

    result = positions.get_open_positions("XAUUSD")

    assert captured == {"symbol": "XAUUSD"}
    assert len(result) == 2
    assert result[0].side is OrderSide.BUY
    assert result[1].side is OrderSide.SELL
    assert result[1].volume == pytest.approx(0.02)


def test_get_open_positions_empty_query_returns_empty_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        positions.mt5,
        "positions_get",
        lambda **kwargs: (),
    )

    assert positions.get_open_positions("XAUUSD") == []
