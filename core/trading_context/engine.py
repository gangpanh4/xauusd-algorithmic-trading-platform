"""
Trading Context Engine.

Responsible for creating and validating TradingContext objects.

This engine intentionally contains no trading logic.

Its only responsibility is ensuring that all pipeline outputs
belong to the same market snapshot before exposing them to
downstream engines.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import datetime
from typing import Any

from .models import TradingContext

from core.market_structure.models import MarketStructureResult
from core.regime_detector.models import MarketRegime
from core.signal_generator.models import TradingSignal
from core.feature_engineering.models import FeatureVector
from core.probability_engine.models import ProbabilityResult
from core.confluence_engine.models import ConfluenceResult
from core.decision_engine.models import DecisionResult


class TradingContextEngine:
    """
    Creates and validates immutable TradingContext objects.
    """

    # ==========================================================
    # PUBLIC API
    # ==========================================================

    def create(
        self,
        *,
        timestamp: datetime,
        market_structure: MarketStructureResult | None = None,
        market_regime: MarketRegime | None = None,
        signal: TradingSignal | None = None,
        probability: ProbabilityResult | None = None,
        confluence: ConfluenceResult | None = None,
        decision: DecisionResult | None = None,
        feature_vector: FeatureVector | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TradingContext:
        """
        Create an immutable TradingContext.
        """

        context = TradingContext(
            timestamp=timestamp,
            market_structure=market_structure,
            market_regime=market_regime,
            signal=signal,
            probability=probability,
            confluence=confluence,
            decision=decision,
            feature_vector=feature_vector,
            metadata=metadata or {},
        )

        self.validate(context)

        return context

    # ==========================================================
    # VALIDATION
    # ==========================================================

    def validate(
        self,
        context: TradingContext,
    ) -> None:
        """
        Validate TradingContext consistency.

        Raises
        ------
        ValueError
            If invalid data is detected.
        """

        if context.timestamp is None:
            raise ValueError("TradingContext timestamp cannot be None.")

        self._validate_metadata(context)

    # ==========================================================
    # STATUS
    # ==========================================================

    def is_complete(
        self,
        context: TradingContext,
    ) -> bool:
        """
        Returns True if all required engine outputs exist.
        """

        return context.is_complete

    # ==========================================================
    # DEBUG
    # ==========================================================

    def summary(
        self,
        context: TradingContext,
    ) -> str:
        """
        Human-readable summary used for debugging.
        """

        lines = [
            "=" * 60,
            "Trading Context",
            "=" * 60,
        ]

        for field in fields(context):

            if field.name in ("timestamp", "metadata"):
                continue

            value = getattr(context, field.name)

            status = "✓" if value is not None else "✗"

            lines.append(
                f"{field.name:<20} {status}"
            )

        lines.append("")
        lines.append(
            f"Complete : {self.is_complete(context)}"
        )

        lines.append("=" * 60)

        return "\n".join(lines)

    # ==========================================================
    # INTERNAL
    # ==========================================================

    def _validate_metadata(
        self,
        context: TradingContext,
    ) -> None:
        """
        Metadata must always be a dictionary.
        """

        if not isinstance(context.metadata, dict):
            raise ValueError(
                "TradingContext metadata must be a dictionary."
            )