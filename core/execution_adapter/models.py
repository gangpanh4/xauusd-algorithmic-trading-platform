"""
Execution Adapter models.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.mt5_execution.models import (
    OrderSide,
)

from core.trading_pipeline.models import (
    PipelineResult,
)


@dataclass(frozen=True)
class ExecutionPlan:
    """
    Strategy-level execution plan.

    This is independent of MT5 and contains only the
    information needed to prepare an execution.
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
    """

    pipeline_result: PipelineResult

    execution_plan: ExecutionPlan