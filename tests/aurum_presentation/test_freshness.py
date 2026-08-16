from core.aurum_presentation import (
    AurumDataMode,
    AurumOperatorState,
    AurumReadModelBuilder,
    FreshnessAssessment,
)

from .conftest import make_inputs


def test_explicit_critical_freshness_failure_blocks_ready() -> None:
    assessment = FreshnessAssessment(
        policy_id="REAL_V1",
        valid=False,
        critical_failure=True,
        reason_code="STALE_ANALYTICAL_STATE",
        reason="M5 analytical state is stale.",
    )
    model = AurumReadModelBuilder.build(make_inputs(freshness=assessment))
    assert model.operator_state.state is AurumOperatorState.BLOCKED
    assert model.operator_state.reason_code == "STALE_ANALYTICAL_STATE"


def test_research_replay_does_not_require_live_quote() -> None:
    model = AurumReadModelBuilder.build(
        make_inputs(mode=AurumDataMode.RESEARCH_REPLAY, include_risk_state=False)
    )
    assert model.quote.available is False
    assert model.operator_state.state is AurumOperatorState.READY_BUY


def test_real_mode_missing_risk_runtime_fails_closed() -> None:
    model = AurumReadModelBuilder.build(make_inputs(include_risk_state=False))
    assert model.operator_state.state is AurumOperatorState.BLOCKED
    assert model.operator_state.reason_code == "RISK_RUNTIME_UNAVAILABLE"


def test_critical_freshness_failure_precedes_normal_hold() -> None:
    assessment = FreshnessAssessment(
        policy_id="REAL_V1",
        valid=False,
        critical_failure=True,
        reason_code="CRITICAL_STALE",
        reason="Critical freshness failure.",
    )
    model = AurumReadModelBuilder.build(
        make_inputs(probability_accepted=False, freshness=assessment)
    )
    assert model.operator_state.state is AurumOperatorState.BLOCKED
    assert model.operator_state.reason_code == "CRITICAL_STALE"
