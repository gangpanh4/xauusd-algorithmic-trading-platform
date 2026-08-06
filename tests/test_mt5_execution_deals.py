from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import MetaTrader5 as mt5

from core.mt5_execution.deal_history import get_execution_deals
from core.mt5_execution.models import OrderSide


def test_get_execution_deals_preserves_provenance(monkeypatch) -> None:
    raw = SimpleNamespace(
        ticket=303,
        order=202,
        position_id=404,
        time=1_700_000_005,
        time_msc=1_700_000_005_000,
        symbol="XAUUSD",
        type=mt5.DEAL_TYPE_BUY,
        volume=0.01,
        price=4001.0,
        entry=getattr(mt5, "DEAL_ENTRY_IN", 0),
        magic=234000,
        comment="xau:0123456789abcdef",
    )
    monkeypatch.setattr(
        "core.mt5_execution.deal_history.mt5.history_deals_get",
        lambda *args, **kwargs: (raw,),
    )

    result = get_execution_deals(
        date_from=datetime(2023, 1, 1, tzinfo=UTC),
        date_to=datetime(2026, 1, 1, tzinfo=UTC),
        symbol="XAUUSD",
    )

    assert len(result) == 1
    assert result[0].ticket == 303
    assert result[0].order_ticket == 202
    assert result[0].side is OrderSide.BUY
    assert result[0].magic_number == 234000
    assert result[0].comment == "xau:0123456789abcdef"
