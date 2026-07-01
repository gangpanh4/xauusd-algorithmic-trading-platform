from core.execution_adapter.adapter import (
    ExecutionAdapter,
)

from core.execution_adapter.config import (
    ExecutionAdapterConfig,
)

from core.regime_detector.models import (
    MarketRegime,
    RegimeLabel,
)

from core.signal_generator.models import (
    SignalDirection,
    TradingSignal,
)

from core.risk_manager.models import (
    RiskDecision,
    TradePlan,
)

from core.trading_pipeline.models import (
    PipelineResult,
)


def test_execution_adapter():

    signal = TradingSignal(
        direction=SignalDirection.BUY,
        confidence=0.85,
        reasons=["Execution adapter test"],
    )

    trade_plan = TradePlan(
        decision=RiskDecision.APPROVE,
        position_size=0.01,
        stop_loss=2.0,
        take_profit=4.0,
        risk_percent=1.0,
    )

    result = PipelineResult(
        regime=MarketRegime(
            label=RegimeLabel.TRENDING_BULL,
            confidence=0.90,
        ),
        signal=signal,
        trade_plan=trade_plan,
    )

    adapter = ExecutionAdapter(
        ExecutionAdapterConfig(),
    )

    execution = adapter.adapt(result)

    print()
    print("=" * 60)
    print("EXECUTION ADAPTER")
    print("=" * 60)
    print(f"Symbol  : {execution.order_request.symbol}")
    print(f"Side    : {execution.order_request.side.value}")
    print(f"Volume  : {execution.order_request.volume}")
    print(f"Comment : {execution.order_request.comment}")
    print("=" * 60)


if __name__ == "__main__":
    test_execution_adapter()