"""
Core models for the Live Trading Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.mt5_execution.models import (
    OrderResult,
)
from core.trading_pipeline.models import (
    PipelineResult,
)

if TYPE_CHECKING:
    from core.multi_timeframe.models import MultiTimeframeResult


@dataclass(frozen=True)
class LiveTradingResult:
    """
    Result of processing one completed market bar.
    """

    pipeline_result: PipelineResult

    execution_result: OrderResult | None

    trade_executed: bool

    multi_timeframe_result: MultiTimeframeResult | None = None