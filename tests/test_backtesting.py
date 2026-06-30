from datetime import UTC, datetime, timedelta

from core.backtesting.config import (
    BacktestConfig,
)

from core.backtesting.engine import (
    BacktestingEngine,
)

from core.backtesting.reporter import (
    print_report,
)

from core.regime_detector.models import (
    MarketBar,
)


def test_backtesting():

    config = BacktestConfig()

    engine = BacktestingEngine(config)

    bars = []

    price = 3300.0

    for index in range(100):

        bar = MarketBar(
            timestamp=datetime.now(UTC)
            + timedelta(minutes=index),

            open=price,

            high=price + 2,

            low=price - 2,

            close=price + 0.5,

            volume=1000,
        )

        bars.append(bar)

        price += 0.3

    result = engine.run(bars)

    print_report(result)


if __name__ == "__main__":
    test_backtesting()