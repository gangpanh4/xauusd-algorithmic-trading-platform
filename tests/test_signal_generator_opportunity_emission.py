from __future__ import annotations

from datetime import UTC, datetime, timedelta

from core.regime_detector.models import ConfidenceTier, MarketRegime, RegimeLabel
from core.signal_generator.config import SignalGeneratorConfig
from core.signal_generator.detector import SignalGenerator
from core.signal_generator.models import SignalType


def _regime(*, timestamp: datetime, label: RegimeLabel) -> MarketRegime:
    return MarketRegime(
        observation_timestamp=timestamp,
        computation_timestamp=timestamp,
        primary_regime=label,
        confidence=0.90,
        confidence_tier=ConfidenceTier.HIGH,
        trend_score=4.0,
        momentum_score=1.0,
        volatility_score=1.0,
        ema_score=1.0,
        choppiness_score=2.0,
        total_score=9.0,
    )


def test_approved_opportunity_can_emit_inside_existing_regime() -> None:
    generator = SignalGenerator(SignalGeneratorConfig())
    timestamp = datetime(2026, 5, 11, 16, 0, tzinfo=UTC)
    generator.state.last_regime = RegimeLabel.TRENDING_BEAR

    result = generator.generate_signal(
        _regime(timestamp=timestamp, label=RegimeLabel.TRENDING_BEAR)
    )

    assert result.signal is SignalType.SELL
    assert result.timestamp == timestamp
    assert generator.state.last_emitted_signal is SignalType.SELL


def test_duplicate_signal_is_blocked_within_same_regime_by_default() -> None:
    generator = SignalGenerator(SignalGeneratorConfig())
    timestamp = datetime(2026, 5, 11, 16, 0, tzinfo=UTC)
    regime = _regime(timestamp=timestamp, label=RegimeLabel.TRENDING_BULL)

    first = generator.generate_signal(regime)
    second = generator.generate_signal(
        _regime(
            timestamp=timestamp + timedelta(minutes=15),
            label=RegimeLabel.TRENDING_BULL,
        )
    )

    assert first.signal is SignalType.BUY
    assert second.signal is SignalType.HOLD
    assert generator.state.bars_since_last_signal == 1


def test_duplicate_signal_respects_cooldown_when_enabled() -> None:
    generator = SignalGenerator(
        SignalGeneratorConfig(
            allow_duplicate_signals=True,
            signal_cooldown_bars=2,
        )
    )
    timestamp = datetime(2026, 5, 11, 16, 0, tzinfo=UTC)

    first = generator.generate_signal(
        _regime(timestamp=timestamp, label=RegimeLabel.TRENDING_BEAR)
    )
    blocked_1 = generator.generate_signal(
        _regime(
            timestamp=timestamp + timedelta(minutes=15),
            label=RegimeLabel.TRENDING_BEAR,
        )
    )
    blocked_2 = generator.generate_signal(
        _regime(
            timestamp=timestamp + timedelta(minutes=30),
            label=RegimeLabel.TRENDING_BEAR,
        )
    )
    emitted = generator.generate_signal(
        _regime(
            timestamp=timestamp + timedelta(minutes=45),
            label=RegimeLabel.TRENDING_BEAR,
        )
    )

    assert first.signal is SignalType.SELL
    assert blocked_1.signal is SignalType.HOLD
    assert blocked_2.signal is SignalType.HOLD
    assert emitted.signal is SignalType.SELL


def test_non_directional_regime_remains_hold() -> None:
    generator = SignalGenerator(SignalGeneratorConfig())
    timestamp = datetime(2026, 5, 11, 16, 0, tzinfo=UTC)

    result = generator.generate_signal(
        _regime(timestamp=timestamp, label=RegimeLabel.RANGING)
    )

    assert result.signal is SignalType.HOLD
