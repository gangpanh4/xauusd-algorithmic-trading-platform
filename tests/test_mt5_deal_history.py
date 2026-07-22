from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import MetaTrader5 as mt5
import pytest

from core.mt5_execution import deal_history


def _raw_deal(
    *,
    ticket: int,
    entry: int,
    symbol: str = "XAUUSD",
    timestamp: datetime,
    position_id: int = 100,
    profit: float = 0.0,
    commission: float = 0.0,
    swap: float = 0.0,
    fee: float = 0.0,
) -> SimpleNamespace:
    return SimpleNamespace(
        ticket=ticket,
        position_id=position_id,
        time=int(timestamp.timestamp()),
        time_msc=int(timestamp.timestamp() * 1000),
        symbol=symbol,
        entry=entry,
        profit=profit,
        commission=commission,
        swap=swap,
        fee=fee,
    )


def test_realized_deal_net_pnl_includes_all_broker_costs() -> None:
    deal = deal_history.RealizedDeal(
        ticket=1,
        position_id=10,
        timestamp=datetime(2026, 7, 22, 8, 0, tzinfo=UTC),
        symbol="XAUUSD",
        entry=mt5.DEAL_ENTRY_OUT,
        profit=125.0,
        commission=-2.5,
        swap=-1.25,
        fee=-0.75,
    )

    assert deal.net_pnl == pytest.approx(120.5)


def test_get_realized_deals_filters_and_orders(monkeypatch: pytest.MonkeyPatch) -> None:
    start = datetime(2026, 7, 22, 8, 0, tzinfo=UTC)
    end = datetime(2026, 7, 22, 10, 0, tzinfo=UTC)

    raw = [
        _raw_deal(
            ticket=8,
            entry=mt5.DEAL_ENTRY_OUT,
            timestamp=datetime(2026, 7, 22, 9, 0, tzinfo=UTC),
            profit=40.0,
            commission=-1.0,
        ),
        _raw_deal(
            ticket=2,
            entry=mt5.DEAL_ENTRY_IN,
            timestamp=datetime(2026, 7, 22, 8, 5, tzinfo=UTC),
        ),
        _raw_deal(
            ticket=5,
            entry=mt5.DEAL_ENTRY_OUT,
            symbol="EURUSD",
            timestamp=datetime(2026, 7, 22, 8, 30, tzinfo=UTC),
        ),
        _raw_deal(
            ticket=4,
            entry=mt5.DEAL_ENTRY_INOUT,
            timestamp=datetime(2026, 7, 22, 8, 45, tzinfo=UTC),
            profit=-20.0,
            swap=-0.5,
        ),
        _raw_deal(
            ticket=3,
            entry=mt5.DEAL_ENTRY_OUT_BY,
            timestamp=datetime(2026, 7, 22, 8, 45, tzinfo=UTC),
            profit=10.0,
            fee=-0.25,
        ),
    ]

    history_mock = lambda *args, **kwargs: raw
    monkeypatch.setattr(deal_history.mt5, "history_deals_get", history_mock)

    deals = deal_history.get_realized_deals(
        date_from=start,
        date_to=end,
        symbol="XAUUSD",
    )

    assert [deal.ticket for deal in deals] == [3, 4, 8]
    assert all(deal.symbol == "XAUUSD" for deal in deals)
    assert deals[0].net_pnl == pytest.approx(9.75)
    assert deals[1].net_pnl == pytest.approx(-20.5)
    assert deals[2].net_pnl == pytest.approx(39.0)


def test_get_realized_deals_passes_symbol_group_to_mt5(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_history(date_from, date_to, *, group):
        captured["date_from"] = date_from
        captured["date_to"] = date_to
        captured["group"] = group
        return []

    monkeypatch.setattr(deal_history.mt5, "history_deals_get", fake_history)

    start = datetime(2026, 7, 22, 8, 0, tzinfo=UTC)
    end = datetime(2026, 7, 22, 9, 0, tzinfo=UTC)

    assert deal_history.get_realized_deals(
        date_from=start,
        date_to=end,
        symbol="XAUUSD",
    ) == []

    assert captured == {
        "date_from": start,
        "date_to": end,
        "group": "XAUUSD",
    }


def test_get_realized_deals_raises_when_mt5_history_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        deal_history.mt5,
        "history_deals_get",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        deal_history.mt5,
        "last_error",
        lambda: (500, "history unavailable"),
    )

    with pytest.raises(RuntimeError, match="history unavailable"):
        deal_history.get_realized_deals(
            date_from=datetime(2026, 7, 22, 8, 0, tzinfo=UTC),
            date_to=datetime(2026, 7, 22, 9, 0, tzinfo=UTC),
            symbol="XAUUSD",
        )


def test_get_realized_deals_rejects_invalid_boundaries() -> None:
    start = datetime(2026, 7, 22, 9, 0, tzinfo=UTC)
    end = datetime(2026, 7, 22, 8, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="date_to"):
        deal_history.get_realized_deals(
            date_from=start,
            date_to=end,
            symbol="XAUUSD",
        )

    with pytest.raises(ValueError, match="timezone-aware"):
        deal_history.get_realized_deals(
            date_from=datetime(2026, 7, 22, 8, 0),
            date_to=start,
            symbol="XAUUSD",
        )
