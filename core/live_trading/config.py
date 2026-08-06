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

    execution: MT5ExecutionConfig = field(
        default_factory=MT5ExecutionConfig,
    )

    symbol: str = "XAUUSD"

    timeframe: str = "M5"

    poll_interval_seconds: int = 5

    history_window_bars: int = 500

    # This broker's MT5 terminal currently encodes market timestamps three
    # hours ahead of actual UTC. MarketDataService subtracts this offset at
    # the ingestion boundary before constructing UTC MarketBar objects.
    mt5_server_utc_offset_hours: float = 3.0

    # Fail closed when the normalized broker tick differs materially from
    # the system UTC clock.
    mt5_clock_max_skew_seconds: float = 120.0

    live_execution_enabled: bool = False

    shadow_recording_enabled: bool = False

    shadow_observation_path: Path = Path(
        "runtime/live_shadow_observations.jsonl"
    )

    shadow_summary_directory: Path = Path(
        "output/live_shadow"
    )

    parity_recording_enabled: bool = False

    parity_evidence_path: Path = Path(
        "runtime/live_parity_evidence.jsonl"
    )

    parity_report_directory: Path = Path(
        "output/live_parity"
    )

    partial_fill_state_path: Path = Path(
        "runtime/live_partial_fill_state.json"
    )
