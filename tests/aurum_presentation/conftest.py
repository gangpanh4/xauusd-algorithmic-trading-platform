from __future__ import annotations

from datetime import UTC, datetime, timedelta

from core.aurum_presentation import (
    AurumDataMode,
    AurumSnapshotInputs,
    FreshnessAssessment,
)
from core.confluence_engine.models import ConfluenceFactor, ConfluenceResult
from core.data.models import MarketBar
from core.decision_engine.models import DecisionResult, DecisionType
from core.fair_value_gap_detector.enums import FairValueGapStatus, FairValueGapType
from core.fair_value_gap_detector.models import FairValueGap, FairValueGapCandidate
from core.feature_engineering.models import Feature, FeatureVector
from core.live_trading.config import LiveTradingConfig
from core.live_trading.state import LiveTradingState
from core.market_structure.enums import (
    BreakType,
    MarketTrend,
    OrderBlockType,
    SwingClassification,
    SwingType,
    TrendDirection,
)
from core.market_structure.measurements import MarketStructureMeasurements
from core.market_structure.models import (
    BOSEvent,
    LiquidityLevel,
    LiquiditySweepEvent,
    MarketStructureResult,
    StructureState,
    SwingPoint,
)
from core.mt5_execution.models import SymbolInfo
from core.multi_timeframe.enums import MarketBias, Timeframe, TimeframeAlignment
from core.multi_timeframe.models import MultiTimeframeResult, TimeframeState
from core.order_block_detector.models import OrderBlock
from core.price_action.models import PriceActionResult
from core.probability_engine.models import EvidenceScore, ProbabilityResult
from core.regime_detector.models import ConfidenceTier, MarketRegime, RegimeLabel
from core.risk_manager.models import RiskDecision, TradePlan
from core.risk_manager.state import RiskManagerState
from core.signal_generator.models import SignalDirection, SignalStrength, TradingSignal
from core.trade_quality.models import QualityLevel, TradeQuality
from core.trading_pipeline.models import (
    PipelineDisposition,
    PipelineObservationAudit,
    PipelineResult,
    PipelineStage,
)

T = datetime(2026, 8, 16, 8, 30, tzinfo=UTC)


def _bar(time: datetime = T, close: float = 100.0) -> MarketBar:
    return MarketBar(
        timestamp=time,
        open=99.5,
        high=101.0,
        low=99.0,
        close=close,
        tick_volume=1000,
    )


def _structure(time: datetime = T) -> MarketStructureResult:
    high = SwingPoint(
        timestamp=time,
        index=10,
        price=101.0,
        swing_type=SwingType.HIGH,
        confirmation_index=12,
        distance_from_previous=2.0,
        atr_multiple=1.5,
        pivot_dominance=0.8,
        confirmation_strength=0.9,
        classification=SwingClassification.HIGHER_HIGH,
    )
    low = SwingPoint(
        timestamp=time,
        index=8,
        price=98.0,
        swing_type=SwingType.LOW,
        confirmation_index=10,
        classification=SwingClassification.HIGHER_LOW,
    )
    bos = BOSEvent(
        timestamp=time,
        break_type=BreakType.BOS,
        direction=TrendDirection.BULLISH,
        swing_point=high,
        break_price=101.2,
        confirmation_index=13,
        break_distance=0.2,
        break_atr_multiple=1.2,
        quality=0.8,
        strength=0.8,
        power_score=0.7,
        structure_score=0.9,
        age=1,
    )
    level = LiquidityLevel(
        timestamp=time,
        price=102.0,
        swing_point=high,
        is_buy_side=True,
    )
    sweep = LiquiditySweepEvent(
        timestamp=time,
        liquidity_level=level,
        sweep_price=102.2,
        confirmation_index=14,
        sweep_distance=0.2,
        atr_multiple=0.9,
        sweep_strength=0.8,
        reaction_strength=0.7,
        reclaim_strength=0.6,
        density=0.5,
        quality=0.75,
        age=1,
    )
    snapshot = StructureState(
        timestamp=time,
        current_bar_index=20,
        trend=MarketTrend.BULLISH,
        confirmed_swings=(low, high),
        last_swing=high,
        last_high=high,
        last_low=low,
        protected_high=high,
        protected_low=low,
        last_bos=bos,
        last_liquidity=sweep,
        tracked_liquidity_levels=(level,),
    )
    return MarketStructureResult(
        timestamp=time,
        last_swing=high,
        last_bos=bos,
        last_choch=None,
        last_liquidity=sweep,
        current_trend=MarketTrend.BULLISH,
        structure_confidence=0.82,
        measurements=MarketStructureMeasurements(),
        swing_score=0.8,
        bos_score=0.9,
        choch_score=0.0,
        liquidity_score=0.75,
        bos_freshness=0.9,
        choch_freshness=0.0,
        liquidity_freshness=0.8,
        freshness_decay_bars=10,
        structure_state=snapshot,
    )


