"""Pure source-object projections into immutable Aurum read-model contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from math import isfinite
from typing import TYPE_CHECKING

from core.fair_value_gap_detector.models import FairValueGap, FairValueGapCandidate
from core.market_structure.models import (
    BOSEvent,
    CHOCHEvent,
    LiquidityLevel,
    LiquiditySweepEvent,
    MarketStructureResult,
    SwingPoint,
)
from core.order_block_detector.models import OrderBlock
from core.price_action.models import PriceActionResult

from .models import (
    BarBucketV1,
    BarsV1,
    BarV1,
    BreakV1,
    ConfluenceFactorV1,
    ConfluenceV1,
    DecisionV1,
    ExecutionConfigV1,
    ExecutionStateV1,
    ExecutionV1,
    FairValueGapV1,
    FeatureItemV1,
    FeaturesV1,
    LiquidityLevelV1,
    LiquiditySweepV1,
    MarketV1,
    MultiTimeframeFrameV1,
    MultiTimeframeV1,
    OrderBlockV1,
    PipelineAuditV1,
    PipelineConsistencyV1,
    PriceActionFrameV1,
    PriceActionV1,
    ProbabilityEvidenceV1,
    ProbabilityV1,
    QuoteV1,
    RegimeV1,
    ResearchComparisonV1,
    ResearchEventV1,
    ResearchProvenanceV1,
    ResearchSummaryV1,
    ResearchV1,
    RiskRuntimeV1,
    RiskV1,
    SignalV1,
    StructureFrameV1,
    StructureV1,
    SwingV1,
    SymbolSpecificationV1,
    TimeframeMapV1,
    TradeQualityV1,
    UnavailableFeatureSetV1,
)

if TYPE_CHECKING:
    from core.backtesting.models import BacktestResult
    from core.backtesting.strategy_comparison import BacktestStrategyComparison
    from core.data.models import MarketBar
    from core.data.quote import MarketQuote
    from core.live_trading.config import LiveTradingConfig
    from core.live_trading.state import LiveTradingState
    from core.mt5_execution.models import SymbolInfo
    from core.multi_timeframe.models import MultiTimeframeResult, TimeframeState
    from core.risk_manager.models import TradePlan
    from core.risk_manager.state import RiskManagerState
    from core.trading_pipeline.models import PipelineObservationAudit, PipelineResult


_TIMEFRAMES = ("W1", "D1", "H4", "H1", "M15", "M5")


def _timeframe_map(
    values: Mapping[
        str,
        BarBucketV1 | MultiTimeframeFrameV1 | StructureFrameV1 | PriceActionFrameV1 | None,
    ],
) -> TimeframeMapV1:
    return TimeframeMapV1(
        W1=values["W1"],
        D1=values["D1"],
        H4=values["H4"],
        H1=values["H1"],
        M15=values["M15"],
        M5=values["M5"],
    )


def _finite_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    numeric = float(value)
    return numeric if isfinite(numeric) else None


def project_bar(bar: MarketBar) -> BarV1:
    return BarV1(
        timestamp_utc=bar.timestamp,
        open=float(bar.open),
        high=float(bar.high),
        low=float(bar.low),
        close=float(bar.close),
        tick_volume=int(bar.tick_volume),
    )


def _bars_for_code(
    bars_by_timeframe: Mapping[TimeframeLike, Sequence[MarketBar]],
    code: str,
) -> Sequence[MarketBar]:
    for timeframe, bars in bars_by_timeframe.items():
        if timeframe.value == code:
            return bars
    return ()


if TYPE_CHECKING:
    from core.multi_timeframe.enums import Timeframe as TimeframeLike
else:
    class TimeframeLike:
        value: str


def project_bars(
    bars_by_timeframe: Mapping[TimeframeLike, Sequence[MarketBar]],
) -> BarsV1:
    buckets: dict[str, BarBucketV1] = {}
    for code in _TIMEFRAMES:
        source_bars = _bars_for_code(bars_by_timeframe, code)
        items = tuple(project_bar(bar) for bar in source_bars)
        buckets[code] = BarBucketV1(
            timeframe=code,
            completed_only=True,
            items=items,
            latest_timestamp_utc=items[-1].timestamp_utc if items else None,
        )
    return BarsV1(frames=_timeframe_map(buckets))


def project_symbol_specification(
    symbol_info: SymbolInfo | None,
    *,
    observed_at_utc: datetime | None,
) -> SymbolSpecificationV1:
    if symbol_info is None:
        return SymbolSpecificationV1(available=False)
    if observed_at_utc is None:
        raise ValueError("symbol_info_observed_at_utc is required with symbol_info")
    return SymbolSpecificationV1(
        available=True,
        name=symbol_info.name,
        digits=symbol_info.digits,
        point=float(symbol_info.point),
        spread=symbol_info.spread,
        volume_min=float(symbol_info.volume_min),
        volume_max=float(symbol_info.volume_max),
        volume_step=float(symbol_info.volume_step),
        trade_allowed=symbol_info.trade_allowed,
        tick_size=float(symbol_info.tick_size),
        minimum_stop_distance=float(symbol_info.minimum_stop_distance),
        filling_mode_flags=symbol_info.filling_mode_flags,
        trade_execution_mode=symbol_info.trade_execution_mode,
        observed_at_utc=observed_at_utc,
    )


def project_market(
    *,
    symbol: str,
    observation_bar: MarketBar,
    symbol_info: SymbolInfo | None,
    symbol_info_observed_at_utc: datetime | None,
) -> MarketV1:
    return MarketV1(
        symbol=symbol.strip().upper(),
        analysis_price=float(observation_bar.close),
        analysis_timestamp_utc=observation_bar.timestamp,
        symbol_spec=project_symbol_specification(
            symbol_info,
            observed_at_utc=symbol_info_observed_at_utc,
        ),
    )



def project_quote(
    quote: MarketQuote | None,
    *,
    symbol_info: SymbolInfo | None,
    generated_at_utc: datetime,
) -> QuoteV1:
    """Project one validated quote without inventing freshness thresholds."""

    if quote is None:
        return QuoteV1(available=False)

    if generated_at_utc.tzinfo is None or generated_at_utc.utcoffset() is None:
        raise ValueError("generated_at_utc must be timezone-aware")
    generated_at = generated_at_utc.astimezone(quote.timestamp_utc.tzinfo)
    age_ms: float | None = None
    if quote.timestamp_utc <= generated_at:
        age_ms = max(
            0.0,
            (generated_at - quote.timestamp_utc).total_seconds() * 1000.0,
        )

    spread_points: float | None = None
    if symbol_info is not None:
        point = float(symbol_info.point)
        if isfinite(point) and point > 0.0:
            spread_points = quote.spread_price / point

    return QuoteV1(
        available=True,
        bid=quote.bid,
        ask=quote.ask,
        mid=quote.mid,
        spread_price=quote.spread_price,
        spread_points=spread_points,
        observed_at_utc=quote.timestamp_utc,
        age_ms=age_ms,
        stale=None,
    )

def _project_mtf_frame(state: TimeframeState) -> MultiTimeframeFrameV1:
    return MultiTimeframeFrameV1(
        timeframe=state.timeframe.value,
        timestamp_utc=state.timestamp,
        bias=state.bias.value,
        alignment=state.alignment.value,
        confidence=float(state.confidence),
        metadata=(),
    )


def project_multi_timeframe(result: MultiTimeframeResult) -> MultiTimeframeV1:
    frames = {
        "W1": _project_mtf_frame(result.weekly),
        "D1": _project_mtf_frame(result.daily),
        "H4": _project_mtf_frame(result.h4),
        "H1": _project_mtf_frame(result.h1),
        "M15": _project_mtf_frame(result.m15),
        "M5": _project_mtf_frame(result.m5),
    }
    return MultiTimeframeV1(
        timestamp_utc=result.timestamp,
        overall_bias=result.overall_bias.value,
        overall_alignment=result.overall_alignment.value,
        confidence=float(result.confidence),
        frames=_timeframe_map(frames),
    )


def _project_swing(swing: SwingPoint | None) -> SwingV1 | None:
    if swing is None:
        return None
    return SwingV1(
        timestamp_utc=swing.timestamp,
        index=swing.index,
        price=float(swing.price),
        swing_type=swing.swing_type.name,
        confirmation_index=swing.confirmation_index,
        distance_from_previous=float(swing.distance_from_previous),
        atr_multiple=float(swing.atr_multiple),
        pivot_dominance=float(swing.pivot_dominance),
        confirmation_strength=float(swing.confirmation_strength),
        classification=swing.classification.name,
    )


def _project_required_swing(swing: SwingPoint) -> SwingV1:
    projected = _project_swing(swing)
    if projected is None:
        raise ValueError("required swing cannot be None")
    return projected


def _project_break(event: BOSEvent | CHOCHEvent | None) -> BreakV1 | None:
    if event is None:
        return None
    return BreakV1(
        timestamp_utc=event.timestamp,
        break_type=event.break_type.name,
        direction=event.direction.name,
        swing_point=_project_required_swing(event.swing_point),
        break_price=float(event.break_price),
        confirmation_index=event.confirmation_index,
        break_distance=float(event.break_distance),
        break_atr_multiple=float(event.break_atr_multiple),
        quality=float(event.quality),
        strength=float(event.strength),
        power_score=float(event.power_score),
        structure_score=float(event.structure_score),
        age=event.age,
    )


def _project_liquidity_level(level: LiquidityLevel) -> LiquidityLevelV1:
    return LiquidityLevelV1(
        timestamp_utc=level.timestamp,
        price=float(level.price),
        swing_point=_project_required_swing(level.swing_point),
        is_buy_side=level.is_buy_side,
        side="BUY_SIDE" if level.is_buy_side else "SELL_SIDE",
    )


def _project_liquidity_sweep(
    sweep: LiquiditySweepEvent | None,
) -> LiquiditySweepV1 | None:
    if sweep is None:
        return None
    return LiquiditySweepV1(
        timestamp_utc=sweep.timestamp,
        liquidity_level=_project_liquidity_level(sweep.liquidity_level),
        sweep_price=float(sweep.sweep_price),
        confirmation_index=sweep.confirmation_index,
        sweep_distance=float(sweep.sweep_distance),
        atr_multiple=float(sweep.atr_multiple),
        sweep_strength=float(sweep.sweep_strength),
        reaction_strength=float(sweep.reaction_strength),
        reclaim_strength=float(sweep.reclaim_strength),
        density=float(sweep.density),
        quality=float(sweep.quality),
        age=sweep.age,
    )


def _project_structure_state(state: TimeframeState) -> StructureFrameV1:
    value = state.market_structure
    if value is None:
        return StructureFrameV1(available=False)
    if not isinstance(value, MarketStructureResult):
        raise TypeError("TimeframeState.market_structure must be MarketStructureResult or None")

    snapshot = value.structure_state
    protected_high = _project_swing(snapshot.protected_high) if snapshot else None
    protected_low = _project_swing(snapshot.protected_low) if snapshot else None
    levels = (
        tuple(_project_liquidity_level(level) for level in snapshot.tracked_liquidity_levels)
        if snapshot
        else ()
    )
    return StructureFrameV1(
        available=True,
        timestamp_utc=value.timestamp,
        current_trend=value.current_trend.name if value.current_trend is not None else None,
        structure_confidence=float(value.structure_confidence),
        swing_score=float(value.swing_score),
        bos_score=float(value.bos_score),
        choch_score=float(value.choch_score),
        liquidity_score=float(value.liquidity_score),
        bos_freshness=float(value.bos_freshness),
        choch_freshness=float(value.choch_freshness),
        liquidity_freshness=float(value.liquidity_freshness),
        freshness_decay_bars=value.freshness_decay_bars,
        last_swing=_project_swing(value.last_swing),
        last_bos=_project_break(value.last_bos),
        last_choch=_project_break(value.last_choch),
        protected_high=protected_high,
        protected_low=protected_low,
        latest_liquidity_sweep=_project_liquidity_sweep(value.last_liquidity),
        tracked_liquidity_levels=levels,
    )


def project_structure(result: MultiTimeframeResult) -> StructureV1:
    states = (result.weekly, result.daily, result.h4, result.h1, result.m15, result.m5)
    frames = {state.timeframe.value: _project_structure_state(state) for state in states}
    return StructureV1(
        available=any(frame.available for frame in frames.values()),
        frames=_timeframe_map(frames),
    )


def _project_fvg(
    value: FairValueGap | FairValueGapCandidate | None,
) -> FairValueGapV1 | None:
    if value is None:
        return None
    if isinstance(value, FairValueGap):
        kind = "CONFIRMED"
        identifier: int | None = value.id
    elif isinstance(value, FairValueGapCandidate):
        kind = "CANDIDATE"
        identifier = None
    else:
        raise TypeError("unsupported fair value gap type")
    return FairValueGapV1(
        kind=kind,
        id=identifier,
        timestamp_utc=value.timestamp,
        gap_type=value.gap_type.value,
        top_price=float(value.top_price),
        bottom_price=float(value.bottom_price),
        equilibrium_price=float(value.equilibrium_price),
        is_discount_zone=value.is_discount_zone,
        is_premium_zone=value.is_premium_zone,
        quality_score=float(value.quality_score),
        age=value.age,
        status=value.status.value,
    )


def _project_order_block(value: OrderBlock | None) -> OrderBlockV1 | None:
    if value is None:
        return None
    trigger_break = _project_break(value.trigger_break)
    if trigger_break is None:
        raise ValueError("OrderBlock.trigger_break cannot be None")
    return OrderBlockV1(
        timestamp_utc=value.timestamp,
        block_type=value.block_type.name,
        top_price=float(value.top_price),
        bottom_price=float(value.bottom_price),
        origin_swing=_project_required_swing(value.origin_swing),
        trigger_break=trigger_break,
        trigger_liquidity=_project_liquidity_sweep(value.trigger_liquidity),
        creation_index=value.creation_index,
        confirmation_index=value.confirmation_index,
    )


def _project_price_action_state(state: TimeframeState) -> PriceActionFrameV1:
    value = state.price_action
    if value is None:
        return PriceActionFrameV1(available=False)
    if not isinstance(value, PriceActionResult):
        raise TypeError("TimeframeState.price_action must be PriceActionResult or None")
    return PriceActionFrameV1(
        available=True,
        timestamp_utc=value.timestamp,
        confidence=float(value.price_action_confidence),
        fair_value_gap=_project_fvg(value.last_fair_value_gap),
        order_block=_project_order_block(value.last_order_block),
    )


def project_price_action(result: MultiTimeframeResult) -> PriceActionV1:
    states = (result.weekly, result.daily, result.h4, result.h1, result.m15, result.m5)
    frames = {state.timeframe.value: _project_price_action_state(state) for state in states}
    return PriceActionV1(
        available=any(frame.available for frame in frames.values()),
        frames=_timeframe_map(frames),
    )


def project_regime(result: PipelineResult) -> RegimeV1:
    regime = result.regime
    return RegimeV1(
        available=True,
        primary_regime=regime.primary_regime.value,
        confidence=float(regime.confidence),
        confidence_tier=regime.confidence_tier.value,
        status_flags=tuple(sorted(flag.value for flag in regime.status_flags)),
        observation_time_utc=regime.observation_timestamp,
        computation_time_utc=regime.computation_timestamp,
        trend_score=float(regime.trend_score),
        momentum_score=float(regime.momentum_score),
        volatility_score=float(regime.volatility_score),
        ema_score=float(regime.ema_score),
        choppiness_score=float(regime.choppiness_score),
        total_score=float(regime.total_score),
        feature_set=UnavailableFeatureSetV1(available=False),
    )


def project_features(result: PipelineResult) -> FeaturesV1:
    vector = result.features
    if vector is None:
        return FeaturesV1(available=False)
    items = tuple(
        FeatureItemV1(
            name=feature.name,
            value=float(feature.value),
            confidence=float(feature.confidence),
            normalized=feature.normalized,
            family=feature.family,
            source=feature.source,
        )
        for feature in vector.features
    )
    return FeaturesV1(
        available=True,
        count=vector.size,
        families=tuple(sorted(vector.families)),
        items=items,
    )


def project_confluence(result: PipelineResult) -> ConfluenceV1:
    source = result.confluence
    if source is None:
        return ConfluenceV1(available=False)
    return ConfluenceV1(
        available=True,
        score=float(source.score),
        maximum_score=float(source.maximum_score),
        confidence=float(source.confidence),
        approved=source.approved,
        factors=tuple(
            ConfluenceFactorV1(
                name=factor.name,
                passed=factor.passed,
                score=float(factor.score),
                weight=float(factor.weight),
                reason=factor.reason,
            )
            for factor in source.factors
        ),
    )


def project_probability(result: PipelineResult) -> ProbabilityV1:
    source = result.probability
    if source is None:
        return ProbabilityV1(available=False)
    return ProbabilityV1(
        available=True,
        probability=float(source.probability),
        confidence=float(source.confidence),
        accepted=source.accepted,
        reasons=tuple(source.reasons),
        evidence=tuple(
            ProbabilityEvidenceV1(
                family=evidence.family,
                score=float(evidence.score),
                confidence=float(evidence.confidence),
            )
            for evidence in source.evidence
        ),
    )


def project_decision(result: PipelineResult) -> DecisionV1:
    source = result.decision
    if source is None:
        return DecisionV1(available=False)
    return DecisionV1(
        available=True,
        timestamp_utc=source.timestamp,
        type=source.decision.value,
        approved=source.approved,
        confidence=float(source.confidence),
        decision_score=float(source.decision_score),
        regime_confidence=float(source.regime_confidence),
        confluence_score=float(source.confluence_score),
    )


def project_signal(result: PipelineResult) -> SignalV1:
    source = result.signal
    if source is None:
        return SignalV1(available=False)
    return SignalV1(
        available=True,
        timestamp_utc=source.timestamp,
        direction=source.direction.value,
        strength=source.strength.value,
        confidence=float(source.confidence),
        decision_score=float(source.decision_score),
        reasons=tuple(source.reasons),
    )


def project_trade_quality(result: PipelineResult) -> TradeQualityV1:
    source = result.trade_quality
    if source is None:
        return TradeQualityV1(available=False)
    return TradeQualityV1(
        available=True,
        timestamp_utc=source.timestamp,
        score=float(source.score),
        level=source.level.value,
        approved=source.approved,
        confidence=float(source.confidence),
        reasons=tuple(source.reasons),
    )


def project_pipeline_audit(audit: PipelineObservationAudit) -> PipelineAuditV1:
    return PipelineAuditV1(
        available=True,
        timestamp_utc=audit.timestamp,
        disposition=audit.disposition.value,
        stage_reached=audit.stage_reached.value,
        rejection_stage=audit.rejection_stage.value if audit.rejection_stage else None,
        reason_code=audit.reason_code,
        reason=audit.reason,
        regime_confirmed=audit.regime_confirmed,
        bos_present=audit.bos_present,
        choch_present=audit.choch_present,
        liquidity_present=audit.liquidity_present,
        feature_count=audit.feature_count,
        probability_calculated=audit.probability_calculated,
        probability_accepted=audit.probability_accepted,
        probability_value=audit.probability_value,
        trade_quality_calculated=audit.trade_quality_calculated,
        trade_quality_approved=audit.trade_quality_approved,
        trade_quality_score=audit.trade_quality_score,
        confluence_available=audit.confluence_available,
        confluence_approved=audit.confluence_approved,
        confluence_score=audit.confluence_score,
        signal_generated=audit.signal_generated,
        risk_approved=audit.risk_approved,
        accepted=audit.accepted,
    )


def project_pipeline_consistency(
    result: PipelineResult,
    audit: PipelineObservationAudit,
) -> PipelineConsistencyV1:
    result_approved = result.approved
    audit_accepted = audit.accepted
    return PipelineConsistencyV1(
        pipeline_result_approved=result_approved,
        pipeline_audit_accepted=audit_accepted,
        approval_consistent=result_approved == audit_accepted,
    )


def project_risk_runtime(state: RiskManagerState | None) -> RiskRuntimeV1:
    if state is None:
        return RiskRuntimeV1(available=False)
    return RiskRuntimeV1(
        available=True,
        initialized=state.initialized,
        last_decision_time_utc=state.last_decision_time,
        last_trade_close_time_utc=state.last_trade_close_time,
        last_balance_update_time_utc=state.last_balance_update_time,
        processed_signal_count=state.processed_signal_count,
        approved_count=state.approved_trade_count,
        rejected_count=state.rejected_trade_count,
        skipped_count=state.skipped_trade_count,
        completed_trade_count=state.completed_trade_count,
        breakeven_trade_count=state.breakeven_trade_count,
        virtual_balance=float(state.virtual_balance),
        peak_balance=float(state.peak_balance),
        starting_balance=float(state.starting_balance),
        current_trading_date=state.current_trading_date,
        daily_start_balance=float(state.daily_start_balance),
        daily_profit=float(state.daily_profit),
        daily_loss=float(state.daily_loss),
        total_profit=float(state.total_profit),
        total_loss=float(state.total_loss),
        total_net_pnl=float(state.total_net_pnl),
        daily_net_pnl=float(state.daily_net_pnl),
        consecutive_wins=state.consecutive_wins,
        consecutive_losses=state.consecutive_losses,
        largest_win=float(state.largest_win),
        largest_loss=float(state.largest_loss),
        open_position_count=state.open_position_count,
        current_drawdown=float(state.current_drawdown),
        max_drawdown=float(state.max_drawdown),
        daily_drawdown=float(state.daily_drawdown),
        daily_drawdown_fraction=float(state.daily_drawdown_fraction),
        current_drawdown_fraction=float(state.current_drawdown_fraction),
        emergency_stop=state.emergency_stop,
        daily_loss_limit_hit=state.daily_loss_limit_hit,
    )


def project_risk(
    plan: TradePlan | None,
    state: RiskManagerState | None,
) -> RiskV1:
    runtime = project_risk_runtime(state)
    if plan is None:
        return RiskV1(available=False, runtime=runtime)
    return RiskV1(
        available=True,
        decision=plan.decision.value,
        reason=plan.reason or None,
        evaluated_position_size=_finite_or_none(plan.position_size),
        risk_percent=_finite_or_none(plan.risk_percent),
        reward_percent=_finite_or_none(plan.reward_percent),
        risk_reward_ratio=_finite_or_none(plan.risk_reward_ratio),
        probability_snapshot=_finite_or_none(plan.probability),
        confidence_snapshot=_finite_or_none(plan.confidence),
        feature_count_snapshot=plan.feature_count,
        evidence_count_snapshot=plan.evidence_count,
        regime_snapshot=plan.regime,
        runtime=runtime,
    )


def project_execution(
    state: LiveTradingState | None,
    config: LiveTradingConfig | None,
) -> ExecutionV1:
    if state is None:
        projected_state = ExecutionStateV1(available=False)
    else:
        projected_state = ExecutionStateV1(
            available=True,
            running=state.running,
            processed_bars=state.processed_bars,
            executed_trades=state.executed_trades,
            skipped_trades=state.skipped_trades,
            shadow_observations_recorded=state.shadow_observations_recorded,
            shadow_session_id=state.shadow_session_id or None,
            shadow_session_started_at_utc=state.shadow_session_started_at,
            last_ticket=state.last_ticket,
            open_position_count=state.open_position_count,
            active_order_count=state.active_order_count,
            positions_synchronized=state.positions_synchronized,
            active_orders_synchronized=state.active_orders_synchronized,
            realized_deals_synchronized=state.realized_deals_synchronized,
            symbol_specification_loaded=state.symbol_specification_loaded,
            clock_normalization_validated=state.clock_normalization_validated,
            parity_validation_passed=state.parity_validation_passed,
            order_submissions_this_session=state.order_submissions_this_session,
            consecutive_execution_failures=state.consecutive_execution_failures,
            last_error=state.last_error or None,
            execution_intent_reconciliation_status=(
                state.execution_intent_reconciliation_status or None
            ),
            execution_intent_reconciliation_reason=(
                state.execution_intent_reconciliation_reason or None
            ),
            execution_intent_reconciliation_ticket=(
                state.execution_intent_reconciliation_ticket
            ),
            last_processed_timestamp_utc=state.last_processed_timestamp,
            last_deal_reconciliation_time_utc=state.last_deal_reconciliation_time,
            processed_deal_tickets=tuple(sorted(state.processed_deal_tickets)),
            unresolved_partial_ticket=state.unresolved_partial_ticket,
            unresolved_requested_volume=_finite_or_none(state.unresolved_requested_volume),
            unresolved_executed_volume=_finite_or_none(state.unresolved_executed_volume),
            unresolved_remaining_volume=_finite_or_none(state.unresolved_remaining_volume),
            unresolved_partial_created_at_utc=state.unresolved_partial_created_at,
            last_partial_fill_resolution=state.last_partial_fill_resolution or None,
        )

    if config is None:
        projected_config = ExecutionConfigV1(available=False)
    else:
        projected_config = ExecutionConfigV1(
            available=True,
            symbol=config.symbol,
            timeframe=config.timeframe,
            poll_interval_seconds=config.poll_interval_seconds,
            history_window_bars=config.history_window_bars,
            warmup_bars=config.warmup_bars,
            server_utc_offset_hours=float(config.mt5_server_utc_offset_hours),
            clock_max_skew_seconds=float(config.mt5_clock_max_skew_seconds),
            live_execution_enabled=config.live_execution_enabled,
            demo_execution_approved=config.demo_execution_approved,
            kill_switch_enabled=config.execution_kill_switch_enabled,
            max_order_submissions=config.maximum_order_submissions_per_session,
            max_execution_failures=config.maximum_consecutive_execution_failures,
        )

    return ExecutionV1(
        available=projected_state.available or projected_config.available,
        read_only=True,
        can_submit_order=False,
        state=projected_state,
        config=projected_config,
    )


def _provenance_complete(provenance: ResearchProvenanceV1 | None) -> bool:
    if provenance is None:
        return False
    required = (
        provenance.run_id,
        provenance.dataset_identity,
        provenance.configuration_fingerprint,
        provenance.artifact_id,
        provenance.source_commit,
    )
    if not all(value.strip() for value in required):
        return False
    checksum = provenance.artifact_sha256.strip().lower()
    if len(checksum) != 64 or any(character not in "0123456789abcdef" for character in checksum):
        return False
    timestamp = provenance.generated_at_utc
    return timestamp.tzinfo is not None and timestamp.utcoffset() is not None


def project_research(
    result: BacktestResult | None,
    comparison: BacktestStrategyComparison | None,
    provenance: ResearchProvenanceV1 | None,
) -> ResearchV1:
    if result is None or comparison is None or not _provenance_complete(provenance):
        return ResearchV1(available=False, complete=False)

    summary = ResearchSummaryV1(
        total_trades=result.total_trades,
        winning_trades=result.winning_trades,
        losing_trades=result.losing_trades,
        breakeven_trades=result.breakeven_trades,
        net_profit=float(result.net_profit),
        win_rate=float(result.win_rate),
        max_drawdown=float(result.max_drawdown),
        gross_profit=float(result.gross_profit),
        gross_loss=float(result.gross_loss),
        profit_factor=float(result.profit_factor),
        expectancy=float(result.expectancy),
        average_win=float(result.average_win),
        average_loss=float(result.average_loss),
        largest_win=float(result.largest_win),
        largest_loss=float(result.largest_loss),
        consecutive_wins=result.consecutive_wins,
        consecutive_losses=result.consecutive_losses,
        average_probability=float(result.average_probability),
        average_confidence=float(result.average_confidence),
        average_feature_count=float(result.average_feature_count),
        average_trade_quality=float(result.average_trade_quality),
        average_trade_quality_confidence=float(result.average_trade_quality_confidence),
        excellent_quality_trades=result.excellent_quality_trades,
        high_quality_trades=result.high_quality_trades,
        medium_quality_trades=result.medium_quality_trades,
        low_quality_trades=result.low_quality_trades,
        rejected_quality_trades=result.rejected_quality_trades,
    )
    projected_comparison = ResearchComparisonV1(
        pipeline_observation_count=comparison.pipeline_observation_count,
        pipeline_approval_count=comparison.pipeline_approval_count,
        executed_trade_count=comparison.executed_trade_count,
        strategy_observation_count=comparison.strategy_observation_count,
        strategy_setup_count=comparison.strategy_setup_count,
        strategy_candidate_count=comparison.strategy_candidate_count,
        pipeline_reason_counts=comparison.pipeline_reason_counts,
        strategy_reason_counts=comparison.strategy_reason_counts,
        events=tuple(
            ResearchEventV1(
                timestamp_utc=event.timestamp,
                source=event.source,
                event_type=event.event_type,
                direction=event.direction,
                identifier=event.identifier,
            )
            for event in comparison.events
        ),
    )
    return ResearchV1(
        available=True,
        complete=True,
        summary=summary,
        comparison=projected_comparison,
        provenance=provenance,
    )
