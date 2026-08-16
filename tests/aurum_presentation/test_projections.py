import pytest

from core.aurum_presentation import AurumReadModelBuilder

from .conftest import make_inputs


def test_mtf_projects_all_six_exact_frames() -> None:
    model = AurumReadModelBuilder.build(make_inputs())
    frames = model.multi_timeframe.frames
    assert tuple(frame.timeframe for frame in (frames.W1, frames.D1, frames.H4, frames.H1, frames.M15, frames.M5)) == (
        "W1", "D1", "H4", "H1", "M15", "M5"
    )
    assert frames.M5.metadata == ()


def test_structure_projects_typed_facts_and_liquidity_side() -> None:
    model = AurumReadModelBuilder.build(make_inputs())
    frame = model.structure.frames.M5
    assert frame.available is True
    assert frame.current_trend == "BULLISH"
    assert frame.last_bos.break_type == "BOS"
    assert frame.protected_high is not None
    assert frame.latest_liquidity_sweep.liquidity_level.side == "BUY_SIDE"
    assert frame.tracked_liquidity_levels[0].is_buy_side is True


def test_price_action_projects_confirmed_fvg_and_order_block_without_invented_status() -> None:
    model = AurumReadModelBuilder.build(make_inputs())
    frame = model.price_action.frames.M5
    assert frame.fair_value_gap.kind == "CONFIRMED"
    assert frame.fair_value_gap.id == 7
    assert frame.order_block.block_type == "BULLISH"
    assert not hasattr(frame.order_block, "status")
    assert not hasattr(frame.order_block, "analysis")


def test_price_action_supports_fvg_candidate() -> None:
    model = AurumReadModelBuilder.build(make_inputs(candidate_fvg=True))
    fvg = model.price_action.frames.M5.fair_value_gap
    assert fvg.kind == "CANDIDATE"
    assert fvg.id is None
    assert fvg.status == "new"


def test_null_structure_and_price_action_are_no_current_fact_not_source_failure() -> None:
    inputs = make_inputs()
    inputs.multi_timeframe_result.m5.market_structure = None
    inputs.multi_timeframe_result.m5.price_action = None
    model = AurumReadModelBuilder.build(inputs)
    assert model.structure.frames.M5.available is False
    assert model.price_action.frames.M5.available is False


def test_wrong_weak_boundary_type_fails_explicitly() -> None:
    inputs = make_inputs()
    inputs.multi_timeframe_result.m5.market_structure = "not structure"
    with pytest.raises(TypeError, match="MarketStructureResult"):
        AurumReadModelBuilder.build(inputs)


def test_feature_probability_confluence_decision_signal_quality_are_direct_projections() -> None:
    model = AurumReadModelBuilder.build(make_inputs())
    assert model.features.count == 2
    assert model.features.families == ("momentum", "structure")
    assert model.probability.accepted is True
    assert model.probability.evidence[0].family == "structure"
    assert model.confluence.approved is True
    assert model.confluence.factors[0].reason == "aligned"
    assert model.decision.type == "BUY"
    assert model.signal.direction == "BUY"
    assert model.trade_quality.approved is True


def test_symbol_spec_uses_only_frozen_v1_surface() -> None:
    model = AurumReadModelBuilder.build(make_inputs())
    spec = model.market.symbol_spec
    assert spec.available is True
    assert spec.name == "XAUUSD"
    assert not hasattr(spec, "tick_value_per_lot")
    assert not hasattr(spec, "contract_size")


def test_pipeline_audit_risk_runtime_and_execution_are_read_only_factual_projections() -> None:
    model = AurumReadModelBuilder.build(make_inputs())
    assert model.pipeline_audit.available is True
    assert model.pipeline_audit.accepted is True
    assert model.pipeline_audit.regime_confirmed is True
    assert model.risk.decision == "APPROVE"
    assert model.risk.runtime.available is True
    assert model.risk.runtime.virtual_balance == 10000.0
    assert model.execution.read_only is True
    assert model.execution.can_submit_order is False
    assert model.execution.state.clock_normalization_validated is True


def test_unavailable_symbol_info_remains_null_without_fallback() -> None:
    from dataclasses import replace

    inputs = make_inputs()
    model = AurumReadModelBuilder.build(
        replace(inputs, symbol_info=None, symbol_info_observed_at_utc=None)
    )
    assert model.market.symbol_spec.available is False
    assert model.market.symbol_spec.point is None
    assert model.market.symbol_spec.spread is None
