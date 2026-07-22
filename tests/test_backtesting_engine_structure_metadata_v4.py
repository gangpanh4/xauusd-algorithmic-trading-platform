from __future__ import annotations

from datetime import UTC, datetime

from core.backtesting.config import BacktestConfig
from core.backtesting.engine import BacktestingEngine
from core.data.models import MarketBar
from core.feature_engineering.models import Feature, FeatureVector
from core.market_structure.enums import BreakType, SwingType, TrendDirection
from core.market_structure.models import BOSEvent, SwingPoint
from core.regime_detector.models import MarketRegime, RegimeLabel
from core.trading_pipeline.models import PipelineResult


def test_pipeline_metadata_exports_structure_atr_and_freshness() -> None:
    timestamp = datetime(2025, 1, 1, tzinfo=UTC)
    swing = SwingPoint(
        timestamp=timestamp,
        index=0,
        price=100.0,
        swing_type=SwingType.HIGH,
        confirmation_index=0,
    )
    bos = BOSEvent(
        timestamp=timestamp,
        break_type=BreakType.BOS,
        direction=TrendDirection.BULLISH,
        swing_point=swing,
        break_price=101.0,
        confirmation_index=1,
        break_distance=1.0,
        break_atr_multiple=0.5,
        quality=0.6,
        age=2,
    )
    features = FeatureVector(
        features=[
            Feature("structure_confidence", 0.3),
            Feature("bos_freshness", 0.75),
        ]
    )
    result = PipelineResult(
        regime=MarketRegime(primary_regime=RegimeLabel.TRENDING_BULL),
        bos_event=bos,
        features=features,
    )
    engine = BacktestingEngine(BacktestConfig())
    bar = MarketBar(
        timestamp=timestamp,
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.0,
        tick_volume=100,
    )

    metadata = engine._build_pipeline_evidence_metadata(
        result=result,
        entry_bar=bar,
        exit_timestamp=timestamp,
    )

    assert metadata["structure_confidence"] == 0.3
    assert metadata["bos_break_atr_multiple"] == 0.5
    assert metadata["bos_freshness"] == 0.75
    assert metadata["choch_freshness"] is None
    assert metadata["liquidity_freshness"] is None
