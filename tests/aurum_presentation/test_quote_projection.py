from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from core.aurum_presentation.builder import AurumReadModelBuilder
from core.aurum_presentation.enums import AurumOperatorState
from core.aurum_presentation.projections import project_quote
from core.data.quote import MarketQuote
from core.mt5_execution.models import SymbolInfo

from .conftest import T, make_inputs


def _quote(*, timestamp=T + timedelta(minutes=5)) -> MarketQuote:
    return MarketQuote("XAUUSD", timestamp, 100.00, 100.04)


def _symbol(*, point: float = 0.01) -> SymbolInfo:
    return SymbolInfo(
        name="XAUUSD",
        digits=2,
        point=point,
        spread=4,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
        trade_allowed=True,
        tick_size=0.01,
    )


def test_none_quote_is_structurally_unavailable() -> None:
    projected = project_quote(None, symbol_info=None, generated_at_utc=T + timedelta(minutes=5))

    assert projected.available is False
    assert projected.bid is None
    assert projected.ask is None
    assert projected.mid is None
    assert projected.spread_price is None
    assert projected.spread_points is None
    assert projected.observed_at_utc is None
    assert projected.age_ms is None
    assert projected.stale is None


def test_valid_quote_projects_prices_and_age() -> None:
    projected = project_quote(
        _quote(timestamp=T + timedelta(minutes=4, seconds=59)),
        symbol_info=None,
        generated_at_utc=T + timedelta(minutes=5),
    )

    assert projected.available is True
    assert projected.bid == pytest.approx(100.0)
    assert projected.ask == pytest.approx(100.04)
    assert projected.mid == pytest.approx(100.02)
    assert projected.spread_price == pytest.approx(0.04)
    assert projected.spread_points is None
    assert projected.age_ms == pytest.approx(1000.0)
    assert projected.stale is None


def test_spread_points_requires_authoritative_positive_symbol_point() -> None:
    with_point = project_quote(
        _quote(),
        symbol_info=_symbol(point=0.01),
        generated_at_utc=T + timedelta(minutes=5),
    )
    zero_point = project_quote(
        _quote(),
        symbol_info=_symbol(point=0.0),
        generated_at_utc=T + timedelta(minutes=5),
    )

    assert with_point.spread_points == pytest.approx(4.0)
    assert zero_point.spread_points is None


def test_future_quote_fails_closed_as_integrity_blocker() -> None:
    inputs = make_inputs(generated_at=T + timedelta(minutes=5))
    future = _quote(timestamp=T + timedelta(minutes=5, seconds=1))
    model = AurumReadModelBuilder.build(replace(inputs, quote=future))

    assert model.operator_state.state is AurumOperatorState.BLOCKED
    assert model.operator_state.reason_code == "QUOTE_TIMESTAMP_IN_FUTURE"
    assert model.trade_plan.actionable is False
    assert model.trade_plan.entry_price is None
    assert "QUOTE_TIMESTAMP_IN_FUTURE" in model.health.reason_codes
    assert model.quote.available is True
    assert model.quote.age_ms is None


def test_quote_absence_does_not_itself_change_ready_state() -> None:
    model = AurumReadModelBuilder.build(make_inputs())

    assert model.quote.available is False
    assert model.operator_state.state is AurumOperatorState.READY_BUY


def test_quote_fact_does_not_change_decision_risk_or_trade_plan_truth() -> None:
    inputs = make_inputs(generated_at=T + timedelta(minutes=5))
    without = AurumReadModelBuilder.build(inputs)
    with_quote = AurumReadModelBuilder.build(replace(inputs, quote=_quote()))

    assert with_quote.decision == without.decision
    assert with_quote.risk == without.risk
    assert with_quote.trade_plan == without.trade_plan
    assert with_quote.operator_state == without.operator_state


def test_quote_capability_tracks_quote_availability() -> None:
    inputs = make_inputs(generated_at=T + timedelta(minutes=5))
    without = AurumReadModelBuilder.build(inputs)
    with_quote = AurumReadModelBuilder.build(replace(inputs, quote=_quote()))

    without_caps = {item.name: item.available for item in without.meta.capabilities}
    with_caps = {item.name: item.available for item in with_quote.meta.capabilities}
    assert without_caps["quote"] is False
    assert with_caps["quote"] is True
