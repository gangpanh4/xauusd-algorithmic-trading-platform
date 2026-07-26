"""Build SMC/ICT context from the active strategy observation contract."""

from __future__ import annotations

from datetime import UTC, datetime, time
from math import isfinite

from core.fair_value_gap_detector.models import FairValueGap, FairValueGapCandidate
from core.market_structure.enums import TrendDirection
from core.market_structure.models import (
    BOSEvent,
    CHOCHEvent,
    LiquidityLevel,
    LiquiditySweepEvent,
    MarketStructureResult,
    StructureState,
)
from core.multi_timeframe.enums import MarketBias, Timeframe
from core.multi_timeframe.models import TimeframeState
from core.order_block_detector.models import OrderBlock
from core.price_action.models import PriceActionResult

from .context import StrategyContext
from .smc_ict_context import PriceLocation, SMCICTContext


class SMCICTContextBuilder:
    """Assemble confirmed, chronology-safe facts without applying strategy rules."""

    _ALWAYS_UNAVAILABLE = (
        "market_regime",
    )
    _DEALING_RANGE_PRIORITY = (
        Timeframe.H1,
        Timeframe.H4,
        Timeframe.M15,
        Timeframe.M5,
    )
    _STRUCTURE_PRIORITY = (
        Timeframe.M5,
        Timeframe.M15,
        Timeframe.H1,
        Timeframe.H4,
    )
    _PRICE_ACTION_PRIORITY = (
        Timeframe.M15,
        Timeframe.M5,
    )

    def build(self, context: StrategyContext) -> SMCICTContext:
        if not isinstance(context, StrategyContext):
            raise TypeError("context must be StrategyContext")

        observation_timestamp = context.current_bar.timestamp
        states = {
            Timeframe.H4: context.multi_timeframe.h4,
            Timeframe.H1: context.multi_timeframe.h1,
            Timeframe.M15: context.multi_timeframe.m15,
            Timeframe.M5: context.multi_timeframe.m5,
        }
        structures = {
            timeframe: self._structure(
                state,
                observation_timestamp=observation_timestamp,
            )
            for timeframe, state in states.items()
        }

        event, event_timeframe = self._latest_event(
            structures,
            observation_timestamp=observation_timestamp,
        )
        sweep, sweep_timeframe = self._latest_sweep(
            structures,
            observation_timestamp=observation_timestamp,
        )
        target, target_timeframe = self._opposing_liquidity(
            structure=structures[event_timeframe] if event_timeframe else None,
            timeframe=event_timeframe,
            direction=event.direction if event else None,
            current_price=float(context.current_bar.close),
            observation_timestamp=observation_timestamp,
        )
        fair_value_gap, fair_value_gap_timeframe = self._latest_fair_value_gap(
            states,
            observation_timestamp=observation_timestamp,
        )
        order_block, order_block_timeframe = self._latest_order_block(
            states,
            structures=structures,
            observation_timestamp=observation_timestamp,
        )
        (
            dealing_range_high,
            dealing_range_low,
            dealing_range_equilibrium,
            dealing_range_timeframe,
            price_location,
        ) = self._dealing_range_price_location(
            structures,
            current_price=float(context.current_bar.close),
            observation_timestamp=observation_timestamp,
        )
        (
            displacement_present,
            displacement_direction,
            displacement_timeframe,
            displacement_atr_multiple,
        ) = self._displacement(event, event_timeframe)
        session_name = self._session_name(observation_timestamp)
        missing_capabilities = self._missing_capabilities(
            price_location,
            displacement_present,
        )

        return SMCICTContext(
            timestamp=observation_timestamp,
            current_bar_index=context.current_bar_index,
            current_price=float(context.current_bar.close),
            higher_timeframe_bias=self._htf_bias(
                context.multi_timeframe.h4.bias,
                context.multi_timeframe.h1.bias,
            ),
            h4_structure=structures[Timeframe.H4],
            h1_structure=structures[Timeframe.H1],
            m15_structure=structures[Timeframe.M15],
            m5_structure=structures[Timeframe.M5],
            latest_structure_event=event,
            latest_liquidity_sweep=sweep,
            opposing_liquidity_level=target,
            active_fair_value_gap=fair_value_gap,
            active_order_block=order_block,
            latest_structure_event_timeframe=event_timeframe,
            latest_liquidity_sweep_timeframe=sweep_timeframe,
            opposing_liquidity_timeframe=target_timeframe,
            active_fair_value_gap_timeframe=fair_value_gap_timeframe,
            active_order_block_timeframe=order_block_timeframe,
            dealing_range_high=dealing_range_high,
            dealing_range_low=dealing_range_low,
            dealing_range_equilibrium=dealing_range_equilibrium,
            dealing_range_timeframe=dealing_range_timeframe,
            price_location=price_location,
            displacement_present=displacement_present,
            displacement_direction=displacement_direction,
            displacement_timeframe=displacement_timeframe,
            displacement_atr_multiple=displacement_atr_multiple,
            session_name=session_name,
            regime_name=None,
            missing_capabilities=missing_capabilities,
        )

    @classmethod
    def _structure(
        cls,
        state: TimeframeState,
        *,
        observation_timestamp: datetime,
    ) -> StructureState | None:
        if not cls._state_is_known(state, observation_timestamp):
            return None
        value = state.market_structure
        if isinstance(value, StructureState):
            structure = value
        elif isinstance(value, MarketStructureResult):
            structure = value.structure_state
        else:
            return None
        if structure is None or not cls._timestamp_is_known(
            structure.timestamp,
            observation_timestamp,
        ):
            return None
        return structure

    @staticmethod
    def _price_action(state: TimeframeState) -> PriceActionResult | None:
        return (
            state.price_action
            if isinstance(state.price_action, PriceActionResult)
            else None
        )

    @staticmethod
    def _htf_bias(h4: MarketBias, h1: MarketBias) -> MarketBias:
        return (
            h4
            if h4 is h1 and h4 is not MarketBias.NEUTRAL
            else MarketBias.NEUTRAL
        )


    @classmethod
    def _dealing_range_price_location(
        cls,
        structures: dict[Timeframe, StructureState | None],
        *,
        current_price: float,
        observation_timestamp: datetime,
    ) -> tuple[
        float | None,
        float | None,
        float | None,
        Timeframe | None,
        PriceLocation,
    ]:
        for timeframe in cls._DEALING_RANGE_PRIORITY:
            structure = structures[timeframe]
            if structure is None:
                continue

            high = structure.last_high
            low = structure.last_low
            if not cls._swing_is_known(
                high,
                structure=structure,
                observation_timestamp=observation_timestamp,
            ):
                continue
            if not cls._swing_is_known(
                low,
                structure=structure,
                observation_timestamp=observation_timestamp,
            ):
                continue
            if high.price <= low.price:
                continue

            equilibrium = (float(high.price) + float(low.price)) / 2.0
            if current_price > equilibrium:
                location = PriceLocation.PREMIUM
            elif current_price < equilibrium:
                location = PriceLocation.DISCOUNT
            else:
                location = PriceLocation.EQUILIBRIUM

            return (
                float(high.price),
                float(low.price),
                equilibrium,
                timeframe,
                location,
            )

        return None, None, None, None, PriceLocation.UNKNOWN


    @staticmethod
    def _session_name(timestamp: datetime) -> str | None:
        """Classify a completed candle into deterministic UTC research sessions."""

        utc_time = timestamp.astimezone(UTC).time().replace(tzinfo=None)

        if time(0, 0) <= utc_time < time(8, 0):
            return "Asia"
        if time(8, 0) <= utc_time < time(13, 0):
            return "London"
        if time(13, 0) <= utc_time < time(16, 0):
            return "London/New York Overlap"
        if time(16, 0) <= utc_time < time(21, 0):
            return "New York"
        return None

    @classmethod
    def _missing_capabilities(
        cls,
        price_location: PriceLocation,
        displacement_present: bool | None,
    ) -> tuple[str, ...]:
        missing = list(cls._ALWAYS_UNAVAILABLE)
        if displacement_present is None:
            missing.insert(0, "displacement_detection")
        if price_location is PriceLocation.UNKNOWN:
            missing.insert(0, "dealing_range_price_location")
        return tuple(missing)

    @staticmethod
    def _displacement(
        event: BOSEvent | CHOCHEvent | None,
        timeframe: Timeframe | None,
    ) -> tuple[
        bool | None,
        TrendDirection | None,
        Timeframe | None,
        float | None,
    ]:
        if event is None or timeframe is None:
            return None, None, None, None

        atr_multiple = float(event.break_atr_multiple)
        if not isfinite(atr_multiple) or atr_multiple <= 0.0:
            return None, None, None, None

        return (
            atr_multiple >= 1.0,
            event.direction,
            timeframe,
            atr_multiple,
        )

    @classmethod
    def _latest_event(
        cls,
        structures: dict[Timeframe, StructureState | None],
        *,
        observation_timestamp: datetime,
    ) -> tuple[BOSEvent | CHOCHEvent | None, Timeframe | None]:
        candidates: list[tuple[BOSEvent | CHOCHEvent, Timeframe]] = []
        for timeframe in cls._STRUCTURE_PRIORITY:
            structure = structures[timeframe]
            if structure is None:
                continue
            for event in (structure.last_bos, structure.last_choch):
                if cls._event_is_known(
                    event,
                    structure=structure,
                    observation_timestamp=observation_timestamp,
                ):
                    candidates.append((event, timeframe))
        if not candidates:
            return None, None
        return max(candidates, key=lambda item: item[0].timestamp)

    @classmethod
    def _latest_sweep(
        cls,
        structures: dict[Timeframe, StructureState | None],
        *,
        observation_timestamp: datetime,
    ) -> tuple[LiquiditySweepEvent | None, Timeframe | None]:
        candidates: list[tuple[LiquiditySweepEvent, Timeframe]] = []
        for timeframe in cls._STRUCTURE_PRIORITY:
            structure = structures[timeframe]
            if structure is None:
                continue
            sweep = structure.last_liquidity
            if cls._sweep_is_known(
                sweep,
                structure=structure,
                observation_timestamp=observation_timestamp,
            ):
                candidates.append((sweep, timeframe))
        if not candidates:
            return None, None
        return max(candidates, key=lambda item: item[0].timestamp)

    @classmethod
    def _opposing_liquidity(
        cls,
        *,
        structure: StructureState | None,
        timeframe: Timeframe | None,
        direction: TrendDirection | None,
        current_price: float,
        observation_timestamp: datetime,
    ) -> tuple[LiquidityLevel | None, Timeframe | None]:
        if structure is None or timeframe is None or direction is None:
            return None, None
        levels = tuple(
            level
            for level in structure.tracked_liquidity_levels
            if cls._liquidity_level_is_known(
                level,
                structure=structure,
                observation_timestamp=observation_timestamp,
            )
        )
        if direction is TrendDirection.BULLISH:
            eligible = tuple(
                level
                for level in levels
                if level.is_buy_side and level.price > current_price
            )
            selected = min(eligible, key=lambda level: level.price, default=None)
            return selected, timeframe if selected else None
        if direction is TrendDirection.BEARISH:
            eligible = tuple(
                level
                for level in levels
                if not level.is_buy_side and level.price < current_price
            )
            selected = max(eligible, key=lambda level: level.price, default=None)
            return selected, timeframe if selected else None
        return None, None

    @classmethod
    def _latest_fair_value_gap(
        cls,
        states: dict[Timeframe, TimeframeState],
        *,
        observation_timestamp: datetime,
    ) -> tuple[FairValueGap | FairValueGapCandidate | None, Timeframe | None]:
        candidates: list[
            tuple[FairValueGap | FairValueGapCandidate, Timeframe]
        ] = []
        for timeframe in cls._PRICE_ACTION_PRIORITY:
            state = states[timeframe]
            if not cls._state_is_known(state, observation_timestamp):
                continue
            price_action = cls._price_action(state)
            if price_action is None or not cls._timestamp_is_known(
                price_action.timestamp,
                observation_timestamp,
            ):
                continue
            gap = price_action.last_fair_value_gap
            if cls._fair_value_gap_is_known(
                gap,
                observation_timestamp=observation_timestamp,
            ):
                candidates.append((gap, timeframe))
        if not candidates:
            return None, None
        return max(candidates, key=lambda item: item[0].timestamp)

    @classmethod
    def _latest_order_block(
        cls,
        states: dict[Timeframe, TimeframeState],
        *,
        structures: dict[Timeframe, StructureState | None],
        observation_timestamp: datetime,
    ) -> tuple[OrderBlock | None, Timeframe | None]:
        candidates: list[tuple[OrderBlock, Timeframe]] = []
        for timeframe in cls._PRICE_ACTION_PRIORITY:
            state = states[timeframe]
            structure = structures[timeframe]
            if structure is None or not cls._state_is_known(
                state,
                observation_timestamp,
            ):
                continue
            price_action = cls._price_action(state)
            if price_action is None or not cls._timestamp_is_known(
                price_action.timestamp,
                observation_timestamp,
            ):
                continue
            block = price_action.last_order_block
            if cls._order_block_is_known(
                block,
                structure=structure,
                observation_timestamp=observation_timestamp,
            ):
                candidates.append((block, timeframe))
        if not candidates:
            return None, None
        return max(candidates, key=lambda item: item[0].timestamp)

    @staticmethod
    def _state_is_known(
        state: TimeframeState,
        observation_timestamp: datetime,
    ) -> bool:
        return (
            state.timestamp is None
            or SMCICTContextBuilder._timestamp_is_known(
                state.timestamp,
                observation_timestamp,
            )
        )

    @staticmethod
    def _timestamp_is_known(
        timestamp: object,
        observation_timestamp: datetime,
    ) -> bool:
        return (
            isinstance(timestamp, datetime)
            and timestamp.tzinfo is not None
            and timestamp.utcoffset() is not None
            and timestamp <= observation_timestamp
        )

    @classmethod
    def _swing_is_known(
        cls,
        swing,
        *,
        structure: StructureState,
        observation_timestamp: datetime,
    ) -> bool:
        return (
            swing is not None
            and cls._timestamp_is_known(swing.timestamp, observation_timestamp)
            and swing.confirmation_index <= structure.current_bar_index
        )

    @classmethod
    def _event_is_known(
        cls,
        event: BOSEvent | CHOCHEvent | None,
        *,
        structure: StructureState,
        observation_timestamp: datetime,
    ) -> bool:
        return (
            event is not None
            and cls._timestamp_is_known(event.timestamp, observation_timestamp)
            and event.confirmation_index <= structure.current_bar_index
            and cls._swing_is_known(
                event.swing_point,
                structure=structure,
                observation_timestamp=observation_timestamp,
            )
        )

    @classmethod
    def _liquidity_level_is_known(
        cls,
        level: LiquidityLevel,
        *,
        structure: StructureState,
        observation_timestamp: datetime,
    ) -> bool:
        return (
            isinstance(level, LiquidityLevel)
            and cls._timestamp_is_known(level.timestamp, observation_timestamp)
            and cls._swing_is_known(
                level.swing_point,
                structure=structure,
                observation_timestamp=observation_timestamp,
            )
        )

    @classmethod
    def _sweep_is_known(
        cls,
        sweep: LiquiditySweepEvent | None,
        *,
        structure: StructureState,
        observation_timestamp: datetime,
    ) -> bool:
        return (
            sweep is not None
            and cls._timestamp_is_known(sweep.timestamp, observation_timestamp)
            and sweep.confirmation_index <= structure.current_bar_index
            and cls._liquidity_level_is_known(
                sweep.liquidity_level,
                structure=structure,
                observation_timestamp=observation_timestamp,
            )
        )

    @classmethod
    def _fair_value_gap_is_known(
        cls,
        gap: FairValueGap | FairValueGapCandidate | None,
        *,
        observation_timestamp: datetime,
    ) -> bool:
        if gap is None:
            return False
        bars = (gap.first_bar, gap.middle_bar, gap.third_bar)
        return (
            cls._timestamp_is_known(gap.timestamp, observation_timestamp)
            and all(
                cls._timestamp_is_known(bar.timestamp, observation_timestamp)
                for bar in bars
            )
            and bars[0].timestamp < bars[1].timestamp < bars[2].timestamp
        )

    @classmethod
    def _order_block_is_known(
        cls,
        block: OrderBlock | None,
        *,
        structure: StructureState,
        observation_timestamp: datetime,
    ) -> bool:
        if block is None:
            return False
        return (
            cls._timestamp_is_known(block.timestamp, observation_timestamp)
            and block.confirmation_index <= structure.current_bar_index
            and cls._swing_is_known(
                block.origin_swing,
                structure=structure,
                observation_timestamp=observation_timestamp,
            )
            and cls._event_is_known(
                block.trigger_break,
                structure=structure,
                observation_timestamp=observation_timestamp,
            )
            and (
                block.trigger_liquidity is None
                or cls._sweep_is_known(
                    block.trigger_liquidity,
                    structure=structure,
                    observation_timestamp=observation_timestamp,
                )
            )
        )
