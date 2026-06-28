"""
Market Regime Detection Engine.
"""

from __future__ import annotations

from datetime import datetime

from .config import RegimeDetectorConfig
from .indicators.adx import ADXIndicator
from .indicators.atr import ATRIndicator
from .indicators.efficiency_ratio import EfficiencyRatioIndicator
from .indicators.momentum import MomentumIndicator
from .indicators.ema import EMAIndicator

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

        # Initialize technical indicators
        self._adx = ADXIndicator(
            period=self.config.adx.lookback_period,
        )

        self._atr = ATRIndicator(
            period=self.config.adx.lookback_period,
        )

        self._efficiency_ratio = EfficiencyRatioIndicator(
            period=self.config.adx.lookback_period,
        )

        self._momentum = MomentumIndicator(
            period=self.config.adx.lookback_period,
        )

        self._ema20 = EMAIndicator(period=20)
        self._ema50 = EMAIndicator(period=50)
        self._ema200 = EMAIndicator(period=200)

    # =========================================================
    # INPUT PIPELINE
    # =========================================================

    def process_bar(
        self,
        bar: MarketBar,
    ) -> MarketRegime:

        self._validate_input(bar)

        features = self._compute_features(bar)

        regime = self._evaluate_regime(
            bar=bar,
            features=features,
        )

        self._update_state(bar, regime)

        return regime

    # =========================================================
    # VALIDATION
    # =========================================================

    def _validate_input(self, bar: MarketBar) -> None:
        if bar is None:
            raise ValueError("MarketBar cannot be None.")

    # =========================================================
    # FEATURES
    # =========================================================

    def _compute_features(self, bar: MarketBar) -> FeatureSet:

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

        er_result = self._efficiency_ratio.update(
            close=bar.close,
        )
        momentum_result = self._momentum.update(
            close=bar.close,
        )

        ema20_result = self._ema20.update(
            close=bar.close,
        )
        ema50_result = self._ema50.update(
            close=bar.close,
        )
        ema200_result = self._ema200.update(
            close=bar.close,
        )


        return FeatureSet(
            adx=adx_result.adx,
            atr=atr_result.atr,

            ema20=ema20_result.ema,
            ema50=ema50_result.ema,
            ema200=ema200_result.ema,

            efficiency_ratio=er_result.efficiency_ratio,
            volatility_percentile=0.0,
            trend_strength=adx_result.trend_strength,
            momentum=momentum_result.momentum,
            normalized_volatility=atr_result.normalized_atr,
        )

    # =========================================================
    # HELPER METHODS
    # =========================================================

    def _is_bullish_alignment(self, features: FeatureSet) -> bool:
        return (
            features.ema20 > features.ema50
            and features.ema50 > features.ema200
        )

    def _is_bearish_alignment(self, features: FeatureSet) -> bool:
        return (
            features.ema20 < features.ema50
            and features.ema50 < features.ema200
        )

    def _is_strong_trend(self, features: FeatureSet) -> bool:
        return features.adx >= self.config.adx.trending_threshold

    def _calculate_trend_score(
        self, 
        features: FeatureSet,
    ) -> float:
        """
        Calculate how strongly the market is trending.

        Uses:
        - ADX to measure trend strength
        - EMA alignment to measure trend direction
        """

        score = 0.0

        if self._is_strong_trend(features):
            score += 2.0

        if (
            self._is_bullish_alignment(features)
            or self._is_bearish_alignment(features)
        ):
            score += 2.0

        return score

    def _calculate_volatility_score(self, features: FeatureSet) -> float:
        """
        Calculate the contribution of volatility
        to the overall market regime score.
        """
        return 0.0

    def _calculate_momentum_score(
        self, 
        features: FeatureSet,
    ) -> float:
        return 0.0

    # =========================================================
    # REGIME ENGINE
    # =========================================================

    def _evaluate_regime(
        self,
        bar: MarketBar,
        features: FeatureSet,
    ) -> MarketRegime:

        trend_score = self._calculate_trend_score(features)
        volatility_score = self._calculate_volatility_score(features)
        momentum_score = self._calculate_momentum_score(features)

        total_score = trend_score + volatility_score + momentum_score

        if total_score >= 3.0:

            if self._is_bullish_alignment(features):
                regime = RegimeLabel.TRENDING_BULL
            elif self._is_bearish_alignment(features):
                regime = RegimeLabel.TRENDING_BEAR
            else:
                regime = RegimeLabel.RANGING

            confidence = min(0.5 + total_score / 6.0, 0.95)

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

    # =========================================================
    # STATE UPDATE
    # =========================================================

    def _update_state(
        self,
        bar: MarketBar,
        regime: MarketRegime,
    ) -> None:

        self.state.previous_regime = self.state.current_regime
        self.state.current_regime = regime.primary_regime
        self.state.last_observation_time = bar.timestamp
        self.state.last_result = regime

        if (
            self.state.current_regime_start is None
            or self.state.previous_regime != self.state.current_regime
        ):
            self.state.current_regime_start = bar.timestamp
            self.state.bars_in_current_regime = 1
        else:
            self.state.bars_in_current_regime += 1

        self.state.initialized = True