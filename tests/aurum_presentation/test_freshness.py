from core.aurum_presentation import (
    AURUM_LIVE_FRESHNESS_V1,
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


def test_builder_projects_live_freshness_policy_identity() -> None:
    assessment = FreshnessAssessment(
        policy_id=AURUM_LIVE_FRESHNESS_V1,
        valid=True,
    )

    model = AurumReadModelBuilder.build(make_inputs(freshness=assessment))

    assert model.meta.freshness_policy_id == AURUM_LIVE_FRESHNESS_V1


def test_live_quote_unavailable_fails_closed_without_fabricated_prices() -> None:
    assessment = FreshnessAssessment(
        policy_id=AURUM_LIVE_FRESHNESS_V1,
        valid=False,
        critical_failure=True,
        reason_code="LIVE_QUOTE_UNAVAILABLE",
        reason="A current live quote is unavailable.",
    )

    model = AurumReadModelBuilder.build(make_inputs(freshness=assessment))

    assert model.operator_state.state is AurumOperatorState.BLOCKED
    assert model.operator_state.reason_code == "LIVE_QUOTE_UNAVAILABLE"
    assert model.quote.available is False
    assert model.quote.bid is None
    assert model.quote.ask is None
