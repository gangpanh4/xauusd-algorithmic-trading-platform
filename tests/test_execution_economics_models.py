from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from core.backtesting.config import BacktestConfig
from core.execution_economics.models import (
    InstrumentSpecification,
    PriceSideClassification,
    SpecificationProvenance,
)
from core.execution_economics.profiles import (
    pinned_xauusd_research_profile,
)


def test_pinned_profile_declares_truthful_hybrid_provenance() -> None:
    profile = pinned_xauusd_research_profile()
    payload = profile.to_dict()

    assert payload["contract"] == "DETERMINISTIC_HYBRID"
    assert profile.instrument.contract_size is None
    assert profile.instrument.provenance is (
        SpecificationProvenance.CURRENT_SNAPSHOT_ASSUMPTION
    )
    assert profile.instrument.historical_specification_verified is False
    assert profile.historical_price_side is (
        PriceSideClassification.UNKNOWN_SINGLE_PRICE
    )
    assert profile.costs.historical_spread_field_used is False
    assert set(payload["parity_claims"].values()) == {False}

    with pytest.raises(FrozenInstanceError):
        profile.instrument.tick_size = 1.0  # type: ignore[misc]


def test_legacy_scalar_config_resolves_to_deterministic_profile() -> None:
    config = BacktestConfig(
        stop_loss_distance=0.5,
        tick_size=0.1,
        tick_value_per_lot=2.0,
        lot_step=0.05,
        minimum_lot=0.05,
        maximum_lot=5.0,
        point_size=0.01,
        spread_points=3.0,
        slippage_points=2.0,
        commission_per_trade=1.0,
        commission_per_lot=4.0,
    )

    profile = config.resolved_execution_profile()

    assert profile.instrument.tick_size == pytest.approx(0.1)
    assert profile.instrument.tick_value_per_lot == pytest.approx(2.0)
    assert profile.instrument.volume_step == pytest.approx(0.05)
    assert profile.instrument.minimum_volume == pytest.approx(0.05)
    assert profile.instrument.maximum_volume == pytest.approx(5.0)
    assert profile.costs.spread_points == pytest.approx(3.0)
    assert profile.costs.slippage_points == pytest.approx(2.0)
    assert profile.costs.commission_per_trade == pytest.approx(1.0)
    assert profile.costs.commission_per_lot == pytest.approx(4.0)


def test_explicit_profile_is_authoritative_over_legacy_scalars() -> None:
    profile = pinned_xauusd_research_profile()
    config = BacktestConfig(
        execution_profile=profile,
        tick_size=99.0,
        tick_value_per_lot=99.0,
        spread_points=99.0,
    )

    assert config.resolved_execution_profile() is profile


def test_assumption_provenance_cannot_claim_historical_verification() -> None:
    with pytest.raises(ValueError, match="cannot be historically verified"):
        InstrumentSpecification(
            specification_id="INVALID",
            symbol="XAUUSD",
            tick_size=0.01,
            tick_value_per_lot=1.0,
            point_size=0.01,
            volume_step=0.01,
            minimum_volume=0.01,
            maximum_volume=10.0,
            contract_size=None,
            minimum_stop_distance=0.01,
            provenance=(
                SpecificationProvenance.CURRENT_SNAPSHOT_ASSUMPTION
            ),
            source="TEST",
            historical_specification_verified=True,
        )
