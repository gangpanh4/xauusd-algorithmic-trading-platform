from datetime import datetime, timedelta

from core.regime_detector.config import RegimeDetectorConfig
from core.regime_detector.detector import MarketRegimeDetector
from core.regime_detector.models import MarketBar


# Create the detector
config = RegimeDetectorConfig(
    debug_logging=True,
)

detector = MarketRegimeDetector(config)


# Generate fake market data
start = datetime.utcnow()
import random

random.seed(42)

price = 3300.0

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

    detector.process_bar(bar)

    price = close_price