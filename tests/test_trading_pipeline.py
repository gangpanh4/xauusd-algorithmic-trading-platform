from datetime import datetime, UTC

from core.regime_detector.models import (
    MarketBar,
)

from core.trading_pipeline.config import (
    TradingPipelineConfig,
)

from core.trading_pipeline.pipeline import (
    TradingPipeline,
)


def test_trading_pipeline():

    config = TradingPipelineConfig()

    pipeline = TradingPipeline(config)

    bar = MarketBar(
        timestamp=datetime.now(UTC),
        open=3300.0,
        high=3302.0,
        low=3298.0,
        close=3301.0,
        volume=1000,
    )

    result = pipeline.process_bar(
        bar,
        account_balance=10_000.0,
        stop_loss_distance=2.5,
        pip_value=1.0,
    )

    print()
    print("=" * 60)
    print("TRADING PIPELINE")
    print("=" * 60)

    print(
        f"Regime   : {result.regime.primary_regime.value}"
    )

    print(
        f"Signal   : {result.signal.signal.value}"
    )

    print(
        f"Decision : {result.trade_plan.decision.value}"
    )

    print("=" * 60)


if __name__ == "__main__":
    test_trading_pipeline()