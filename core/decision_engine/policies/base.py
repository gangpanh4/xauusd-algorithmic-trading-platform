"""
Base Decision Policy.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.confluence_engine.models import (
    ConfluenceResult,
)

from core.regime_detector.models import (
    MarketRegime,
)

from core.decision_engine.models import (
    DecisionResult,
)


class DecisionPolicy(ABC):
    """
    Base class for all decision policies.

    A Decision Policy converts market analysis into a
    quantitative DecisionResult.

    Different trading styles should inherit from this class.
    """

    @abstractmethod
    def evaluate(
        self,
        *,
        regime: MarketRegime,
        confluence: ConfluenceResult | None,
    ) -> DecisionResult:
        """
        Produce a trading decision.
        """
        raise NotImplementedError