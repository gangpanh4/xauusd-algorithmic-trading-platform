from __future__ import annotations

from dataclasses import FrozenInstanceError
import math

import pytest

from core.decision_engine.config import DecisionEngineConfig


def test_default_policy_remains_seventy_percent() -> None:
    config = DecisionEngineConfig()

    assert config.minimum_decision_score == 0.70
    assert config.total_weight == 1.0
    assert config.normalized_regime_weight == 0.5
    assert config.normalized_supporting_evidence_weight == 0.5


def test_relative_weights_are_normalized_without_requiring_sum_one() -> None:
    config = DecisionEngineConfig(regime_weight=3.0, confluence_weight=1.0)

    assert config.total_weight == 4.0
    assert config.normalized_regime_weight == 0.75
    assert config.normalized_supporting_evidence_weight == 0.25


def test_config_is_immutable() -> None:
    config = DecisionEngineConfig()

    with pytest.raises(FrozenInstanceError):
        config.minimum_decision_score = 0.6  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("minimum_decision_score", -0.1),
        ("minimum_decision_score", 1.1),
        ("minimum_decision_score", math.nan),
        ("regime_weight", -0.1),
        ("regime_weight", math.inf),
        ("confluence_weight", -0.1),
        ("confluence_weight", math.nan),
    ],
)
def test_invalid_numeric_policy_fails_closed(field: str, value: float) -> None:
    with pytest.raises(ValueError):
        DecisionEngineConfig(**{field: value})


@pytest.mark.parametrize(
    "field",
    ["minimum_decision_score", "regime_weight", "confluence_weight"],
)
def test_boolean_policy_values_are_rejected(field: str) -> None:
    with pytest.raises(TypeError):
        DecisionEngineConfig(**{field: True})


def test_zero_total_weight_fails_closed() -> None:
    with pytest.raises(ValueError, match="positive total"):
        DecisionEngineConfig(regime_weight=0.0, confluence_weight=0.0)
