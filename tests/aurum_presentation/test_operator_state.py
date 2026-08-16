import pytest

from core.aurum_presentation import AurumOperatorState, AurumReadModelBuilder
from core.risk_manager.models import RiskDecision

from .conftest import make_inputs


@pytest.mark.parametrize(
    ("kwargs", "expected_code"),
    [
        ({"probability_accepted": False}, "NOT_APPROVED"),
        ({"quality_approved": False}, "NOT_APPROVED"),
        ({"confluence_approved": False}, "NOT_APPROVED"),
        ({"decision_approved": False}, "NOT_APPROVED"),
        ({"signal_hold": True, "risk_decision": RiskDecision.SKIP}, "NOT_APPROVED"),
    ],
)
def test_normal_upstream_rejections_are_hold(
    kwargs: dict[str, object],
    expected_code: str,
) -> None:
    model = AurumReadModelBuilder.build(make_inputs(**kwargs))
    assert model.operator_state.state is AurumOperatorState.HOLD
    assert model.operator_state.reason_code == expected_code
    assert model.operator_state.blocked is False


def test_ready_buy() -> None:
    model = AurumReadModelBuilder.build(make_inputs(direction="BUY"))
    assert model.pipeline_consistency.pipeline_result_approved is True
    assert model.pipeline_consistency.pipeline_audit_accepted is True
    assert model.pipeline_consistency.approval_consistent is True
    assert model.operator_state.state is AurumOperatorState.READY_BUY
    assert model.operator_state.ready is True
    assert model.operator_state.direction == "BUY"


def test_ready_sell() -> None:
    model = AurumReadModelBuilder.build(make_inputs(direction="SELL"))
    assert model.operator_state.state is AurumOperatorState.READY_SELL
    assert model.operator_state.ready is True
    assert model.operator_state.direction == "SELL"


def test_risk_reject_blocks_otherwise_directional_path() -> None:
    model = AurumReadModelBuilder.build(
        make_inputs(risk_decision=RiskDecision.REJECT)
    )
    assert model.operator_state.state is AurumOperatorState.BLOCKED
    assert model.operator_state.reason_code == "RISK_REJECTED"


def test_risk_skip_with_no_upstream_opportunity_is_hold() -> None:
    model = AurumReadModelBuilder.build(
        make_inputs(signal_hold=True, risk_decision=RiskDecision.SKIP)
    )
    assert model.operator_state.state is AurumOperatorState.HOLD


def test_directional_risk_skip_is_blocked() -> None:
    model = AurumReadModelBuilder.build(
        make_inputs(risk_decision=RiskDecision.SKIP)
    )
    assert model.operator_state.state is AurumOperatorState.BLOCKED
    assert model.operator_state.reason_code == "RISK_SKIPPED"


def test_emergency_stop_blocks_directional_readiness() -> None:
    model = AurumReadModelBuilder.build(make_inputs(emergency_stop=True))
    assert model.operator_state.state is AurumOperatorState.BLOCKED
    assert model.operator_state.reason_code == "RISK_EMERGENCY_STOP"


def test_daily_loss_limit_blocks_directional_readiness() -> None:
    model = AurumReadModelBuilder.build(make_inputs(daily_loss_limit_hit=True))
    assert model.operator_state.state is AurumOperatorState.BLOCKED
    assert model.operator_state.reason_code == "DAILY_LOSS_LIMIT_HIT"


def test_pipeline_inconsistency_blocks_and_suppresses_geometry() -> None:
    model = AurumReadModelBuilder.build(make_inputs(audit_accepted=False))
    assert model.pipeline_consistency.pipeline_result_approved is True
    assert model.pipeline_consistency.pipeline_audit_accepted is False
    assert model.pipeline_consistency.approval_consistent is False
    assert model.operator_state.reason_code == "PIPELINE_APPROVAL_INCONSISTENCY"
    assert model.trade_plan.actionable is False
    assert model.trade_plan.position_size is None


def test_false_false_pipeline_consistency_is_consistent() -> None:
    model = AurumReadModelBuilder.build(make_inputs(probability_accepted=False))
    assert model.pipeline_consistency.pipeline_result_approved is False
    assert model.pipeline_consistency.pipeline_audit_accepted is False
    assert model.pipeline_consistency.approval_consistent is True


def test_false_true_pipeline_inconsistency_is_blocked() -> None:
    model = AurumReadModelBuilder.build(
        make_inputs(probability_accepted=False, audit_accepted=True)
    )
    assert model.pipeline_consistency.pipeline_result_approved is False
    assert model.pipeline_consistency.pipeline_audit_accepted is True
    assert model.pipeline_consistency.approval_consistent is False
    assert model.operator_state.reason_code == "PIPELINE_APPROVAL_INCONSISTENCY"


def test_live_execution_disabled_does_not_block_ready() -> None:
    model = AurumReadModelBuilder.build(make_inputs())
    assert model.execution.config.live_execution_enabled is False
    assert model.operator_state.state is AurumOperatorState.READY_BUY


def test_unavailable_diagnostics_news_and_ai_do_not_prevent_ready() -> None:
    model = AurumReadModelBuilder.build(make_inputs())
    assert model.methodology.available is False
    assert model.intelligence_diagnostics.available is False
    assert model.news.available is False
    assert model.ai.available is False
    assert model.operator_state.state is AurumOperatorState.READY_BUY
