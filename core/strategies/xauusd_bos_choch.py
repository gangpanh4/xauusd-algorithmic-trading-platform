"""Observational XAUUSD BOS/CHOCH strategy.

The engine defines setup and entry semantics but is intentionally disconnected
from signal generation, risk approval, execution, and position management.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, timedelta
from uuid import uuid4

from core.market_structure.enums import MarketTrend, TrendDirection
from core.market_structure.models import (
    BOSEvent,
    CHOCHEvent,
    MarketStructureResult,
    StructureState,
    SwingPoint,
)
from core.multi_timeframe.enums import MarketBias, Timeframe
from core.multi_timeframe.models import TimeframeState

from .config import XAUUSDBOSCHOCHConfig
from .context import StrategyContext, StrategyObservation
from .enums import (
    EntryTriggerStatus,
    EntryTriggerType,
    PriceReferenceType,
    SetupDirection,
    SetupInvalidationReason,
    SetupStatus,
)
from .models import (
    CandidateTrade,
    EntryTrigger,
    PriceReference,
    TradingSetup,
)
from .state import XAUUSDBOSCHOCHState


class XAUUSDBOSCHOCHStrategy:
    """Create and observe one deterministic XAUUSD setup lifecycle."""

    def __init__(
        self,
        config: XAUUSDBOSCHOCHConfig | None = None,
    ) -> None:
        self.config = config or XAUUSDBOSCHOCHConfig()
        self.state = XAUUSDBOSCHOCHState()

    def reset(self) -> None:
        self.state.reset()

    def observe(self, context: StrategyContext) -> StrategyObservation:
        """Evaluate one completed M5 observation without authorizing a trade."""

        if not isinstance(context, StrategyContext):
            raise TypeError("context must be StrategyContext")
        if isinstance(context.current_bar_index, bool) or not isinstance(
            context.current_bar_index,
            int,
        ):
            raise TypeError("current_bar_index must be an integer")
        if context.current_bar_index < 0:
            raise ValueError("current_bar_index cannot be negative")

        timestamp = context.current_bar.timestamp.astimezone(UTC)
        self.state.processed_observations += 1

        active = self.state.active_setup
        if active is not None:
            terminal = self._terminal_transition(active, context)
            if terminal is not None:
                self.state.active_setup = terminal
                return self._publish(
                    timestamp=timestamp,
                    setup=terminal,
                    reason_code=terminal.status.value,
                    reason=(
                        "Setup expired."
                        if terminal.status is SetupStatus.EXPIRED
                        else "Setup invalidated by current market facts."
                    ),
                )

            trigger = self._entry_trigger(active, context)
            if trigger is not None:
                triggered_setup = replace(
                    active,
                    status=SetupStatus.TRIGGERED,
                )
                candidate = self._candidate_trade(
                    setup=triggered_setup,
                    trigger=trigger,
                )
                if candidate is None:
                    return self._publish(
                        timestamp=timestamp,
                        setup=active,
                        trigger=trigger,
                        reason_code="INVALID_TRADE_GEOMETRY",
                        reason=(
                            "Trigger confirmed, but target geometry is not "
                            "valid beyond the executable entry."
                        ),
                    )

                consumed = replace(
                    triggered_setup,
                    status=SetupStatus.CONSUMED,
                )
                self.state.active_setup = None
                self.state.consumed_setup_ids.add(consumed.setup_id)
                return self._publish(
                    timestamp=timestamp,
                    setup=consumed,
                    trigger=trigger,
                    candidate_trade=candidate,
                    reason_code="CANDIDATE_CREATED",
                    reason=(
                        "Confirmed M5 trigger converted the active M15 setup "
                        "into an observational candidate trade."
                    ),
                )

            return self._publish(
                timestamp=timestamp,
                setup=active,
                reason_code="SETUP_ACTIVE",
                reason="Valid setup remains active and is awaiting an M5 trigger.",
            )

        setup = self._detect_setup(context)
        if setup is None:
            return self._publish(
                timestamp=timestamp,
                reason_code="NO_SETUP",
                reason=(
                    "H4/H1 bias and M15 structural setup requirements are "
                    "not simultaneously satisfied."
                ),
            )

        self.state.active_setup = setup
        return self._publish(
            timestamp=timestamp,
            setup=setup,
            reason_code="SETUP_DETECTED",
            reason="A valid M15 setup was detected under aligned H4/H1 bias.",
        )

    def _detect_setup(
        self,
        context: StrategyContext,
    ) -> TradingSetup | None:
        direction = self._higher_timeframe_direction(context)
        if direction is None:
            return None

        m15 = context.multi_timeframe.m15
        structure = self._structure_state(m15)
        if structure is None:
            return None

        event = self._latest_directional_event(structure, direction)
        if event is None or event.age > self.config.maximum_structure_event_age_bars:
            return None

        invalidation_swing = self._invalidation_swing(structure, direction)
        target_swing = self._target_swing(
            context=context,
            direction=direction,
        )
        if invalidation_swing is None or target_swing is None:
            return None

        detected_at = context.current_bar.timestamp.astimezone(UTC)
        expires_at = detected_at + timedelta(
            minutes=15 * self.config.setup_expiry_bars
        )
        setup_direction = (
            SetupDirection.BUY
            if direction is TrendDirection.BULLISH
            else SetupDirection.SELL
        )

        invalidation = PriceReference(
            reference_type=PriceReferenceType.SETUP_INVALIDATION,
            price=invalidation_swing.price,
            timeframe=Timeframe.M15,
            source="M15 protected/last opposing swing",
        )
        target = PriceReference(
            reference_type=PriceReferenceType.HIGHER_TIMEFRAME_LEVEL,
            price=target_swing.price,
            timeframe=Timeframe.H1,
            source="H1 opposing structural level",
        )

        return TradingSetup(
            setup_id=uuid4(),
            strategy_id=self.config.strategy_id,
            direction=setup_direction,
            status=SetupStatus.ACTIVE,
            setup_timeframe=self.config.setup_timeframe,
            trigger_timeframe=self.config.trigger_timeframe,
            detected_at=detected_at,
            expires_at=expires_at,
            structure_state=structure,
            invalidation=invalidation,
            stop_reference=PriceReference(
                reference_type=PriceReferenceType.PROTECTED_SWING,
                price=invalidation_swing.price,
                timeframe=Timeframe.M15,
                source="M15 structural invalidation",
            ),
            target_references=(target,),
            required_conditions=(
                "H4 and H1 directional bias aligned",
                "M15 fresh BOS or CHOCH aligned with bias",
                "M15 structural invalidation level available",
                "H1 opposing target level available",
            ),
            metadata={
                "setup_event_type": event.break_type.name,
                "setup_event_confirmation_index": event.confirmation_index,
                "setup_event_age": event.age,
            },
        )

    def _terminal_transition(
        self,
        setup: TradingSetup,
        context: StrategyContext,
    ) -> TradingSetup | None:
        timestamp = context.current_bar.timestamp.astimezone(UTC)
        if timestamp >= setup.expires_at:
            return replace(
                setup,
                status=SetupStatus.EXPIRED,
                invalidation_reason=SetupInvalidationReason.SETUP_EXPIRED,
            )

        current_price = context.current_bar.close
        crossed = (
            current_price <= setup.invalidation.price
            if setup.direction is SetupDirection.BUY
            else current_price >= setup.invalidation.price
        )
        if crossed:
            return replace(
                setup,
                status=SetupStatus.INVALIDATED,
                invalidation_reason=(
                    SetupInvalidationReason.PRICE_CROSSED_INVALIDATION
                ),
            )

        direction = self._higher_timeframe_direction(context)
        expected = (
            TrendDirection.BULLISH
            if setup.direction is SetupDirection.BUY
            else TrendDirection.BEARISH
        )
        if direction is not expected:
            return replace(
                setup,
                status=SetupStatus.INVALIDATED,
                invalidation_reason=SetupInvalidationReason.BIAS_CHANGED,
            )
        return None

    def _entry_trigger(
        self,
        setup: TradingSetup,
        context: StrategyContext,
    ) -> EntryTrigger | None:
        structure = self._structure_state(context.multi_timeframe.m5)
        if structure is None:
            return None

        direction = (
            TrendDirection.BULLISH
            if setup.direction is SetupDirection.BUY
            else TrendDirection.BEARISH
        )
        event = self._latest_directional_event(structure, direction)
        if event is None:
            return None
        if event.confirmation_index != context.current_bar_index:
            return None
        if event.age != 0:
            return None

        return EntryTrigger(
            setup_id=setup.setup_id,
            trigger_type=(
                EntryTriggerType.BOS_CONFIRMATION
                if isinstance(event, BOSEvent)
                else EntryTriggerType.CHOCH_CONFIRMATION
            ),
            status=EntryTriggerStatus.CONFIRMED,
            timeframe=Timeframe.M5,
            observed_at=context.current_bar.timestamp,
            trigger_price=context.current_bar.close,
            confirmation_bar_index=context.current_bar_index,
            reason="Fresh M5 structural break aligned with active setup.",
            metadata={
                "event_confirmation_index": event.confirmation_index,
                "event_direction": event.direction.name,
            },
        )

    def _candidate_trade(
        self,
        *,
        setup: TradingSetup,
        trigger: EntryTrigger,
    ) -> CandidateTrade | None:
        target_prices = tuple(
            reference.price
            for reference in setup.target_references
            if (
                reference.price > trigger.trigger_price
                if setup.direction is SetupDirection.BUY
                else reference.price < trigger.trigger_price
            )
        )
        if not target_prices:
            return None

        risk = abs(trigger.trigger_price - setup.stop_reference.price)
        if risk <= 0.0:
            return None
        nearest_reward = min(
            abs(target - trigger.trigger_price)
            for target in target_prices
        )
        if nearest_reward / risk < self.config.minimum_target_reward_risk:
            return None

        return CandidateTrade(
            setup=setup,
            trigger=trigger,
            created_at=trigger.observed_at,
            entry_price=trigger.trigger_price,
            stop_loss_price=setup.stop_reference.price,
            take_profit_prices=target_prices,
            metadata={"observational_only": True},
        )

    @staticmethod
    def _structure_state(
        timeframe_state: TimeframeState,
    ) -> StructureState | None:
        result = timeframe_state.market_structure
        if not isinstance(result, MarketStructureResult):
            return None
        return result.structure_state

    @staticmethod
    def _latest_directional_event(
        structure: StructureState,
        direction: TrendDirection,
    ) -> BOSEvent | CHOCHEvent | None:
        events = tuple(
            event
            for event in (structure.last_bos, structure.last_choch)
            if event is not None and event.direction is direction
        )
        if not events:
            return None
        return max(events, key=lambda event: event.confirmation_index)

    @staticmethod
    def _invalidation_swing(
        structure: StructureState,
        direction: TrendDirection,
    ) -> SwingPoint | None:
        if direction is TrendDirection.BULLISH:
            return structure.protected_low or structure.last_low
        return structure.protected_high or structure.last_high

    def _target_swing(
        self,
        *,
        context: StrategyContext,
        direction: TrendDirection,
    ) -> SwingPoint | None:
        h1_structure = self._structure_state(context.multi_timeframe.h1)
        if h1_structure is None:
            return None
        if direction is TrendDirection.BULLISH:
            return h1_structure.last_high
        return h1_structure.last_low

    @staticmethod
    def _higher_timeframe_direction(
        context: StrategyContext,
    ) -> TrendDirection | None:
        h4_bias = context.multi_timeframe.h4.bias
        h1_bias = context.multi_timeframe.h1.bias
        if h4_bias is MarketBias.BULLISH and h1_bias is MarketBias.BULLISH:
            return TrendDirection.BULLISH
        if h4_bias is MarketBias.BEARISH and h1_bias is MarketBias.BEARISH:
            return TrendDirection.BEARISH
        return None

    def _publish(
        self,
        *,
        timestamp,
        setup: TradingSetup | None = None,
        trigger: EntryTrigger | None = None,
        candidate_trade: CandidateTrade | None = None,
        reason_code: str,
        reason: str,
    ) -> StrategyObservation:
        observation = StrategyObservation(
            timestamp=timestamp,
            setup=setup,
            trigger=trigger,
            candidate_trade=candidate_trade,
            reason_code=reason_code,
            reason=reason,
        )
        self.state.latest_observation = observation
        return observation
