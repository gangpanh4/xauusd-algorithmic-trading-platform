from datetime import UTC, datetime

from core.regime_detector.models import (
    ConfidenceTier,
    MarketRegime,
    RegimeLabel,
)

from core.signal_generator.config import SignalGeneratorConfig
from core.signal_generator.detector import SignalGenerator
from core.signal_generator.models import (
    SignalStrength,
    SignalType,
)


def test_signal_generator():
    config = SignalGeneratorConfig(
        debug_logging=True,
    )

    generator = SignalGenerator(config)

    regime = MarketRegime(
        observation_timestamp=datetime.now(UTC),
        computation_timestamp=datetime.now(UTC),
        primary_regime=RegimeLabel.TRENDING_BULL,
        confidence=0.87,
        confidence_tier=ConfidenceTier.HIGH,

        # Required by the current SignalGenerator
        trend_score=4.0,
        momentum_score=1.0,
        volatility_score=1.0,
        ema_score=1.0,
        choppiness_score=2.0,
        total_score=9.0,
    )

    signal = generator.generate_signal(regime)

    print()
    print("========== SIGNAL ==========")
    print(f"Signal      : {signal.signal.value}")
    print(f"Strength    : {signal.strength.value}")
    print(f"Confidence  : {signal.confidence:.2f}")
    print(f"Reason      : {signal.reason}")

    # Current architecture assertions
    assert signal.signal == SignalType.BUY
    assert signal.strength == SignalStrength.STRONG
    assert abs(signal.confidence - 0.87) < 1e-6

    assert "TRENDING_BULL" in signal.reason
    assert "confidence" in signal.reason


if __name__ == "__main__":
    test_signal_generator()