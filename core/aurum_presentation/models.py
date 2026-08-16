"""Immutable typed contracts for ``AURUM_READ_MODEL_V1``."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from .enums import AurumDataMode, AurumOperatorState


@dataclass(frozen=True, slots=True)
class CapabilityFlagV1:
    name: str
    available: bool


@dataclass(frozen=True, slots=True)
class MetaV1:
    schema_name: str
    schema_version: str
    backend_repository: str
    backend_commit: str
    generated_at_utc: datetime
    data_mode: AurumDataMode
    read_only: bool
    decision_timeframe: str
    observation_time_utc: datetime
    decision_available_at_utc: datetime
    snapshot_id: str
    observation_id: str
    freshness_policy_id: str | None
    capabilities: tuple[CapabilityFlagV1, ...]


@dataclass(frozen=True, slots=True)
class SymbolSpecificationV1:
    available: bool
    name: str | None = None
    digits: int | None = None
    point: float | None = None
    spread: int | float | None = None
    volume_min: float | None = None
    volume_max: float | None = None
    volume_step: float | None = None
    trade_allowed: bool | None = None
    tick_size: float | None = None
    minimum_stop_distance: float | None = None
    filling_mode_flags: int | None = None
    trade_execution_mode: int | None = None
    observed_at_utc: datetime | None = None


@dataclass(frozen=True, slots=True)
class MarketV1:
    symbol: str
    analysis_price: float
    analysis_timestamp_utc: datetime
    symbol_spec: SymbolSpecificationV1


@dataclass(frozen=True, slots=True)
class QuoteV1:
    available: bool = False
    bid: float | None = None
    ask: float | None = None
    mid: float | None = None
    spread_price: float | None = None
    spread_points: float | None = None
    observed_at_utc: datetime | None = None
    age_ms: float | None = None
    stale: bool | None = None


@dataclass(frozen=True, slots=True)
class BarV1:
    timestamp_utc: datetime
    open: float
    high: float
    low: float
    close: float
    tick_volume: int


@dataclass(frozen=True, slots=True)
class BarBucketV1:
    timeframe: str
    completed_only: bool
    items: tuple[BarV1, ...]
    latest_timestamp_utc: datetime | None


@dataclass(frozen=True, slots=True)
class TimeframeMapV1:
    W1: BarBucketV1 | MultiTimeframeFrameV1 | StructureFrameV1 | PriceActionFrameV1 | None
    D1: BarBucketV1 | MultiTimeframeFrameV1 | StructureFrameV1 | PriceActionFrameV1 | None
    H4: BarBucketV1 | MultiTimeframeFrameV1 | StructureFrameV1 | PriceActionFrameV1 | None
    H1: BarBucketV1 | MultiTimeframeFrameV1 | StructureFrameV1 | PriceActionFrameV1 | None
    M15: BarBucketV1 | MultiTimeframeFrameV1 | StructureFrameV1 | PriceActionFrameV1 | None
    M5: BarBucketV1 | MultiTimeframeFrameV1 | StructureFrameV1 | PriceActionFrameV1 | None


@dataclass(frozen=True, slots=True)
class BarsV1:
    frames: TimeframeMapV1


@dataclass(frozen=True, slots=True)
class MultiTimeframeFrameV1:
    timeframe: str
    timestamp_utc: datetime | None
    bias: str
    alignment: str
    confidence: float
    metadata: tuple[tuple[str, str | int | float | bool | None], ...] = ()


@dataclass(frozen=True, slots=True)
class MultiTimeframeV1:
    timestamp_utc: datetime | None
    overall_bias: str
    overall_alignment: str
    confidence: float
    frames: TimeframeMapV1


@dataclass(frozen=True, slots=True)
class SwingV1:
    timestamp_utc: datetime
    index: int
    price: float
    swing_type: str
    confirmation_index: int
    distance_from_previous: float
    atr_multiple: float
    pivot_dominance: float
    confirmation_strength: float
    classification: str


@dataclass(frozen=True, slots=True)
class BreakV1:
    timestamp_utc: datetime
    break_type: str
    direction: str
    swing_point: SwingV1
    break_price: float
    confirmation_index: int
    break_distance: float
    break_atr_multiple: float
    quality: float
    strength: float
    power_score: float
    structure_score: float
    age: int


@dataclass(frozen=True, slots=True)
class LiquidityLevelV1:
    timestamp_utc: datetime
    price: float
    swing_point: SwingV1
    is_buy_side: bool
    side: str


@dataclass(frozen=True, slots=True)
class LiquiditySweepV1:
    timestamp_utc: datetime
    liquidity_level: LiquidityLevelV1
    sweep_price: float
    confirmation_index: int
    sweep_distance: float
    atr_multiple: float
    sweep_strength: float
    reaction_strength: float
    reclaim_strength: float
    density: float
    quality: float
    age: int


@dataclass(frozen=True, slots=True)
class StructureFrameV1:
    available: bool
    timestamp_utc: datetime | None = None
    current_trend: str | None = None
    structure_confidence: float | None = None
    swing_score: float | None = None
    bos_score: float | None = None
    choch_score: float | None = None
    liquidity_score: float | None = None
    bos_freshness: float | None = None
    choch_freshness: float | None = None
    liquidity_freshness: float | None = None
    freshness_decay_bars: int | None = None
    last_swing: SwingV1 | None = None
    last_bos: BreakV1 | None = None
    last_choch: BreakV1 | None = None
    protected_high: SwingV1 | None = None
    protected_low: SwingV1 | None = None
    latest_liquidity_sweep: LiquiditySweepV1 | None = None
    tracked_liquidity_levels: tuple[LiquidityLevelV1, ...] = ()


@dataclass(frozen=True, slots=True)
class StructureV1:
    available: bool
    frames: TimeframeMapV1


@dataclass(frozen=True, slots=True)
class FairValueGapV1:
    kind: str
    id: int | None
    timestamp_utc: datetime
    gap_type: str
    top_price: float
    bottom_price: float
    equilibrium_price: float
    is_discount_zone: bool
    is_premium_zone: bool
    quality_score: float
    age: int
    status: str


@dataclass(frozen=True, slots=True)
class OrderBlockV1:
    timestamp_utc: datetime
    block_type: str
    top_price: float
    bottom_price: float
    origin_swing: SwingV1
    trigger_break: BreakV1
    trigger_liquidity: LiquiditySweepV1 | None
    creation_index: int
    confirmation_index: int


@dataclass(frozen=True, slots=True)
class PriceActionFrameV1:
    available: bool
    timestamp_utc: datetime | None = None
    confidence: float | None = None
    fair_value_gap: FairValueGapV1 | None = None
    order_block: OrderBlockV1 | None = None


@dataclass(frozen=True, slots=True)
class PriceActionV1:
    available: bool
    frames: TimeframeMapV1


@dataclass(frozen=True, slots=True)
class UnavailableFeatureSetV1:
    available: bool = False


@dataclass(frozen=True, slots=True)
class RegimeV1:
    available: bool
    primary_regime: str | None = None
    confidence: float | None = None
    confidence_tier: str | None = None
    status_flags: tuple[str, ...] = ()
    observation_time_utc: datetime | None = None
    computation_time_utc: datetime | None = None
    trend_score: float | None = None
    momentum_score: float | None = None
    volatility_score: float | None = None
    ema_score: float | None = None
    choppiness_score: float | None = None
    total_score: float | None = None
    feature_set: UnavailableFeatureSetV1 = UnavailableFeatureSetV1()


@dataclass(frozen=True, slots=True)
class FeatureItemV1:
    name: str
    value: float
    confidence: float
    normalized: bool
    family: str
    source: str


@dataclass(frozen=True, slots=True)
class FeaturesV1:
    available: bool
    count: int | None = None
    families: tuple[str, ...] = ()
    items: tuple[FeatureItemV1, ...] = ()


@dataclass(frozen=True, slots=True)
class DiagnosticStatusV1:
    available: bool
    classification: str
    status: str | None = None


@dataclass(frozen=True, slots=True)
class MethodologyV1:
    available: bool
    smc: DiagnosticStatusV1
    ict: DiagnosticStatusV1


@dataclass(frozen=True, slots=True)
class IntelligenceDiagnosticsV1:
    available: bool
    classification: str
    items: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ConfluenceFactorV1:
    name: str
    passed: bool
    score: float
    weight: float
    reason: str


@dataclass(frozen=True, slots=True)
class ConfluenceV1:
    available: bool
    score: float | None = None
    maximum_score: float | None = None
    confidence: float | None = None
    approved: bool | None = None
    factors: tuple[ConfluenceFactorV1, ...] = ()


@dataclass(frozen=True, slots=True)
class ProbabilityEvidenceV1:
    family: str
    score: float
    confidence: float


@dataclass(frozen=True, slots=True)
class ProbabilityV1:
    available: bool
    probability: float | None = None
    confidence: float | None = None
    accepted: bool | None = None
    reasons: tuple[str, ...] = ()
    evidence: tuple[ProbabilityEvidenceV1, ...] = ()


@dataclass(frozen=True, slots=True)
class DecisionV1:
    available: bool
    timestamp_utc: datetime | None = None
    type: str | None = None
    approved: bool | None = None
    confidence: float | None = None
    decision_score: float | None = None
    regime_confidence: float | None = None
    confluence_score: float | None = None


@dataclass(frozen=True, slots=True)
class SignalV1:
    available: bool
    timestamp_utc: datetime | None = None
    direction: str | None = None
    strength: str | None = None
    confidence: float | None = None
    decision_score: float | None = None
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TradeQualityV1:
    available: bool
    timestamp_utc: datetime | None = None
    score: float | None = None
    level: str | None = None
    approved: bool | None = None
    confidence: float | None = None
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PipelineAuditV1:
    available: bool
    timestamp_utc: datetime | None = None
    disposition: str | None = None
    stage_reached: str | None = None
    rejection_stage: str | None = None
    reason_code: str | None = None
    reason: str | None = None
    regime_confirmed: bool | None = None
    bos_present: bool | None = None
    choch_present: bool | None = None
    liquidity_present: bool | None = None
    feature_count: int | None = None
    probability_calculated: bool | None = None
    probability_accepted: bool | None = None
    probability_value: float | None = None
    trade_quality_calculated: bool | None = None
    trade_quality_approved: bool | None = None
    trade_quality_score: float | None = None
    confluence_available: bool | None = None
    confluence_approved: bool | None = None
    confluence_score: float | None = None
    signal_generated: bool | None = None
    risk_approved: bool | None = None
    accepted: bool | None = None


@dataclass(frozen=True, slots=True)
class PipelineConsistencyV1:
    pipeline_result_approved: bool
    pipeline_audit_accepted: bool
    approval_consistent: bool


@dataclass(frozen=True, slots=True)
class StrategySetupV1:
    setup_id: str
    strategy_id: str
    direction: str
    status: str
    setup_timeframe: str
    trigger_timeframe: str
    detected_at_utc: datetime
    expires_at_utc: datetime
    cooldown_until_utc: datetime | None
    invalidation_reason: str | None


@dataclass(frozen=True, slots=True)
class StrategyTriggerV1:
    setup_id: str
    trigger_type: str
    status: str
    timeframe: str
    observed_at_utc: datetime
    trigger_price: float
    confirmation_bar_index: int
    reason: str


@dataclass(frozen=True, slots=True)
class StrategyCandidateV1:
    setup_id: str
    created_at_utc: datetime
    direction: str
    entry_price: float
    stop_loss_price: float
    take_profit_prices: tuple[float, ...]
    initial_risk_distance: float
    reward_risk_ratios: tuple[float, ...]
    trigger_type: str
    trigger_timeframe: str


@dataclass(frozen=True, slots=True)
class StrategyObservationV1:
    timestamp_utc: datetime
    reason_code: str
    reason: str
    has_setup: bool
    has_trigger: bool
    has_candidate: bool


@dataclass(frozen=True, slots=True)
class StrategyV1:
    available: bool
    observation: StrategyObservationV1 | None = None
    setup: StrategySetupV1 | None = None
    trigger: StrategyTriggerV1 | None = None
    candidate: StrategyCandidateV1 | None = None


@dataclass(frozen=True, slots=True)
class RiskRuntimeV1:
    available: bool
    initialized: bool | None = None
    last_decision_time_utc: datetime | None = None
    last_trade_close_time_utc: datetime | None = None
    last_balance_update_time_utc: datetime | None = None
    processed_signal_count: int | None = None
    approved_count: int | None = None
    rejected_count: int | None = None
    skipped_count: int | None = None
    completed_trade_count: int | None = None
    breakeven_trade_count: int | None = None
    virtual_balance: float | None = None
    peak_balance: float | None = None
    starting_balance: float | None = None
    current_trading_date: date | None = None
    daily_start_balance: float | None = None
    daily_profit: float | None = None
    daily_loss: float | None = None
    total_profit: float | None = None
    total_loss: float | None = None
    total_net_pnl: float | None = None
    daily_net_pnl: float | None = None
    consecutive_wins: int | None = None
    consecutive_losses: int | None = None
    largest_win: float | None = None
    largest_loss: float | None = None
    open_position_count: int | None = None
    current_drawdown: float | None = None
    max_drawdown: float | None = None
    daily_drawdown: float | None = None
    daily_drawdown_fraction: float | None = None
    current_drawdown_fraction: float | None = None
    emergency_stop: bool | None = None
    daily_loss_limit_hit: bool | None = None


@dataclass(frozen=True, slots=True)
class RiskV1:
    available: bool
    decision: str | None = None
    reason: str | None = None
    evaluated_position_size: float | None = None
    risk_percent: float | None = None
    reward_percent: float | None = None
    risk_reward_ratio: float | None = None
    probability_snapshot: float | None = None
    confidence_snapshot: float | None = None
    feature_count_snapshot: int | None = None
    evidence_count_snapshot: int | None = None
    regime_snapshot: str | None = None
    runtime: RiskRuntimeV1 = RiskRuntimeV1(available=False)


@dataclass(frozen=True, slots=True)
class TradePlanV1:
    source_present: bool
    risk_approved: bool
    geometry_valid: bool
    direction_consistent: bool
    actionable: bool
    suppression_code: str | None
    suppression_reason: str | None
    position_size: float | None = None
    entry_price: float | None = None
    stop_loss_price: float | None = None
    take_profit_price: float | None = None
    risk_percent: float | None = None
    reward_percent: float | None = None
    risk_reward_ratio: float | None = None


@dataclass(frozen=True, slots=True)
class OperatorStateV1:
    state: AurumOperatorState
    direction: str | None
    ready: bool
    blocked: bool
    reason_code: str | None
    reason: str | None
    blocking_stage: str | None


@dataclass(frozen=True, slots=True)
class ExecutionStateV1:
    available: bool
    running: bool | None = None
    processed_bars: int | None = None
    executed_trades: int | None = None
    skipped_trades: int | None = None
    shadow_observations_recorded: int | None = None
    shadow_session_id: str | None = None
    shadow_session_started_at_utc: datetime | None = None
    last_ticket: int | None = None
    open_position_count: int | None = None
    active_order_count: int | None = None
    positions_synchronized: bool | None = None
    active_orders_synchronized: bool | None = None
    realized_deals_synchronized: bool | None = None
    symbol_specification_loaded: bool | None = None
    clock_normalization_validated: bool | None = None
    parity_validation_passed: bool | None = None
    order_submissions_this_session: int | None = None
    consecutive_execution_failures: int | None = None
    last_error: str | None = None
    execution_intent_reconciliation_status: str | None = None
    execution_intent_reconciliation_reason: str | None = None
    execution_intent_reconciliation_ticket: int | None = None
    last_processed_timestamp_utc: datetime | None = None
    last_deal_reconciliation_time_utc: datetime | None = None
    processed_deal_tickets: tuple[int, ...] = ()
    unresolved_partial_ticket: int | None = None
    unresolved_requested_volume: float | None = None
    unresolved_executed_volume: float | None = None
    unresolved_remaining_volume: float | None = None
    unresolved_partial_created_at_utc: datetime | None = None
    last_partial_fill_resolution: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionConfigV1:
    available: bool
    symbol: str | None = None
    timeframe: str | None = None
    poll_interval_seconds: int | None = None
    history_window_bars: int | None = None
    warmup_bars: int | None = None
    server_utc_offset_hours: float | None = None
    clock_max_skew_seconds: float | None = None
    live_execution_enabled: bool | None = None
    demo_execution_approved: bool | None = None
    kill_switch_enabled: bool | None = None
    max_order_submissions: int | None = None
    max_execution_failures: int | None = None


@dataclass(frozen=True, slots=True)
class ExecutionV1:
    available: bool
    read_only: bool
    can_submit_order: bool
    state: ExecutionStateV1
    config: ExecutionConfigV1


@dataclass(frozen=True, slots=True)
class HealthV1:
    atomic_observation_valid: bool
    causal_timestamp_valid: bool
    pipeline_consistency_valid: bool
    freshness_valid: bool
    runtime_safety_valid: bool
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ResearchProvenanceV1:
    run_id: str
    dataset_identity: str
    configuration_fingerprint: str
    artifact_id: str
    artifact_sha256: str
    source_commit: str
    generated_at_utc: datetime


@dataclass(frozen=True, slots=True)
class ResearchSummaryV1:
    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    net_profit: float
    win_rate: float
    max_drawdown: float
    gross_profit: float
    gross_loss: float
    profit_factor: float
    expectancy: float
    average_win: float
    average_loss: float
    largest_win: float
    largest_loss: float
    consecutive_wins: int
    consecutive_losses: int
    average_probability: float
    average_confidence: float
    average_feature_count: float
    average_trade_quality: float
    average_trade_quality_confidence: float
    excellent_quality_trades: int
    high_quality_trades: int
    medium_quality_trades: int
    low_quality_trades: int
    rejected_quality_trades: int


@dataclass(frozen=True, slots=True)
class ResearchEventV1:
    timestamp_utc: datetime
    source: str
    event_type: str
    direction: str | None
    identifier: str | None


@dataclass(frozen=True, slots=True)
class ResearchComparisonV1:
    pipeline_observation_count: int
    pipeline_approval_count: int
    executed_trade_count: int
    strategy_observation_count: int
    strategy_setup_count: int
    strategy_candidate_count: int
    pipeline_reason_counts: tuple[tuple[str, int], ...]
    strategy_reason_counts: tuple[tuple[str, int], ...]
    events: tuple[ResearchEventV1, ...]


@dataclass(frozen=True, slots=True)
class ResearchV1:
    available: bool
    complete: bool
    summary: ResearchSummaryV1 | None = None
    comparison: ResearchComparisonV1 | None = None
    provenance: ResearchProvenanceV1 | None = None


@dataclass(frozen=True, slots=True)
class NewsV1:
    available: bool = False
    events: tuple[str, ...] = ()
    next_event: None = None


@dataclass(frozen=True, slots=True)
class AiV1:
    available: bool = False


@dataclass(frozen=True, slots=True)
class AurumReadModelV1:
    meta: MetaV1
    market: MarketV1
    quote: QuoteV1
    bars: BarsV1
    multi_timeframe: MultiTimeframeV1
    structure: StructureV1
    price_action: PriceActionV1
    regime: RegimeV1
    features: FeaturesV1
    methodology: MethodologyV1
    intelligence_diagnostics: IntelligenceDiagnosticsV1
    confluence: ConfluenceV1
    probability: ProbabilityV1
    decision: DecisionV1
    signal: SignalV1
    trade_quality: TradeQualityV1
    pipeline_audit: PipelineAuditV1
    pipeline_consistency: PipelineConsistencyV1
    strategy: StrategyV1
    risk: RiskV1
    trade_plan: TradePlanV1
    operator_state: OperatorStateV1
    execution: ExecutionV1
    health: HealthV1
    research: ResearchV1
    news: NewsV1
    ai: AiV1
