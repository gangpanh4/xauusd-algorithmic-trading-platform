from __future__ import annotations

import math

import pytest

from core.confluence_engine.config import ConfluenceEngineConfig


def test_default_threshold_matches_continuous_corroboration_model() -> None:
    config = ConfluenceEngineConfig()

    assert config.maximum_score == 100.0
    assert config.minimum_approval_score == 40.0
    assert config.approval_ratio == 0.40


def test_custom_weights_preserve_ratio_contract() -> None:
    config = ConfluenceEngineConfig(
        liquidity_weight=10.0,
        bos_weight=10.0,
        choch_weight=10.0,
        order_block_weight=10.0,
        fair_value_gap_weight=10.0,
        trend_weight=10.0,
        minimum_approval_score=30.0,
    )

    assert config.maximum_score == 60.0
    assert config.approval_ratio == 0.5


@pytest.mark.parametrize(
    ("field", "value", "error_type"),
    [
        ("liquidity_weight", -1.0, ValueError),
        ("bos_weight", math.inf, ValueError),
        ("choch_weight", True, TypeError),
        ("minimum_approval_score", -1.0, ValueError),
        ("minimum_approval_score", math.nan, ValueError),
        ("debug_logging", 1, TypeError),
    ],
)
def test_invalid_values_fail_closed(
    field: str,
    value: object,
    error_type: type[Exception],
) -> None:
    with pytest.raises(error_type):
        ConfluenceEngineConfig(**{field: value})


def test_zero_total_weight_fails_closed() -> None:
    with pytest.raises(ValueError, match="maximum_score must be positive"):
        ConfluenceEngineConfig(
            liquidity_weight=0.0,
            bos_weight=0.0,
            choch_weight=0.0,
            order_block_weight=0.0,
            fair_value_gap_weight=0.0,
            trend_weight=0.0,
            minimum_approval_score=0.0,
        )


def test_threshold_cannot_exceed_maximum_score() -> None:
    with pytest.raises(ValueError, match="must not exceed"):
        ConfluenceEngineConfig(minimum_approval_score=101.0)
