from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.data.models import MarketBar
from core.regime_detector.config import RegimeDetectorConfig
from core.regime_detector.detector import MarketRegimeDetector
from core.regime_detector.models import (
    ConfidenceTier,
    FeatureSet,
    MarketRegime,
    RegimeLabel,
    StatusFlag,
)


_BASE_TIME = datetime(2025, 1, 1, tzinfo=UTC)
_FEATURES = FeatureSet(
    adx=30.0,
    trend_strength=1.0,
    atr=2.0,
    normalized_volatility=1.0,
    volatility_percentile=0.5,
    choppiness=40.0,
    ema20=101.0,
    ema50=100.0,
    ema200=99.0,
    ema20_slope=1.0,
    ema50_slope=1.0,
    ema200_slope=1.0,
    momentum=1.0,
    efficiency_ratio=0.7,
)


def _bar(index: int) -> MarketBar:
    return MarketBar(
        timestamp=_BASE_TIME + timedelta(minutes=15 * index),
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        tick_volume=100,
    )


def _candidate(
    label: RegimeLabel,
    *,
    confidence: float,
    score: float,
) -> MarketRegime:
    tier = (
        ConfidenceTier.HIGH
        if confidence >= 0.8
        else ConfidenceTier.MEDIUM
    )
    return MarketRegime(
        primary_regime=label,
        confidence=confidence,
        confidence_tier=tier,
        trend_score=score,
        momentum_score=score,
        volatility_score=score,
        ema_score=score,
        choppiness_score=score,
        total_score=score,
    )


def _script_detector(
    monkeypatch: pytest.MonkeyPatch,
    candidates: list[MarketRegime],
    *,
    trend_confirmation_bars: int = 3,
    range_confirmation_bars: int = 2,
    crisis_confirmation_bars: int = 1,
    minimum_regime_duration: int = 1,
) -> MarketRegimeDetector:
    detector = MarketRegimeDetector(
        RegimeDetectorConfig(
            trend_confirmation_bars=trend_confirmation_bars,
            range_confirmation_bars=range_confirmation_bars,
            crisis_confirmation_bars=crisis_confirmation_bars,
            minimum_regime_duration=minimum_regime_duration,
        )
    )

    queue = list(candidates)
    monkeypatch.setattr(detector, "_compute_features", lambda bar: _FEATURES)
    monkeypatch.setattr(detector, "_is_warmup_complete", lambda: True)
    monkeypatch.setattr(
        detector,
        "_evaluate_regime",
        lambda *, bar, features: queue.pop(0),
    )
    return detector


def test_initial_trend_is_hidden_until_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    detector = _script_detector(
        monkeypatch,
        [
            _candidate(RegimeLabel.TRENDING_BULL, confidence=0.90, score=8.0),
            _candidate(RegimeLabel.TRENDING_BULL, confidence=0.90, score=8.0),
            _candidate(RegimeLabel.TRENDING_BULL, confidence=0.90, score=8.0),
        ],
        trend_confirmation_bars=3,
    )

    first = detector.process_bar(_bar(0))
    second = detector.process_bar(_bar(1))
    third = detector.process_bar(_bar(2))

    assert first.primary_regime is RegimeLabel.UNKNOWN
    assert second.primary_regime is RegimeLabel.UNKNOWN
    assert third.primary_regime is RegimeLabel.TRENDING_BULL
    assert detector.state.current_regime is RegimeLabel.TRENDING_BULL
    assert len(detector.state.transition_history) == 1


def test_pending_candidate_does_not_leak_its_confidence_or_scores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    detector = _script_detector(
        monkeypatch,
        [
            _candidate(RegimeLabel.TRENDING_BULL, confidence=0.80, score=6.0),
            _candidate(RegimeLabel.TRENDING_BULL, confidence=0.80, score=6.0),
            _candidate(RegimeLabel.TRENDING_BEAR, confidence=0.95, score=10.0),
        ],
        trend_confirmation_bars=2,
    )

    detector.process_bar(_bar(0))
    confirmed_bull = detector.process_bar(_bar(1))
    held_bull = detector.process_bar(_bar(2))

    assert confirmed_bull.primary_regime is RegimeLabel.TRENDING_BULL
    assert held_bull.primary_regime is RegimeLabel.TRENDING_BULL
    assert held_bull.confidence == pytest.approx(0.80)
    assert held_bull.total_score == pytest.approx(6.0)
    assert StatusFlag.OSCILLATION_SUPPRESSION in held_bull.status_flags
    assert StatusFlag.REDUCED_CONFIDENCE in held_bull.status_flags
    assert detector.state.pending_regime is RegimeLabel.TRENDING_BEAR
    assert detector.state.pending_regime_count == 1
    assert detector.state.last_result is held_bull


