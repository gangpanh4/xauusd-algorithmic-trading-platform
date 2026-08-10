"""Immutable execution-economics, provenance, and trace models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from math import isfinite


class SpecificationProvenance(str, Enum):
    """Origin classification for an instrument specification."""

    CURRENT_SNAPSHOT_ASSUMPTION = "CURRENT_SNAPSHOT_ASSUMPTION"
    LEGACY_CONFIGURATION_ASSUMPTION = "LEGACY_CONFIGURATION_ASSUMPTION"
    VERIFIED_HISTORICAL_SPECIFICATION = "VERIFIED_HISTORICAL_SPECIFICATION"


class PriceSideClassification(str, Enum):
    """Declared quote-side semantics of historical prices."""

    UNKNOWN_SINGLE_PRICE = "UNKNOWN_SINGLE_PRICE"
    BID = "BID"
    ASK = "ASK"
    MID = "MID"


class SizingProfile(str, Enum):
    """High-level sizing contract used by an execution mode."""

    RESEARCH_RISK_PERCENT = "RESEARCH_RISK_PERCENT"
    LIVE_CANARY_FIXED_0_01 = "LIVE_CANARY_FIXED_0_01"


class RiskCapitalSource(str, Enum):
    """Capital source supplied to risk planning."""

    REALIZED_SIMULATED_BALANCE = "REALIZED_SIMULATED_BALANCE"
    BROKER_ACCOUNT_BALANCE = "BROKER_ACCOUNT_BALANCE"


@dataclass(frozen=True, slots=True)
class InstrumentSpecification:
    """One immutable instrument specification with explicit provenance."""

    specification_id: str
    symbol: str
    tick_size: float
    tick_value_per_lot: float
    point_size: float
    volume_step: float
    minimum_volume: float
    maximum_volume: float
    contract_size: float | None
    minimum_stop_distance: float
    provenance: SpecificationProvenance
    source: str
    historical_specification_verified: bool
    captured_at: datetime | None = None

    def __post_init__(self) -> None:
        _require_nonempty(self.specification_id, "specification_id")
        _require_nonempty(self.symbol, "symbol")
        _require_positive(self.tick_size, "tick_size")
        _require_positive(self.tick_value_per_lot, "tick_value_per_lot")
        _require_positive(self.point_size, "point_size")
        _require_positive(self.volume_step, "volume_step")
        _require_positive(self.minimum_volume, "minimum_volume")
        _require_positive(self.maximum_volume, "maximum_volume")
        if self.maximum_volume < self.minimum_volume:
            raise ValueError(
                "maximum_volume cannot be smaller than minimum_volume"
            )
        if self.contract_size is not None:
            _require_positive(self.contract_size, "contract_size")
        _require_positive(
            self.minimum_stop_distance,
            "minimum_stop_distance",
        )
        if not isinstance(self.provenance, SpecificationProvenance):
            raise TypeError("provenance must be a SpecificationProvenance")
        _require_nonempty(self.source, "source")
        if not isinstance(self.historical_specification_verified, bool):
            raise TypeError(
                "historical_specification_verified must be a bool"
            )
        if (
            self.provenance
            in {
                SpecificationProvenance.CURRENT_SNAPSHOT_ASSUMPTION,
                SpecificationProvenance.LEGACY_CONFIGURATION_ASSUMPTION,
            }
            and self.historical_specification_verified
        ):
            raise ValueError(
                "assumption provenance cannot be historically verified"
            )
        _require_optional_aware_datetime(self.captured_at, "captured_at")

    def to_dict(self) -> dict[str, object]:
        """Return a stable JSON-compatible representation."""

        return {
            "specification_id": self.specification_id,
            "symbol": self.symbol,
            "tick_size": self.tick_size,
            "tick_value_per_lot": self.tick_value_per_lot,
            "point_size": self.point_size,
            "volume_step": self.volume_step,
            "minimum_volume": self.minimum_volume,
            "maximum_volume": self.maximum_volume,
            "contract_size": self.contract_size,
            "minimum_stop_distance": self.minimum_stop_distance,
            "provenance": self.provenance.value,
            "source": self.source,
            "historical_specification_verified": (
                self.historical_specification_verified
            ),
            "captured_at": (
                self.captured_at.astimezone(UTC).isoformat()
                if self.captured_at is not None
                else None
            ),
        }


@dataclass(frozen=True, slots=True)
class ExecutionCostAssumptions:
    """Pinned deterministic costs for historical simulation."""

    profile_id: str
    spread_points: float
    slippage_points: float
    commission_per_trade: float
    commission_per_lot: float
    verified: bool
    spread_source: str = "PINNED_EXPLICIT_ASSUMPTION"
    historical_spread_field_used: bool = False

    def __post_init__(self) -> None:
        _require_nonempty(self.profile_id, "profile_id")
        _require_nonnegative(self.spread_points, "spread_points")
        _require_nonnegative(self.slippage_points, "slippage_points")
        _require_nonnegative(
            self.commission_per_trade,
            "commission_per_trade",
        )
        _require_nonnegative(self.commission_per_lot, "commission_per_lot")
        if not isinstance(self.verified, bool):
            raise TypeError("verified must be a bool")
        _require_nonempty(self.spread_source, "spread_source")
        if not isinstance(self.historical_spread_field_used, bool):
            raise TypeError("historical_spread_field_used must be a bool")

    def to_dict(self) -> dict[str, object]:
        """Return a stable JSON-compatible representation."""

        return {
            "profile_id": self.profile_id,
            "verified": self.verified,
            "spread_points": self.spread_points,
            "slippage_points": self.slippage_points,
            "commission_per_trade": self.commission_per_trade,
            "commission_per_lot": self.commission_per_lot,
            "spread_source": self.spread_source,
            "historical_spread_field_used": (
                self.historical_spread_field_used
            ),
        }


@dataclass(frozen=True, slots=True)
class ExecutionParityClaims:
    """Explicitly denied parity claims for the deterministic hybrid."""

    exact_broker_execution_parity: bool = False
    exact_fill_parity: bool = False
    realized_pnl_parity: bool = False
    volume_parity: bool = False
    mark_to_market_equity_parity: bool = False

    def __post_init__(self) -> None:
        values = self.to_dict()
        if any(not isinstance(value, bool) for value in values.values()):
            raise TypeError("execution parity claims must be bool values")
        if any(values.values()):
            raise ValueError(
                "the deterministic hybrid cannot assert execution parity"
            )

    def to_dict(self) -> dict[str, bool]:
        """Return parity claims with stable report keys."""

        return {
            "exact_broker_execution_parity": (
                self.exact_broker_execution_parity
            ),
            "exact_fill_parity": self.exact_fill_parity,
            "realized_pnl_parity": self.realized_pnl_parity,
            "volume_parity": self.volume_parity,
            "mark_to_market_equity_parity": (
                self.mark_to_market_equity_parity
            ),
        }


@dataclass(frozen=True, slots=True)
class ExecutionEconomicsProfile:
    """Shared planning inputs and truthful hybrid-parity declarations."""

    profile_id: str
    instrument: InstrumentSpecification
    costs: ExecutionCostAssumptions
    historical_price_side: PriceSideClassification
    research_risk_capital_source: RiskCapitalSource
    live_risk_capital_source: RiskCapitalSource
    research_sizing_profile: SizingProfile
    live_sizing_profile: SizingProfile
    parity_claims: ExecutionParityClaims = field(
        default_factory=ExecutionParityClaims
    )

    def __post_init__(self) -> None:
        _require_nonempty(self.profile_id, "profile_id")
        if not isinstance(self.instrument, InstrumentSpecification):
            raise TypeError("instrument must be an InstrumentSpecification")
        if not isinstance(self.costs, ExecutionCostAssumptions):
            raise TypeError("costs must be ExecutionCostAssumptions")
        if not isinstance(
            self.historical_price_side,
            PriceSideClassification,
        ):
            raise TypeError(
                "historical_price_side must be a PriceSideClassification"
            )
        if not isinstance(
            self.research_risk_capital_source,
            RiskCapitalSource,
        ):
            raise TypeError(
                "research_risk_capital_source must be a RiskCapitalSource"
            )
        if not isinstance(self.live_risk_capital_source, RiskCapitalSource):
            raise TypeError(
                "live_risk_capital_source must be a RiskCapitalSource"
            )
        if not isinstance(self.research_sizing_profile, SizingProfile):
            raise TypeError(
                "research_sizing_profile must be a SizingProfile"
            )
        if not isinstance(self.live_sizing_profile, SizingProfile):
            raise TypeError("live_sizing_profile must be a SizingProfile")
        if not isinstance(self.parity_claims, ExecutionParityClaims):
            raise TypeError("parity_claims must be ExecutionParityClaims")

    def to_dict(self) -> dict[str, object]:
        """Return the complete report and run-manifest payload."""

        return {
            "contract": "DETERMINISTIC_HYBRID",
            "profile_id": self.profile_id,
            "instrument": self.instrument.to_dict(),
            "costs": self.costs.to_dict(),
            "historical_price_side": self.historical_price_side.value,
            "research_risk_capital_source": (
                self.research_risk_capital_source.value
            ),
            "live_risk_capital_source": self.live_risk_capital_source.value,
            "research_sizing_profile": self.research_sizing_profile.value,
            "live_sizing_profile": self.live_sizing_profile.value,
            "parity_claims": self.parity_claims.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class BacktestExecutionTrace:
    """Execution-economics trace with versioned simulator-clock provenance."""

    observation_timestamp: datetime
    decision_available_at: datetime
    actual_entry_timestamp: datetime
    planned_entry_price: float
    reference_entry_price: float
    simulated_fill_price: float
    effective_stop_loss: float
    effective_take_profit: float
    position_size: float
    execution_profile: ExecutionEconomicsProfile
    execution_model_id: str = "M15_COMPLETED_OHLC_V1"
    decision_clock: str = "M5"
    decision_available_after_minutes: int = 5
    entry_policy: str = "NEXT_M15_OPEN"
    entry_clock: str = "M15"
    lifecycle_clock: str = "M15_COMPLETED"
    lifecycle_bar_minutes: int = 15
    closed_bar_consumption: str = "ONLY_AFTER_BAR_COMPLETES"
    same_bar_entry_exit_evaluation: bool = True
    intra_bar_ambiguity_policy: str = "CONSERVATIVE_STOP_FIRST"
    gap_stop_policy: str = "BAR_OPEN_WITH_ADVERSE_SLIPPAGE"
    gap_target_policy: str = "TARGET_PRICE_NO_FAVORABLE_GAP_IMPROVEMENT"
    breakeven_activation_policy: str = (
        "PENDING_AFTER_TRIGGER_BAR_ACTIVE_NEXT_LIFECYCLE_BAR"
    )
    exit_timestamp_semantics: str = (
        "LIFECYCLE_BAR_OPEN_TIMESTAMP_INTRABAR_TIME_UNKNOWN"
    )
    comparable_with_unversioned_results: bool = False
    simulation_clock: str = "M15_COMPLETED"

    def __post_init__(self) -> None:
        _require_aware_datetime(
            self.observation_timestamp,
            "observation_timestamp",
        )
        _require_aware_datetime(
            self.decision_available_at,
            "decision_available_at",
        )
        _require_aware_datetime(
            self.actual_entry_timestamp,
            "actual_entry_timestamp",
        )
        for name in (
            "decision_available_after_minutes",
            "lifecycle_bar_minutes",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer")
            if value <= 0:
                raise ValueError(f"{name} must be greater than zero")
        if self.decision_available_at <= self.observation_timestamp:
            raise ValueError(
                "decision_available_at must follow observation_timestamp"
            )
        expected_decision_available_at = (
            self.observation_timestamp
            + timedelta(minutes=self.decision_available_after_minutes)
        )
        if self.decision_available_at != expected_decision_available_at:
            raise ValueError(
                "decision_available_at must equal observation_timestamp plus "
                "decision_available_after_minutes"
            )
        if self.actual_entry_timestamp < self.decision_available_at:
            raise ValueError(
                "actual_entry_timestamp cannot precede decision_available_at"
            )
        for name in (
            "planned_entry_price",
            "reference_entry_price",
            "simulated_fill_price",
            "effective_stop_loss",
            "effective_take_profit",
            "position_size",
        ):
            _require_positive(getattr(self, name), name)
        if not isinstance(self.execution_profile, ExecutionEconomicsProfile):
            raise TypeError(
                "execution_profile must be an ExecutionEconomicsProfile"
            )
        for name in (
            "execution_model_id",
            "decision_clock",
            "entry_policy",
            "entry_clock",
            "lifecycle_clock",
            "closed_bar_consumption",
            "intra_bar_ambiguity_policy",
            "gap_stop_policy",
            "gap_target_policy",
            "breakeven_activation_policy",
            "exit_timestamp_semantics",
            "simulation_clock",
        ):
            _require_nonempty(getattr(self, name), name)
        if not isinstance(self.same_bar_entry_exit_evaluation, bool):
            raise TypeError("same_bar_entry_exit_evaluation must be a bool")
        if not isinstance(self.comparable_with_unversioned_results, bool):
            raise TypeError("comparable_with_unversioned_results must be a bool")
        if self.comparable_with_unversioned_results:
            raise ValueError(
                "versioned execution results cannot be silently treated as "
                "equivalent to unversioned historical results"
            )

    def to_dict(self) -> dict[str, object]:
        """Return a compact JSON-compatible trade trace."""

        profile = self.execution_profile
        instrument = profile.instrument
        return {
            "observation_timestamp": self.observation_timestamp.astimezone(
                UTC
            ).isoformat(),
            "decision_timestamp": self.observation_timestamp.astimezone(
                UTC
            ).isoformat(),
            "decision_available_at": self.decision_available_at.astimezone(
                UTC
            ).isoformat(),
            "intended_entry_timestamp": (
                self.actual_entry_timestamp.astimezone(UTC).isoformat()
            ),
            "actual_entry_timestamp": self.actual_entry_timestamp.astimezone(
                UTC
            ).isoformat(),
            "entry_reference_timestamp": self.actual_entry_timestamp.astimezone(
                UTC
            ).isoformat(),
            "entry_bar_completed_at": (
                self.actual_entry_timestamp.astimezone(UTC)
                + timedelta(minutes=self.lifecycle_bar_minutes)
            ).isoformat(),
            "first_lifecycle_evaluation_available_at": (
                self.actual_entry_timestamp.astimezone(UTC)
                + timedelta(minutes=self.lifecycle_bar_minutes)
            ).isoformat(),
            "planned_entry_price": self.planned_entry_price,
            "reference_entry_price": self.reference_entry_price,
            "simulated_fill_price": self.simulated_fill_price,
            "effective_stop_loss": self.effective_stop_loss,
            "effective_take_profit": self.effective_take_profit,
            "position_size": self.position_size,
            "execution_model_id": self.execution_model_id,
            "decision_clock": self.decision_clock,
            "decision_available_after_minutes": (
                self.decision_available_after_minutes
            ),
            "entry_policy": self.entry_policy,
            "entry_clock": self.entry_clock,
            "lifecycle_clock": self.lifecycle_clock,
            "lifecycle_bar_minutes": self.lifecycle_bar_minutes,
            "closed_bar_consumption": self.closed_bar_consumption,
            "same_bar_entry_exit_evaluation": (
                self.same_bar_entry_exit_evaluation
            ),
            "intra_bar_ambiguity_policy": self.intra_bar_ambiguity_policy,
            "gap_stop_policy": self.gap_stop_policy,
            "gap_target_policy": self.gap_target_policy,
            "breakeven_activation_policy": self.breakeven_activation_policy,
            "exit_timestamp_semantics": self.exit_timestamp_semantics,
            "comparable_with_unversioned_results": (
                self.comparable_with_unversioned_results
            ),
            "simulation_clock": self.simulation_clock,
            "execution_profile_id": profile.profile_id,
            "instrument_specification_id": instrument.specification_id,
            "cost_profile_id": profile.costs.profile_id,
            "specification_provenance": instrument.provenance.value,
            "historical_specification_verified": (
                instrument.historical_specification_verified
            ),
            "historical_price_side": profile.historical_price_side.value,
            "research_risk_capital_source": (
                profile.research_risk_capital_source.value
            ),
            "research_sizing_profile": (
                profile.research_sizing_profile.value
            ),
            "live_sizing_profile": profile.live_sizing_profile.value,
            "parity_claims": profile.parity_claims.to_dict(),
        }


def _require_nonempty(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _require_positive(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    converted = float(value)
    if not isfinite(converted) or converted <= 0.0:
        raise ValueError(f"{name} must be finite and greater than zero")
    return converted


def _require_nonnegative(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    converted = float(value)
    if not isfinite(converted) or converted < 0.0:
        raise ValueError(f"{name} must be finite and non-negative")
    return converted


def _require_aware_datetime(value: object, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _require_optional_aware_datetime(
    value: object,
    name: str,
) -> datetime | None:
    if value is None:
        return None
    return _require_aware_datetime(value, name)
