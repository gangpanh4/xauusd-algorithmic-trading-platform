"""
Domain models for the Order Block Detection Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.market_structure.enums import (
    OrderBlockEventType,
    OrderBlockType,
)
from core.market_structure.models import (
    BOSEvent,
    CHOCHEvent,
    LiquiditySweepEvent,
    SwingPoint,
)


@dataclass(frozen=True, slots=True)
class OrderBlockCandidate:
    """
    Candidate Order Block awaiting validation.
    """

    timestamp: datetime

    block_type: OrderBlockType

    top_price: float

    bottom_price: float

    origin_swing: SwingPoint

    trigger_break: BOSEvent | CHOCHEvent

    trigger_liquidity: LiquiditySweepEvent | None

    creation_index: int

    # Version 2 evidence

    # Quality score assigned to the selected
    # origin candle during candidate creation.
    origin_bar_score: float = 0.0


@dataclass(frozen=True, slots=True)
class OrderBlock:
    """
    Immutable representation of a confirmed institutional Order Block.

    An Order Block represents the price zone responsible for initiating
    a confirmed structural displacement. It contains only immutable
    market facts and never stores runtime lifecycle state.
    """

    timestamp: datetime

    block_type: OrderBlockType

    top_price: float

    bottom_price: float

    origin_swing: SwingPoint

    trigger_break: BOSEvent | CHOCHEvent

    trigger_liquidity: LiquiditySweepEvent | None

    creation_index: int

    confirmation_index: int


@dataclass(frozen=True, slots=True)
class OrderBlockAnalysis:
    """
    Quality assessment for a confirmed Order Block.

    These scores provide additional information for downstream
    components such as the Signal Generator, Confluence Engine,
    Research Framework, and AI validation modules.
    """

    structure_score: float

    displacement_score: float

    liquidity_score: float

    reaction_score: float

    total_score: float


@dataclass(frozen=True, slots=True)
class OrderBlockEvent:
    """
    Immutable lifecycle event emitted by the Order Block Detector.
    """

    timestamp: datetime

    event_type: OrderBlockEventType

    order_block: OrderBlock

    analysis: OrderBlockAnalysis

    confirmation_index: int