def test_candidate_must_respect_minimum_regime_duration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    detector = _script_detector(
        monkeypatch,
        [
            _candidate(RegimeLabel.TRENDING_BULL, confidence=0.85, score=7.0),
            _candidate(RegimeLabel.TRENDING_BULL, confidence=0.85, score=7.0),
            _candidate(RegimeLabel.RANGING, confidence=0.60, score=2.0),
            _candidate(RegimeLabel.RANGING, confidence=0.60, score=2.0),
            _candidate(RegimeLabel.RANGING, confidence=0.60, score=2.0),
        ],
        trend_confirmation_bars=2,
        range_confirmation_bars=2,
        minimum_regime_duration=3,
    )

    detector.process_bar(_bar(0))
    detector.process_bar(_bar(1))
    first_range = detector.process_bar(_bar(2))
    second_range = detector.process_bar(_bar(3))
    third_range = detector.process_bar(_bar(4))

    assert first_range.primary_regime is RegimeLabel.TRENDING_BULL
    assert second_range.primary_regime is RegimeLabel.TRENDING_BULL
    assert third_range.primary_regime is RegimeLabel.RANGING
    assert detector.state.current_regime is RegimeLabel.RANGING


def test_candidate_abort_resets_pending_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    detector = _script_detector(
        monkeypatch,
        [
            _candidate(RegimeLabel.TRENDING_BULL, confidence=0.85, score=7.0),
            _candidate(RegimeLabel.TRENDING_BULL, confidence=0.85, score=7.0),
            _candidate(RegimeLabel.TRENDING_BEAR, confidence=0.90, score=8.0),
            _candidate(RegimeLabel.TRENDING_BULL, confidence=0.85, score=7.0),
        ],
        trend_confirmation_bars=2,
    )

    detector.process_bar(_bar(0))
    detector.process_bar(_bar(1))
    detector.process_bar(_bar(2))
    returned = detector.process_bar(_bar(3))

    assert returned.primary_regime is RegimeLabel.TRENDING_BULL
    assert detector.state.pending_regime is RegimeLabel.UNKNOWN
    assert detector.state.pending_regime_count == 0
    assert detector.state.trend_confirmation_count == 0
    assert len(detector.state.transition_history) == 1


def test_crisis_uses_crisis_confirmation_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    detector = _script_detector(
        monkeypatch,
        [
            _candidate(RegimeLabel.TRENDING_BULL, confidence=0.85, score=7.0),
            _candidate(RegimeLabel.TRENDING_BULL, confidence=0.85, score=7.0),
            _candidate(RegimeLabel.CRISIS, confidence=0.95, score=10.0),
        ],
        trend_confirmation_bars=2,
        crisis_confirmation_bars=1,
    )

    detector.process_bar(_bar(0))
    detector.process_bar(_bar(1))
    crisis = detector.process_bar(_bar(2))

    assert crisis.primary_regime is RegimeLabel.CRISIS
    assert detector.state.current_regime is RegimeLabel.CRISIS
    assert detector.state.transition_history[-1].new_regime is RegimeLabel.CRISIS


def test_unknown_candidate_does_not_replace_established_regime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    detector = _script_detector(
        monkeypatch,
        [
            _candidate(RegimeLabel.TRENDING_BULL, confidence=0.85, score=7.0),
            _candidate(RegimeLabel.TRENDING_BULL, confidence=0.85, score=7.0),
            _candidate(RegimeLabel.UNKNOWN, confidence=0.0, score=0.0),
        ],
        trend_confirmation_bars=2,
    )

    detector.process_bar(_bar(0))
    detector.process_bar(_bar(1))
    held = detector.process_bar(_bar(2))

    assert held.primary_regime is RegimeLabel.TRENDING_BULL
    assert StatusFlag.DATA_QUALITY_WARNING in held.status_flags
    assert StatusFlag.REDUCED_CONFIDENCE in held.status_flags
    assert detector.state.current_regime is RegimeLabel.TRENDING_BULL
