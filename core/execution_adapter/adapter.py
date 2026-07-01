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

        trade_plan = pipeline_result.trade_plan

        side = (
            OrderSide.BUY
            if signal.action is TradingAction.BUY
            else OrderSide.SELL
        )

        order_request = OrderRequest(
            symbol="XAUUSD",
            side=side,
            volume=trade_plan.position_size,
            entry_price=0.0,
            stop_loss=0.0,
            take_profit=0.0,
            comment=self.config.default_comment,
        )

        return ExecutionRequest(
            pipeline_result=pipeline_result,
            order_request=order_request,
        )