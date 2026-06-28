"""
Market Regime Detection Engine.
"""

from __future__ import annotations

from .config import RegimeDetectorConfig
from .indicators.adx import ADXIndicator
from .models import (
    FeatureSet,
    MarketBar,
    MarketRegime,
)
from .state import DetectorState

class MarketRegimeDetector:
    """
    Core engine responsible for detecting the current market regime.
    """

    def __init__(
        self,
        config: RegimeDetectorConfig,
    ) -> None:
        self.config = config
        self.state = DetectorState()


        self._adx = ADXIndicator(
            period=self.config.adx.lookback_period,
        )



    def process_bar(
        self,
        bar: MarketBar,
    ) -> MarketRegime:
        """
        Process one validated market bar and return the detected regime.
        """

        self._validate_input(bar)

        features = self._compute_features(bar)

        regime = self._evaluate_regime(features)

        self._update_state(
            bar=bar,
            regime=regime,
        )

        return regime

    
    def _validate_input(
        self,
        bar: MarketBar,
    ) -> None:
        """
        Validate an incoming market bar.
        """

        if bar is None:
            raise ValueError("MarketBar cannot be None.")
        

    def _compute_features(
        self,
        bar: MarketBar,
    ) -> FeatureSet:
        """
        Compute all features required for regime detection.
        """

        adx_result = self._adx.update(
            high=bar.high,
            low=bar.low,
            close=bar.close,
        )

        return FeatureSet(
            adx=0.0,
            atr=0.0,
            efficiency_ratio=0.0,
            volatility_percentile=0.0,
            trend_strength=0.0,
            momentum=0.0,
            normalized_volatility=0.0,
        )

    def _evaluate_regime(
        self,
        features: FeatureSet,
    ) -> MarketRegime:
        """
        Evaluate the current market regime from computed features.
        """

        raise NotImplementedError(
            "Regime evaluation is not implemented yet."
        )

    def _update_state(
        self,
        bar: MarketBar,
        regime: MarketRegime,
    ) -> None:
        """
        Update the detector state after a confirmed regime evaluation.
        """
        raise NotImplementedError