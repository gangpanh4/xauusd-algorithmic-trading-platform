from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from core.mt5_execution import symbol_specification


def _info(*, contract_size: float | None = 100.0) -> SimpleNamespace:
    values = {
        "visible": True,
        "trade_tick_size": 0.01,
        "trade_tick_value_loss": 1.25,
        "trade_tick_value": 1.0,
        "volume_step": 0.01,
        "volume_min": 0.01,
        "volume_max": 50.0,
        "point": 0.001,
        "trade_stops_level": 25,
    }
    if contract_size is not None:
        values["trade_contract_size"] = contract_size
    return SimpleNamespace(**values)


def test_live_snapshot_captures_point_contract_and_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = datetime.now(UTC)
    monkeypatch.setattr(
        symbol_specification.mt5,
        "symbol_info",
        lambda symbol: _info(),
    )

    specification = symbol_specification.get_live_symbol_specification(
        "XAUUSD"
    )
    after = datetime.now(UTC)

    assert specification.point_size == pytest.approx(0.001)
    assert specification.contract_size == pytest.approx(100.0)
    assert specification.minimum_stop_distance == pytest.approx(0.025)
    assert specification.captured_at is not None
    assert before <= specification.captured_at <= after

    shared = specification.to_instrument_specification(
        specification_id="CURRENT_TEST_SNAPSHOT"
    )
    assert shared.contract_size == pytest.approx(100.0)
    assert shared.historical_specification_verified is False
    assert shared.provenance.value == "CURRENT_SNAPSHOT_ASSUMPTION"


def test_missing_contract_size_remains_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        symbol_specification.mt5,
        "symbol_info",
        lambda symbol: _info(contract_size=None),
    )

    specification = symbol_specification.get_live_symbol_specification(
        "XAUUSD"
    )

    assert specification.contract_size is None
