from datetime import datetime, timedelta, UTC
import random

from core.regime_detector.config import RegimeDetectorConfig
from core.regime_detector.detector import MarketRegimeDetector
from core.regime_detector.models import MarketBar

from core.signal_generator.config import SignalGeneratorConfig
from core.signal_generator.detector import SignalGenerator

from core.risk_manager.config import RiskManagerConfig
from core.risk_manager.manager import RiskManager


def test_trading_pipeline():

    regime_detector = MarketRegimeDetector(
        RegimeDetectorConfig(
            debug_logging=False,
        )
    )

    signal_generator = SignalGenerator(
        SignalGeneratorConfig(
            debug_logging=False,
        )
    )

    risk_manager = RiskManager(
        RiskManagerConfig(
            debug_logging=False,
        )
    )

    start = datetime.now(UTC)

    price = 3300.0

    trade_plan = None

    for i in range(250):

        open_price = price
        close_price = open_price + random.uniform(-1.0, 1.0)

        high_price = max(open_price, close_price) + random.uniform(0.2, 0.8)
        low_price = min(open_price, close_price) - random.uniform(0.2, 0.8)

        bar = MarketBar(
            timestamp=start + timedelta(minutes=i),
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=1000,
        )

        regime = regime_detector.process_bar(bar)

        signal = signal_generator.generate_signal(regime)

        trade_plan = risk_manager.evaluate_signal(
            signal=signal,
            account_balance=10000.0,
            stop_loss_distance=250.0,
            pip_value=1.0,
        )

        price = close_price

    print()
    print("=" * 60)
    print("FINAL TRADE PLAN")
    print("=" * 60)

    print(f"Decision : {trade_plan.decision.value}")
    print(f"Signal   : {trade_plan.signal.signal.value}")
    print(f"Size     : {trade_plan.position_size:.2f}")
    print(f"Risk %   : {trade_plan.risk_percent:.2%}")
    print(f"Reward % : {trade_plan.reward_percent:.2%}")
    print(f"Reason   : {trade_plan.reason}")

    assert trade_plan is not None


if __name__ == "__main__":
    test_trading_pipeline()