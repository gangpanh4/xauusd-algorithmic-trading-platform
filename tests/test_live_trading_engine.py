from datetime import datetime, UTC

from core.live_trading.engine import LiveTradingEngine
from core.live_trading.config import LiveTradingConfig

from core.regime_detector.models import MarketBar


def test_live_trading_engine():

    engine = LiveTradingEngine(
        LiveTradingConfig(),
    )

    engine.start()

    bar = MarketBar(
        timestamp=datetime.now(UTC),
        open=4000.0,
        high=4005.0,
        low=3998.0,
        close=4003.0,
        volume=1000,
    )

    result = engine.process_bar(
        bar,
        account_balance=1000.0,
        stop_loss_distance=2.0,
        pip_value=1.0,
    )

    assert result is not None
    assert result.pipeline_result is not None

    trade_plan = result.pipeline_result.trade_plan

    assert trade_plan is not None
    assert hasattr(trade_plan, "entry_price")

    # ---- CONTRACT AWARE ASSERTIONS ----

    if trade_plan.decision.value == "APPROVE":

        assert trade_plan.entry_price == bar.close
        assert trade_plan.stop_loss != 0
        assert trade_plan.take_profit != 0
        assert trade_plan.position_size > 0

    else:

        assert trade_plan.entry_price == 0.0
        assert trade_plan.stop_loss == 0.0
        assert trade_plan.take_profit == 0.0
        assert trade_plan.position_size == 0.0