def _price_action(
    time: datetime = T,
    *,
    candidate: bool = False,
    include_order_block: bool = True,
) -> PriceActionResult:
    bar = _bar(time)
    structure = _structure(time)
    if candidate:
        fvg = FairValueGapCandidate(
            timestamp=time,
            gap_type=FairValueGapType.BULLISH,
            top_price=100.5,
            bottom_price=100.0,
            first_bar=bar,
            middle_bar=bar,
            third_bar=bar,
            equilibrium_price=100.25,
            quality_score=0.7,
            status=FairValueGapStatus.NEW,
        )
    else:
        fvg = FairValueGap(
            id=7,
            timestamp=time,
            gap_type=FairValueGapType.BULLISH,
            top_price=100.5,
            bottom_price=100.0,
            first_bar=bar,
            middle_bar=bar,
            third_bar=bar,
            equilibrium_price=100.25,
            quality_score=0.7,
            status=FairValueGapStatus.ACTIVE,
        )
    order_block = None
    if include_order_block:
        order_block = OrderBlock(
            timestamp=time,
            block_type=OrderBlockType.BULLISH,
            top_price=100.0,
            bottom_price=99.0,
            origin_swing=structure.last_swing,
            trigger_break=structure.last_bos,
            trigger_liquidity=structure.last_liquidity,
            creation_index=10,
            confirmation_index=13,
        )
    return PriceActionResult(
        timestamp=time,
        last_order_block=order_block,
        last_fair_value_gap=fvg,
        price_action_confidence=0.77,
    )


def _mtf(
    time: datetime = T,
    *,
    m5_time: datetime | None = None,
    candidate_fvg: bool = False,
) -> MultiTimeframeResult:
    states: dict[Timeframe, TimeframeState] = {}
    for timeframe in Timeframe:
        state_time = m5_time if timeframe is Timeframe.M5 and m5_time is not None else time
        states[timeframe] = TimeframeState(
            timeframe=timeframe,
            timestamp=state_time,
            bias=MarketBias.BULLISH,
            alignment=TimeframeAlignment.ALIGNED,
            confidence=0.8,
            market_structure=_structure(state_time),
            price_action=_price_action(
                state_time,
                candidate=candidate_fvg and timeframe is Timeframe.M5,
            ),
            metadata={"unsafe": {"nested": "ignored"}},
        )
    return MultiTimeframeResult(
        weekly=states[Timeframe.WEEKLY],
        daily=states[Timeframe.DAILY],
        h4=states[Timeframe.H4],
        h1=states[Timeframe.H1],
        m15=states[Timeframe.M15],
        m5=states[Timeframe.M5],
        overall_bias=MarketBias.BULLISH,
        overall_alignment=TimeframeAlignment.ALIGNED,
        confidence=0.81,
        timestamp=time,
    )


