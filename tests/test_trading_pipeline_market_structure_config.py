from __future__ import annotations

from core.market_structure.config import (
    BOSDetectorConfig,
    MarketStructureConfig,
)
from core.trading_pipeline.config import TradingPipelineConfig


def test_pipeline_config_owns_market_structure_configuration() -> None:
    market_structure = MarketStructureConfig(
        bos=BOSDetectorConfig(
            minimum_break_atr_multiple=0.5,
        ),
        maximum_bos_age_bars=12,
        freshness_decay_bars=6,
    )

    config = TradingPipelineConfig(
        market_structure=market_structure,
    )

    assert config.market_structure is market_structure
    assert config.market_structure.bos.minimum_break_atr_multiple == 0.5
    assert config.market_structure.maximum_bos_age_bars == 12
    assert config.market_structure.freshness_decay_bars == 6


def test_pipeline_config_creates_independent_market_structure_defaults() -> None:
    first = TradingPipelineConfig()
    second = TradingPipelineConfig()

    assert first.market_structure == second.market_structure
    assert first.market_structure is not second.market_structure


def test_pipeline_injects_market_structure_configuration() -> None:
    market_structure = MarketStructureConfig(
        bos=BOSDetectorConfig(
            minimum_break_atr_multiple=0.75,
        ),
        maximum_bos_age_bars=10,
        maximum_liquidity_age_bars=18,
        freshness_decay_bars=5,
    )

    pipeline_config = TradingPipelineConfig(
        market_structure=market_structure,
    )

    from core.trading_pipeline.pipeline import TradingPipeline

    pipeline = TradingPipeline(pipeline_config)

    assert pipeline.market_structure.config is market_structure
    assert pipeline.market_structure.bos_detector.config is market_structure.bos
    assert pipeline.market_structure.choch_detector.config is market_structure.choch
    assert (
        pipeline.market_structure.liquidity_detector.config
        is market_structure.liquidity
    )


def test_pipeline_injects_confluence_configuration() -> None:
    from core.confluence_engine.config import ConfluenceEngineConfig
    from core.trading_pipeline.pipeline import TradingPipeline

    confluence = ConfluenceEngineConfig(
        minimum_approval_score=80.0,
    )
    pipeline_config = TradingPipelineConfig(
        confluence_engine=confluence,
    )

    pipeline = TradingPipeline(pipeline_config)

    assert pipeline.confluence_engine.config is confluence
