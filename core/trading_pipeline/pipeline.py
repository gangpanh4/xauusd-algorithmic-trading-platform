"""
Trading Pipeline orchestrator.

The pipeline coordinates analytical engines and converts their outputs into a
broker-independent ``TradePlan``. It does not execute orders and does not own
broker connectivity.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from math import isfinite
from statistics import fmean

from core.confluence_engine.engine import ConfluenceEngine
from core.confluence_engine.models import ConfluenceResult
from core.data.models import MarketBar
from core.decision_engine.engine import DecisionEngine
from core.feature_engineering.engine import FeatureEngineeringEngine
from core.feature_engineering.evidence import FeatureEvidence
from core.feature_engineering.models import Feature, FeatureVector
from core.intelligence.edge.opportunity_ranker import OpportunityRanker
from core.market_context import MarketContext
from core.market_structure.engine import MarketStructureEngine
from core.market_structure.enums import TrendDirection
from core.market_structure.models import MarketStructureResult
from core.multi_timeframe.coordinator import MultiTimeframeCoordinator
from core.multi_timeframe.enums import Timeframe
from core.multi_timeframe.models import MultiTimeframeResult, TimeframeState
from core.probability_engine.engine import ProbabilityEngine
from core.regime_detector.detector import MarketRegimeDetector
from core.regime_detector.models import RegimeLabel
from core.risk_manager.manager import RiskManager
from core.risk_manager.models import RiskDecision
from core.signal_generator.context import SignalContext
from core.signal_generator.detector import SignalGenerator
from core.signal_generator.models import SignalDirection, SignalType, TradingSignal
from core.trade_quality.evidence import TradeQualityEvidenceBuilder
from core.trade_quality.manager import TradeQualityManager

from .config import TradingPipelineConfig
from .models import (
    PipelineDisposition,
    PipelineObservationAudit,
    PipelineResult,
    PipelineStage,
)


class TradingPipeline:
    """Coordinate the complete analytical and risk-decision workflow.

    The pipeline processes completed market bars only. It owns analytical
    state, delegates monetary-risk decisions to ``RiskManager``, and exposes
    explicit lifecycle methods that orchestration layers must call after a
    simulated or broker-confirmed position opens or closes.
    """

    DEFAULT_TICK_SIZE = 1.0
    DEFAULT_LOT_STEP = 0.01
    VOLATILITY_STOP_RANGE_MULTIPLIER = 1.5
    STOP_SAFETY_BUFFER_TICKS = 2.0

    def __init__(self, config: TradingPipelineConfig) -> None:
        self.config = config

        self.regime_detector = MarketRegimeDetector(
            config.regime_detector,
        )

        self.opportunity_ranker = OpportunityRanker()

        self.signal_generator = SignalGenerator(
            config.signal_generator,
            self.opportunity_ranker,
        )

        self.risk_manager = RiskManager(
            config.risk_manager,
        )

        # Phase 2 architecture.
        self.multi_timeframe = MultiTimeframeCoordinator()
        self.market_structure = MarketStructureEngine(
            config.market_structure,
        )
        self.confluence_engine = ConfluenceEngine(
            config.confluence_engine,
        )
        self.feature_engineering = FeatureEngineeringEngine()
        self.probability_engine = ProbabilityEngine()
        self.decision_engine = DecisionEngine()
        self.trade_quality = TradeQualityManager()
        self._last_observation_audit: PipelineObservationAudit | None = None

        self.trade_quality_evidence = TradeQualityEvidenceBuilder(
            planned_risk_reward_ratio=(
                config.risk_manager.minimum_risk_reward_ratio
            ),
        )

    def process(
        self,
        *,
        bars_by_timeframe: Mapping[Timeframe, list[MarketBar]],
        account_balance: float,
        stop_loss_distance: float,
        pip_value: float,
        tick_size: float = DEFAULT_TICK_SIZE,
        lot_step: float = DEFAULT_LOT_STEP,
        minimum_lot: float | None = None,
        maximum_lot: float | None = None,
    ) -> PipelineResult:
        """Process synchronized timeframe data through the compatibility path.

        ``pip_value`` is retained for backward compatibility. It must represent
        the account-currency value of one ``tick_size`` movement for one lot.
        ``tick_size`` and ``lot_step`` should come from an offline symbol
        specification in backtests or from broker symbol metadata in live mode.
        """

        mtf_result = self.multi_timeframe.process(
            bars_by_timeframe,
        )

        confluence = self.confluence_engine.evaluate_multi_timeframe(
            mtf_result,
        )

        current_bars = bars_by_timeframe.get(Timeframe.M5)
        if not current_bars:
            raise ValueError("Missing completed M5 bars for pipeline processing.")

        return self.process_bar(
            current_bars[-1],
            confluence=confluence,
            multi_timeframe_result=mtf_result,
            account_balance=account_balance,
            stop_loss_distance=stop_loss_distance,
            pip_value=pip_value,
            tick_size=tick_size,
            lot_step=lot_step,
            minimum_lot=minimum_lot,
            maximum_lot=maximum_lot,
        )

    def process_bar(
        self,
        bar: MarketBar,
        *,
        confluence: ConfluenceResult | None = None,
        multi_timeframe_result: MultiTimeframeResult | None = None,
        market_structure_result: MarketStructureResult | None = None,
        account_balance: float,
        stop_loss_distance: float,
        pip_value: float,
        tick_size: float = DEFAULT_TICK_SIZE,
        lot_step: float = DEFAULT_LOT_STEP,
        minimum_lot: float | None = None,
        maximum_lot: float | None = None,
    ) -> PipelineResult:
        """Process one completed market bar through the trading pipeline.

        The generated signal is stamped with ``bar.timestamp`` before risk
        evaluation. This prevents historical risk controls from using wall-clock
        time and makes daily-loss sessions deterministic in backtests.
        """

        if bar is None:
            raise ValueError("bar cannot be None")

        regime = self.regime_detector.process_bar(
            bar,
        )

        if market_structure_result is None:
            market_structure = self.market_structure.process(
                bar,
            )
        else:
            if not isinstance(market_structure_result, MarketStructureResult):
                raise TypeError(
                    "market_structure_result must be a MarketStructureResult "
                    "or None"
                )
            market_structure = market_structure_result

        market_context = MarketContext(
            bar=bar,
            market_structure=market_structure,
            market_regime=regime,
        )

        feature_evidence = FeatureEvidence.from_market_context(
            market_context,
        )

        feature_vector = self.feature_engineering.process(
            feature_evidence,
        )

        self._append_multi_timeframe_quality_features(
            feature_vector=feature_vector,
            multi_timeframe_result=multi_timeframe_result,
        )

        probability = self.probability_engine.process(
            feature_vector,
        )

        trade_quality_evidence = self.trade_quality_evidence.build(
            market_structure=market_structure,
            feature_vector=feature_vector,
            probability=probability,
            risk_reward_ratio=(
                self.config.risk_manager.minimum_risk_reward_ratio
            ),
        )

        trade_quality = self.trade_quality.evaluate(
            trend_score=trade_quality_evidence.trend_score,
            momentum_score=trade_quality_evidence.momentum_score,
            volatility_score=trade_quality_evidence.volatility_score,
            regime_confidence=regime.confidence,
            signal_confidence=probability.confidence,
            risk_reward_ratio=trade_quality_evidence.risk_reward_ratio,
        )

        decision = self.decision_engine.evaluate(
            regime=regime,
            confluence=confluence,
            probability=probability,
        )

        signal_state_snapshot = (
            (
                self.signal_generator.state.last_emitted_signal,
                self.signal_generator.state.last_emitted_regime,
                self.signal_generator.state.bars_since_last_signal,
            )
            if isinstance(self.signal_generator, SignalGenerator)
            else None
        )

        signal = self.signal_generator.generate_signal(
            regime=regime,
            probability=probability,
            trade_quality=trade_quality,
            confluence=confluence,
            decision=decision,
            market_structure=market_structure,
        )

        self._annotate_signal_rejection(
            signal=signal,
            regime=regime,
            probability=probability,
            trade_quality=trade_quality,
            confluence=confluence,
            decision=decision,
            market_structure=market_structure,
            state_snapshot=signal_state_snapshot,
        )

        self._synchronize_signal_timestamp(
            signal=signal,
            observation_timestamp=bar.timestamp,
        )

        volatility_stop_distance = self._volatility_stop_distance(bar)
        structural_stop_price = self._structural_stop_price(
            signal=signal,
            market_structure=market_structure,
            entry_price=bar.close,
        )
        safety_buffer_distance = (
            tick_size * self.STOP_SAFETY_BUFFER_TICKS
        )

        trade_plan = self.risk_manager.evaluate_signal(
            signal=signal,
            entry_price=bar.close,
            account_balance=account_balance,
            stop_loss_distance=stop_loss_distance,
            pip_value=pip_value,
            volatility_stop_distance=volatility_stop_distance,
            structural_stop_price=structural_stop_price,
            safety_buffer_distance=safety_buffer_distance,
            tick_size=tick_size,
            lot_step=lot_step,
            minimum_lot=minimum_lot,
            maximum_lot=maximum_lot,
            probability=probability.probability,
            confidence=probability.confidence,
            feature_count=feature_vector.size,
            evidence_count=len(probability.evidence),
            regime=str(regime.primary_regime),
        )

        result = PipelineResult(
            regime=regime,
            bos_event=market_structure.last_bos,
            choch_event=market_structure.last_choch,
            liquidity_event=market_structure.last_liquidity,
            features=feature_vector,
            probability=probability,
            decision=decision,
            trade_quality=trade_quality,
            confluence=confluence,
            signal=signal,
            trade_plan=trade_plan,
        )

        self._last_observation_audit = self._build_observation_audit(
            timestamp=bar.timestamp,
            result=result,
        )
        return result

    @property
    def last_observation_audit(self) -> PipelineObservationAudit | None:
        """Return the immutable audit record for the latest observation."""

        return self._last_observation_audit

    @staticmethod
    def _build_observation_audit(
        *,
        timestamp: datetime,
        result: PipelineResult,
    ) -> PipelineObservationAudit:
        """Create a deterministic scalar audit for one completed observation."""

        regime_confirmed = (
            result.regime.primary_regime is not RegimeLabel.UNKNOWN
        )
        probability = result.probability
        trade_quality = result.trade_quality
        confluence = result.confluence
        signal = result.signal
        trade_plan = result.trade_plan

        probability_calculated = probability is not None
        probability_accepted = bool(
            probability is not None and probability.accepted
        )
        trade_quality_calculated = trade_quality is not None
        trade_quality_approved = bool(
            trade_quality is not None and trade_quality.approved
        )
        confluence_available = confluence is not None
        confluence_approved = bool(
            confluence is not None and confluence.approved
        )
        signal_generated = bool(
            signal is not None
            and signal.direction in (SignalDirection.BUY, SignalDirection.SELL)
        )
        risk_approved = bool(
            trade_plan is not None
            and trade_plan.decision is RiskDecision.APPROVE
        )

        scalar_facts = {
            "timestamp": timestamp,
            "regime_confirmed": regime_confirmed,
            "bos_present": result.bos_event is not None,
            "choch_present": result.choch_event is not None,
            "liquidity_present": result.liquidity_event is not None,
            "feature_count": result.features.size if result.features else 0,
            "probability_calculated": probability_calculated,
            "probability_accepted": probability_accepted,
            "probability_value": (
                probability.probability if probability is not None else None
            ),
            "trade_quality_calculated": trade_quality_calculated,
            "trade_quality_approved": trade_quality_approved,
            "trade_quality_score": (
                TradingPipeline._normalize_quality_score(trade_quality.score)
                if trade_quality is not None
                else None
            ),
            "confluence_available": confluence_available,
            "confluence_approved": confluence_approved,
            "confluence_score": (
                confluence.confidence if confluence is not None else None
            ),
            "signal_generated": signal_generated,
            "risk_approved": risk_approved,
        }

        decision_approved = bool(
            result.decision is not None and result.decision.approved
        )
        fully_approved = (
            regime_confirmed
            and probability_accepted
            and trade_quality_approved
            and (not confluence_available or confluence_approved)
            and decision_approved
            and signal_generated
            and risk_approved
        )
        if fully_approved:
            return PipelineObservationAudit(
                disposition=PipelineDisposition.ACCEPTED,
                stage_reached=PipelineStage.APPROVED,
                **scalar_facts,
            )

        rejection_stage, reason_code, reason = (
            TradingPipeline._resolve_rejection(
                result=result,
                regime_confirmed=regime_confirmed,
                probability_accepted=probability_accepted,
                trade_quality_approved=trade_quality_approved,
                confluence_available=confluence_available,
                confluence_approved=confluence_approved,
                signal_generated=signal_generated,
            )
        )
        return PipelineObservationAudit(
            disposition=PipelineDisposition.REJECTED,
            stage_reached=PipelineStage.RISK,
            rejection_stage=rejection_stage,
            reason_code=reason_code,
            reason=reason,
            **scalar_facts,
        )

    @staticmethod
    def _resolve_rejection(
        *,
        result: PipelineResult,
        regime_confirmed: bool,
        probability_accepted: bool,
        trade_quality_approved: bool,
        confluence_available: bool,
        confluence_approved: bool,
        signal_generated: bool,
    ) -> tuple[PipelineStage, str, str]:
        if not regime_confirmed:
            return (
                PipelineStage.REGIME,
                "REGIME_UNCONFIRMED",
                "The market regime is not confirmed.",
            )
        if not probability_accepted:
            reasons = getattr(result.probability, "reasons", None) or []
            return (
                PipelineStage.PROBABILITY,
                "PROBABILITY_REJECTED",
                "; ".join(str(item) for item in reasons)
                or "Probability policy rejected the observation.",
            )
        if not trade_quality_approved:
            reasons = getattr(result.trade_quality, "reasons", None) or []
            return (
                PipelineStage.TRADE_QUALITY,
                "TRADE_QUALITY_REJECTED",
                "; ".join(str(item) for item in reasons)
                or "Trade-quality policy rejected the observation.",
            )
        if confluence_available and not confluence_approved:
            return (
                PipelineStage.CONFLUENCE,
                "CONFLUENCE_REJECTED",
                "Multi-timeframe confluence rejected the observation.",
            )
        if result.decision is not None and not result.decision.approved:
            return (
                PipelineStage.SIGNAL,
                "DECISION_REJECTED",
                "Decision policy did not approve a directional trade.",
            )
        if not signal_generated:
            metadata = getattr(result.signal, "metadata", None) or {}
            reason_code = metadata.get(
                "rejection_code",
                "SIGNAL_NOT_GENERATED",
            )
            reason = metadata.get("rejection_reason") or (
                getattr(result.signal, "reason", "")
                or "Signal generator returned HOLD."
            )
            return (
                PipelineStage.SIGNAL,
                str(reason_code),
                str(reason),
            )

        trade_plan_reason = getattr(result.trade_plan, "reason", "") or (
            "Risk policy rejected the generated signal."
        )
        return (
            PipelineStage.RISK,
            "RISK_REJECTED",
            trade_plan_reason,
        )


    def _annotate_signal_rejection(
        self,
        *,
        signal: TradingSignal,
        regime: object,
        probability: object,
        trade_quality: object,
        confluence: object,
        decision: object,
        market_structure: object,
        state_snapshot: tuple[SignalType, RegimeLabel | None, int] | None,
    ) -> None:
        """Attach the first deterministic signal-emission rejection."""

        if signal.direction in (SignalDirection.BUY, SignalDirection.SELL):
            return
        if not isinstance(self.signal_generator, SignalGenerator):
            return
        if state_snapshot is None:
            return

        generator = self.signal_generator
        context = SignalContext(
            regime=regime,
            probability=probability,
            trade_quality=trade_quality,
            decision=decision,
            confluence=confluence,
        )
        candidate = generator._candidate_signal(regime)
        has_upstream_evidence = any(
            item is not None
            for item in (probability, trade_quality, confluence, decision)
        )

        if not generator.gatekeeper.approve(context):
            code = "UPSTREAM_GATE_REJECTED"
            reason = "An upstream approval gate vetoed signal generation."
        elif candidate is SignalType.HOLD:
            code = "NON_DIRECTIONAL_REGIME"
            reason = "The confirmed regime does not imply BUY or SELL."
        elif regime.confidence < generator.config.minimum_signal_confidence:
            code = "REGIME_CONFIDENCE_BELOW_THRESHOLD"
            reason = (
                f"Regime confidence {regime.confidence:.6f} is below "
                f"{generator.config.minimum_signal_confidence:.6f}."
            )
        elif regime.total_score < generator.config.minimum_total_score:
            code = "REGIME_SCORE_BELOW_THRESHOLD"
            reason = (
                f"Regime total score {regime.total_score:.6f} is below "
                f"{generator.config.minimum_total_score:.6f}."
            )
        else:
            score = generator.scorer.score(context)
            if has_upstream_evidence and not generator.policy.should_emit(score):
                code = "SIGNAL_SCORE_BELOW_THRESHOLD"
                reason = (
                    f"Composite signal score {score.normalized:.6f} is below "
                    "the emission threshold 0.500000."
                )
            elif not generator._decision_direction_agrees(
                candidate_signal=candidate,
                decision=decision,
            ):
                code = "DECISION_DIRECTION_MISMATCH"
                reason = "The approved decision does not match regime direction."
            elif not generator._structure_direction_agrees(
                candidate_signal=candidate,
                market_structure=market_structure,
            ):
                code = "STRUCTURE_DIRECTION_CONFLICT"
                reason = "The newest active BOS/CHOCH opposes signal direction."
            else:
                last_signal, last_regime, bars_since = state_snapshot
                if (
                    last_signal is not SignalType.HOLD
                    and bars_since < generator.config.signal_cooldown_bars
                ):
                    code = "SIGNAL_COOLDOWN"
                    reason = (
                        f"Signal cooldown is active: {bars_since} of "
                        f"{generator.config.signal_cooldown_bars} bars elapsed."
                    )
                elif (
                    not generator.config.allow_duplicate_signals
                    and last_signal is candidate
                    and last_regime is regime.primary_regime
                ):
                    code = "DUPLICATE_SIGNAL"
                    reason = "Duplicate signal in the same regime is disabled."
                else:
                    code = "SIGNAL_NOT_GENERATED"
                    reason = "Signal generator returned HOLD without a known veto."

        signal.metadata["rejection_code"] = code
        signal.metadata["rejection_reason"] = reason


    @classmethod
    def _volatility_stop_distance(cls, bar: MarketBar) -> float | None:
        """Return a deterministic volatility floor from the signal bar range.

        The current pipeline does not expose the regime detector's raw ATR.
        Until that contract is promoted explicitly, the completed signal bar's
        full range is the only broker-independent price-distance volatility
        measurement available here. A multiplier greater than one prevents the
        stop from sitting inside ordinary signal-bar noise.
        """

        try:
            range_size = float(bar.high) - float(bar.low)
        except (AttributeError, TypeError, ValueError) as exc:
            raise TypeError(
                "bar must expose numeric high and low prices"
            ) from exc
        if not isfinite(range_size) or range_size < 0.0:
            raise ValueError("bar range must be finite and non-negative")
        if range_size == 0.0:
            return None

        distance = range_size * cls.VOLATILITY_STOP_RANGE_MULTIPLIER
        if not isfinite(distance) or distance <= 0.0:
            raise ValueError("volatility stop distance must be positive")
        return distance

    @staticmethod
    def _structural_stop_price(
        *,
        signal: TradingSignal,
        market_structure: MarketStructureResult,
        entry_price: float,
    ) -> float | None:
        """Return the newest active aligned BOS/CHOCH invalidation price.

        The protected swing behind the newest active event defines structural
        invalidation. Opposing, neutral, expired, or incorrectly positioned
        events are ignored rather than forcing an invalid risk plan.
        """

        if not isinstance(signal, TradingSignal):
            raise TypeError("signal must be TradingSignal")
        if not isinstance(market_structure, MarketStructureResult):
            raise TypeError("market_structure must be MarketStructureResult")
        if isinstance(entry_price, bool) or not isinstance(
            entry_price, (int, float)
        ):
            raise TypeError("entry_price must be numeric")
        numeric_entry = float(entry_price)
        if not isfinite(numeric_entry) or numeric_entry <= 0.0:
            raise ValueError("entry_price must be positive and finite")

        if signal.signal not in (SignalType.BUY, SignalType.SELL):
            return None

        candidates: list[tuple[datetime, TrendDirection, float]] = []
        if (
            market_structure.last_bos is not None
            and market_structure.bos_freshness > 0.0
        ):
            candidates.append(
                (
                    market_structure.last_bos.timestamp,
                    market_structure.last_bos.direction,
                    market_structure.last_bos.swing_point.price,
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
                    market_structure.last_choch.swing_point.price,
                )
            )

        if not candidates:
            return None

        _, direction, price = max(candidates, key=lambda item: item[0])
        expected_direction = (
            TrendDirection.BULLISH
            if signal.signal is SignalType.BUY
            else TrendDirection.BEARISH
        )
        if direction is not expected_direction:
            return None

        numeric_price = float(price)
        if not isfinite(numeric_price) or numeric_price <= 0.0:
            raise ValueError("structural stop price must be positive and finite")

        if signal.signal is SignalType.BUY and numeric_price < numeric_entry:
            return numeric_price
        if signal.signal is SignalType.SELL and numeric_price > numeric_entry:
            return numeric_price
        return None

    @staticmethod
    def _normalize_quality_score(score: object) -> float:
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise TypeError("trade quality score must be numeric")
        numeric = float(score)
        if not isfinite(numeric):
            raise ValueError("trade quality score must be finite")
        if 0.0 <= numeric <= 1.0:
            return numeric
        if 0.0 <= numeric <= 100.0:
            return numeric / 100.0
        raise ValueError("trade quality score must be within [0, 100]")


    _MOMENTUM_METADATA_KEYS = (
        "momentum",
        "momentum_score",
        "directional_momentum",
        "trend_momentum",
    )
    _VOLATILITY_METADATA_KEYS = (
        "volatility",
        "volatility_score",
        "normalized_volatility",
        "atr_percentile",
    )

    @classmethod
    def _append_multi_timeframe_quality_features(
        cls,
        *,
        feature_vector: FeatureVector,
        multi_timeframe_result: MultiTimeframeResult | None,
    ) -> None:
        """Append independent MTF momentum/volatility facts when available.

        The coordinator currently guarantees directional structure and
        price-action state, but momentum and volatility are optional metadata.
        Missing metadata remains missing; this method never derives those facts
        from probability or confluence confidence.
        """

        if not isinstance(feature_vector, FeatureVector):
            raise TypeError("feature_vector must be FeatureVector")
        if multi_timeframe_result is None:
            return
        if not isinstance(multi_timeframe_result, MultiTimeframeResult):
            raise TypeError(
                "multi_timeframe_result must be MultiTimeframeResult or None"
            )

        states = cls._timeframe_states(multi_timeframe_result)
        cls._append_metadata_feature(
            feature_vector=feature_vector,
            states=states,
            metadata_keys=cls._MOMENTUM_METADATA_KEYS,
            name="multi_timeframe_momentum",
            family="momentum",
        )
        cls._append_metadata_feature(
            feature_vector=feature_vector,
            states=states,
            metadata_keys=cls._VOLATILITY_METADATA_KEYS,
            name="multi_timeframe_volatility",
            family="volatility",
        )

    @staticmethod
    def _timeframe_states(
        result: MultiTimeframeResult,
    ) -> tuple[TimeframeState, ...]:
        states = (
            result.weekly,
            result.daily,
            result.h4,
            result.h1,
            result.m15,
            result.m5,
        )
        if any(not isinstance(state, TimeframeState) for state in states):
            raise TypeError(
                "multi_timeframe_result must contain TimeframeState values"
            )
        return states

    @classmethod
    def _append_metadata_feature(
        cls,
        *,
        feature_vector: FeatureVector,
        states: tuple[TimeframeState, ...],
        metadata_keys: tuple[str, ...],
        name: str,
        family: str,
    ) -> None:
        observations: list[tuple[float, float]] = []

        for state in states:
            if not isinstance(state.metadata, Mapping):
                raise TypeError("TimeframeState.metadata must be a mapping")

            value = cls._first_metadata_value(
                state=state,
                metadata_keys=metadata_keys,
            )
            if value is None:
                continue

            confidence = cls._unit_interval(
                state.confidence,
                f"{state.timeframe.value} confidence",
            )
            observations.append((value, confidence))

        if not observations:
            return

        feature_vector.add(
            Feature(
                name=name,
                value=fmean(value for value, _ in observations),
                confidence=fmean(
                    confidence for _, confidence in observations
                ),
                normalized=True,
                family=family,
                source="multi_timeframe_metadata",
            )
        )

    @classmethod
    def _first_metadata_value(
        cls,
        *,
        state: TimeframeState,
        metadata_keys: tuple[str, ...],
    ) -> float | None:
        for key in metadata_keys:
            if key not in state.metadata:
                continue
            raw_value = state.metadata[key]
            if raw_value is None:
                continue
            return cls._unit_interval(
                raw_value,
                f"{state.timeframe.value} metadata {key!r}",
            )
        return None

    @staticmethod
    def _unit_interval(value: object, name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be a real number")
        normalized = float(value)
        if not isfinite(normalized) or not 0.0 <= normalized <= 1.0:
            raise ValueError(f"{name} must be finite and within [0, 1]")
        return normalized

    def synchronize_account_balance(
        self,
        balance: float,
        *,
        timestamp: datetime | None = None,
    ) -> None:
        """Synchronize authoritative balance with the risk subsystem."""

        self.risk_manager.synchronize_account_balance(
            balance,
            timestamp=timestamp,
        )

    def register_position_opened(self, count: int = 1) -> None:
        """Register exposure after confirmed simulator or broker execution."""

        self.risk_manager.register_position_opened(count)

    def register_position_closed(self, count: int = 1) -> None:
        """Register exposure removal after confirmed position closure."""

        self.risk_manager.register_position_closed(count)

    def register_realized_pnl(
        self,
        pnl: float,
        *,
        timestamp: datetime | None = None,
        balance_after: float | None = None,
    ) -> None:
        """Apply broker deal-level realized P&L to risk state."""

        self.risk_manager.register_realized_pnl(
            pnl,
            timestamp=timestamp,
            balance_after=balance_after,
        )

    def set_open_position_count(self, count: int) -> None:
        """Synchronize externally observed open-position exposure."""

        self.risk_manager.set_open_position_count(count)

    def register_completed_trade(
        self,
        pnl: float,
        *,
        timestamp: datetime | None = None,
        balance_after: float | None = None,
    ) -> None:
        """Register one realized net trade result with risk state."""

        self.risk_manager.register_completed_trade(
            pnl,
            timestamp=timestamp,
            balance_after=balance_after,
        )

    def set_emergency_stop(self, active: bool = True) -> None:
        """Activate or clear the risk subsystem's fail-closed stop."""

        self.risk_manager.set_emergency_stop(active)

    @staticmethod
    def _synchronize_signal_timestamp(
        *,
        signal: object,
        observation_timestamp: datetime,
    ) -> None:
        """Stamp a mutable signal with its completed-bar observation time."""

        if not isinstance(observation_timestamp, datetime):
            raise TypeError("bar timestamp must be a datetime")

        # ``TradingSignal`` is intentionally mutable for backward compatibility.
        # Keeping this assignment in the pipeline avoids changing its public model
        # while ensuring historical risk state uses event time, not wall-clock time.
        setattr(signal, "timestamp", observation_timestamp)
