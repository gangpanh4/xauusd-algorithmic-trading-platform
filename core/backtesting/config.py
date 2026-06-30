"""
Configuration for the Backtesting Engine.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BacktestConfig:
    """
    Configuration options for the Backtesting Engine.
    """

    initial_balance: float = 10_000.0

    commission_per_trade: float = 0.0

    spread_points: float = 0.0

    slippage_points: float = 0.0

    allow_short_positions: bool = True

    allow_long_positions: bool = True

    max_open_positions: int = 1

    debug_logging: bool = False
    