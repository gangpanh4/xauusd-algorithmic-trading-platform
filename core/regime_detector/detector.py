"""
Market Regime Detection Engine.
"""

from __future__ import annotations

from datetime import datetime

from .config import RegimeDetectorConfig
from .indicators.adx import ADXIndicator
from .indicators.atr import ATRIndicator
from .models import (
    ConfidenceTier,
    FeatureSet,
    MarketBar,
    MarketRegime,
    RegimeLabel,
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

        self._atr = ATRIndicator(
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

        atr_result = self._atr.update(
            high=bar.high,
            low=bar.low,
            close=bar.close,
        )


        return FeatureSet(
            adx=adx_result.adx,
            atr=atr_result.atr,
            efficiency_ratio=0.0,
            volatility_percentile=0.0,
            trend_strength=adx_result.trend_strength,
            momentum=0.0,
            normalized_volatility=atr_result.normalized_atr,
        )

    def _evaluate_regime(
        self,
        features: FeatureSet,
    ) -> MarketRegime:
        """
        Evaluate the current market regime from computed features.
        """

        if features.adx >= self.config.adx.trending_threshold:
            regime = RegimeLabel.TRENDING_BULL
            confidence = 0.80
        else:
            regime = RegimeLabel.RANGING
            confidence = 0.40

        return MarketRegime(
            observation_timestamp=bar.timestamp,
            computation_timestamp=datetime.utcnow(),
            primary_regime=regime,
            confidence=confidence,
            confidence_tier=ConfidenceTier.MEDIUM,
        )

    def _update_state(
        self,
        bar: MarketBar,
        regime: MarketRegime,
    ) -> None:
        """
        Update the detector state after a confirmed regime evaluation.
        """
        self.state.previous_regime = self.state.current_regime

        self.state.current_regime = regime.primary_regime

        self.state.last_observation_time = (
            bar.timestamp
        )

        self.state.last_result = regime

        if (
            self.state.current_regime_start is None
            or self.state.previous_regime
            != self.state.current_regime
        ):
            self.state.current_regime_start = (
                bar.timestamp
            )

            self.state.bars_in_current_regime = 1

        else:
            self.state.bars_in_current_regime += 1

        self.state.initialized = True