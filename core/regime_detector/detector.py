"""
Market Regime Detection Engine.
"""

from __future__ import annotations

from datetime import UTC, datetime

from core.data.models import MarketBar

from .config import RegimeDetectorConfig
from .indicators.adx import ADXIndicator
from .indicators.atr import ATRIndicator
from .indicators.choppiness import ChoppinessIndicator
from .indicators.efficiency_ratio import EfficiencyRatioIndicator
from .indicators.ema import EMAIndicator
from .indicators.ema_slope import EMASlopeIndicator
from .indicators.momentum import MomentumIndicator
from .models import (
    ConfidenceTier,
    FeatureSet,
    MarketRegime,
    RegimeLabel,
    StatusFlag,
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

    def process_bar(
        self,
        bar: MarketBar,
        *,
        computation_timestamp: datetime | None = None,
    ) -> MarketRegime:
        """Process one completed bar and return the confirmed regime.

        The raw indicator assessment is treated as a candidate.  A candidate
        cannot reach downstream trading components until it satisfies the
        configured confirmation and minimum-duration rules.
        """

        self._validate_input(bar)

        result_available_at = (
            datetime.now(UTC)
            if computation_timestamp is None
            else computation_timestamp
        )

        features = self._compute_features(bar)

        if not self._is_warmup_complete():
            candidate = MarketRegime(
                observation_timestamp=bar.timestamp,
                computation_timestamp=result_available_at,
                primary_regime=RegimeLabel.UNKNOWN,
                confidence=0.0,
                confidence_tier=ConfidenceTier.LOW,
                status_flags=frozenset({StatusFlag.INITIALIZATION_PERIOD}),
            )
        else:
            candidate = self._evaluate_regime(
                bar=bar,
                features=features,
            )
            candidate.computation_timestamp = result_available_at

        confirmed = self._update_state(bar, candidate)

        if self.config.debug_logging:
            self._log_regime(
                bar=bar,
                features=features,
                regime=confirmed,
                candidate_regime=candidate,
            )

        self.state.warmup_complete = self._is_warmup_complete()

        return confirmed

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
        slopes = (
            features.ema20_slope,
            features.ema50_slope,
            features.ema200_slope,
        )
        if all(slope > 0 for slope in slopes) or all(
            slope < 0 for slope in slopes
        ):
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

    def _evaluate_regime(
        self,
        bar: MarketBar,
        features: FeatureSet,
    ) -> MarketRegime:
        if features.choppiness > self.config.choppiness.veto_threshold:
            regime = RegimeLabel.RANGING
            confidence = 0.60

            trend_score = 0.0
            volatility_score = 0.0
            momentum_score = 0.0
            ema_score = 0.0
            choppiness_score = 0.0
            total_score = 0.0

        else:
            trend_score = self._calculate_trend_score(features)

            volatility_score = self._calculate_volatility_score(features)

            momentum_score = self._calculate_momentum_score(features)

            ema_score = self._calculate_ema_slope_score(features)

            choppiness_score = self._calculate_choppiness_score(features)

            total_score = (
                trend_score
                + volatility_score
                + momentum_score
                + ema_score
                + choppiness_score
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
            computation_timestamp=datetime.now(UTC),
            primary_regime=regime,
            confidence=confidence,
            confidence_tier=tier,

            trend_score=trend_score,
            momentum_score=momentum_score,
            volatility_score=volatility_score,
            ema_score=ema_score,
            choppiness_score=choppiness_score,
            total_score=total_score,
        )

    def _update_state(
        self,
        bar: MarketBar,
        candidate: MarketRegime,
    ) -> MarketRegime:
        """Advance confirmation state and return the confirmed regime.

        The detector may observe a candidate that differs from the active
        regime.  Until the candidate satisfies both its confirmation count and
        the minimum duration of the active regime, downstream callers continue
        receiving the previously confirmed regime.
        """

        self.state.last_observation_time = bar.timestamp
        self.state.processed_bar_count += 1

        candidate_label = candidate.primary_regime

        if not self.state.initialized:
            self.state.current_regime = RegimeLabel.UNKNOWN
            self.state.previous_regime = RegimeLabel.UNKNOWN
            self.state.current_regime_start = bar.timestamp
            self.state.last_transition_time = bar.timestamp
            self.state.bars_in_current_regime = 1
            self.state.initialized = True

            if candidate_label is RegimeLabel.UNKNOWN:
                self._clear_pending_confirmation()
                self.state.last_result = candidate
                return candidate

        if candidate_label is RegimeLabel.UNKNOWN:
            self._clear_pending_confirmation()
            confirmed = self._hold_confirmed_regime(
                bar=bar,
                candidate=candidate,
                additional_flags=frozenset(
                    {
                        StatusFlag.DATA_QUALITY_WARNING,
                        StatusFlag.REDUCED_CONFIDENCE,
                    }
                ),
            )
            self._increment_current_regime_duration()
            self.state.last_result = confirmed
            return confirmed

        if candidate_label == self.state.current_regime:
            self._clear_pending_confirmation()
            self._increment_current_regime_duration()
            self.state.last_result = candidate
            return candidate

        self._register_pending_candidate(candidate_label)

        confirmation_ready = (
            self.state.pending_regime_count
            >= self._required_confirmations(candidate_label)
        )
        duration_ready = (
            self.state.current_regime is RegimeLabel.UNKNOWN
            or self.state.bars_in_current_regime
            >= self.config.minimum_regime_duration
        )

        if confirmation_ready and duration_ready:
            self._commit_transition(bar=bar, candidate=candidate)
            self.state.last_result = candidate
            return candidate

        confirmed = self._hold_confirmed_regime(
            bar=bar,
            candidate=candidate,
            additional_flags=frozenset(
                {
                    StatusFlag.OSCILLATION_SUPPRESSION,
                    StatusFlag.REDUCED_CONFIDENCE,
                }
            ),
        )
        self._increment_current_regime_duration()
        self.state.last_result = confirmed
        return confirmed

    def _required_confirmations(self, candidate: RegimeLabel) -> int:
        if candidate in (
            RegimeLabel.TRENDING_BULL,
            RegimeLabel.TRENDING_BEAR,
        ):
            return self.config.trend_confirmation_bars

        if candidate is RegimeLabel.CRISIS:
            return self.config.crisis_confirmation_bars

        return self.config.range_confirmation_bars

    def _register_pending_candidate(self, candidate: RegimeLabel) -> None:
        if candidate == self.state.pending_regime:
            self.state.pending_regime_count += 1
        else:
            self.state.pending_regime = candidate
            self.state.pending_regime_count = 1

        self.state.trend_confirmation_count = 0
        self.state.range_confirmation_count = 0
        self.state.crisis_confirmation_count = 0

        if candidate in (
            RegimeLabel.TRENDING_BULL,
            RegimeLabel.TRENDING_BEAR,
        ):
            self.state.trend_confirmation_count = (
                self.state.pending_regime_count
            )
        elif candidate is RegimeLabel.CRISIS:
            self.state.crisis_confirmation_count = (
                self.state.pending_regime_count
            )
        else:
            self.state.range_confirmation_count = (
                self.state.pending_regime_count
            )

    def _clear_pending_confirmation(self) -> None:
        self.state.pending_regime = RegimeLabel.UNKNOWN
        self.state.pending_regime_count = 0
        self.state.trend_confirmation_count = 0
        self.state.range_confirmation_count = 0
        self.state.crisis_confirmation_count = 0

    def _increment_current_regime_duration(self) -> None:
        if self.state.current_regime is not RegimeLabel.UNKNOWN:
            self.state.bars_in_current_regime += 1

    def _commit_transition(
        self,
        *,
        bar: MarketBar,
        candidate: MarketRegime,
    ) -> None:
        previous_regime = self.state.current_regime
        new_regime = candidate.primary_regime

        self.state.previous_regime = previous_regime
        self.state.current_regime = new_regime
        self.state.current_regime_start = bar.timestamp
        self.state.last_transition_time = bar.timestamp
        self.state.bars_in_current_regime = 1

        self.state.transition_history.append(
            TransitionRecord(
                timestamp=bar.timestamp,
                previous_regime=previous_regime,
                new_regime=new_regime,
                confidence=candidate.confidence,
                reason=(
                    "Confirmation threshold and minimum duration reached"
                ),
            )
        )

        self._clear_pending_confirmation()

    def _hold_confirmed_regime(
        self,
        *,
        bar: MarketBar,
        candidate: MarketRegime,
        additional_flags: frozenset[StatusFlag],
    ) -> MarketRegime:
        """Return the active regime without leaking candidate evidence."""

        previous = self.state.last_result
        current_label = self.state.current_regime

        if (
            previous is not None
            and previous.primary_regime == current_label
        ):
            source = previous
        else:
            source = MarketRegime(
                primary_regime=current_label,
                confidence=0.0,
                confidence_tier=ConfidenceTier.LOW,
            )

        flags = frozenset(source.status_flags | additional_flags)

        if current_label is RegimeLabel.UNKNOWN:
            flags = frozenset(
                flags | {StatusFlag.INITIALIZATION_PERIOD}
            )

        return MarketRegime(
            observation_timestamp=bar.timestamp,
            computation_timestamp=candidate.computation_timestamp,
            primary_regime=current_label,
            confidence=source.confidence,
            confidence_tier=source.confidence_tier,
            status_flags=flags,
            trend_score=source.trend_score,
            momentum_score=source.momentum_score,
            volatility_score=source.volatility_score,
            ema_score=source.ema_score,
            choppiness_score=source.choppiness_score,
            total_score=source.total_score,
        )

    def _log_regime(
        self,
        bar: MarketBar,
        features: FeatureSet,
        regime: MarketRegime,
        candidate_regime: MarketRegime | None = None,
    ) -> None:
        """
        Print debug information for the current regime assessment.
        """

        print("=" * 60)
        print("Market Regime Detector")
        print(f"Time            : {bar.timestamp}")
        print()

        if candidate_regime is not None:
            print(
                "Candidate       : "
                f"{candidate_regime.primary_regime.value}"
            )
        print(f"Confirmed       : {regime.primary_regime.value}")
        print(f"Confidence      : {regime.confidence:.2f}")
        print()

        print(f"ADX             : {features.adx:.2f}")
        print(f"ATR             : {features.atr:.2f}")
        print(f"Momentum        : {features.momentum:.2f}")
        print(f"Choppiness      : {features.choppiness:.2f}")
        print()

        print(f"Current         : {self.state.current_regime.value}")
        print(f"Pending         : {self.state.pending_regime.value}")
        print(f"Pending Count   : {self.state.pending_regime_count}")
        print(f"Bars In Regime  : {self.state.bars_in_current_regime}")

        print("=" * 60)