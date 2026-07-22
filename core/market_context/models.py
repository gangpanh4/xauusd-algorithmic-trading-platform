"""
Shared market context models.

The MarketContext object represents the complete understanding
of the market after the Market Structure and Regime engines
have finished processing the current bar.

Downstream engines consume this object instead of receiving
multiple independent parameters.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.data.models import (
    MarketBar,
)

from core.market_structure.models import (
    MarketStructureResult,
)

from core.regime_detector.models import (
    MarketRegime,
)


@dataclass(slots=True, frozen=True)
class MarketContext:
    """
    Immutable snapshot of the current market state.

    This object contains only market information.

    It intentionally does NOT contain:
        - Probability
        - Decision
        - Signal
        - TradePlan

    Those belong to the pipeline output rather than the
    market itself.
    """

    # Current completed candle
    bar: MarketBar

    # Complete market structure analysis
    market_structure: MarketStructureResult

    # Current detected market regime
    market_regime: MarketRegime

    @property
    def timestamp(self):
        """
        Timestamp of the current market snapshot.
        """
        return self.bar.timestamp