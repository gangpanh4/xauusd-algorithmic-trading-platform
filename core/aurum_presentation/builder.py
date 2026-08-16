"""Atomic builder for one immutable ``AURUM_READ_MODEL_V1`` snapshot."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from math import isfinite
from typing import TYPE_CHECKING

from .enums import AurumDataMode, AurumOperatorState
from .freshness import FreshnessAssessment
from .identity import build_observation_id, build_snapshot_id, require_aware_utc
from .models import (
    AiV1,
    AurumReadModelV1,
    CapabilityFlagV1,
    DiagnosticStatusV1,
    HealthV1,
    IntelligenceDiagnosticsV1,
    MetaV1,
    MethodologyV1,
    NewsV1,
    OperatorStateV1,
    PipelineConsistencyV1,
    QuoteV1,
    ResearchProvenanceV1,
    StrategyV1,
    TradePlanV1,
)
from .projections import (
    project_bars,
    project_confluence,
    project_decision,
    project_execution,
    project_features,
    project_market,
    project_multi_timeframe,
    project_pipeline_audit,
    project_pipeline_consistency,
    project_price_action,
    project_probability,
    project_regime,
    project_research,
    project_risk,
    project_signal,
    project_structure,
    project_trade_quality,
)

if TYPE_CHECKING:
    from datetime import datetime

    from core.backtesting.models import BacktestResult
    from core.backtesting.strategy_comparison import BacktestStrategyComparison
    from core.data.models import MarketBar
    from core.live_trading.config import LiveTradingConfig
    from core.live_trading.state import LiveTradingState
    from core.mt5_execution.models import SymbolInfo
    from core.multi_timeframe.enums import Timeframe
    from core.multi_timeframe.models import MultiTimeframeResult
    from core.risk_manager.state import RiskManagerState
    from core.trading_pipeline.models import PipelineObservationAudit, PipelineResult


_SCHEMA_NAME = "AURUM_READ_MODEL_V1"
_SCHEMA_VERSION = "1.0.0"
_BACKEND_REPOSITORY = "gangpanh4/xauusd-algorithmic-trading-platform"


@dataclass(frozen=True, slots=True)
class AurumSnapshotInputs:
    """Already-produced sanctioned results consumed by the projection layer."""

    mode: AurumDataMode
    symbol: str
    generated_at_utc: datetime
    backend_commit: str
    observation_bar: MarketBar
    bars_by_timeframe: Mapping[Timeframe, Sequence[MarketBar]]
    multi_timeframe_result: MultiTimeframeResult
    pipeline_result: PipelineResult
    pipeline_audit: PipelineObservationAudit
    freshness: FreshnessAssessment
    risk_state: RiskManagerState | None = None
    live_state: LiveTradingState | None = None
    live_config: LiveTradingConfig | None = None
    symbol_info: SymbolInfo | None = None
    symbol_info_observed_at_utc: datetime | None = None
    research_result: BacktestResult | None = None
    research_comparison: BacktestStrategyComparison | None = None
    research_provenance: ResearchProvenanceV1 | None = None


def _latest_m5_timestamp(inputs: AurumSnapshotInputs) -> datetime | None:
    for timeframe, bars in inputs.bars_by_timeframe.items():
        if timeframe.value == "M5":
            return bars[-1].timestamp if bars else None
    return None


def _same_time(value: datetime | None, expected: datetime, *, name: str) -> bool:
    if value is None:
        return False
    return require_aware_utc(value, name=name) == expected


def _atomic_observation_valid(
    inputs: AurumSnapshotInputs,
    observation_time: datetime,
) -> bool:
    checks = (
        _same_time(
            _latest_m5_timestamp(inputs),
            observation_time,
            name="latest_m5_timestamp",
        ),
        _same_time(
            inputs.multi_timeframe_result.m5.timestamp,
            observation_time,
            name="multi_timeframe_result.m5.timestamp",
        ),
        _same_time(
            inputs.pipeline_audit.timestamp,
            observation_time,
            name="pipeline_audit.timestamp",
        ),
        _same_time(
            inputs.pipeline_result.regime.observation_timestamp,
            observation_time,
            name="regime.observation_timestamp",
        ),
    )
    if not all(checks):
        return False

    signal = inputs.pipeline_result.signal
    if signal is not None and not _same_time(
        signal.timestamp,
        observation_time,
        name="signal.timestamp",
    ):
        return False

    plan = inputs.pipeline_result.trade_plan
    return plan is None or _same_time(
        plan.timestamp,
        observation_time,
        name="trade_plan.timestamp",
    ) 


def _causal_timestamp_valid(
    inputs: AurumSnapshotInputs,
    observation_time: datetime,
    generated_at: datetime,
) -> bool:
    decision_available_at = observation_time + timedelta(minutes=5)
    decision = inputs.pipeline_result.decision
    if decision is not None:
        decision_time = require_aware_utc(decision.timestamp, name="decision.timestamp")
        if decision_time < decision_available_at:
            return False
    if inputs.pipeline_result.approved and generated_at < decision_available_at:
        return False
    return generated_at >= observation_time


def _upstream_directional_path(inputs: AurumSnapshotInputs) -> bool:
    result = inputs.pipeline_result
    probability = result.probability
    quality = result.trade_quality
    confluence = result.confluence
    decision = result.decision
    signal = result.signal
    return bool(
        probability is not None
        and probability.accepted
        and quality is not None
        and quality.approved
        and confluence is not None
        and confluence.approved
        and decision is not None
        and decision.approved
        and decision.decision.value in {"BUY", "SELL"}
        and signal is not None
        and signal.direction.value in {"BUY", "SELL"}
    )


def _direction_consistent(inputs: AurumSnapshotInputs) -> bool:
    result = inputs.pipeline_result
    decision = result.decision
    signal = result.signal
    plan = result.trade_plan
    if decision is None or signal is None or plan is None or plan.signal is None:
        return False
    direction = decision.decision.value
    return bool(
        direction in {"BUY", "SELL"}
        and signal.direction.value == direction
        and plan.signal.direction.value == direction
    )


def _geometry_valid(inputs: AurumSnapshotInputs) -> bool:
    plan = inputs.pipeline_result.trade_plan
    decision = inputs.pipeline_result.decision
    if plan is None or decision is None:
        return False
    values = (plan.position_size, plan.entry_price, plan.stop_loss, plan.take_profit)
    if not all(isfinite(float(value)) for value in values):
        return False
    if plan.position_size <= 0.0:
        return False
    if decision.decision.value == "BUY":
        return plan.stop_loss < plan.entry_price < plan.take_profit
    if decision.decision.value == "SELL":
        return plan.take_profit < plan.entry_price < plan.stop_loss
    return False


def _runtime_safety_valid(inputs: AurumSnapshotInputs) -> bool:
    state = inputs.risk_state
    if inputs.mode is AurumDataMode.REAL_READ_ONLY and state is None:
        return False
    if state is None:
        return True
    return not state.emergency_stop and not state.daily_loss_limit_hit


def _normal_upstream_hold(inputs: AurumSnapshotInputs) -> bool:
    result = inputs.pipeline_result
    probability = result.probability
    quality = result.trade_quality
    confluence = result.confluence
    decision = result.decision
    signal = result.signal
    return bool(
        probability is None
        or not probability.accepted
        or quality is None
        or not quality.approved
        or confluence is None
        or not confluence.approved
        or decision is None
        or not decision.approved
        or decision.decision.value == "HOLD"
        or signal is None
        or signal.direction.value == "HOLD"
    )


def _audit_hold_state(inputs: AurumSnapshotInputs) -> OperatorStateV1:
    audit = inputs.pipeline_audit
    return OperatorStateV1(
        state=AurumOperatorState.HOLD,
        direction=None,
        ready=False,
        blocked=False,
        reason_code=audit.reason_code,
        reason=audit.reason,
        blocking_stage=audit.rejection_stage.value if audit.rejection_stage else None,
    )


def _blocked(
    *,
    code: str,
    reason: str,
    stage: str | None = None,
) -> OperatorStateV1:
    return OperatorStateV1(
        state=AurumOperatorState.BLOCKED,
        direction=None,
        ready=False,
        blocked=True,
        reason_code=code,
        reason=reason,
        blocking_stage=stage,
    )


def _derive_operator_state(
    inputs: AurumSnapshotInputs,
    *,
    atomic_valid: bool,
    causal_valid: bool,
    consistency: PipelineConsistencyV1,
    freshness_valid: bool,
    runtime_safety_valid: bool,
    geometry_valid: bool,
    direction_consistent: bool,
) -> OperatorStateV1:
    if not atomic_valid:
        return _blocked(
            code="SNAPSHOT_PROVENANCE_MISMATCH",
            reason="Readiness-critical results do not belong to one M5 observation.",
        )
    if not causal_valid:
        return _blocked(
            code="CAUSAL_TIMESTAMP_VIOLATION",
            reason="Decision chronology violates the M5 +5 minute availability rule.",
        )
    if not consistency.approval_consistent:
        return _blocked(
            code="PIPELINE_APPROVAL_INCONSISTENCY",
            reason="PipelineResult.approved disagrees with PipelineObservationAudit.accepted.",
        )

    upstream_directional = _upstream_directional_path(inputs)
    if inputs.freshness.critical_failure:
        return _blocked(
            code=inputs.freshness.reason_code or "CRITICAL_FRESHNESS_FAILURE",
            reason=inputs.freshness.reason or "Readiness-critical freshness is invalid.",
        )
    if not freshness_valid and upstream_directional:
        return _blocked(
            code=inputs.freshness.reason_code or "FRESHNESS_INVALID",
            reason=inputs.freshness.reason or "Readiness-critical freshness is invalid.",
        )

    if inputs.mode is AurumDataMode.REAL_READ_ONLY and inputs.risk_state is None:
        return _blocked(
            code="RISK_RUNTIME_UNAVAILABLE",
            reason="Required real-time risk runtime state is unavailable.",
        )

    if not runtime_safety_valid and upstream_directional:
        state = inputs.risk_state
        if state is not None and state.emergency_stop:
            return _blocked(
                code="RISK_EMERGENCY_STOP",
                reason="RiskManager emergency stop prevents readiness.",
                stage="RISK",
            )
        if state is not None and state.daily_loss_limit_hit:
            return _blocked(
                code="DAILY_LOSS_LIMIT_HIT",
                reason="RiskManager daily loss limit prevents readiness.",
                stage="RISK",
            )
        return _blocked(
            code="RUNTIME_SAFETY_BLOCKER",
            reason="Required runtime safety state prevents readiness.",
            stage="RISK",
        )

    if upstream_directional:
        plan = inputs.pipeline_result.trade_plan
        if plan is None:
            return _blocked(
                code="TRADE_PLAN_UNAVAILABLE",
                reason="Directional approved evidence has no TradePlan source.",
                stage="RISK",
            )
        if not direction_consistent:
            return _blocked(
                code="DIRECTION_MISMATCH",
                reason="Decision, Signal, and TradePlan directions do not agree.",
                stage="RISK",
            )
        if plan.decision.value == "APPROVE" and not geometry_valid:
            return _blocked(
                code="INVALID_TRADE_PLAN_GEOMETRY",
                reason="Approved TradePlan geometry is not finite and directional.",
                stage="RISK",
            )

    if _normal_upstream_hold(inputs):
        return _audit_hold_state(inputs)

    plan = inputs.pipeline_result.trade_plan
    if plan is None:
        return _blocked(
            code="TRADE_PLAN_UNAVAILABLE",
            reason="Directional opportunity has no TradePlan source.",
            stage="RISK",
        )
    if plan.decision.value == "REJECT":
        return _blocked(
            code="RISK_REJECTED",
            reason=plan.reason or "RiskManager rejected the directional opportunity.",
            stage="RISK",
        )
    if plan.decision.value == "SKIP":
        return _blocked(
            code="RISK_SKIPPED",
            reason=plan.reason or "RiskManager skipped an otherwise directional opportunity.",
            stage="RISK",
        )

    ready = bool(
        consistency.pipeline_result_approved
        and consistency.pipeline_audit_accepted
        and freshness_valid
        and runtime_safety_valid
        and geometry_valid
        and direction_consistent
        and plan.decision.value == "APPROVE"
    )
    if ready:
        decision = inputs.pipeline_result.decision
        if decision is not None and decision.decision.value == "BUY":
            return OperatorStateV1(
                state=AurumOperatorState.READY_BUY,
                direction="BUY",
                ready=True,
                blocked=False,
                reason_code=None,
                reason=None,
                blocking_stage=None,
            )
        if decision is not None and decision.decision.value == "SELL":
            return OperatorStateV1(
                state=AurumOperatorState.READY_SELL,
                direction="SELL",
                ready=True,
                blocked=False,
                reason_code=None,
                reason=None,
                blocking_stage=None,
            )

    return _audit_hold_state(inputs)


def _project_trade_plan(
    inputs: AurumSnapshotInputs,
    *,
    operator_state: OperatorStateV1,
    geometry_valid: bool,
    direction_consistent: bool,
) -> TradePlanV1:
    source = inputs.pipeline_result.trade_plan
    if source is None:
        return TradePlanV1(
            source_present=False,
            risk_approved=False,
            geometry_valid=False,
            direction_consistent=False,
            actionable=False,
            suppression_code=operator_state.reason_code or "TRADE_PLAN_UNAVAILABLE",
            suppression_reason=operator_state.reason or "No TradePlan source is available.",
        )

    risk_approved = source.decision.value == "APPROVE"
    actionable = operator_state.ready and risk_approved and geometry_valid and direction_consistent
    if not actionable:
        return TradePlanV1(
            source_present=True,
            risk_approved=risk_approved,
            geometry_valid=geometry_valid,
            direction_consistent=direction_consistent,
            actionable=False,
            suppression_code=operator_state.reason_code or "NO_ACTIONABLE_OPPORTUNITY",
            suppression_reason=operator_state.reason or source.reason or "TradePlan is not actionable.",
            risk_percent=float(source.risk_percent) if isfinite(float(source.risk_percent)) else None,
            reward_percent=(
                float(source.reward_percent) if isfinite(float(source.reward_percent)) else None
            ),
            risk_reward_ratio=(
                float(source.risk_reward_ratio)
                if isfinite(float(source.risk_reward_ratio))
                else None
            ),
        )

    return TradePlanV1(
        source_present=True,
        risk_approved=True,
        geometry_valid=True,
        direction_consistent=True,
        actionable=True,
        suppression_code=None,
        suppression_reason=None,
        position_size=float(source.position_size),
        entry_price=float(source.entry_price),
        stop_loss_price=float(source.stop_loss),
        take_profit_price=float(source.take_profit),
        risk_percent=float(source.risk_percent),
        reward_percent=float(source.reward_percent),
        risk_reward_ratio=float(source.risk_reward_ratio),
    )


def _capabilities(
    *,
    structure_available: bool,
    price_action_available: bool,
    features_available: bool,
    confluence_available: bool,
    probability_available: bool,
    decision_available: bool,
    signal_available: bool,
    trade_quality_available: bool,
    execution_available: bool,
    research_available: bool,
    symbol_spec_available: bool,
) -> tuple[CapabilityFlagV1, ...]:
    facts = {
        "ai": False,
        "bars": True,
        "confluence": confluence_available,
        "decision": decision_available,
        "execution": execution_available,
        "features": features_available,
        "intelligence_diagnostics": False,
        "methodology": False,
        "multi_timeframe": True,
        "news": False,
        "price_action": price_action_available,
        "probability": probability_available,
        "quote": False,
        "regime": True,
        "research": research_available,
        "signal": signal_available,
        "strategy": False,
        "structure": structure_available,
        "symbol_spec": symbol_spec_available,
        "trade_quality": trade_quality_available,
    }
    return tuple(
        CapabilityFlagV1(name=name, available=facts[name])
        for name in sorted(facts)
    )


class AurumReadModelBuilder:
    """Build one atomic read-only snapshot from already-produced result objects."""

    @staticmethod
    def build(inputs: AurumSnapshotInputs) -> AurumReadModelV1:
        if inputs.mode is AurumDataMode.MOCK:
            raise ValueError("production AurumReadModelBuilder rejects MOCK mode")

        symbol = inputs.symbol.strip().upper()
        if not symbol:
            raise ValueError("symbol must be non-empty")
        backend_commit = inputs.backend_commit.strip()
        if not backend_commit:
            raise ValueError("backend_commit must be non-empty")

        generated_at = require_aware_utc(inputs.generated_at_utc, name="generated_at_utc")
        observation_time = require_aware_utc(
            inputs.observation_bar.timestamp,
            name="observation_bar.timestamp",
        )
        decision_available_at = observation_time + timedelta(minutes=5)

        atomic_valid = _atomic_observation_valid(inputs, observation_time)
        causal_valid = _causal_timestamp_valid(inputs, observation_time, generated_at)
        consistency = project_pipeline_consistency(
            inputs.pipeline_result,
            inputs.pipeline_audit,
        )
        freshness_valid = inputs.freshness.valid and not inputs.freshness.critical_failure
        runtime_safety_valid = _runtime_safety_valid(inputs)
        geometry_valid = _geometry_valid(inputs)
        direction_consistent = _direction_consistent(inputs)

        operator_state = _derive_operator_state(
            inputs,
            atomic_valid=atomic_valid,
            causal_valid=causal_valid,
            consistency=consistency,
            freshness_valid=freshness_valid,
            runtime_safety_valid=runtime_safety_valid,
            geometry_valid=geometry_valid,
            direction_consistent=direction_consistent,
        )
        trade_plan = _project_trade_plan(
            inputs,
            operator_state=operator_state,
            geometry_valid=geometry_valid,
            direction_consistent=direction_consistent,
        )

        bars = project_bars(inputs.bars_by_timeframe)
        multi_timeframe = project_multi_timeframe(inputs.multi_timeframe_result)
        structure = project_structure(inputs.multi_timeframe_result)
        price_action = project_price_action(inputs.multi_timeframe_result)
        regime = project_regime(inputs.pipeline_result)
        features = project_features(inputs.pipeline_result)
        confluence = project_confluence(inputs.pipeline_result)
        probability = project_probability(inputs.pipeline_result)
        decision = project_decision(inputs.pipeline_result)
        signal = project_signal(inputs.pipeline_result)
        trade_quality = project_trade_quality(inputs.pipeline_result)
        pipeline_audit = project_pipeline_audit(inputs.pipeline_audit)
        risk = project_risk(inputs.pipeline_result.trade_plan, inputs.risk_state)
        execution = project_execution(inputs.live_state, inputs.live_config)
        research = project_research(
            inputs.research_result,
            inputs.research_comparison,
            inputs.research_provenance,
        )
        market = project_market(
            symbol=symbol,
            observation_bar=inputs.observation_bar,
            symbol_info=inputs.symbol_info,
            symbol_info_observed_at_utc=inputs.symbol_info_observed_at_utc,
        )

        reasons: list[str] = []
        if not atomic_valid:
            reasons.append("SNAPSHOT_PROVENANCE_MISMATCH")
        if not causal_valid:
            reasons.append("CAUSAL_TIMESTAMP_VIOLATION")
        if not consistency.approval_consistent:
            reasons.append("PIPELINE_APPROVAL_INCONSISTENCY")
        if not freshness_valid:
            reasons.append(inputs.freshness.reason_code or "CRITICAL_FRESHNESS_FAILURE")
        if not runtime_safety_valid:
            if inputs.mode is AurumDataMode.REAL_READ_ONLY and inputs.risk_state is None:
                reasons.append("RISK_RUNTIME_UNAVAILABLE")
            elif inputs.risk_state is not None and inputs.risk_state.emergency_stop:
                reasons.append("RISK_EMERGENCY_STOP")
            elif inputs.risk_state is not None and inputs.risk_state.daily_loss_limit_hit:
                reasons.append("DAILY_LOSS_LIMIT_HIT")
            else:
                reasons.append("RUNTIME_SAFETY_BLOCKER")

        capabilities = _capabilities(
            structure_available=structure.available,
            price_action_available=price_action.available,
            features_available=features.available,
            confluence_available=confluence.available,
            probability_available=probability.available,
            decision_available=decision.available,
            signal_available=signal.available,
            trade_quality_available=trade_quality.available,
            execution_available=execution.available,
            research_available=research.available,
            symbol_spec_available=market.symbol_spec.available,
        )

        return AurumReadModelV1(
            meta=MetaV1(
                schema_name=_SCHEMA_NAME,
                schema_version=_SCHEMA_VERSION,
                backend_repository=_BACKEND_REPOSITORY,
                backend_commit=backend_commit,
                generated_at_utc=generated_at,
                data_mode=inputs.mode,
                read_only=True,
                decision_timeframe="M5",
                observation_time_utc=observation_time,
                decision_available_at_utc=decision_available_at,
                snapshot_id=build_snapshot_id(),
                observation_id=build_observation_id(
                    symbol=symbol,
                    observation_time_utc=observation_time,
                ),
                freshness_policy_id=inputs.freshness.policy_id,
                capabilities=capabilities,
            ),
            market=market,
            quote=QuoteV1(available=False),
            bars=bars,
            multi_timeframe=multi_timeframe,
            structure=structure,
            price_action=price_action,
            regime=regime,
            features=features,
            methodology=MethodologyV1(
                available=False,
                smc=DiagnosticStatusV1(
                    available=False,
                    classification="DIAGNOSTIC",
                    status=None,
                ),
                ict=DiagnosticStatusV1(
                    available=False,
                    classification="DIAGNOSTIC",
                    status=None,
                ),
            ),
            intelligence_diagnostics=IntelligenceDiagnosticsV1(
                available=False,
                classification="DIAGNOSTIC",
                items=(),
            ),
            confluence=confluence,
            probability=probability,
            decision=decision,
            signal=signal,
            trade_quality=trade_quality,
            pipeline_audit=pipeline_audit,
            pipeline_consistency=consistency,
            strategy=StrategyV1(available=False),
            risk=risk,
            trade_plan=trade_plan,
            operator_state=operator_state,
            execution=execution,
            health=HealthV1(
                atomic_observation_valid=atomic_valid,
                causal_timestamp_valid=causal_valid,
                pipeline_consistency_valid=consistency.approval_consistent,
                freshness_valid=freshness_valid,
                runtime_safety_valid=runtime_safety_valid,
                reason_codes=tuple(dict.fromkeys(reasons)),
            ),
            research=research,
            news=NewsV1(available=False, events=(), next_event=None),
            ai=AiV1(available=False),
        )
