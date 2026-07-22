"""
Execution Adapter.
"""

from __future__ import annotations

from core.mt5_execution.models import (
    OrderRequest,
    OrderSide,
)

from core.trading_pipeline.models import (
    PipelineResult,
)

from .config import (
    ExecutionAdapterConfig,
)

from .models import (
    ExecutionPlan,
    ExecutionRequest,
)


class ExecutionAdapter:
    """
    Converts pipeline results into execution requests.
    """

    def __init__(
        self,
        config: ExecutionAdapterConfig,
    ) -> None:

        self.config = config

    def adapt(
        self,
        pipeline_result: PipelineResult,
    ) -> ExecutionRequest:
        """
        Convert a PipelineResult into an OrderRequest.
        """

        if pipeline_result is None:
            raise ValueError("pipeline_result cannot be None")

        trade_plan = pipeline_result.trade_plan
        signal = pipeline_result.signal

        if trade_plan is None:
            raise ValueError(
                "pipeline_result.trade_plan is required for execution"
            )
        if signal is None:
            raise ValueError(
                "pipeline_result.signal is required for execution"
            )

        direction = getattr(signal, "direction", None)
        if direction is None:
            direction = getattr(signal, "signal", None)

        direction_name = getattr(direction, "name", None)
        if direction_name == "BUY":
            side = OrderSide.BUY
        elif direction_name == "SELL":
            side = OrderSide.SELL
        else:
            raise ValueError(
                "Execution requires an explicit BUY or SELL signal"
            )

        execution_plan = ExecutionPlan(
            symbol=self.config.symbol,
            side=side,
            volume=trade_plan.position_size,
            entry_price=trade_plan.entry_price,
            stop_loss=trade_plan.stop_loss,
            take_profit=trade_plan.take_profit,
            account_balance=0.0,
            stop_loss_distance=abs(
                trade_plan.entry_price - trade_plan.stop_loss
            ),
            risk_reward_ratio=trade_plan.risk_reward_ratio,
            comment=self.config.default_comment,
        )

        return ExecutionRequest(
            pipeline_result=pipeline_result,
            execution_plan=execution_plan,
        )