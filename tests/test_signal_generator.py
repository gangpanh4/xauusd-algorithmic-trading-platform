from datetime import datetime, UTC

from core.regime_detector.models import (
    ConfidenceTier,
    MarketRegime,
    RegimeLabel,
)

from core.signal_generator.config import (
    SignalGeneratorConfig,
)

from core.signal_generator.detector import (
    SignalGenerator,
)

from core.signal_generator.models import (
    SignalStrength,
    SignalType,
)


def test_signal_generator():
    # Create generator
    config = SignalGeneratorConfig(
        debug_logging=True,
    )

    generator = SignalGenerator(config)

    # Create fake market regime
    regime = MarketRegime(
        observation_timestamp=datetime.now(UTC),
        computation_timestamp=datetime.now(UTC),
        primary_regime=RegimeLabel.TRENDING_BULL,
        confidence=0.87,
        confidence_tier=ConfidenceTier.HIGH,
    )

    # Generate signal
    signal = generator.generate_signal(regime)

    # Display output
    print()
    print("========== SIGNAL ==========")
    print(f"Signal      : {signal.signal.value}")
    print(f"Strength    : {signal.strength.value}")
    print(f"Confidence  : {signal.confidence:.2f}")
    print(f"Reason      : {signal.reason}")

    # Assertions
    assert signal.signal == SignalType.BUY
    assert signal.strength == SignalStrength.STRONG
    assert abs(signal.confidence - 0.87) < 1e-6
    assert signal.reason == "Market regime: TRENDING_BULL"

if __name__ == "__main__":
    test_signal_generator()