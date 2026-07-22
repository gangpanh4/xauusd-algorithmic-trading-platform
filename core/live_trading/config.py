"""
Configuration for the Live Trading Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.mt5_execution.config import (
    MT5ExecutionConfig,
)

from core.trading_pipeline.config import (
    TradingPipelineConfig,
)


@dataclass(frozen=True)
class LiveTradingConfig:
    """
    Configuration for live trading.
    """

    pipeline: TradingPipelineConfig = field(
        default_factory=TradingPipelineConfig,
    )

    execution: MT5ExecutionConfig = (
        MT5ExecutionConfig()
    )

    symbol: str = "XAUUSD"

    timeframe: str = "M5"

    poll_interval_seconds: int = 5

    live_execution_enabled: bool = False