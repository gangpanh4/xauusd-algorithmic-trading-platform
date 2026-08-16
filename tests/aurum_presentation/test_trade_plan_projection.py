import math

import pytest

from core.aurum_presentation import AurumOperatorState, AurumReadModelBuilder
from core.risk_manager.models import RiskDecision

from .conftest import make_inputs


def test_valid_buy_and_sell_geometry_are_actionable() -> None:
    buy = AurumReadModelBuilder.build(make_inputs(direction="BUY"))
    sell = AurumReadModelBuilder.build(make_inputs(direction="SELL"))
    assert buy.trade_plan.actionable is True
    assert buy.trade_plan.stop_loss_price < buy.trade_plan.entry_price < buy.trade_plan.take_profit_price
    assert sell.trade_plan.actionable is True
    assert sell.trade_plan.take_profit_price < sell.trade_plan.entry_price < sell.trade_plan.stop_loss_price


@pytest.mark.parametrize("decision", [RiskDecision.REJECT, RiskDecision.SKIP])
def test_reject_and_skip_suppress_actionable_geometry(decision: RiskDecision) -> None:
    model = AurumReadModelBuilder.build(make_inputs(risk_decision=decision))
    assert model.trade_plan.actionable is False
    assert model.trade_plan.position_size is None
    assert model.trade_plan.entry_price is None
    assert model.trade_plan.stop_loss_price is None
    assert model.trade_plan.take_profit_price is None


@pytest.mark.parametrize("geometry", ["ZERO_SIZE", "WRONG_SIDE", "NON_FINITE"])
def test_invalid_geometry_is_blocked_and_suppressed(geometry: str) -> None:
    inputs = make_inputs(geometry=geometry)
    original = inputs.pipeline_result.trade_plan
    original_values = (
        original.position_size,
        original.entry_price,
        original.stop_loss,
        original.take_profit,
    )
    model = AurumReadModelBuilder.build(inputs)
    assert model.operator_state.state is AurumOperatorState.BLOCKED
    assert model.operator_state.reason_code == "INVALID_TRADE_PLAN_GEOMETRY"
    assert model.trade_plan.actionable is False
    assert model.trade_plan.position_size is None
    if geometry == "NON_FINITE":
        assert math.isnan(original.stop_loss)
    assert (
        original.position_size,
        original.entry_price,
        original.stop_loss,
        original.take_profit,
    ) == original_values


def test_direction_mismatch_is_blocked_and_suppressed() -> None:
    model = AurumReadModelBuilder.build(
        make_inputs(direction="BUY", plan_direction="SELL")
    )
    assert model.operator_state.state is AurumOperatorState.BLOCKED
    assert model.operator_state.reason_code == "DIRECTION_MISMATCH"
    assert model.trade_plan.actionable is False
    assert model.trade_plan.entry_price is None
