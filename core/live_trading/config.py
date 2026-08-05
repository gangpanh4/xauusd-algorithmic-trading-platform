"""
Configuration for the Live Trading Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

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

    history_window_bars: int = 500

    live_execution_enabled: bool = False

    shadow_recording_enabled: bool = False

    shadow_observation_path: Path = Path(
        "runtime/live_shadow_observations.jsonl"
    )

    partial_fill_state_path: Path = Path(
        "runtime/live_partial_fill_state.json"
    )
