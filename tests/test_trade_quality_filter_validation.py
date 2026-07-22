from __future__ import annotations

import math

import pytest

from core.trade_quality.filters import (
    TradeQualityFilter,
    TradeQualityFilterConfig,
)
from core.trade_quality.models import QualityLevel, TradeQuality


def _quality(
    *,
    score: float = 60.0,
    confidence: float = 0.70,
    level: QualityLevel = QualityLevel.MEDIUM,
) -> TradeQuality:
    return TradeQuality(
        score=score,
        confidence=confidence,
        level=level,
    )


def test_default_filter_matches_medium_quality_contract() -> None:
    quality = TradeQualityFilter().apply(_quality())

    assert quality.approved
    assert quality.metadata["filter"]["failed_checks"] == []
    assert quality.metadata["filter"]["minimum_score"] == 60.0


def test_each_filter_condition_is_reported_independently() -> None:
    quality = TradeQualityFilter().apply(
        _quality(
            score=59.99,
            confidence=0.69,
            level=QualityLevel.LOW,
        )
    )

    assert not quality.approved
    assert quality.metadata["filter"]["checks"] == {
        "score": False,
        "confidence": False,
        "level": False,
    }
    assert quality.metadata["filter"]["failed_checks"] == [
        "score",
        "confidence",
        "level",
    ]


def test_score_pass_does_not_bypass_confidence() -> None:
    quality = TradeQualityFilter().apply(
        _quality(score=100.0, confidence=0.69)
    )

    assert not quality.approved
    assert quality.metadata["filter"]["failed_checks"] == ["confidence"]


def test_custom_filter_policy_remains_supported() -> None:
    trade_filter = TradeQualityFilter(
        TradeQualityFilterConfig(
            minimum_score=75.0,
            minimum_confidence=0.8,
            minimum_level=QualityLevel.HIGH,
        )
    )

    assert trade_filter.passes(
        _quality(
            score=75.0,
            confidence=0.8,
            level=QualityLevel.HIGH,
        )
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("minimum_score", -0.1),
        ("minimum_score", 100.1),
        ("minimum_score", math.nan),
        ("minimum_confidence", -0.1),
        ("minimum_confidence", 1.1),
        ("minimum_confidence", math.inf),
        ("minimum_level", "MEDIUM"),
    ],
)
def test_invalid_config_fails_closed(field: str, value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        TradeQualityFilterConfig(**{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("score", -0.1),
        ("score", 100.1),
        ("score", math.nan),
        ("confidence", -0.1),
        ("confidence", 1.1),
        ("confidence", math.inf),
        ("level", "MEDIUM"),
    ],
)
def test_invalid_quality_fails_closed(field: str, value: object) -> None:
    quality = _quality()
    setattr(quality, field, value)

    with pytest.raises((TypeError, ValueError)):
        TradeQualityFilter().passes(quality)
