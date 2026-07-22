"""
Master strategy configuration for the trading platform.

All configurable trading parameters should live here.
Business logic (algorithms) should never contain hardcoded
strategy values.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ==========================================================
# Risk Management
# ==========================================================

@dataclass(slots=True)
class RiskConfig:
    """
    Risk management parameters.
    """

    fixed_lot_size: float = 0.01

    risk_percent: float = 1.0

    risk_reward_ratio: float = 2.0

    maximum_open_positions: int = 1

    maximum_daily_loss: float = 5.0

    allow_multiple_positions: bool = False


# ==========================================================
# Signal Generator
# ==========================================================

@dataclass(slots=True)
class SignalConfig:
    """
    Signal generation parameters.
    """

    minimum_signal_confidence: float = 0.70

    minimum_total_score: float = 6.0

    signal_cooldown_bars: int = 3

    trend_confirmation_bars: int = 1


# ==========================================================
# Trade Management
# ==========================================================

@dataclass(slots=True)
class TradeManagementConfig:
    """
    Trade management configuration.
    """

    breakeven_enabled: bool = False

    breakeven_trigger_r: float = 1.0

    trailing_stop_enabled: bool = False

    trailing_stop_trigger_r: float = 2.0

    trailing_stop_distance_r: float = 1.0

    time_exit_enabled: bool = False

    maximum_holding_bars: int = 50


# ==========================================================
# Backtesting
# ==========================================================

@dataclass(slots=True)
class BacktestConfig:
    """
    Backtesting configuration.
    """

    spread: float = 0.0

    slippage: float = 0.0

    commission: float = 0.0

    initial_balance: float = 10_000.0


# ==========================================================
# Strategy
# ==========================================================

@dataclass(slots=True)
class StrategyConfig:
    """
    Root strategy configuration.

    Every trading module should receive this object
    instead of hardcoded values.
    """

    risk: RiskConfig = field(default_factory=RiskConfig)

    signal: SignalConfig = field(default_factory=SignalConfig)

    trade_management: TradeManagementConfig = field(
        default_factory=TradeManagementConfig
    )

    backtest: BacktestConfig = field(
        default_factory=BacktestConfig
    )