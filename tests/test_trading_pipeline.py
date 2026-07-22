from datetime import datetime, UTC

from core.trading_pipeline.pipeline import TradingPipeline
from core.trading_pipeline.config import TradingPipelineConfig

from core.regime_detector.models import MarketBar


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

    assert result is not None
    assert result.regime is not None
    assert result.signal is not None
    assert result.trade_plan is not None

    plan = result.trade_plan

    assert hasattr(plan, "entry_price")

    # ---- CONTRACT-AWARE ASSERTIONS ----

    if plan.decision.value == "APPROVE":

        assert plan.entry_price == bar.close
        assert plan.stop_loss != 0
        assert plan.take_profit != 0
        assert plan.position_size > 0

    else:

        assert plan.entry_price == 0.0
        assert plan.position_size == 0.0
        assert plan.stop_loss == 0.0
        assert plan.take_profit == 0.0