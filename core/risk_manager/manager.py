"""
Risk Management Engine.
"""

from __future__ import annotations

from datetime import datetime, UTC

from core.signal_generator.models import SignalType, TradingSignal

from .config import RiskManagerConfig
from .models import (
    RiskDecision,
    TradePlan,
)
from .position_sizer import PositionSizer
from .rules import approve_trade
from .state import RiskManagerState


class RiskManager:
    """
    Evaluates trading signals and produces TradePlan objects.

    Responsibility:
        Convert signal + entry price into a fully defined execution plan.
    """

    def __init__(
        self,
        config: RiskManagerConfig,
    ) -> None:

        self.config = config
        self.state = RiskManagerState()

    def evaluate_signal(
        self,
        signal: TradingSignal,
        *,
        entry_price: float,
        account_balance: float,
        stop_loss_distance: float,
        pip_value: float,
    ) -> TradePlan:
        """
        Convert a trading signal into a complete TradePlan.

        IMPORTANT:
        SL/TP must be stored as ACTUAL PRICES, not distances.
        """

        direction = getattr(
            signal,
            "direction",
            getattr(signal, "signal", SignalType.HOLD),
        )

        # --------------------------------------------------
        # HOLD case
        # --------------------------------------------------
        if direction == SignalType.HOLD:
            trade_plan = TradePlan(
                timestamp=datetime.now(UTC),
                signal=signal,
                decision=RiskDecision.SKIP,
                entry_price=0.0,
                position_size=0.0,
                stop_loss=0.0,
                take_profit=0.0,
                risk_percent=0.0,
                reward_percent=0.0,
                risk_reward_ratio=0.0,
                reason="No trading opportunity.",
            )

            self._update_state(trade_plan)
            return trade_plan

        # --------------------------------------------------
        # Balance source
        # --------------------------------------------------
        working_balance = (
            self.config.virtual_balance
            if self.config.use_virtual_balance
            else account_balance
        )

        # --------------------------------------------------
        # Position sizing
        # --------------------------------------------------
        if self.config.lot_sizing_mode.name == "FIXED":
            position_size = self.config.fixed_lot_size

        elif self.config.lot_sizing_mode.name == "DYNAMIC":
            multiplier = max(1.0, working_balance / 100.0)
            position_size = round(
                self.config.fixed_lot_size * multiplier,
                2,
            )

        else:
            position_size = PositionSizer.calculate_position_size(
                account_balance=working_balance,
                risk_percent=self.config.risk_percent / 100.0,
                stop_loss_distance=stop_loss_distance,
                pip_value=pip_value,
            )

        # Safety limits
        position_size = max(self.config.minimum_position_size, position_size)
        position_size = min(self.config.maximum_position_size, position_size)

        risk_reward_ratio = self.config.minimum_risk_reward_ratio

        approved, reason = approve_trade(
            position_size=position_size,
            risk_reward_ratio=risk_reward_ratio,
            config=self.config,
        )

        decision = (
            RiskDecision.APPROVE
            if approved
            else RiskDecision.REJECT
        )

        # --------------------------------------------------
        # Convert DISTANCE → PRICE (IMPORTANT CHANGE)
        # --------------------------------------------------
        if signal.signal == SignalType.BUY:
            stop_loss = entry_price - stop_loss_distance
            take_profit = entry_price + (stop_loss_distance * risk_reward_ratio)

        else:
            stop_loss = entry_price + stop_loss_distance
            take_profit = entry_price - (stop_loss_distance * risk_reward_ratio)

        trade_plan = TradePlan(
            timestamp=datetime.now(UTC),
            signal=signal,
            decision=decision,
            entry_price=entry_price,
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_percent=self.config.risk_percent,
            reward_percent=self.config.risk_percent * risk_reward_ratio,
            risk_reward_ratio=risk_reward_ratio,
            reason=reason,
        )

        self._update_state(trade_plan)
        return trade_plan

    def _update_state(
        self,
        trade_plan: TradePlan,
    ) -> None:

        self.state.initialized = True
        self.state.last_trade_plan = trade_plan
        self.state.last_decision_time = trade_plan.timestamp
        self.state.processed_signal_count += 1

        if trade_plan.decision == RiskDecision.APPROVE:
            self.state.approved_trade_count += 1

        elif trade_plan.decision == RiskDecision.REJECT:
            self.state.rejected_trade_count += 1

        elif trade_plan.decision == RiskDecision.SKIP:
            self.state.skipped_trade_count += 1