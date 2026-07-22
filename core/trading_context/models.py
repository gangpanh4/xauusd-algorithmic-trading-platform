"""
Trading Context models.

The TradingContext is the immutable snapshot of the trading pipeline.

It aggregates the outputs produced by the platform's core engines into a
single object that can be consumed by downstream systems without requiring
each engine to know about every other engine.

This module intentionally contains no business logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from core.confluence_engine.models import ConfluenceResult
from core.decision_engine.models import DecisionResult
from core.feature_engineering.models import FeatureVector
from core.market_structure.models import MarketStructureResult
from core.probability_engine.models import ProbabilityResult
from core.regime_detector.models import MarketRegime
from core.signal_generator.models import TradingSignal


@dataclass(slots=True, frozen=True)
class TradingContext:
    """
    Immutable snapshot of the trading pipeline.

    This object represents the complete market intelligence available
    for a single observation.

    It does not calculate anything.

    It simply groups together the outputs produced by the platform's
    engines so downstream components consume one consistent object.
    """

    # ---------------------------------------------------------
    # Snapshot Metadata
    # ---------------------------------------------------------

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    # ---------------------------------------------------------
    # Core Engine Outputs
    # ---------------------------------------------------------

    market_structure: MarketStructureResult | None = None

    market_regime: MarketRegime | None = None

    signal: TradingSignal | None = None

    probability: ProbabilityResult | None = None

    confluence: ConfluenceResult | None = None

    decision: DecisionResult | None = None

    feature_vector: FeatureVector | None = None

    # ---------------------------------------------------------
    # Convenience Properties
    # ---------------------------------------------------------

    @property
    def is_complete(self) -> bool:
        """
        Returns True when every required engine has produced
        an output for this snapshot.
        """

        return all(
            (
                self.market_structure is not None,
                self.market_regime is not None,
                self.signal is not None,
                self.probability is not None,
                self.confluence is not None,
                self.decision is not None,
                self.feature_vector is not None,
            )
        )