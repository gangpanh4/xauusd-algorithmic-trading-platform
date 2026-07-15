"""
Tests for the Trade Simulator.

These tests verify baseline correctness of trade
simulation before improving backtesting realism.
"""

from datetime import UTC, datetime, timedelta

from core.backtesting.models import ExitReason, TradeOutcome
from core.backtesting.simulator import TradeSimulator
from core.regime_detector.models import MarketBar
from core.risk_manager.models import TradePlan


def make_bar(
    *,
    high: float,
    low: float,
    close: float,
    minutes: int = 0,
) -> MarketBar:
    return MarketBar(
        timestamp=datetime(2025, 1, 1, tzinfo=UTC)
        + timedelta(minutes=minutes),
        open=close,
        high=high,
        low=low,
        close=close,
        tick_volume=100,
    )


def make_trade_plan(
    *,
    entry: float = 100.0,
    stop: float = 95.0,
    take: float = 110.0,
):
    """
    Create a valid TradePlan.

    Fill every required field using the same defaults
    used throughout your project.
    """
    ...