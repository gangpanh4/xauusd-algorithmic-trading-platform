"""
Core models for the Live Trading Engine.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.mt5_execution.models import (
    OrderResult,
)

from core.trading_pipeline.models import (
    PipelineResult,
)


@dataclass(frozen=True)
class LiveTradingResult:
    """
    Result of processing one completed market bar.
    """

    pipeline_result: PipelineResult

    execution_result: OrderResult | None

    trade_executed: bool