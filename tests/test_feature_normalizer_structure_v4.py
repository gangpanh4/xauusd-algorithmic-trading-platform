from __future__ import annotations

import pytest

from core.feature_engineering.models import Feature
from core.probability_engine.feature_normalizer import FeatureNormalizer


def _feature(name: str, value: float) -> Feature:
    return Feature(name=name, value=value)


def test_atr_normalized_break_features_use_common_scale() -> None:
    normalizer = FeatureNormalizer()

    assert normalizer.normalize(_feature("bos_break_atr_multiple", 1.5)) == 0.5
    assert normalizer.normalize(_feature("choch_break_efficiency", 3.0)) == 1.0
    assert normalizer.normalize(_feature("liquidity_reclaim_efficiency", 0.3)) == pytest.approx(0.1)


def test_event_age_normalization_matches_default_expiry_windows() -> None:
    normalizer = FeatureNormalizer()

    assert normalizer.normalize(_feature("bos_age", 8.0)) == 0.5
    assert normalizer.normalize(_feature("choch_age", 16.0)) == 0.0
    assert normalizer.normalize(_feature("liquidity_age", 16.0)) == 0.5
    assert normalizer.normalize(_feature("liquidity_age", 32.0)) == 0.0


def test_explicit_freshness_is_not_reinterpreted() -> None:
    normalizer = FeatureNormalizer()

    assert normalizer.normalize(_feature("bos_freshness", 0.4)) == 0.4
    assert normalizer.normalize(_feature("liquidity_freshness", 1.2)) == 1.0
