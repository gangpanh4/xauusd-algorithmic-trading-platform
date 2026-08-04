"""
Configuration for the Backtesting Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from core.trading_pipeline.config import TradingPipelineConfig


class LotSizingMode(Enum):
    FIXED = "FIXED"
    DYNAMIC = "DYNAMIC"
    RISK_PERCENT = "RISK_PERCENT"


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