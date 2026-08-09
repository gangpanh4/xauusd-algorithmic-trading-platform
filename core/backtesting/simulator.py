"""Deterministic historical trade execution simulation.

The simulator supports both a compatibility batch API and an incremental
one-completed-bar lifecycle.  A signal observed on ``observation_bar`` is
filled at the open of the next completed bar, so historical execution never
uses an unavailable signal-candle close.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from math import isfinite
from typing import Any

from core.execution_economics.models import (
    BacktestExecutionTrace,
    ExecutionEconomicsProfile,
)
from core.execution_economics.pricing import recenter_exit_levels
from core.regime_detector.models import MarketBar
from core.risk_manager.models import RiskDecision, TradePlan
from core.signal_generator.models import SignalDirection

from .models import BacktestTrade, ExitReason, TradeOutcome


class ExecutionPolicy(Enum):
    """Resolve candles that contain both stop-loss and take-profit levels."""

    CONSERVATIVE = "CONSERVATIVE"
    OPTIMISTIC = "OPTIMISTIC"


class SimulationPhase(Enum):
    """Lifecycle phase for an incremental historical trade simulation."""

    PENDING_ENTRY = "PENDING_ENTRY"
    OPEN = "OPEN"
    CLOSED = "CLOSED"


@dataclass(frozen=True, slots=True)
class SimulationEconomics:
    """Broker-independent execution economics for one simulated trade.

    ``commission_per_trade`` and ``commission_per_lot`` are interpreted as
    round-trip account-currency costs. Spread is charged once per round trip.
    Slippage is applied adversely to market entry and to stop-loss or
    end-of-data exits; take-profit orders are filled at their limit price.
    """

    tick_size: float
    tick_value_per_lot: float
    spread_points: float = 0.0
    slippage_points: float = 0.0
    commission_per_trade: float = 0.0
    commission_per_lot: float = 0.0


@dataclass(slots=True)
class SimulationState:
    """Mutable price and excursion state for one filled simulated trade."""

    entry_price: float
    is_buy: bool
    original_stop_loss: float
    take_profit: float
    current_stop_loss: float

    holding_bars: int = 0
    highest_price: float = 0.0
    lowest_price: float = 0.0
    max_favorable_excursion: float = 0.0
    max_adverse_excursion: float = 0.0
    breakeven_triggered: bool = False
    breakeven_pending: bool = False
    lifecycle_events: list[str] = field(default_factory=list)


@dataclass(slots=True)
class IncrementalTradeSimulation:
    """State owned by the one-bar-at-a-time simulation API.

    A simulation starts in :attr:`SimulationPhase.PENDING_ENTRY`. The first
    completed bar after ``observation_bar`` supplies the market-entry fill and
    is also evaluated for stop/target interaction. The object then remains
    open until :meth:`TradeSimulator.process_bar` returns a completed trade or
    :meth:`TradeSimulator.finalize_at_end_of_data` is called.
    """

    trade_plan: TradePlan
    observation_bar: MarketBar
    direction: SignalDirection
    phase: SimulationPhase = SimulationPhase.PENDING_ENTRY

    fill_bar: MarketBar | None = None
    last_bar: MarketBar | None = None
    economics: SimulationEconomics | None = None
    used_legacy_economics: bool = False
    reference_entry_price: float | None = None
    effective_stop_loss: float | None = None
    effective_take_profit: float | None = None
    state: SimulationState | None = None
    completed_trade: BacktestTrade | None = None

    @property
    def is_pending_entry(self) -> bool:
        return self.phase is SimulationPhase.PENDING_ENTRY

    @property
    def is_open(self) -> bool:
        return self.phase is SimulationPhase.OPEN

    @property
    def is_closed(self) -> bool:
        return self.phase is SimulationPhase.CLOSED


@dataclass(frozen=True, slots=True)
class _ExitDecision:
    reference_price: float
    reason: ExitReason
    applies_exit_slippage: bool
    gap_exit: bool = False


class TradeSimulator:
    """Execute approved trade plans against completed historical bars.

    ``begin`` / ``process_bar`` / ``finalize_at_end_of_data`` form the
    production incremental API. The original ``simulate`` method remains a
    compatibility wrapper and delegates to that same lifecycle, ensuring the
    batch and incremental paths have identical execution semantics.
    """

    _PRICE_EPSILON = 1e-12

    def __init__(
        self,
        execution_policy: ExecutionPolicy = ExecutionPolicy.CONSERVATIVE,
        *,
        tick_size: float | None = None,
        tick_value_per_lot: float | None = None,
        spread_points: float | None = None,
        slippage_points: float | None = None,
        commission_per_trade: float | None = None,
        commission_per_lot: float | None = None,
        execution_profile: ExecutionEconomicsProfile | None = None,
        breakeven_enabled: bool = True,
        recenter_exit_levels_on_fill: bool = True,
    ) -> None:
        if not isinstance(execution_policy, ExecutionPolicy):
            raise TypeError("execution_policy must be an ExecutionPolicy")
        if not isinstance(breakeven_enabled, bool):
            raise TypeError("breakeven_enabled must be a bool")
        if not isinstance(recenter_exit_levels_on_fill, bool):
            raise TypeError("recenter_exit_levels_on_fill must be a bool")

        self.execution_policy = execution_policy
        self._tick_size = self._validate_optional_positive(
            tick_size,
            "tick_size",
        )
        self._tick_value_per_lot = self._validate_optional_positive(
            tick_value_per_lot,
            "tick_value_per_lot",
        )
        self._spread_points = self._validate_optional_nonnegative(
            spread_points,
            "spread_points",
        )
        self._slippage_points = self._validate_optional_nonnegative(
            slippage_points,
            "slippage_points",
        )
        self._commission_per_trade = self._validate_optional_nonnegative(
            commission_per_trade,
            "commission_per_trade",
        )
        self._commission_per_lot = self._validate_optional_nonnegative(
            commission_per_lot,
            "commission_per_lot",
        )
        if execution_profile is not None and not isinstance(
            execution_profile,
            ExecutionEconomicsProfile,
        ):
            raise TypeError(
                "execution_profile must be an ExecutionEconomicsProfile"
            )
        self.execution_profile = execution_profile
        self.breakeven_enabled = breakeven_enabled
        self.recenter_exit_levels_on_fill = recenter_exit_levels_on_fill

    def begin(
        self,
        trade_plan: TradePlan,
        observation_bar: MarketBar,
    ) -> IncrementalTradeSimulation:
        """Create a pending simulation without accessing any future bar."""

        direction = self._validate_trade_plan(trade_plan)
        if not isinstance(observation_bar, MarketBar):
            raise TypeError("observation_bar must be a MarketBar")
        self._validate_bar(observation_bar, "observation_bar")

        return IncrementalTradeSimulation(
            trade_plan=trade_plan,
            observation_bar=observation_bar,
            direction=direction,
        )

    def process_bar(
        self,
        simulation: IncrementalTradeSimulation,
        bar: MarketBar,
    ) -> BacktestTrade | None:
        """Advance one pending/open simulation with one completed OHLC bar.

        Returns the completed :class:`BacktestTrade` when the current bar exits
        the position; otherwise returns ``None``. Bars must be strictly
        chronological and each bar can be consumed only once.
        """

        self._validate_incremental_simulation(simulation)
        if simulation.is_closed:
            raise RuntimeError("cannot process a closed trade simulation")
        if not isinstance(bar, MarketBar):
            raise TypeError("bar must be a MarketBar")
        self._validate_bar(bar, "bar")

        previous_timestamp = (
            simulation.last_bar.timestamp
            if simulation.last_bar is not None
            else simulation.observation_bar.timestamp
        )
        if bar.timestamp <= previous_timestamp:
            raise ValueError(
                "bar timestamp must be strictly later than the previously "
                "observed simulation timestamp"
            )

        if simulation.is_pending_entry:
            self._open_on_bar(simulation=simulation, fill_bar=bar)

        state = simulation.state
        if state is None:
            raise RuntimeError("open simulation is missing price state")

        state.holding_bars += 1
        if state.breakeven_pending:
            state.current_stop_loss = state.entry_price
            state.breakeven_triggered = True
            state.breakeven_pending = False
            state.lifecycle_events.append("BREAKEVEN_ACTIVE")

        decision = self._resolve_bar_exit(state=state, bar=bar)
        self._update_excursions(state=state, bar=bar, decision=decision)
        simulation.last_bar = bar

        if decision is not None:
            if decision.gap_exit:
                state.lifecycle_events.append("GAP_EXIT")
            state.lifecycle_events.append(decision.reason.value)
            return self._complete_simulation(
                simulation=simulation,
                exit_bar=bar,
                exit_decision=decision,
            )

        if (
            self.breakeven_enabled
            and not state.breakeven_triggered
            and not state.breakeven_pending
            and self._should_activate_breakeven(state=state, bar=bar)
        ):
            state.breakeven_pending = True
            state.lifecycle_events.append("BREAKEVEN_PENDING")

        return None

    def finalize_at_end_of_data(
        self,
        simulation: IncrementalTradeSimulation,
    ) -> BacktestTrade:
        """Close an open simulation at the latest processed bar's close."""

        self._validate_incremental_simulation(simulation)
        if simulation.is_closed:
            completed = simulation.completed_trade
            if completed is None:
                raise RuntimeError("closed simulation is missing its trade")
            return completed
        if simulation.is_pending_entry:
            raise ValueError(
                "cannot finalize a pending trade before a market-entry bar"
            )
        if simulation.last_bar is None or simulation.state is None:
            raise RuntimeError("open simulation has no processed market bar")

        simulation.state.lifecycle_events.append(ExitReason.END_OF_DATA.value)
        return self._complete_simulation(
            simulation=simulation,
            exit_bar=simulation.last_bar,
            exit_decision=_ExitDecision(
                reference_price=float(simulation.last_bar.close),
                reason=ExitReason.END_OF_DATA,
                applies_exit_slippage=True,
            ),
        )

    def simulate(
        self,
        trade_plan: TradePlan,
        entry_bar: MarketBar,
        future_bars: list[MarketBar],
    ) -> BacktestTrade:
        """Compatibility wrapper around the incremental lifecycle."""

        self._validate_inputs(
            trade_plan=trade_plan,
            entry_bar=entry_bar,
            future_bars=future_bars,
        )
        simulation = self.begin(trade_plan, entry_bar)
        for bar in future_bars:
            completed = self.process_bar(simulation, bar)
            if completed is not None:
                return completed
        return self.finalize_at_end_of_data(simulation)

    def _open_on_bar(
        self,
        *,
        simulation: IncrementalTradeSimulation,
        fill_bar: MarketBar,
    ) -> None:
        trade_plan = simulation.trade_plan
        is_buy = simulation.direction is SignalDirection.BUY
        economics, used_legacy_economics = self._resolve_economics(
            trade_plan=trade_plan,
            fill_bar=fill_bar,
        )

        entry_slippage = economics.slippage_points * economics.tick_size
        reference_entry_price = float(fill_bar.open)
        entry_price = (
            reference_entry_price + entry_slippage
            if is_buy
            else reference_entry_price - entry_slippage
        )

        geometry = recenter_exit_levels(
            is_buy=is_buy,
            planned_entry_price=trade_plan.entry_price,
            planned_stop_loss=trade_plan.stop_loss,
            planned_take_profit=trade_plan.take_profit,
            reference_entry_price=reference_entry_price,
            normalize_to_tick=False,
        )
        if self.recenter_exit_levels_on_fill:
            stop_loss = geometry.stop_loss
            take_profit = geometry.take_profit
        else:
            stop_loss = float(trade_plan.stop_loss)
            take_profit = float(trade_plan.take_profit)

        self._validate_exit_side(
            is_buy=is_buy,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        simulation.fill_bar = fill_bar
        simulation.economics = economics
        simulation.used_legacy_economics = used_legacy_economics
        simulation.reference_entry_price = reference_entry_price
        simulation.effective_stop_loss = stop_loss
        simulation.effective_take_profit = take_profit
        simulation.state = SimulationState(
            entry_price=entry_price,
            is_buy=is_buy,
            original_stop_loss=stop_loss,
            take_profit=take_profit,
            current_stop_loss=stop_loss,
            highest_price=entry_price,
            lowest_price=entry_price,
            lifecycle_events=["ENTRY_NEXT_BAR_OPEN"],
        )
        simulation.phase = SimulationPhase.OPEN

    def _complete_simulation(
        self,
        *,
        simulation: IncrementalTradeSimulation,
        exit_bar: MarketBar,
        exit_decision: _ExitDecision,
    ) -> BacktestTrade:
        trade_plan = simulation.trade_plan
        state = simulation.state
        economics = simulation.economics
        fill_bar = simulation.fill_bar
        reference_entry_price = simulation.reference_entry_price
        stop_loss = simulation.effective_stop_loss
        take_profit = simulation.effective_take_profit

        if (
            state is None
            or economics is None
            or fill_bar is None
            or reference_entry_price is None
            or stop_loss is None
            or take_profit is None
        ):
            raise RuntimeError("simulation is missing required execution state")

        exit_price = self._apply_exit_slippage(
            reference_price=exit_decision.reference_price,
            is_buy=state.is_buy,
            economics=economics,
            apply_slippage=exit_decision.applies_exit_slippage,
        )
        gross_profit = self._calculate_gross_profit(
            is_buy=state.is_buy,
            entry_price=state.entry_price,
            exit_price=exit_price,
            position_size=trade_plan.position_size,
            economics=economics,
        )
        spread_cost = (
            economics.spread_points
            * economics.tick_value_per_lot
            * trade_plan.position_size
        )
        commission = (
            economics.commission_per_trade
            + economics.commission_per_lot * trade_plan.position_size
        )
        net_profit = gross_profit - spread_cost - commission
        outcome = self._classify_outcome(
            net_profit=net_profit,
            economics=economics,
            position_size=trade_plan.position_size,
        )

        original_risk_distance = abs(state.entry_price - stop_loss)
        realized_price_movement = (
            exit_price - state.entry_price
            if state.is_buy
            else state.entry_price - exit_price
        )
        gross_r_multiple = (
            realized_price_movement / original_risk_distance
            if original_risk_distance > 0.0
            else 0.0
        )
        monetary_risk = self._calculate_monetary_risk(
            risk_distance=original_risk_distance,
            position_size=trade_plan.position_size,
            economics=economics,
        )
        net_r_multiple = (
            net_profit / monetary_risk if monetary_risk > 0.0 else 0.0
        )
        execution_trace = (
            BacktestExecutionTrace(
                observation_timestamp=simulation.observation_bar.timestamp,
                decision_available_at=(
                    simulation.observation_bar.timestamp
                    + timedelta(minutes=5)
                ),
                actual_entry_timestamp=fill_bar.timestamp,
                planned_entry_price=trade_plan.entry_price,
                reference_entry_price=reference_entry_price,
                simulated_fill_price=state.entry_price,
                effective_stop_loss=stop_loss,
                effective_take_profit=take_profit,
                position_size=trade_plan.position_size,
                execution_profile=self.execution_profile,
            )
            if self.execution_profile is not None
            else None
        )

        metadata: dict[str, Any] = {
            **trade_plan.metadata,
            "probability": trade_plan.probability,
            "confidence": trade_plan.confidence,
            "feature_count": trade_plan.feature_count,
            "evidence_count": trade_plan.evidence_count,
            "regime": trade_plan.regime,
            "signal_observation_time": (
                simulation.observation_bar.timestamp.isoformat()
            ),
            "reference_entry_price": reference_entry_price,
            "actual_entry_price": state.entry_price,
            "planned_entry_price": trade_plan.entry_price,
            "effective_stop_loss": stop_loss,
            "effective_take_profit": take_profit,
            "tick_size": economics.tick_size,
            "tick_value_per_lot": economics.tick_value_per_lot,
            "spread_points": economics.spread_points,
            "slippage_points": economics.slippage_points,
            "commission_per_trade": economics.commission_per_trade,
            "commission_per_lot": economics.commission_per_lot,
            "slippage_cost": self._calculate_slippage_cost(
                is_buy=state.is_buy,
                reference_entry_price=reference_entry_price,
                actual_entry_price=state.entry_price,
                reference_exit_price=exit_decision.reference_price,
                actual_exit_price=exit_price,
                position_size=trade_plan.position_size,
                economics=economics,
            ),
            "planned_risk_reward_ratio": trade_plan.risk_reward_ratio,
            "realized_gross_r_multiple": gross_r_multiple,
            "realized_net_r_multiple": net_r_multiple,
            # Backward-compatible metadata aliases.
            "gross_r_multiple": gross_r_multiple,
            "net_r_multiple": net_r_multiple,
            "monetary_risk": monetary_risk,
            "same_bar_exit": fill_bar.timestamp == exit_bar.timestamp,
            "execution_policy": self.execution_policy.value,
            "entry_policy": "NEXT_BAR_OPEN",
            "exit_levels_recentered": self.recenter_exit_levels_on_fill,
            "legacy_unit_economics_fallback": (
                simulation.used_legacy_economics
            ),
            "simulation_mode": "INCREMENTAL_BAR_LIFECYCLE",
            "historical_spread_field_used": False,
        }
        if execution_trace is not None:
            metadata["execution_economics_trace"] = execution_trace.to_dict()

        trade = BacktestTrade(
            entry_time=fill_bar.timestamp,
            exit_time=exit_bar.timestamp,
            direction=simulation.direction.value,
            entry_price=state.entry_price,
            exit_price=exit_price,
            position_size=trade_plan.position_size,
            spread_cost=spread_cost,
            commission=commission,
            gross_profit=gross_profit,
            net_profit=net_profit,
            outcome=outcome,
            exit_reason=exit_decision.reason,
            holding_bars=state.holding_bars,
            holding_time=exit_bar.timestamp - fill_bar.timestamp,
            risk_reward=trade_plan.risk_reward_ratio,
            max_favorable_excursion=state.max_favorable_excursion,
            max_adverse_excursion=state.max_adverse_excursion,
            highest_price=state.highest_price,
            lowest_price=state.lowest_price,
            breakeven_triggered=state.breakeven_triggered,
            trailing_stop_triggered=False,
            partial_exit_taken=False,
            lifecycle_events=tuple(state.lifecycle_events),
            metadata=metadata,
        )
        simulation.completed_trade = trade
        simulation.phase = SimulationPhase.CLOSED
        return trade

    def _validate_trade_plan(self, trade_plan: TradePlan) -> SignalDirection:
        if not isinstance(trade_plan, TradePlan):
            raise TypeError("trade_plan must be a TradePlan")
        if trade_plan.decision is not RiskDecision.APPROVE:
            raise ValueError("only approved trade plans can be simulated")

        self._require_positive(trade_plan.position_size, "position_size")
        planned_entry = self._require_positive(
            trade_plan.entry_price,
            "entry_price",
        )
        planned_stop = self._require_positive(
            trade_plan.stop_loss,
            "stop_loss",
        )
        planned_target = self._require_positive(
            trade_plan.take_profit,
            "take_profit",
        )

        signal = trade_plan.signal
        direction = getattr(signal, "direction", getattr(signal, "signal", None))
        if direction not in (SignalDirection.BUY, SignalDirection.SELL):
            raise ValueError(
                "trade plan must contain an explicit BUY or SELL signal"
            )
        self._validate_exit_side(
            is_buy=direction is SignalDirection.BUY,
            entry_price=planned_entry,
            stop_loss=planned_stop,
            take_profit=planned_target,
        )
        return direction

    @staticmethod
    def _validate_incremental_simulation(
        simulation: IncrementalTradeSimulation,
    ) -> None:
        if not isinstance(simulation, IncrementalTradeSimulation):
            raise TypeError(
                "simulation must be an IncrementalTradeSimulation"
            )

    def _resolve_bar_exit(
        self,
        *,
        state: SimulationState,
        bar: MarketBar,
    ) -> _ExitDecision | None:
        """Resolve gap behavior before ambiguous intrabar level touches."""

        bar_open = float(bar.open)
        if state.is_buy:
            if bar_open <= state.current_stop_loss:
                return _ExitDecision(
                    reference_price=bar_open,
                    reason=ExitReason.STOP_LOSS,
                    applies_exit_slippage=True,
                    gap_exit=True,
                )
            if bar_open >= state.take_profit:
                return _ExitDecision(
                    reference_price=state.take_profit,
                    reason=ExitReason.TAKE_PROFIT,
                    applies_exit_slippage=False,
                    gap_exit=True,
                )

            stop_hit = bar.low <= state.current_stop_loss
            target_hit = bar.high >= state.take_profit
        else:
            if bar_open >= state.current_stop_loss:
                return _ExitDecision(
                    reference_price=bar_open,
                    reason=ExitReason.STOP_LOSS,
                    applies_exit_slippage=True,
                    gap_exit=True,
                )
            if bar_open <= state.take_profit:
                return _ExitDecision(
                    reference_price=state.take_profit,
                    reason=ExitReason.TAKE_PROFIT,
                    applies_exit_slippage=False,
                    gap_exit=True,
                )

            stop_hit = bar.high >= state.current_stop_loss
            target_hit = bar.low <= state.take_profit

        if stop_hit and target_hit:
            if self.execution_policy is ExecutionPolicy.CONSERVATIVE:
                return _ExitDecision(
                    reference_price=state.current_stop_loss,
                    reason=ExitReason.STOP_LOSS,
                    applies_exit_slippage=True,
                )
            return _ExitDecision(
                reference_price=state.take_profit,
                reason=ExitReason.TAKE_PROFIT,
                applies_exit_slippage=False,
            )

        if stop_hit:
            return _ExitDecision(
                reference_price=state.current_stop_loss,
                reason=ExitReason.STOP_LOSS,
                applies_exit_slippage=True,
            )
        if target_hit:
            return _ExitDecision(
                reference_price=state.take_profit,
                reason=ExitReason.TAKE_PROFIT,
                applies_exit_slippage=False,
            )
        return None

    def _update_excursions(
        self,
        *,
        state: SimulationState,
        bar: MarketBar,
        decision: _ExitDecision | None,
    ) -> None:
        """Update MFE/MAE without using post-exit extremes from the exit bar."""

        if decision is None:
            observed_high = float(bar.high)
            observed_low = float(bar.low)
        elif decision.gap_exit:
            observed_high = float(bar.open)
            observed_low = float(bar.open)
        elif decision.reason is ExitReason.STOP_LOSS:
            if state.is_buy:
                observed_high = max(float(bar.open), state.entry_price)
                observed_low = decision.reference_price
            else:
                observed_high = decision.reference_price
                observed_low = min(float(bar.open), state.entry_price)
        else:
            if state.is_buy:
                observed_high = decision.reference_price
                observed_low = min(float(bar.open), state.entry_price)
            else:
                observed_high = max(float(bar.open), state.entry_price)
                observed_low = decision.reference_price

        state.highest_price = max(state.highest_price, observed_high)
        state.lowest_price = min(state.lowest_price, observed_low)

        if state.is_buy:
            state.max_favorable_excursion = max(
                state.max_favorable_excursion,
                state.highest_price - state.entry_price,
            )
            state.max_adverse_excursion = max(
                state.max_adverse_excursion,
                state.entry_price - state.lowest_price,
            )
        else:
            state.max_favorable_excursion = max(
                state.max_favorable_excursion,
                state.entry_price - state.lowest_price,
            )
            state.max_adverse_excursion = max(
                state.max_adverse_excursion,
                state.highest_price - state.entry_price,
            )

    def _should_activate_breakeven(
        self,
        *,
        state: SimulationState,
        bar: MarketBar,
    ) -> bool:
        risk = abs(state.entry_price - state.original_stop_loss)
        if risk <= 0.0:
            return False
        if state.is_buy:
            return bar.high >= state.entry_price + risk
        return bar.low <= state.entry_price - risk

    def _resolve_economics(
        self,
        *,
        trade_plan: TradePlan,
        fill_bar: MarketBar,
    ) -> tuple[SimulationEconomics, bool]:
        del fill_bar

        if self.execution_profile is not None:
            instrument = self.execution_profile.instrument
            costs = self.execution_profile.costs
            return (
                SimulationEconomics(
                    tick_size=instrument.tick_size,
                    tick_value_per_lot=instrument.tick_value_per_lot,
                    spread_points=costs.spread_points,
                    slippage_points=costs.slippage_points,
                    commission_per_trade=costs.commission_per_trade,
                    commission_per_lot=costs.commission_per_lot,
                ),
                False,
            )

        metadata = trade_plan.metadata

        tick_size_value = self._first_defined(
            self._tick_size,
            metadata.get("tick_size"),
            1.0,
        )
        tick_value_value = self._first_defined(
            self._tick_value_per_lot,
            metadata.get("tick_value_per_lot"),
            1.0,
        )
        used_legacy_economics = (
            self._tick_size is None
            and "tick_size" not in metadata
            or self._tick_value_per_lot is None
            and "tick_value_per_lot" not in metadata
        )

        economics = SimulationEconomics(
            tick_size=self._require_positive(
                tick_size_value,
                "tick_size",
            ),
            tick_value_per_lot=self._require_positive(
                tick_value_value,
                "tick_value_per_lot",
            ),
            spread_points=self._require_nonnegative(
                self._first_defined(
                    self._spread_points,
                    metadata.get("spread_points"),
                    0.0,
                ),
                "spread_points",
            ),
            slippage_points=self._require_nonnegative(
                self._first_defined(
                    self._slippage_points,
                    metadata.get("slippage_points"),
                    0.0,
                ),
                "slippage_points",
            ),
            commission_per_trade=self._require_nonnegative(
                self._first_defined(
                    self._commission_per_trade,
                    metadata.get("commission_per_trade"),
                    0.0,
                ),
                "commission_per_trade",
            ),
            commission_per_lot=self._require_nonnegative(
                self._first_defined(
                    self._commission_per_lot,
                    metadata.get("commission_per_lot"),
                    0.0,
                ),
                "commission_per_lot",
            ),
        )
        return economics, bool(used_legacy_economics)

    def _validate_inputs(
        self,
        *,
        trade_plan: TradePlan,
        entry_bar: MarketBar,
        future_bars: list[MarketBar],
    ) -> SignalDirection:
        self._validate_trade_plan(trade_plan)
        if not isinstance(entry_bar, MarketBar):
            raise TypeError("entry_bar must be a MarketBar")
        if not isinstance(future_bars, list):
            raise TypeError("future_bars must be a list")
        if not future_bars:
            raise ValueError("future_bars must contain at least one completed bar")

        self._validate_bar(entry_bar, "entry_bar")
        previous_timestamp = entry_bar.timestamp
        for index, bar in enumerate(future_bars):
            if not isinstance(bar, MarketBar):
                raise TypeError(f"future_bars[{index}] must be a MarketBar")
            self._validate_bar(bar, f"future_bars[{index}]")
            if bar.timestamp <= previous_timestamp:
                raise ValueError(
                    "future_bars must be strictly later than entry_bar and "
                    "strictly increasing"
                )
            previous_timestamp = bar.timestamp

        return self._validate_trade_plan(trade_plan)

    def _validate_exit_side(
        self,
        *,
        is_buy: bool,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
    ) -> None:
        if is_buy and not (stop_loss < entry_price < take_profit):
            raise ValueError(
                "BUY trade requires stop_loss < entry_price < take_profit"
            )
        if not is_buy and not (take_profit < entry_price < stop_loss):
            raise ValueError(
                "SELL trade requires take_profit < entry_price < stop_loss"
            )

    def _validate_bar(self, bar: MarketBar, name: str) -> None:
        timestamp = bar.timestamp
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError(f"{name}.timestamp must be timezone-aware")

        open_price = self._require_positive(bar.open, f"{name}.open")
        high_price = self._require_positive(bar.high, f"{name}.high")
        low_price = self._require_positive(bar.low, f"{name}.low")
        close_price = self._require_positive(bar.close, f"{name}.close")

        if high_price < max(open_price, close_price):
            raise ValueError(f"{name}.high is below its open or close")
        if low_price > min(open_price, close_price):
            raise ValueError(f"{name}.low is above its open or close")
        if high_price < low_price:
            raise ValueError(f"{name}.high must be greater than or equal to low")

    @staticmethod
    def _apply_exit_slippage(
        *,
        reference_price: float,
        is_buy: bool,
        economics: SimulationEconomics,
        apply_slippage: bool,
    ) -> float:
        if not apply_slippage:
            return reference_price
        price_slippage = economics.slippage_points * economics.tick_size
        return (
            reference_price - price_slippage
            if is_buy
            else reference_price + price_slippage
        )

    @staticmethod
    def _calculate_gross_profit(
        *,
        is_buy: bool,
        entry_price: float,
        exit_price: float,
        position_size: float,
        economics: SimulationEconomics,
    ) -> float:
        directional_move = (
            exit_price - entry_price
            if is_buy
            else entry_price - exit_price
        )
        ticks = directional_move / economics.tick_size
        return ticks * economics.tick_value_per_lot * position_size

    @staticmethod
    def _calculate_monetary_risk(
        *,
        risk_distance: float,
        position_size: float,
        economics: SimulationEconomics,
    ) -> float:
        risk_ticks = risk_distance / economics.tick_size
        return risk_ticks * economics.tick_value_per_lot * position_size

    @staticmethod
    def _calculate_slippage_cost(
        *,
        is_buy: bool,
        reference_entry_price: float,
        actual_entry_price: float,
        reference_exit_price: float,
        actual_exit_price: float,
        position_size: float,
        economics: SimulationEconomics,
    ) -> float:
        entry_adverse_move = (
            actual_entry_price - reference_entry_price
            if is_buy
            else reference_entry_price - actual_entry_price
        )
        exit_adverse_move = (
            reference_exit_price - actual_exit_price
            if is_buy
            else actual_exit_price - reference_exit_price
        )
        total_adverse_ticks = max(
            0.0,
            (entry_adverse_move + exit_adverse_move) / economics.tick_size,
        )
        return total_adverse_ticks * economics.tick_value_per_lot * position_size

    @staticmethod
    def _classify_outcome(
        *,
        net_profit: float,
        economics: SimulationEconomics,
        position_size: float,
    ) -> TradeOutcome:
        tolerance = max(
            TradeSimulator._PRICE_EPSILON,
            economics.tick_value_per_lot * position_size * 1e-9,
        )
        if abs(net_profit) <= tolerance:
            return TradeOutcome.BREAKEVEN
        if net_profit > 0.0:
            return TradeOutcome.WIN
        return TradeOutcome.LOSS

    @staticmethod
    def _first_defined(*values: Any) -> Any:
        for value in values:
            if value is not None:
                return value
        raise RuntimeError("at least one fallback value is required")

    @staticmethod
    def _validate_optional_positive(
        value: float | None,
        name: str,
    ) -> float | None:
        if value is None:
            return None
        return TradeSimulator._require_positive(value, name)

    @staticmethod
    def _validate_optional_nonnegative(
        value: float | None,
        name: str,
    ) -> float | None:
        if value is None:
            return None
        return TradeSimulator._require_nonnegative(value, name)

    @staticmethod
    def _require_positive(value: Any, name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be a real number")
        converted = float(value)
        if not isfinite(converted) or converted <= 0.0:
            raise ValueError(f"{name} must be finite and greater than zero")
        return converted

    @staticmethod
    def _require_nonnegative(value: Any, name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be a real number")
        converted = float(value)
        if not isfinite(converted) or converted < 0.0:
            raise ValueError(f"{name} must be finite and non-negative")
        return converted
