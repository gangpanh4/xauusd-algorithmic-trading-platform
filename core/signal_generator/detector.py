"""
Signal Generation Engine.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.confluence_engine.models import ConfluenceResult
from core.decision_engine.models import DecisionResult, DecisionType
from core.market_structure.enums import TrendDirection
from core.market_structure.models import MarketStructureResult
from core.probability_engine.models import ProbabilityResult
from core.regime_detector.models import MarketRegime, RegimeLabel
from core.trade_quality.manager import TradeQualityManager
from core.trade_quality.models import TradeQuality

from .builder import SignalBuilder
from .config import SignalGeneratorConfig
from .context import SignalContext
from .gatekeeper import SignalGatekeeper
from .models import SignalStrength, SignalType, TradingSignal
from .policy import SignalPolicy
from .scorer import SignalScorer
from .state import SignalGeneratorState


class SignalGenerator:
    """
    Converts MarketRegime into a TradingSignal.

    This implementation is intentionally based on the current
    MarketRegimeDetector architecture.

    Intelligence v2 will replace this later.
    """

    def __init__(
        self,
        config: SignalGeneratorConfig,
        opportunity_ranker: Any | None = None,
    ) -> None:

        self.config = config
        self.state = SignalGeneratorState()

        # kept for future integration
        self.opportunity_ranker = opportunity_ranker
        self.trade_quality = TradeQualityManager()
        self.gatekeeper = SignalGatekeeper()
        self.scorer = SignalScorer()
        self.policy = SignalPolicy()
        self.builder = SignalBuilder()

    def generate_signal(
        self,
        regime: MarketRegime,
        probability: ProbabilityResult | None = None,
        trade_quality: TradeQuality | None = None,
        confluence: ConfluenceResult | None = None,
        decision: DecisionResult | None = None,
        market_structure: MarketStructureResult | None = None,
    ) -> TradingSignal:
        """
        Generate a signal from the detected market regime.
        """

        confidence = regime.confidence

        self.state.trend_scores[regime.trend_score] += 1

        self.state.momentum_scores[regime.momentum_score] += 1

        self.state.volatility_scores[regime.volatility_score] += 1

        self.state.ema_scores[regime.ema_score] += 1

        self.state.choppiness_scores[regime.choppiness_score] += 1

        self.state.total_scores[regime.total_score] += 1

        current_regime = regime.primary_regime

        # -------------------------------------------------
        # Opportunity-based signal generation
        # -------------------------------------------------

        signal = SignalType.HOLD

        context = SignalContext(
            regime=regime,
            probability=probability,
            trade_quality=trade_quality,
            decision=decision,
            confluence=confluence,
        )
        
        signal_score = self.scorer.score(context)
        has_upstream_evidence = any(
            result is not None
            for result in (
                probability,
                trade_quality,
                confluence,
                decision,
            )
        )

        upstream_approved = self.gatekeeper.approve(context)
        candidate_signal = self._candidate_signal(regime)

        if (
            upstream_approved
            and candidate_signal is not SignalType.HOLD
            and confidence >= self.config.minimum_signal_confidence
            and regime.total_score >= self.config.minimum_total_score
            and (
                not has_upstream_evidence
                or self.policy.should_emit(signal_score)
            )
            and self._decision_direction_agrees(
                candidate_signal=candidate_signal,
                decision=decision,
            )
            and self._structure_direction_agrees(
                candidate_signal=candidate_signal,
                market_structure=market_structure,
            )
            and self._has_active_aligned_choch(
                candidate_signal=candidate_signal,
                market_structure=market_structure,
            )
            and self._emission_policy_allows(
                candidate_signal=candidate_signal,
                regime=current_regime,
            )
        ):
            signal = candidate_signal

        # -------------------------------------------------
        # Signal Strength
        # -------------------------------------------------
        if (
            probability is None
            and trade_quality is None
            and confluence is None
            and decision is None
        ):
            if confidence >= 0.90:
                strength = SignalStrength.VERY_STRONG
            elif confidence >= 0.75:
                strength = SignalStrength.STRONG
            elif confidence >= 0.60:
                strength = SignalStrength.MODERATE
            else:
                strength = SignalStrength.WEAK
        else:
            strength = self.policy.classify_strength(signal_score)

        result = self._build_signal(
            timestamp=regime.observation_timestamp,
            signal=signal,
            strength=strength,
            confidence=confidence,
            decision_score=(
                decision.decision_score
                if decision is not None
                else (
                    confluence.score
                    if confluence is not None
                    else 0.0
                )
            ),
            reason=(
                f"Regime={regime.primary_regime.value}, "
                f"confidence={confidence:.3f}"
            ),
        )

        self._update_state(
            result,
            regime=current_regime,
        )

        return result

    @staticmethod
    def _candidate_signal(
        regime: MarketRegime,
    ) -> SignalType:
        """Return the directional candidate implied by the regime."""

        if regime.primary_regime is RegimeLabel.TRENDING_BULL:
            return SignalType.BUY

        if regime.primary_regime is RegimeLabel.TRENDING_BEAR:
            return SignalType.SELL

        return SignalType.HOLD

    def _decision_direction_agrees(
        self,
        *,
        candidate_signal: SignalType,
        decision: DecisionResult | None,
    ) -> bool:
        """Require an available approved decision to match the candidate."""

        if decision is None:
            return True

        expected = (
            DecisionType.BUY
            if candidate_signal is SignalType.BUY
            else DecisionType.SELL
        )

        return decision.approved and decision.decision is expected


    @staticmethod
    def _structure_direction_agrees(
        *,
        candidate_signal: SignalType,
        market_structure: MarketStructureResult | None,
    ) -> bool:
        """Require the freshest active BOS/CHOCH to agree with the signal.

        Missing structure remains neutral for backward compatibility. Evidence
        with zero freshness is treated as expired and does not veto a signal.
        When both BOS and CHOCH are active, the newest confirmed event is the
        directional authority.
        """

        if market_structure is None:
            return True

        candidates: list[tuple[datetime, TrendDirection]] = []

        if (
            market_structure.last_bos is not None
            and market_structure.bos_freshness > 0.0
        ):
            candidates.append(
                (
                    market_structure.last_bos.timestamp,
                    market_structure.last_bos.direction,
                )
            )

        if (
            market_structure.last_choch is not None
            and market_structure.choch_freshness > 0.0
        ):
            candidates.append(
                (
                    market_structure.last_choch.timestamp,
                    market_structure.last_choch.direction,
                )
            )

        if not candidates:
            return True

        _, direction = max(candidates, key=lambda item: item[0])

        if direction is TrendDirection.NEUTRAL:
            return True

        expected = (
            TrendDirection.BULLISH
            if candidate_signal is SignalType.BUY
            else TrendDirection.BEARISH
        )

        return direction is expected

    @staticmethod
    def _has_active_aligned_choch(
        *,
        candidate_signal: SignalType,
        market_structure: MarketStructureResult | None,
    ) -> bool:
        """Require a fresh CHOCH aligned with the candidate direction.

        This is an explicit active-pipeline strategy filter rather than a
        general structure compatibility check. Standalone legacy callers that
        do not supply market structure retain their existing behavior. When a
        structure result is supplied, a missing, expired, neutral, or opposing
        CHOCH prevents signal emission.
        """

        if market_structure is None:
            return True

        if (
            market_structure.last_choch is None
            or market_structure.choch_freshness <= 0.0
        ):
            return False

        expected = (
            TrendDirection.BULLISH
            if candidate_signal is SignalType.BUY
            else TrendDirection.BEARISH
        )

        return market_structure.last_choch.direction is expected

    def _emission_policy_allows(
        self,
        *,
        candidate_signal: SignalType,
        regime: RegimeLabel,
    ) -> bool:
        """Apply duplicate and cooldown rules to an approved candidate."""

        if (
            self.state.last_emitted_signal is not SignalType.HOLD
            and self.state.bars_since_last_signal
            < self.config.signal_cooldown_bars
        ):
            return False

        if (
            not self.config.allow_duplicate_signals
            and self.state.last_emitted_signal is candidate_signal
            and self.state.last_emitted_regime is regime
        ):
            return False

        return True

    def _build_signal(
        self,
        *,
        timestamp: datetime,
        signal: SignalType,
        strength: SignalStrength,
        confidence: float,
        decision_score: float,
        reason: str,
    ) -> TradingSignal:
        """
        Build the final TradingSignal.

        Version 2 centralizes TradingSignal construction in one
        location so future decision sources can reuse it.
        """

        return TradingSignal(
            timestamp=timestamp.astimezone(UTC),
            signal=signal,
            strength=strength,
            confidence=confidence,
            decision_score=decision_score,
            reason=reason,
            metadata={
                "decision_score": decision_score,
            },  
        )

    def _update_state(
        self,
        signal: TradingSignal,
        *,
        regime: RegimeLabel,
    ) -> None:
        """Record the result using the canonical state lifecycle."""

        self.state.record_result(
            signal,
            regime=regime,
        )
