"""Immutable SMC/ICT market-context contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from core.fair_value_gap_detector.models import FairValueGap, FairValueGapCandidate
from core.market_structure.models import (
    BOSEvent,
    CHOCHEvent,
    LiquidityLevel,
    LiquiditySweepEvent,
    StructureState,
)
from core.multi_timeframe.enums import MarketBias
from core.order_block_detector.models import OrderBlock


class PriceLocation(str, Enum):
    PREMIUM = "premium"
    EQUILIBRIUM = "equilibrium"
    DISCOUNT = "discount"
    UNKNOWN = "unknown"


@dataclass(slots=True, frozen=True)
class SMCICTContext:
    """Objective facts for methodology evaluation; never trade authorization."""

    timestamp: datetime
    current_bar_index: int
    current_price: float
    higher_timeframe_bias: MarketBias
    h4_structure: StructureState | None
    h1_structure: StructureState | None
    m15_structure: StructureState | None
    m5_structure: StructureState | None
    latest_structure_event: BOSEvent | CHOCHEvent | None
    latest_liquidity_sweep: LiquiditySweepEvent | None
    opposing_liquidity_level: LiquidityLevel | None
    active_fair_value_gap: FairValueGap | FairValueGapCandidate | None
    active_order_block: OrderBlock | None
    price_location: PriceLocation = PriceLocation.UNKNOWN
    displacement_present: bool | None = None
    session_name: str | None = None
    regime_name: str | None = None
    missing_capabilities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.current_bar_index, bool) or not isinstance(
            self.current_bar_index, int
        ):
            raise TypeError("current_bar_index must be an integer")
        if self.current_bar_index < 0:
            raise ValueError("current_bar_index cannot be negative")
        if isinstance(self.current_price, bool) or not isinstance(
            self.current_price, (int, float)
        ):
            raise TypeError("current_price must be numeric")
        if self.current_price <= 0:
            raise ValueError("current_price must be positive")
        if not isinstance(self.higher_timeframe_bias, MarketBias):
            raise TypeError("higher_timeframe_bias must be a MarketBias")
        if not isinstance(self.price_location, PriceLocation):
            raise TypeError("price_location must be a PriceLocation")
