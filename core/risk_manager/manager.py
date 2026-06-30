"""
Risk Management Engine.
"""

from __future__ import annotations

from datetime import datetime, UTC

from core.signal_generator.models import TradingSignal

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
    Evaluates trading signals and produces trade plans.
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
        account_balance: float,
        stop_loss_distance: float,
        pip_value: float,
    ) -> TradePlan:
        """
        Convert a trading signal into a trade plan.
        """

        position_size = PositionSizer.calculate_position_size(
            account_balance=account_balance,
            risk_percent=self.config.max_risk_per_trade,
            stop_loss_distance=stop_loss_distance,
            pip_value=pip_value,
        )

        risk_reward_ratio = 2.0

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

        trade_plan = TradePlan(
            timestamp=datetime.now(UTC),
            signal=signal,
            decision=decision,
            position_size=position_size,
            stop_loss=stop_loss_distance,
            take_profit=stop_loss_distance * risk_reward_ratio,
            risk_percent=self.config.max_risk_per_trade,
            reward_percent=(
                self.config.max_risk_per_trade
                * risk_reward_ratio
            ),
            risk_reward_ratio=risk_reward_ratio,
            reason=reason,
        )

        self._update_state(trade_plan)

        return trade_plan

    def _update_state(
        self,
        trade_plan: TradePlan,
    ) -> None:
        """
        Update internal manager state.
        """

        self.state.initialized = True

        self.state.last_trade_plan = trade_plan

        self.state.last_decision_time = trade_plan.timestamp

        self.state.processed_signal_count += 1

        if trade_plan.decision == RiskDecision.APPROVE:
            self.state.approved_trade_count += 1
        else:
            self.state.rejected_trade_count += 1
