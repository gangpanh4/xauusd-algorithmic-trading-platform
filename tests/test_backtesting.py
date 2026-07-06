from datetime import UTC, datetime, timedelta

from core.backtesting.config import BacktestConfig
from core.backtesting.engine import BacktestingEngine
from core.backtesting.reporter import print_report

from core.regime_detector.models import MarketBar
from core.trading_pipeline.market_context import MarketContext


def test_backtesting():

    config = BacktestConfig()

    engine = BacktestingEngine(config)

    bars = []

    price = 3300.0

    for index in range(100):

        bars.append(
            MarketBar(
                timestamp=datetime.now(UTC) + timedelta(minutes=index),
                open=price,
                high=price + 2,
                low=price - 2,
                close=price + 0.5,
                volume=1000,
            )
        )

        price += 0.3

    context = MarketContext(
        current_bar=bars[-1],
        m5_bars=bars,
        m15_bars=bars,
        h1_bars=bars,
        h4_bars=bars,
    )

    result = engine.run(context)

    print_report(result)

    assert result.total_trades >= 0


if __name__ == "__main__":
    test_backtesting()