def make_inputs(
    *,
    mode: AurumDataMode = AurumDataMode.REAL_READ_ONLY,
    direction: str = "BUY",
    probability_accepted: bool = True,
    quality_approved: bool = True,
    confluence_approved: bool = True,
    decision_approved: bool = True,
    signal_hold: bool = False,
    risk_decision: RiskDecision = RiskDecision.APPROVE,
    audit_accepted: bool | None = None,
    observation_time: datetime = T,
    audit_time: datetime | None = None,
    signal_time: datetime | None = None,
    plan_time: datetime | None = None,
    m5_time: datetime | None = None,
    decision_time: datetime | None = None,
    generated_at: datetime | None = None,
    emergency_stop: bool = False,
    daily_loss_limit_hit: bool = False,
    include_risk_state: bool = True,
    freshness: FreshnessAssessment | None = None,
    geometry: str = "VALID",
    plan_direction: str | None = None,
    candidate_fvg: bool = False,
) -> AurumSnapshotInputs:
    direction_enum = DecisionType.BUY if direction == "BUY" else DecisionType.SELL
    signal_direction = SignalDirection.BUY if direction == "BUY" else SignalDirection.SELL
    if signal_hold:
        signal_direction = SignalDirection.HOLD
    plan_direction_enum = signal_direction
    if plan_direction == "BUY":
        plan_direction_enum = SignalDirection.BUY
    elif plan_direction == "SELL":
        plan_direction_enum = SignalDirection.SELL

    probability = ProbabilityResult(
        probability=0.72,
        confidence=0.8,
        accepted=probability_accepted,
        reasons=[] if probability_accepted else ["probability rejected"],
        evidence=[EvidenceScore("structure", 0.8, 0.9)],
    )
    quality = TradeQuality(
        timestamp=observation_time + timedelta(minutes=5),
        score=75.0,
        level=QualityLevel.HIGH,
        approved=quality_approved,
        confidence=0.76,
        reasons=[] if quality_approved else ["quality rejected"],
    )
    confluence = ConfluenceResult(
        score=0.8,
        maximum_score=1.0,
        confidence=0.8,
        approved=confluence_approved,
        factors=[ConfluenceFactor("structure", True, 0.8, 1.0, "aligned")],
    )
    decision = DecisionResult(
        timestamp=decision_time or observation_time + timedelta(minutes=5),
        decision=direction_enum if decision_approved else DecisionType.HOLD,
        approved=decision_approved,
        confidence=0.75,
        decision_score=0.75,
        regime_confidence=0.8,
        confluence_score=0.8,
    )
    signal = TradingSignal(
        timestamp=signal_time or observation_time,
        direction=signal_direction,
        strength=SignalStrength.STRONG,
        confidence=0.78,
        decision_score=0.75,
        reasons=["fixture signal"],
    )
    plan_signal = TradingSignal(
        timestamp=signal.timestamp,
        direction=plan_direction_enum,
        strength=SignalStrength.STRONG,
        confidence=signal.confidence,
        decision_score=signal.decision_score,
        reasons=["plan signal"],
    )

    if geometry == "VALID":
        entry, stop, target, size = (100.0, 99.0, 102.0, 1.0) if direction == "BUY" else (100.0, 102.0, 98.0, 1.0)
    elif geometry == "WRONG_SIDE":
        entry, stop, target, size = (100.0, 101.0, 102.0, 1.0)
    elif geometry == "ZERO_SIZE":
        entry, stop, target, size = (100.0, 99.0, 102.0, 0.0)
    else:
        entry, stop, target, size = (100.0, float("nan"), 102.0, 1.0)

    trade_plan = TradePlan(
        timestamp=plan_time or observation_time,
        signal=plan_signal,
        decision=risk_decision,
        position_size=size if risk_decision is RiskDecision.APPROVE else 0.0,
        entry_price=entry if risk_decision is RiskDecision.APPROVE else 0.0,
        stop_loss=stop if risk_decision is RiskDecision.APPROVE else 0.0,
        take_profit=target if risk_decision is RiskDecision.APPROVE else 0.0,
        risk_percent=1.0 if risk_decision is RiskDecision.APPROVE else 0.0,
        reward_percent=2.0 if risk_decision is RiskDecision.APPROVE else 0.0,
        risk_reward_ratio=2.0 if risk_decision is RiskDecision.APPROVE else 0.0,
        reason="approved" if risk_decision is RiskDecision.APPROVE else "risk blocked",
        probability=probability.probability,
        confidence=probability.confidence,
        feature_count=2,
        evidence_count=1,
        regime="TRENDING_BULL",
    )
    regime = MarketRegime(
        primary_regime=RegimeLabel.TRENDING_BULL,
        confidence=0.8,
        confidence_tier=ConfidenceTier.HIGH,
        observation_timestamp=observation_time,
        computation_timestamp=observation_time + timedelta(minutes=5),
        trend_score=1.0,
        momentum_score=1.0,
        volatility_score=1.0,
        ema_score=1.0,
        choppiness_score=1.0,
        total_score=5.0,
    )
    features = FeatureVector(
        [
            Feature("structure_score", 0.8, 0.9, True, "structure", "market_structure"),
            Feature("momentum_score", 0.6, 0.8, True, "momentum", "confirmed_regime_detector"),
        ]
    )
    pipeline = PipelineResult(
        regime=regime,
        features=features,
        probability=probability,
        decision=decision,
        trade_quality=quality,
        confluence=confluence,
        signal=signal,
        trade_plan=trade_plan,
    )
    result_approved = pipeline.approved
    final_audit_accepted = result_approved if audit_accepted is None else audit_accepted
    audit = PipelineObservationAudit(
        timestamp=audit_time or observation_time,
        disposition=(
            PipelineDisposition.ACCEPTED if final_audit_accepted else PipelineDisposition.REJECTED
        ),
        stage_reached=PipelineStage.APPROVED if final_audit_accepted else PipelineStage.RISK,
        rejection_stage=None if final_audit_accepted else PipelineStage.RISK,
        reason_code=None if final_audit_accepted else "NOT_APPROVED",
        reason=None if final_audit_accepted else "fixture rejection",
        regime_confirmed=True,
        bos_present=True,
        choch_present=False,
        liquidity_present=True,
        feature_count=2,
        probability_calculated=True,
        probability_accepted=probability_accepted,
        probability_value=probability.probability,
        trade_quality_calculated=True,
        trade_quality_approved=quality_approved,
        trade_quality_score=0.75,
        confluence_available=True,
        confluence_approved=confluence_approved,
        confluence_score=0.8,
        signal_generated=signal_direction is not SignalDirection.HOLD,
        risk_approved=risk_decision is RiskDecision.APPROVE,
    )
    bars = {
        timeframe: [_bar(observation_time)]
        for timeframe in Timeframe
    }
    if m5_time is not None:
        bars[Timeframe.M5] = [_bar(m5_time)]
    risk_state = None
    if include_risk_state:
        risk_state = RiskManagerState(
            initialized=True,
            virtual_balance=10000.0,
            peak_balance=10000.0,
            starting_balance=10000.0,
            current_trading_date=observation_time.date(),
            daily_start_balance=10000.0,
            emergency_stop=emergency_stop,
            daily_loss_limit_hit=daily_loss_limit_hit,
        )
    return AurumSnapshotInputs(
        mode=mode,
        symbol="XAUUSD",
        generated_at_utc=generated_at or observation_time + timedelta(minutes=5),
        backend_commit="7fbb0dc",
        observation_bar=_bar(observation_time),
        bars_by_timeframe=bars,
        multi_timeframe_result=_mtf(
            observation_time,
            m5_time=m5_time,
            candidate_fvg=candidate_fvg,
        ),
        pipeline_result=pipeline,
        pipeline_audit=audit,
        freshness=freshness or FreshnessAssessment("TEST_POLICY", True),
        risk_state=risk_state,
        live_state=LiveTradingState(clock_normalization_validated=True),
        live_config=LiveTradingConfig(live_execution_enabled=False),
        symbol_info=SymbolInfo(
            "XAUUSD", 2, 0.01, 20, 0.01, 100.0, 0.01, True, 0.01, 0.0, 3, 2
        ),
        symbol_info_observed_at_utc=observation_time,
    )
