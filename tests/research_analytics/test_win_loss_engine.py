from __future__ import annotations

from datetime import UTC
from datetime import datetime

import pytest

from core.feature_engineering.models import (
    Feature,
    FeatureVector,
)
from core.research_analytics.engine import (
    ResearchAnalyticsEngine,
)
from core.research_analytics.models import (
    TradeAnalytics,
)
from core.research_analytics.storage import (
    ResearchStorage,
)
from core.signal_generator.models import (
    SignalDirection,
)


def make_trade(
    *,
    result: str,
    probability: float,
    structure: float,
    liquidity: float,
) -> TradeAnalytics:
    """
    Create a TradeAnalytics object for testing.
    """

    features = FeatureVector()

    features.add(
        Feature(
            name="structure_confidence",
            value=structure,
            family="structure",
        )
    )

    features.add(
        Feature(
            name="liquidity_quality",
            value=liquidity,
            family="liquidity",
        )
    )
    
    features.add(
        Feature(
            name="liquidity_atr_multiple",
            value=3.0,
            family="liquidity",
        )
    )
    
    features.add(
        Feature(
            name="liquidity_density",
            value=0.6,
            family="liquidity",
        )
    )

    return TradeAnalytics(
        timestamp=datetime.now(UTC),
        direction=SignalDirection.BUY,
        regime="TRENDING_BULL",
        result=result,
        profit=1.0,
        probability=probability,
        confidence=0.90,
        features=features,
    )


def test_win_loss_analysis() -> None:
    storage = ResearchStorage()

    storage.add_trade(
        make_trade(
            result="WIN",
            probability=0.90,
            structure=0.80,
            liquidity=0.70,
        )
    )

    storage.add_trade(
        make_trade(
            result="WIN",
            probability=0.80,
            structure=0.60,
            liquidity=0.90,
        )
    )

    storage.add_trade(
        make_trade(
            result="LOSS",
            probability=0.50,
            structure=0.40,
            liquidity=0.30,
        )
    )

    engine = ResearchAnalyticsEngine(storage)

    analysis = engine.win_loss_analysis

    assert analysis.winning_probability == pytest.approx(0.85)
    assert analysis.losing_probability == pytest.approx(0.50)

    assert analysis.winning_structure == pytest.approx(0.70)
    assert analysis.losing_structure == pytest.approx(0.40)

    assert analysis.winning_liquidity == pytest.approx(0.80)
    assert analysis.losing_liquidity == pytest.approx(0.30)

    assert analysis.probability_gap == pytest.approx(0.35)
    assert analysis.structure_gap == pytest.approx(0.30)
    assert analysis.liquidity_gap == pytest.approx(0.50)


def test_empty_win_loss_analysis() -> None:
    storage = ResearchStorage()

    engine = ResearchAnalyticsEngine(storage)

    analysis = engine.win_loss_analysis

    assert analysis.winning_probability == 0.0
    assert analysis.losing_probability == 0.0

    assert analysis.winning_structure == 0.0
    assert analysis.losing_structure == 0.0

    assert analysis.winning_liquidity == 0.0
    assert analysis.losing_liquidity == 0.0

    assert analysis.probability_gap == 0.0
    assert analysis.structure_gap == 0.0
    assert analysis.liquidity_gap == 0.0