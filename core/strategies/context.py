"""Input and output contracts for observational strategy evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.data.models import MarketBar
from core.multi_timeframe.models import MultiTimeframeResult
from core.regime_detector.models import MarketRegime

from .models import CandidateTrade, EntryTrigger, TradingSetup


@dataclass(slots=True, frozen=True)
class StrategyContext:
    """Completed market facts supplied to the strategy on one M5 close."""

    multi_timeframe: MultiTimeframeResult
    current_bar: MarketBar
    current_bar_index: int
    market_regime: MarketRegime | None = None


@dataclass(slots=True, frozen=True)
class StrategyObservation:
    """Diagnostic output that does not authorize execution."""

    timestamp: datetime
    setup: TradingSetup | None
    trigger: EntryTrigger | None
    candidate_trade: CandidateTrade | None
    reason_code: str
    reason: str
