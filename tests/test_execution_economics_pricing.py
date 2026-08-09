from __future__ import annotations

import pytest

from core.execution_economics.pricing import (
    normalize_price_to_tick,
    recenter_exit_levels,
)
from core.mt5_execution import orders
from core.mt5_execution.models import OrderRequest, OrderSide, SymbolInfo


def _symbol() -> SymbolInfo:
    return SymbolInfo(
        name="XAUUSD",
        digits=2,
        point=0.01,
        spread=20,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
        trade_allowed=True,
        tick_size=0.05,
        minimum_stop_distance=0.05,
        filling_mode_flags=1,
        trade_execution_mode=2,
    )


@pytest.mark.parametrize(
    ("is_buy", "planned_stop", "planned_target", "expected_stop", "expected_target"),
    [
        (True, 3298.0, 3304.0, 3298.05, 3304.05),
        (False, 3302.0, 3296.0, 3301.95, 3295.95),
    ],
)
def test_recenter_without_normalization_preserves_approved_distances(
    is_buy: bool,
    planned_stop: float,
    planned_target: float,
    expected_stop: float,
    expected_target: float,
) -> None:
    geometry = recenter_exit_levels(
        is_buy=is_buy,
        planned_entry_price=3300.0,
        planned_stop_loss=planned_stop,
        planned_take_profit=planned_target,
        reference_entry_price=3299.95 if not is_buy else 3300.05,
        normalize_to_tick=False,
    )

    assert geometry.stop_loss == pytest.approx(expected_stop)
    assert geometry.take_profit == pytest.approx(expected_target)
    assert geometry.normalized_to_tick is False


def test_normalization_matches_nearest_tick_contract() -> None:
    assert normalize_price_to_tick(
        3300.061,
        tick_size=0.05,
        digits=2,
    ) == pytest.approx(3300.05)


@pytest.mark.parametrize(
    ("side", "market_price", "stop_loss", "take_profit"),
    [
        (OrderSide.BUY, 3300.061, 3298.0, 3304.0),
        (OrderSide.SELL, 3299.939, 3302.0, 3296.0),
    ],
)
def test_pure_geometry_matches_offline_live_request_construction(
    monkeypatch: pytest.MonkeyPatch,
    side: OrderSide,
    market_price: float,
    stop_loss: float,
    take_profit: float,
) -> None:
    symbol = _symbol()
    request = OrderRequest(
        symbol="XAUUSD",
        side=side,
        volume=0.01,
        entry_price=3300.0,
        stop_loss=stop_loss,
        take_profit=take_profit,
        comment="Offline contract comparison",
    )
    monkeypatch.setattr(
        orders,
        "get_market_price",
        lambda symbol_name, order_side: market_price,
    )
    monkeypatch.setattr(orders.mt5, "order_check", pytest.fail)
    monkeypatch.setattr(orders.mt5, "order_send", pytest.fail)

    payload = orders.build_mt5_request(
        request,
        magic_number=123,
        deviation=20,
        symbol=symbol,
    )
    geometry = recenter_exit_levels(
        is_buy=side is OrderSide.BUY,
        planned_entry_price=request.entry_price,
        planned_stop_loss=request.stop_loss,
        planned_take_profit=request.take_profit,
        reference_entry_price=market_price,
        normalize_to_tick=True,
        tick_size=symbol.tick_size,
        digits=symbol.digits,
    )

    assert payload["price"] == pytest.approx(geometry.reference_entry_price)
    assert payload["sl"] == pytest.approx(geometry.stop_loss)
    assert payload["tp"] == pytest.approx(geometry.take_profit)
