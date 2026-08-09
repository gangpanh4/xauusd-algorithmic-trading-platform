"""Construction of explicit offline execution-economics profiles."""

from __future__ import annotations

from datetime import datetime

from .models import (
    ExecutionCostAssumptions,
    ExecutionEconomicsProfile,
    InstrumentSpecification,
    PriceSideClassification,
    RiskCapitalSource,
    SizingProfile,
    SpecificationProvenance,
)


def build_compatibility_execution_profile(
    *,
    profile_id: str,
    specification_id: str,
    symbol: str,
    tick_size: float,
    tick_value_per_lot: float,
    point_size: float,
    volume_step: float,
    minimum_volume: float,
    maximum_volume: float,
    contract_size: float | None,
    minimum_stop_distance: float,
    specification_provenance: SpecificationProvenance,
    specification_source: str,
    historical_specification_verified: bool,
    specification_captured_at: datetime | None,
    historical_price_side: PriceSideClassification,
    cost_profile_id: str,
    costs_verified: bool,
    spread_points: float,
    slippage_points: float,
    commission_per_trade: float,
    commission_per_lot: float,
) -> ExecutionEconomicsProfile:
    """Build a deterministic profile from legacy scalar configuration."""

    return ExecutionEconomicsProfile(
        profile_id=profile_id,
        instrument=InstrumentSpecification(
            specification_id=specification_id,
            symbol=symbol,
            tick_size=tick_size,
            tick_value_per_lot=tick_value_per_lot,
            point_size=point_size,
            volume_step=volume_step,
            minimum_volume=minimum_volume,
            maximum_volume=maximum_volume,
            contract_size=contract_size,
            minimum_stop_distance=minimum_stop_distance,
            provenance=specification_provenance,
            source=specification_source,
            historical_specification_verified=(
                historical_specification_verified
            ),
            captured_at=specification_captured_at,
        ),
        costs=ExecutionCostAssumptions(
            profile_id=cost_profile_id,
            spread_points=spread_points,
            slippage_points=slippage_points,
            commission_per_trade=commission_per_trade,
            commission_per_lot=commission_per_lot,
            verified=costs_verified,
            spread_source="PINNED_EXPLICIT_ASSUMPTION",
            historical_spread_field_used=False,
        ),
        historical_price_side=historical_price_side,
        research_risk_capital_source=(
            RiskCapitalSource.REALIZED_SIMULATED_BALANCE
        ),
        live_risk_capital_source=RiskCapitalSource.BROKER_ACCOUNT_BALANCE,
        research_sizing_profile=SizingProfile.RESEARCH_RISK_PERCENT,
        live_sizing_profile=SizingProfile.LIVE_CANARY_FIXED_0_01,
    )


def pinned_xauusd_research_profile() -> ExecutionEconomicsProfile:
    """Return the source-pinned, offline XAUUSD research assumptions.

    These values preserve the existing scalar backtest defaults. Their
    provenance is an unverified current-snapshot assumption; they are not a
    historical broker specification and they are never refreshed at runtime.
    """

    return build_compatibility_execution_profile(
        profile_id="XAUUSD_PINNED_RESEARCH_ECONOMICS_V1",
        specification_id="XAUUSD_CURRENT_SNAPSHOT_ASSUMPTION_V1",
        symbol="XAUUSD",
        tick_size=0.01,
        tick_value_per_lot=1.0,
        point_size=0.01,
        volume_step=0.01,
        minimum_volume=0.01,
        maximum_volume=10.0,
        contract_size=None,
        minimum_stop_distance=2.5,
        specification_provenance=(
            SpecificationProvenance.CURRENT_SNAPSHOT_ASSUMPTION
        ),
        specification_source="PINNED_OFFLINE_BACKTEST_CONFIGURATION",
        historical_specification_verified=False,
        specification_captured_at=None,
        historical_price_side=(
            PriceSideClassification.UNKNOWN_SINGLE_PRICE
        ),
        cost_profile_id="UNVERIFIED_ZERO_COST",
        costs_verified=False,
        spread_points=0.0,
        slippage_points=0.0,
        commission_per_trade=0.0,
        commission_per_lot=0.0,
    )
