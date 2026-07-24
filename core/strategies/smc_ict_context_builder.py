"""Build SMC/ICT context from the active strategy observation contract."""

from __future__ import annotations

from core.market_structure.enums import TrendDirection
from core.market_structure.models import (
    BOSEvent,
    CHOCHEvent,
    MarketStructureResult,
    StructureState,
)
from core.multi_timeframe.enums import MarketBias
from core.multi_timeframe.models import TimeframeState
from core.price_action.models import PriceActionResult

from .context import StrategyContext
from .smc_ict_context import PriceLocation, SMCICTContext


class SMCICTContextBuilder:
    """Assemble reusable facts without applying strategy rules."""

    _UNAVAILABLE = (
        "dealing_range_price_location",
        "displacement_detection",
        "session_context",
        "market_regime",
    )

    def build(self, context: StrategyContext) -> SMCICTContext:
        if not isinstance(context, StrategyContext):
            raise TypeError("context must be StrategyContext")

        h4 = self._structure(context.multi_timeframe.h4)
        h1 = self._structure(context.multi_timeframe.h1)
        m15 = self._structure(context.multi_timeframe.m15)
        m5 = self._structure(context.multi_timeframe.m5)
        event = self._latest_event(m5, m15, h1, h4)
        sweep = self._latest_sweep(m5, m15, h1, h4)
        pa = self._price_action(context.multi_timeframe.m15) or self._price_action(
            context.multi_timeframe.m5
        )
        target = self._opposing_liquidity(
            structure=m15 or h1 or h4 or m5,
            direction=event.direction if event is not None else None,
            current_price=float(context.current_bar.close),
        )

        return SMCICTContext(
            timestamp=context.current_bar.timestamp,
            current_bar_index=context.current_bar_index,
            current_price=float(context.current_bar.close),
            higher_timeframe_bias=self._htf_bias(
                context.multi_timeframe.h4.bias,
                context.multi_timeframe.h1.bias,
            ),
            h4_structure=h4,
            h1_structure=h1,
            m15_structure=m15,
            m5_structure=m5,
            latest_structure_event=event,
            latest_liquidity_sweep=sweep,
            opposing_liquidity_level=target,
            active_fair_value_gap=pa.last_fair_value_gap if pa else None,
            active_order_block=pa.last_order_block if pa else None,
            price_location=PriceLocation.UNKNOWN,
            displacement_present=None,
            session_name=None,
            regime_name=None,
            missing_capabilities=self._UNAVAILABLE,
        )

    @staticmethod
    def _structure(state: TimeframeState) -> StructureState | None:
        value = state.market_structure
        if isinstance(value, StructureState):
            return value
        if isinstance(value, MarketStructureResult):
            return value.structure_state
        return None

    @staticmethod
    def _price_action(state: TimeframeState) -> PriceActionResult | None:
        return state.price_action if isinstance(state.price_action, PriceActionResult) else None

    @staticmethod
    def _htf_bias(h4: MarketBias, h1: MarketBias) -> MarketBias:
        return h4 if h4 is h1 and h4 is not MarketBias.NEUTRAL else MarketBias.NEUTRAL

    @staticmethod
    def _latest_event(*states: StructureState | None) -> BOSEvent | CHOCHEvent | None:
        events = []
        for state in states:
            if state is None:
                continue
            if state.last_bos is not None:
                events.append(state.last_bos)
            if state.last_choch is not None:
                events.append(state.last_choch)
        return max(events, key=lambda item: item.confirmation_index) if events else None

    @staticmethod
    def _latest_sweep(*states: StructureState | None):
        sweeps = [
            state.last_liquidity
            for state in states
            if state is not None and state.last_liquidity is not None
        ]
        return max(sweeps, key=lambda item: item.confirmation_index) if sweeps else None

    @staticmethod
    def _opposing_liquidity(
        *,
        structure: StructureState | None,
        direction: TrendDirection | None,
        current_price: float,
    ):
        if structure is None or direction is None:
            return None
        if direction is TrendDirection.BULLISH:
            levels = [
                level for level in structure.tracked_liquidity_levels
                if level.is_buy_side and level.price > current_price
            ]
            return min(levels, key=lambda level: level.price, default=None)
        if direction is TrendDirection.BEARISH:
            levels = [
                level for level in structure.tracked_liquidity_levels
                if not level.is_buy_side and level.price < current_price
            ]
            return max(levels, key=lambda level: level.price, default=None)
        return None
