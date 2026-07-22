from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from core.market_structure.config import (
    BOSDetectorConfig,
    CHOCHDetectorConfig,
    LiquidityDetectorConfig,
    MarketStructureConfig,
    SwingDetectorConfig,
)


def test_market_structure_config_composes_detector_configs() -> None:
    swing = SwingDetectorConfig(pivot_left=2, pivot_right=4)
    bos = BOSDetectorConfig(minimum_break_atr_multiple=0.25)
    choch = CHOCHDetectorConfig(minimum_break_distance=0.5)
    liquidity = LiquidityDetectorConfig(require_reclaim_close=True)

    config = MarketStructureConfig(
        swing=swing,
        bos=bos,
        choch=choch,
        liquidity=liquidity,
        maximum_bos_age_bars=12,
        maximum_choch_age_bars=10,
        maximum_liquidity_age_bars=24,
        freshness_decay_bars=6,
    )

    assert config.swing is swing
    assert config.bos is bos
    assert config.choch is choch
    assert config.liquidity is liquidity
    assert config.maximum_bos_age_bars == 12
    assert config.maximum_choch_age_bars == 10
    assert config.maximum_liquidity_age_bars == 24
    assert config.freshness_decay_bars == 6


def test_market_structure_config_accepts_legacy_swing_keywords() -> None:
    config = MarketStructureConfig(
        pivot_left=1,
        pivot_right=2,
        atr_validation=False,
        maximum_history=123,
    )

    assert config.pivot_left == 1
    assert config.pivot_right == 2
    assert config.atr_validation is False
    assert config.maximum_history == 123
    assert config.swing == SwingDetectorConfig(
        pivot_left=1,
        pivot_right=2,
        atr_validation=False,
        maximum_history=123,
    )


def test_market_structure_config_rejects_ambiguous_swing_configuration() -> None:
    with pytest.raises(ValueError, match="cannot be combined"):
        MarketStructureConfig(
            swing=SwingDetectorConfig(),
            pivot_left=1,
        )


@pytest.mark.parametrize(
    ("keyword", "value"),
    [
        ("maximum_bos_age_bars", 0),
        ("maximum_choch_age_bars", 0),
        ("maximum_liquidity_age_bars", 0),
        ("freshness_decay_bars", 0),
        ("maximum_bar_history", 0),
    ],
)
def test_market_structure_config_rejects_invalid_age_limits(
    keyword: str,
    value: int,
) -> None:
    with pytest.raises(ValueError):
        MarketStructureConfig(**{keyword: value})


def test_detector_configs_are_immutable_and_validated() -> None:
    config = LiquidityDetectorConfig()

    with pytest.raises(FrozenInstanceError):
        config.minimum_sweep_distance = 1.0  # type: ignore[misc]

    with pytest.raises(ValueError):
        BOSDetectorConfig(
            require_close_break=False,
            allow_wick_break=False,
        )

    with pytest.raises(ValueError):
        CHOCHDetectorConfig(maximum_history=0)


def test_default_freshness_limits_are_selective() -> None:
    config = MarketStructureConfig()

    assert config.expire_stale_events is True
    assert config.maximum_bos_age_bars < config.maximum_liquidity_age_bars
    assert config.freshness_decay_bars <= config.maximum_bos_age_bars
