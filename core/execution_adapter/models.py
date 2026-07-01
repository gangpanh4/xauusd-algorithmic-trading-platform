"""
Execution Adapter models.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.mt5_execution.models import OrderSide, OrderRequest
from core.trading_pipeline.models import PipelineResult


@dataclass(frozen=True)
class ExecutionPlan:
    """
    Strategy-level execution plan.
    """

    symbol: str
    side: OrderSide
    volume: float
    account_balance: float
    stop_loss_distance: float
    risk_reward_ratio: float
    comment: str


@dataclass(frozen=True)
class ExecutionRequest:
    """
    Adapter output.

    Supports both the new ExecutionPlan API and the legacy
    OrderRequest API used by older tests.
    """

    pipeline_result: PipelineResult
    execution_plan: ExecutionPlan

    @property
    def order_request(self) -> OrderRequest:
        """
        Backward-compatible OrderRequest view.
        """

        return OrderRequest(
            symbol=self.execution_plan.symbol,
            side=self.execution_plan.side,
            volume=self.execution_plan.volume,
            entry_price=0.0,
            stop_loss=0.0,
            take_profit=0.0,
            comment=self.execution_plan.comment,
        )