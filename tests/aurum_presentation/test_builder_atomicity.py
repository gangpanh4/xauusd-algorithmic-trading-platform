from datetime import timedelta

import pytest

from core.aurum_presentation import AurumOperatorState, AurumReadModelBuilder

from .conftest import T, make_inputs


@pytest.mark.parametrize(
    "kwargs",
    [
        {"audit_time": T - timedelta(minutes=5)},
        {"signal_time": T - timedelta(minutes=5)},
        {"plan_time": T - timedelta(minutes=5)},
        {"m5_time": T - timedelta(minutes=5)},
    ],
)
def test_n_n_minus_one_mixing_blocks_snapshot(kwargs: dict[str, object]) -> None:
    model = AurumReadModelBuilder.build(make_inputs(**kwargs))
    assert model.operator_state.state is AurumOperatorState.BLOCKED
    assert model.operator_state.reason_code == "SNAPSHOT_PROVENANCE_MISMATCH"
    assert model.trade_plan.actionable is False
    assert model.trade_plan.entry_price is None


def test_decision_before_m5_plus_five_is_causal_violation() -> None:
    model = AurumReadModelBuilder.build(
        make_inputs(decision_time=T + timedelta(minutes=4))
    )
    assert model.operator_state.state is AurumOperatorState.BLOCKED
    assert model.operator_state.reason_code == "CAUSAL_TIMESTAMP_VIOLATION"


def test_naive_generated_time_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        AurumReadModelBuilder.build(
            make_inputs(generated_at=T.replace(tzinfo=None))
        )
