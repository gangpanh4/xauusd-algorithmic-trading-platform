"""
Configuration for the Backtesting Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from core.execution_economics.models import (
    ExecutionEconomicsProfile,
    PriceSideClassification,
    SpecificationProvenance,
)
from core.execution_economics.profiles import (
    build_compatibility_execution_profile,
)
from core.trading_pipeline.config import TradingPipelineConfig


class LotSizingMode(Enum):
    FIXED = "FIXED"
    DYNAMIC = "DYNAMIC"
    RISK_PERCENT = "RISK_PERCENT"


class BacktestExecutionModel(str, Enum):
    """Versioned historical execution-bar clocks.

    V1 preserves the accepted completed-M15 lifecycle. V2 changes only the
    simulation bar clock to completed M5 bars while retaining the existing
    execution-economics formulas and lifecycle rules.
    """

    M15_COMPLETED_OHLC_V1 = "M15_COMPLETED_OHLC_V1"
    M5_COMPLETED_OHLC_V2 = "M5_COMPLETED_OHLC_V2"

    @property
    def lifecycle_bar_minutes(self) -> int:
        if self is BacktestExecutionModel.M15_COMPLETED_OHLC_V1:
            return 15
        return 5

    def provenance(self) -> dict[str, object]:
        """Return stable, explicit execution-model provenance."""

        if self is BacktestExecutionModel.M15_COMPLETED_OHLC_V1:
            entry_policy = "NEXT_M15_OPEN"
            entry_clock = "M15"
            lifecycle_clock = "M15_COMPLETED"
        else:
            entry_policy = "NEXT_AVAILABLE_M5_OPEN"
            entry_clock = "M5"
            lifecycle_clock = "M5_COMPLETED"

        return {
            "execution_model_id": self.value,
            "decision_clock": "M5",
            "decision_available_after_minutes": 5,
            "entry_policy": entry_policy,
            "entry_clock": entry_clock,
            "lifecycle_clock": lifecycle_clock,
            "lifecycle_bar_minutes": self.lifecycle_bar_minutes,
            "closed_bar_consumption": "ONLY_AFTER_BAR_COMPLETES",
            "same_bar_entry_exit_evaluation": True,
            "intra_bar_ambiguity_policy": "CONSERVATIVE_STOP_FIRST",
            "gap_stop_policy": "BAR_OPEN_WITH_ADVERSE_SLIPPAGE",
            "gap_target_policy": "TARGET_PRICE_NO_FAVORABLE_GAP_IMPROVEMENT",
            "breakeven_activation_policy": (
                "PENDING_AFTER_TRIGGER_BAR_ACTIVE_NEXT_LIFECYCLE_BAR"
            ),
            "exit_timestamp_semantics": (
                "LIFECYCLE_BAR_OPEN_TIMESTAMP_INTRABAR_TIME_UNKNOWN"
            ),
            "comparable_with_unversioned_results": False,
        }


@dataclass(frozen=True)
class BacktestConfig:
    """
    Configuration for historical backtesting.
    """

    # ===========================
    # Trading Pipeline
    # ===========================

    pipeline: TradingPipelineConfig = field(
        default_factory=TradingPipelineConfig,
    )

    # ===========================
    # Account
    # ===========================

    initial_balance: float = 10_000.0

    use_virtual_balance: bool = False

    virtual_balance: float = 100.0

    # ===========================
    # Position Sizing
    # ===========================

    lot_mode: LotSizingMode = LotSizingMode.RISK_PERCENT

    fixed_lot_size: float = 0.01

    risk_percent: float = 1.0

    # ===========================
    # Execution Model
    # ===========================

    execution_model: BacktestExecutionModel = (
        BacktestExecutionModel.M15_COMPLETED_OHLC_V1
    )

    # ===========================
    # Execution Economics
    # ===========================

    stop_loss_distance: float = 2.5

    tick_size: float = 0.01

    tick_value_per_lot: float = 1.0

    lot_step: float = 0.01

    minimum_lot: float = 0.01

    maximum_lot: float = 10.0

    # ===========================
    # Trading Costs
    # ===========================

    commission_per_trade: float = 0.0

    commission_per_lot: float = 0.0

    spread_points: float = 0.0

    slippage_points: float = 0.0

    cost_assumption_profile: str = "UNVERIFIED_ZERO_COST"

    cost_assumptions_verified: bool = False

    # ===========================
    # Execution Provenance
    # ===========================

    execution_profile: ExecutionEconomicsProfile | None = None

    execution_profile_id: str = "BACKTEST_CONFIG_COMPATIBILITY_V1"

    instrument_specification_id: str = (
        "XAUUSD_CURRENT_SNAPSHOT_ASSUMPTION_V1"
    )

    instrument_symbol: str = "XAUUSD"

    point_size: float = 0.01

    contract_size: float | None = None

    specification_provenance: SpecificationProvenance = (
        SpecificationProvenance.CURRENT_SNAPSHOT_ASSUMPTION
    )

    specification_source: str = "PINNED_BACKTEST_CONFIGURATION"

    historical_specification_verified: bool = False

    specification_captured_at: datetime | None = None

    historical_price_side: PriceSideClassification = (
        PriceSideClassification.UNKNOWN_SINGLE_PRICE
    )

    # ===========================
    # Trading Options
    # ===========================

    allow_short_positions: bool = True

    allow_long_positions: bool = True

    max_open_positions: int = 1

    # ===========================
    # Backtest Range
    # ===========================

    start_date: datetime | None = None

    end_date: datetime | None = None

    warmup_bars: int = 200

    maximum_trades: int | None = None

    # ===========================
    # Reporting
    # ===========================

    save_trade_log: bool = True

    save_equity_curve: bool = True

    save_statistics: bool = True

    output_directory: str = "output/backtests"

    # ===========================
    # Debug
    # ===========================

    debug_logging: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.execution_model, BacktestExecutionModel):
            raise TypeError(
                "execution_model must be a BacktestExecutionModel"
            )

    def resolved_execution_profile(self) -> ExecutionEconomicsProfile:
        """Return the explicit profile or derive one from legacy scalars.

        An explicit profile is authoritative. Existing callers that configure
        only scalar fields keep their numerical behavior and receive a stable
        compatibility profile with truthful assumption provenance.
        """

        if self.execution_profile is not None:
            if not isinstance(
                self.execution_profile,
                ExecutionEconomicsProfile,
            ):
                raise TypeError(
                    "execution_profile must be an ExecutionEconomicsProfile"
                )
            return self.execution_profile

        return build_compatibility_execution_profile(
            profile_id=self.execution_profile_id,
            specification_id=self.instrument_specification_id,
            symbol=self.instrument_symbol,
            tick_size=self.tick_size,
            tick_value_per_lot=self.tick_value_per_lot,
            point_size=self.point_size,
            volume_step=self.lot_step,
            minimum_volume=self.minimum_lot,
            maximum_volume=self.maximum_lot,
            contract_size=self.contract_size,
            minimum_stop_distance=self.stop_loss_distance,
            specification_provenance=self.specification_provenance,
            specification_source=self.specification_source,
            historical_specification_verified=(
                self.historical_specification_verified
            ),
            specification_captured_at=self.specification_captured_at,
            historical_price_side=self.historical_price_side,
            cost_profile_id=self.cost_assumption_profile,
            costs_verified=self.cost_assumptions_verified,
            spread_points=self.spread_points,
            slippage_points=self.slippage_points,
            commission_per_trade=self.commission_per_trade,
            commission_per_lot=self.commission_per_lot,
        )

    def execution_model_provenance(self) -> dict[str, object]:
        """Return the selected versioned simulator-clock contract."""

        return self.execution_model.provenance()
