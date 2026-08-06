from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import MetaTrader5 as mt5

from core.mt5_execution.models import OrderSide
from core.mt5_execution.order_history import get_historical_orders


def test_get_historical_orders_preserves_provenance(monkeypatch) -> None:
    raw = SimpleNamespace(
        ticket=202,
        symbol="XAUUSD",
        type=mt5.ORDER_TYPE_SELL,
        volume_initial=0.01,
        volume_current=0.0,
        price_open=4000.0,
        sl=4010.0,
        tp=3980.0,
        magic=234000,
        comment="xau:fedcba9876543210",
        time_setup=1_700_000_000,
        time_setup_msc=1_700_000_000_000,
        time_done=1_700_000_005,
        time_done_msc=1_700_000_005_000,
        state=4,
    )
    monkeypatch.setattr(
        "core.mt5_execution.order_history.mt5.history_orders_get",
        lambda *args, **kwargs: (raw,),
    )

    result = get_historical_orders(
        date_from=datetime(2023, 1, 1, tzinfo=UTC),
        date_to=datetime(2026, 1, 1, tzinfo=UTC),
        symbol="XAUUSD",
    )

    assert len(result) == 1
    assert result[0].ticket == 202
    assert result[0].side is OrderSide.SELL
    assert result[0].magic_number == 234000
    assert result[0].comment == "xau:fedcba9876543210"
