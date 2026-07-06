"""
Unit tests for the Trade Quality subsystem.
"""

from core.trade_quality.manager import TradeQualityManager
from core.trade_quality.models import QualityLevel


def test_high_quality_trade():
    manager = TradeQualityManager()

    quality = manager.evaluate(
        trend_score=10.0,
        momentum_score=10.0,
        volatility_score=10.0,
        regime_confidence=0.95,
        signal_confidence=0.95,
        risk_reward_ratio=3.0,
    )

    assert quality.score >= 90
    assert quality.level == QualityLevel.EXCELLENT
    assert quality.approved


def test_medium_quality_trade():
    manager = TradeQualityManager()

    quality = manager.evaluate(
        trend_score=6.0,
        momentum_score=6.0,
        volatility_score=6.0,
        regime_confidence=0.70,
        signal_confidence=0.70,
        risk_reward_ratio=2.0,
    )

    assert quality.score >= 60
    assert quality.level in (
        QualityLevel.MEDIUM,
        QualityLevel.HIGH,
        QualityLevel.EXCELLENT,
    )


def test_low_quality_trade():
    manager = TradeQualityManager()

    quality = manager.evaluate(
        trend_score=1.0,
        momentum_score=1.0,
        volatility_score=1.0,
        regime_confidence=0.20,
        signal_confidence=0.20,
        risk_reward_ratio=1.0,
    )

    assert quality.score < 40
    assert quality.level == QualityLevel.REJECTED
    assert not quality.approved


def test_trade_quality_contains_reasons():
    manager = TradeQualityManager()

    quality = manager.evaluate(
        trend_score=10.0,
        momentum_score=10.0,
        volatility_score=10.0,
        regime_confidence=0.90,
        signal_confidence=0.90,
        risk_reward_ratio=3.0,
    )

    assert len(quality.reasons) > 0


def test_trade_quality_confidence():
    manager = TradeQualityManager()

    quality = manager.evaluate(
        trend_score=8.0,
        momentum_score=8.0,
        volatility_score=8.0,
        regime_confidence=0.85,
        signal_confidence=0.80,
        risk_reward_ratio=2.5,
    )

    assert quality.confidence == 0.85