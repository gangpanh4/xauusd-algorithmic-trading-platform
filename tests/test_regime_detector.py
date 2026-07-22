"""
Test the Market Regime Detector.
"""

from __future__ import annotations

from datetime import UTC, datetime

from core.regime_detector.config import (
    RegimeDetectorConfig,
)
from core.regime_detector.detector import (
    MarketRegimeDetector,
)
from core.regime_detector.models import (
    MarketBar,
)


def main() -> None:
    """
    Run a simple regime detector test.
    """

    detector = MarketRegimeDetector(
        RegimeDetectorConfig(),
    )

    bar = MarketBar(
        timestamp=datetime.now(UTC),
        open=4000.0,
        high=4002.0,
        low=3998.0,
        close=4001.0,
        volume=1000.0,
    )

    regime = detector.process_bar(
        bar,
    )

    print()
    print("=" * 60)
    print("MARKET REGIME DETECTOR")
    print("=" * 60)
    print(f"Regime     : {regime.primary_regime.value}")
    print(f"Confidence : {regime.confidence:.2f}")
    print(f"Tier       : {regime.confidence_tier.value}")

    if regime.status_flags:
        print(
            "Flags      : "
            + ", ".join(
                flag.value
                for flag in regime.status_flags
            )
        )
    else:
        print("Flags      : None")
    
    print("=" * 60)
    print()

if __name__ == "__main__":
    main()