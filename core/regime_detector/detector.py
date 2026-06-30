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
from .indicators.choppiness import ChoppinessIndicator
from .indicators.ema import EMAIndicator
from .indicators.ema_slope import EMASlopeIndicator

from .models import (
    ConfidenceTier,
    FeatureSet,
    MarketBar,
    MarketRegime,
    RegimeLabel,
    TransitionRecord,
)

from .state import DetectorState


class MarketRegimeDetector:
    """
    Core engine responsible for detecting the current market regime.
    """

    def __init__(self, config: RegimeDetectorConfig) -> None:
        self.config = config
        self.state = DetectorState()

        # Initialize technical indicators
        self._adx = ADXIndicator(period=self.config.adx.lookback_period)
        self._atr = ATRIndicator(period=self.config.adx.lookback_period)
        self._efficiency_ratio = EfficiencyRatioIndicator(
            period=self.config.adx.lookback_period
        )
        self._momentum = MomentumIndicator(period=self.config.adx.lookback_period)
        self._choppiness = ChoppinessIndicator(period=self.config.adx.lookback_period)

        self._ema20 = EMAIndicator(period=20)
        self._ema50 = EMAIndicator(period=50)
        self._ema200 = EMAIndicator(period=200)

        self._ema20_slope = EMASlopeIndicator(period=20)
        self._ema50_slope = EMASlopeIndicator(period=50)
        self._ema200_slope = EMASlopeIndicator(period=200)

    # =========================================================
    # INPUT PIPELINE
    # =========================================================

    def process_bar(self, bar: MarketBar) -> MarketRegime:
        self._validate_input(bar)

        features = self._compute_features(bar)

        if not self._is_warmup_complete():
            regime = MarketRegime(
                observation_timestamp=bar.timestamp,
                computation_timestamp=datetime.utcnow(),
                primary_regime=RegimeLabel.UNKNOWN,
                confidence=0.0,
                confidence_tier=ConfidenceTier.LOW,
            )
        else:
            regime = self._evaluate_regime(
                bar=bar,
                features=features,
            )

        self._update_state(bar, regime)

        self.state.warmup_complete = self._is_warmup_complete()

        return regime

    def _validate_input(self, bar: MarketBar) -> None:
        if bar is None:
            raise ValueError("MarketBar cannot be None.")

    # =========================================================
    # FEATURES & SCORING
    # =========================================================

    def _is_warmup_complete(self) -> bool:
        """
        Returns True once all indicators have accumulated enough history.
        """

        required_bars = max(
            self.config.adx.lookback_period,
            20,
            50,
            200,
        )

        return self.state.processed_bar_count >= required_bars

    def _compute_features(self, bar: MarketBar) -> FeatureSet:
        adx_result = self._adx.update(high=bar.high, low=bar.low, close=bar.close)
        atr_result = self._atr.update(high=bar.high, low=bar.low, close=bar.close)
        er_result = self._efficiency_ratio.update(close=bar.close)
        momentum_result = self._momentum.update(close=bar.close)
        choppiness_result = self._choppiness.update(high=bar.high, low=bar.low, close=bar.close)

        ema20_result = self._ema20.update(close=bar.close)
        ema50_result = self._ema50.update(close=bar.close)
        ema200_result = self._ema200.update(close=bar.close)

        ema20_slope_result = self._ema20_slope.update(ema20_result.ema)
        ema50_slope_result = self._ema50_slope.update(ema50_result.ema)
        ema200_slope_result = self._ema200_slope.update(ema200_result.ema)

        return FeatureSet(
            adx=adx_result.adx,
            atr=atr_result.atr,
            ema20=ema20_result.ema,
            ema50=ema50_result.ema,
            ema200=ema200_result.ema,
            ema20_slope=ema20_slope_result.slope,
            ema50_slope=ema50_slope_result.slope,
            ema200_slope=ema200_slope_result.slope,
            efficiency_ratio=er_result.efficiency_ratio,
            choppiness=choppiness_result.choppiness,
            volatility_percentile=0.0,
            trend_strength=adx_result.trend_strength,
            momentum=momentum_result.momentum,
            normalized_volatility=atr_result.normalized_atr,
        )

    def _is_bullish_alignment(self, features: FeatureSet) -> bool:
        return features.ema20 > features.ema50 > features.ema200

    def _is_bearish_alignment(self, features: FeatureSet) -> bool:
        return features.ema20 < features.ema50 < features.ema200

    def _is_strong_trend(self, features: FeatureSet) -> bool:
        return features.adx >= self.config.adx.trending_threshold

    def _calculate_trend_score(self, features: FeatureSet) -> float:
        score = 0.0
        if self._is_strong_trend(features):
            score += 2.0
        if self._is_bullish_alignment(features) or self._is_bearish_alignment(features):
            score += 2.0
        return score

    def _calculate_volatility_score(self, features: FeatureSet) -> float:
        score = 0.0
        if features.normalized_volatility >= self.config.volatility.high_threshold:
            score += 2.0
        elif features.normalized_volatility >= self.config.volatility.medium_threshold:
            score += 1.0
        return score

    def _calculate_momentum_score(self, features: FeatureSet) -> float:
        score = 0.0
        if features.momentum > 0:
            score += 1.0
        if features.efficiency_ratio >= 0.50:
            score += 1.0
        return score

    def _calculate_ema_slope_score(self, features: FeatureSet) -> float:
        score = 0.0
        if all(
            slope > 0
            for slope in (
                features.ema20_slope,
                features.ema50_slope,
                features.ema200_slope,
            )
        ):
            score += 1.0
        elif features.ema20_slope < 0 and features.ema50_slope < 0 and features.ema200_slope < 0:
            score += 1.0
        return score

    def _calculate_choppiness_score(self, features: FeatureSet) -> float:
        score = 0.0
        if features.choppiness <= self.config.choppiness.trending_threshold:
            score += 2.0
        elif features.choppiness <= self.config.choppiness.neutral_threshold:
            score += 1.0
        return score

    # =========================================================
    # REGIME ENGINE
    # =========================================================

    def _evaluate_regime(self, bar: MarketBar, features: FeatureSet) -> MarketRegime:
        if features.choppiness > self.config.choppiness.veto_threshold:
            regime = RegimeLabel.RANGING
            confidence = 0.60
        else:
            total_score = (
                self._calculate_trend_score(features)
                + self._calculate_volatility_score(features)
                + self._calculate_momentum_score(features)
                + self._calculate_ema_slope_score(features)
                + self._calculate_choppiness_score(features)
            )

            if total_score >= self.config.regime.min_score_threshold:
                if self._is_bullish_alignment(features):
                    regime = RegimeLabel.TRENDING_BULL
                elif self._is_bearish_alignment(features):
                    regime = RegimeLabel.TRENDING_BEAR
                else:
                    regime = RegimeLabel.RANGING
                confidence = min(0.45 + total_score / 10.0, 0.95)
            else:
                regime = RegimeLabel.RANGING
                confidence = 0.40


        if confidence >= 0.80:
            tier = ConfidenceTier.HIGH
        elif confidence >= 0.50:
            tier = ConfidenceTier.MEDIUM
        else:
            tier = ConfidenceTier.LOW


        return MarketRegime(
            observation_timestamp=bar.timestamp,
            computation_timestamp=datetime.utcnow(),
            primary_regime=regime,
            confidence=confidence,
            confidence_tier=tier,
        )

    def _update_state(self, bar: MarketBar, regime: MarketRegime) -> None:
        self.state.last_observation_time = bar.timestamp
        self.state.last_result = regime

        self.state.processed_bar_count += 1

        candidate = regime.primary_regime


        # Initialize on the first valid observation.
        if not self.state.initialized:
            self.state.current_regime = candidate
            self.state.previous_regime = candidate
            self.state.current_regime_start = bar.timestamp
            self.state.last_transition_time = bar.timestamp
            self.state.bars_in_current_regime = 1
            self.state.initialized = True
            return

        # No change detected
        if candidate == self.state.current_regime:
            self.state.pending_regime = RegimeLabel.UNKNOWN
            self.state.pending_regime_count = 0

        elif candidate == self.state.pending_regime:
            self.state.pending_regime_count += 1

        else:
            self.state.pending_regime = candidate
            self.state.pending_regime_count = 1

        # Determine how many confirmations are required.
        if candidate in (
            RegimeLabel.TRENDING_BULL,
            RegimeLabel.TRENDING_BEAR,
        ):
            required_confirmations = self.config.trend_confirmation_bars
        else:
            required_confirmations = self.config.range_confirmation_bars

        # Commit the regime transition once confirmed.
        if self.state.pending_regime_count >= required_confirmations:
            self.state.previous_regime = self.state.current_regime
            self.state.current_regime = self.state.pending_regime

            self.state.current_regime_start = bar.timestamp
            self.state.last_transition_time = bar.timestamp

            transition = TransitionRecord(
                timestamp=bar.timestamp,
                previous_regime=self.state.previous_regime,
                new_regime=self.state.current_regime,
                confidence=regime.confidence,
                reason="Confirmation threshold reached",
            )

            self.state.transition_history.append(transition)

            self.state.pending_regime = RegimeLabel.UNKNOWN
            self.state.pending_regime_count = 0

            self.state.bars_in_current_regime = 1

        # Otherwise continue counting bars in the current regime.
        else:
            if self.state.current_regime != RegimeLabel.UNKNOWN:
                self.state.bars_in_current_regime += 1
