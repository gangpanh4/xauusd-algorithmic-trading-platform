from __future__ import annotations

from core.market_structure import (
    BOSDetector,
    BOSDetectorConfig,
    BOSEvent,
    CHOCHDetector,
    CHOCHDetectorConfig,
    CHOCHEvent,
    LiquidityDetector,
    LiquidityDetectorConfig,
    LiquiditySweepEvent,
    MarketStructureConfig,
    MarketStructureEngine,
    MarketStructureResult,
    SwingDetector,
    SwingDetectorConfig,
    SwingPoint,
)


def test_market_structure_public_api_exports_primary_types() -> None:
    exported = (
        BOSDetector,
        BOSDetectorConfig,
        BOSEvent,
        CHOCHDetector,
        CHOCHDetectorConfig,
        CHOCHEvent,
        LiquidityDetector,
        LiquidityDetectorConfig,
        LiquiditySweepEvent,
        MarketStructureConfig,
        MarketStructureEngine,
        MarketStructureResult,
        SwingDetector,
        SwingDetectorConfig,
        SwingPoint,
    )

    assert all(item is not None for item in exported)
