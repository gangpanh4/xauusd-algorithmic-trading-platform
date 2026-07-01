from core.live_trading.config import (
    LiveTradingConfig,
)

from core.live_trading.engine import (
    LiveTradingEngine,
)

from core.regime_detector.models import (
    MarketBar,
)

from datetime import UTC, datetime


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

    print()

    print("=" * 60)
    print("LIVE TRADING ENGINE")
    print("=" * 60)
    print(f"Executed : {result.trade_executed}")
    print(f"Bars      : {engine.state.processed_bars}")
    print("=" * 60)

    engine.stop()


if __name__ == "__main__":
    test_live_trading_engine()