from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.backtesting.config import BacktestConfig, BacktestExecutionModel
from core.backtesting.engine import BacktestingEngine
from core.backtesting.exporter import BacktestExporter
from core.backtesting.models import BacktestResult, ExitReason, TradeOutcome
from core.backtesting.runner import BacktestRunner
from core.backtesting.simulator import TradeSimulator
from core.backtesting.statistics import StatisticsCalculator
from core.execution_economics.profiles import pinned_xauusd_research_profile
from core.feature_engineering.models import Feature, FeatureVector
from core.regime_detector.models import MarketBar, MarketRegime, RegimeLabel
from core.risk_manager.models import RiskDecision, TradePlan
from core.signal_generator.models import (
    SignalDirection,
    SignalStrength,
    TradingSignal,
)
from core.trading_pipeline.market_context import MarketContext

START = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)
INITIAL_BALANCE = 10_000.0


class MigrationClassification(str, Enum):
    EXPECTED_EXECUTION_MODEL_DIFFERENCE = (
        "EXPECTED_EXECUTION_MODEL_DIFFERENCE"
    )
    UNEXPECTED_ANALYTICAL_DIFFERENCE = "UNEXPECTED_ANALYTICAL_DIFFERENCE"
    PROVENANCE_MISMATCH = "PROVENANCE_MISMATCH"
    POTENTIAL_REGRESSION = "POTENTIAL_REGRESSION"


class _QualityLevel(str, Enum):
    HIGH = "HIGH"


class _DecisionValue(str, Enum):
    APPROVE = "APPROVE"


@dataclass(frozen=True)
class _AnalyticalSnapshot:
    timestamp: datetime
    market_regime: tuple[object, ...]
    market_structure: tuple[object, ...]
    features: tuple[tuple[object, ...], ...]
    probability: tuple[object, ...]
    trade_quality: tuple[object, ...]
    confluence: tuple[object, ...]
    decision: tuple[object, ...]
    signal: tuple[object, ...]


@dataclass(frozen=True)
class _RiskSnapshot:
    timestamp: datetime
    account_balance: float
    open_position_count: int
    realized_pnl: float
    probe_position_size: float


@dataclass(frozen=True)
class _ObservationRecord:
    analytical: _AnalyticalSnapshot
    risk: _RiskSnapshot
    trade_plan: TradePlan


@dataclass(frozen=True)
class _AmbiguityObservation:
    timestamp: datetime
    stop_hit: bool
    target_hit: bool

    @property
    def ambiguous(self) -> bool:
        return self.stop_hit and self.target_hit


@dataclass(frozen=True)
class _RunMetrics:
    eligible_m5_observations: int
    analytical_snapshot_count: int
    approved_plan_count: int
    simulator_begin_attempts: int
    completed_trades: int
    entry_timestamps: tuple[datetime, ...]
    entry_reference_prices: tuple[float, ...]
    exit_timestamps: tuple[datetime, ...]
    exit_prices: tuple[float, ...]
    holding_bars: tuple[int, ...]
    holding_durations: tuple[timedelta, ...]
    stop_exits: int
    target_exits: int
    breakeven_exits: int
    actual_stop_and_target_ambiguity_count: int
    end_of_data_exits: int
    gross_pnl: float
    spread_cost: float
    commission: float
    net_pnl: float
    ending_balance: float
    max_drawdown: float
    win_rate: float
    profit_factor: float


@dataclass
class _MigrationRun:
    model: BacktestExecutionModel
    config: BacktestConfig
    context: MarketContext
    pipeline: _MigrationPipeline
    simulator: _InstrumentedTradeSimulator
    engine: BacktestingEngine
    result: BacktestResult
    metrics: _RunMetrics


@dataclass(frozen=True)
class _Difference:
    field: str
    left: object
    right: object
    classification: MigrationClassification
    reason: str


@dataclass(frozen=True)
class _ArtifactBundle:
    historical_window: Mapping[str, object]
    summary: Mapping[str, object]
    statistics: Mapping[str, object]
    trade_metadata: Mapping[str, object]
    execution_economics_trace: Mapping[str, object]

    def items(self) -> tuple[tuple[str, Mapping[str, object]], ...]:
        return (
            ("historical_window", self.historical_window),
            ("summary", self.summary),
            ("statistics", self.statistics),
            ("trade_metadata", self.trade_metadata),
            ("execution_economics_trace", self.execution_economics_trace),
        )


class _ProvenanceValidationError(AssertionError):
    classification = MigrationClassification.PROVENANCE_MISMATCH


class _MigrationPipeline:
    """Test-local analytical/risk probe with no broker or data-source access."""

    def __init__(self) -> None:
        self.records: list[_ObservationRecord] = []
        self.open_position_count = 0
        self.realized_pnl = 0.0
        self.synchronized_balance = INITIAL_BALANCE

    def synchronize_account_balance(
        self,
        balance: float,
        *,
        timestamp: datetime | None = None,
    ) -> None:
        del timestamp
        self.synchronized_balance = float(balance)

    def process_bar(self, bar: MarketBar, **kwargs: object) -> SimpleNamespace:
        account_balance = float(kwargs["account_balance"])
        index = len(self.records)

        regime = MarketRegime(
            primary_regime=RegimeLabel.TRENDING_BULL,
            confidence=0.82,
            observation_timestamp=bar.timestamp,
            computation_timestamp=bar.timestamp,
            trend_score=0.71,
            momentum_score=0.64,
            volatility_score=0.55,
            total_score=0.70,
        )
        market_structure = SimpleNamespace(
            trend="BULLISH",
            structure_id=f"fixture-{bar.timestamp.isoformat()}",
            swing_reference=float(bar.close) - 1.0,
        )
        features = FeatureVector(
            features=[
                Feature(
                    name="fixture_close_normalized",
                    value=float(bar.close) / 100.0,
                    confidence=0.90,
                    normalized=True,
                    family="migration",
                    source="group_4a_fixture",
                ),
                Feature(
                    name="structure_confidence",
                    value=0.80,
                    confidence=0.90,
                    normalized=True,
                    family="structure",
                    source="group_4a_fixture",
                ),
            ]
        )
        probability = SimpleNamespace(
            probability=0.72,
            confidence=0.81,
            accepted=True,
            reasons=(),
            evidence=("GROUP_4A_DETERMINISTIC",),
        )
        trade_quality = SimpleNamespace(
            score=82.0,
            confidence=0.88,
            level=_QualityLevel.HIGH,
            approved=True,
            reasons=(),
        )
        confluence = SimpleNamespace(
            score=0.79,
            confidence=0.79,
            approved=True,
        )
        decision = SimpleNamespace(
            decision=_DecisionValue.APPROVE,
            approved=True,
            direction=SignalDirection.BUY,
        )

        signal_direction = (
            SignalDirection.BUY if index == 0 else SignalDirection.HOLD
        )
        signal = TradingSignal(
            timestamp=bar.timestamp,
            direction=signal_direction,
            strength=SignalStrength.STRONG,
            confidence=0.80,
            decision_score=0.75,
            reasons=["GROUP_4A_DETERMINISTIC"],
            metadata={"strategy_id": "GROUP_4A_FIXTURE"},
        )

        if index == 0:
            trade_plan = TradePlan(
                timestamp=bar.timestamp,
                signal=signal,
                decision=RiskDecision.APPROVE,
                position_size=0.10,
                entry_price=100.0,
                stop_loss=95.0,
                take_profit=105.0,
                risk_percent=1.0,
                reward_percent=1.0,
                risk_reward_ratio=1.0,
                reason="GROUP_4A_FIRST_COMMON_PLAN",
                metadata={
                    "working_balance": account_balance,
                    "open_position_count": self.open_position_count,
                },
                probability=0.72,
                confidence=0.81,
                feature_count=features.size,
                evidence_count=len(probability.evidence),
                regime=regime.primary_regime.value,
            )
        else:
            # This plan is intentionally non-executable (HOLD/SKIP). Its
            # position-size probe makes later execution-derived risk state
            # observable without creating another simulated trade.
            probe_size = (
                0.0
                if self.open_position_count > 0
                else round(account_balance / 100_000.0, 6)
            )
            trade_plan = TradePlan(
                timestamp=bar.timestamp,
                signal=signal,
                decision=RiskDecision.SKIP,
                position_size=probe_size,
                entry_price=float(bar.close),
                stop_loss=float(bar.close) - 5.0,
                take_profit=float(bar.close) + 5.0,
                risk_reward_ratio=1.0,
                reason="GROUP_4A_RISK_STATE_PROBE",
                metadata={
                    "working_balance": account_balance,
                    "open_position_count": self.open_position_count,
                    "realized_pnl": self.realized_pnl,
                },
                probability=0.72,
                confidence=0.81,
                feature_count=features.size,
                evidence_count=len(probability.evidence),
                regime=regime.primary_regime.value,
            )

        analytical = _AnalyticalSnapshot(
            timestamp=bar.timestamp,
            market_regime=(
                regime.primary_regime.value,
                regime.confidence,
                regime.trend_score,
                regime.momentum_score,
                regime.volatility_score,
                regime.total_score,
            ),
            market_structure=(
                market_structure.trend,
                market_structure.structure_id,
                market_structure.swing_reference,
            ),
            features=tuple(
                (
                    feature.name,
                    feature.value,
                    feature.confidence,
                    feature.normalized,
                    feature.family,
                    feature.source,
                )
                for feature in features.features
            ),
            probability=(
                probability.probability,
                probability.confidence,
                probability.accepted,
                probability.reasons,
                probability.evidence,
            ),
            trade_quality=(
                trade_quality.score,
                trade_quality.confidence,
                trade_quality.level.value,
                trade_quality.approved,
                trade_quality.reasons,
            ),
            confluence=(
                confluence.score,
                confluence.confidence,
                confluence.approved,
            ),
            decision=(
                decision.decision.value,
                decision.approved,
                decision.direction.value,
            ),
            signal=(
                signal.direction.value,
                signal.strength.value,
                signal.confidence,
                signal.decision_score,
                tuple(signal.reasons),
                tuple(sorted(signal.metadata.items())),
            ),
        )
        risk = _RiskSnapshot(
            timestamp=bar.timestamp,
            account_balance=account_balance,
            open_position_count=self.open_position_count,
            realized_pnl=self.realized_pnl,
            probe_position_size=trade_plan.position_size,
        )
        self.records.append(
            _ObservationRecord(
                analytical=analytical,
                risk=risk,
                trade_plan=trade_plan,
            )
        )

        return SimpleNamespace(
            regime=regime,
            market_structure=market_structure,
            bos_event=None,
            choch_event=None,
            liquidity_event=None,
            order_block=None,
            fair_value_gap=None,
            features=features,
            probability=probability,
            trade_quality=trade_quality,
            confluence=confluence,
            decision=decision,
            signal=signal,
            trade_plan=trade_plan,
        )

    def register_position_opened(self, count: int = 1) -> None:
        self.open_position_count += count

    def register_position_closed(self, count: int = 1) -> None:
        self.open_position_count -= count
        if self.open_position_count < 0:
            raise AssertionError("test risk state cannot have negative exposure")

    def register_completed_trade(
        self,
        pnl: float,
        *,
        timestamp: datetime | None = None,
        balance_after: float | None = None,
    ) -> None:
        del timestamp
        self.realized_pnl += float(pnl)
        if balance_after is not None:
            self.synchronized_balance = float(balance_after)


class _InstrumentedTradeSimulator(TradeSimulator):
    """Record execution boundaries before delegating to production policy."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.begin_observations: list[datetime] = []
        self.processed_execution_bars: list[datetime] = []
        self.ambiguity_observations: list[_AmbiguityObservation] = []

    def begin(self, trade_plan: TradePlan, observation_bar: MarketBar):
        self.begin_observations.append(observation_bar.timestamp)
        return super().begin(trade_plan, observation_bar)

    def process_bar(self, simulation, bar: MarketBar):
        self.processed_execution_bars.append(bar.timestamp)
        return super().process_bar(simulation, bar)

    def _resolve_bar_exit(self, *, state, bar: MarketBar):
        if state.is_buy:
            stop_hit = float(bar.low) <= state.current_stop_loss
            target_hit = float(bar.high) >= state.take_profit
        else:
            stop_hit = float(bar.high) >= state.current_stop_loss
            target_hit = float(bar.low) <= state.take_profit
        self.ambiguity_observations.append(
            _AmbiguityObservation(
                timestamp=bar.timestamp,
                stop_hit=stop_hit,
                target_hit=target_hit,
            )
        )
        return super()._resolve_bar_exit(state=state, bar=bar)


def _bar(
    minute: int,
    *,
    open_price: float = 100.0,
    high: float = 101.0,
    low: float = 99.0,
    close: float = 100.0,
) -> MarketBar:
    return MarketBar(
        timestamp=START + timedelta(minutes=minute),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=100.0,
        tick_volume=100,
    )


def _main_context() -> MarketContext:
    # V2 fills at 10:05. The 10:05 candle leaves the V2 trade open so the
    # 10:05 analytical observation can prove execution-derived exposure state
    # does not alter pre-risk analytical outputs. The 10:10 candle then hits TP.
    m5 = [
        _bar(0),
        _bar(5, open_price=100.0, high=104.0, low=96.0, close=101.0),
        _bar(10, open_price=101.0, high=106.0, low=100.0, close=105.0),
        _bar(15, open_price=100.0, high=101.0, low=99.0, close=100.0),
        _bar(20, open_price=100.0, high=101.0, low=99.0, close=100.0),
        _bar(25, open_price=100.0, high=101.0, low=99.0, close=100.0),
        _bar(30, open_price=100.0, high=101.0, low=99.0, close=100.0),
        _bar(35, open_price=100.0, high=101.0, low=99.0, close=100.0),
    ]

    # V1 cannot use the 10:00 M15 candle as its fill. At 10:30 the 10:15 M15
    # candle becomes completed and is supplied to the simulator. Its recentered
    # stop/target are 97/107 from the 102 reference; both are touched, so the
    # existing conservative policy chooses the stop.
    m15 = [
        _bar(0),
        _bar(15, open_price=102.0, high=108.0, low=96.0, close=100.0),
        _bar(30, open_price=100.0, high=101.0, low=99.0, close=100.0),
        _bar(45, open_price=100.0, high=101.0, low=99.0, close=100.0),
    ]
    return MarketContext(
        current_bar=m5[-1],
        m5_bars=m5,
        m15_bars=m15,
        h1_bars=m15,
        h4_bars=m15,
    )


def _missing_m5_context() -> MarketContext:
    m5 = [
        _bar(0),
        # 10:05 intentionally absent: V2 must select actual 10:10.
        _bar(10, open_price=100.0, high=106.0, low=96.0, close=105.0),
        _bar(15),
        _bar(20),
    ]
    m15 = [_bar(0), _bar(15), _bar(30)]
    return MarketContext(
        current_bar=m5[-1],
        m5_bars=m5,
        m15_bars=m15,
        h1_bars=m15,
        h4_bars=m15,
    )


def _run_model(
    model: BacktestExecutionModel,
    *,
    context: MarketContext | None = None,
) -> _MigrationRun:
    history = context or _main_context()
    profile = pinned_xauusd_research_profile()
    config = BacktestConfig(
        execution_model=model,
        execution_profile=profile,
        initial_balance=INITIAL_BALANCE,
        warmup_bars=0,
        maximum_trades=None,
    )
    engine = BacktestingEngine(
        config,
        execution_profile=profile,
        progress_interval_bars=None,
    )
    pipeline = _MigrationPipeline()
    engine._create_pipeline = lambda: pipeline  # type: ignore[method-assign]
    simulator = _InstrumentedTradeSimulator(
        execution_profile=profile,
        execution_model=model,
    )
    engine.simulator = simulator

    result = engine.run(history)
    metrics = _metrics(
        context=history,
        pipeline=pipeline,
        simulator=simulator,
        result=result,
    )
    return _MigrationRun(
        model=model,
        config=config,
        context=history,
        pipeline=pipeline,
        simulator=simulator,
        engine=engine,
        result=result,
        metrics=metrics,
    )


def _metrics(
    *,
    context: MarketContext,
    pipeline: _MigrationPipeline,
    simulator: _InstrumentedTradeSimulator,
    result: BacktestResult,
) -> _RunMetrics:
    trades = tuple(result.trades)
    return _RunMetrics(
        eligible_m5_observations=len(context.m5_bars),
        analytical_snapshot_count=len(pipeline.records),
        approved_plan_count=sum(
            record.trade_plan.decision is RiskDecision.APPROVE
            for record in pipeline.records
        ),
        simulator_begin_attempts=len(simulator.begin_observations),
        completed_trades=result.total_trades,
        entry_timestamps=tuple(trade.entry_time for trade in trades),
        entry_reference_prices=tuple(
            float(trade.metadata["reference_entry_price"]) for trade in trades
        ),
        exit_timestamps=tuple(trade.exit_time for trade in trades),
        exit_prices=tuple(float(trade.exit_price) for trade in trades),
        holding_bars=tuple(trade.holding_bars for trade in trades),
        holding_durations=tuple(trade.holding_time for trade in trades),
        stop_exits=sum(trade.exit_reason is ExitReason.STOP_LOSS for trade in trades),
        target_exits=sum(
            trade.exit_reason is ExitReason.TAKE_PROFIT for trade in trades
        ),
        breakeven_exits=sum(
            trade.outcome is TradeOutcome.BREAKEVEN for trade in trades
        ),
        actual_stop_and_target_ambiguity_count=sum(
            observation.ambiguous
            for observation in simulator.ambiguity_observations
        ),
        end_of_data_exits=sum(
            trade.exit_reason is ExitReason.END_OF_DATA for trade in trades
        ),
        gross_pnl=sum(float(trade.gross_profit) for trade in trades),
        spread_cost=sum(float(trade.spread_cost) for trade in trades),
        commission=sum(float(trade.commission) for trade in trades),
        net_pnl=float(result.net_profit),
        ending_balance=INITIAL_BALANCE + float(result.net_profit),
        max_drawdown=float(result.max_drawdown),
        win_rate=float(result.win_rate),
        profit_factor=float(result.profit_factor),
    )


def _common_approved_plans(
    left: _MigrationRun,
    right: _MigrationRun,
) -> tuple[tuple[datetime, TradePlan], ...]:
    matches: list[tuple[datetime, TradePlan]] = []
    for left_record, right_record in zip(
        left.pipeline.records,
        right.pipeline.records,
        strict=True,
    ):
        left_plan = left_record.trade_plan
        right_plan = right_record.trade_plan
        if (
            left_plan.decision is RiskDecision.APPROVE
            and right_plan.decision is RiskDecision.APPROVE
            and left_plan == right_plan
        ):
            matches.append((left_record.analytical.timestamp, left_plan))
    return tuple(matches)


def _analytical_differences(
    left: _MigrationRun,
    right: _MigrationRun,
) -> tuple[_Difference, ...]:
    differences: list[_Difference] = []
    for left_record, right_record in zip(
        left.pipeline.records,
        right.pipeline.records,
        strict=True,
    ):
        if left_record.analytical != right_record.analytical:
            differences.append(
                _Difference(
                    field=f"analytical@{left_record.analytical.timestamp.isoformat()}",
                    left=left_record.analytical,
                    right=right_record.analytical,
                    classification=(
                        MigrationClassification.UNEXPECTED_ANALYTICAL_DIFFERENCE
                    ),
                    reason=(
                        "execution_model_id must not alter pre-risk analytical "
                        "outputs"
                    ),
                )
            )
    return tuple(differences)


def _risk_plan_differences(
    left: _MigrationRun,
    right: _MigrationRun,
) -> tuple[_Difference, ...]:
    differences: list[_Difference] = []
    for left_record, right_record in zip(
        left.pipeline.records,
        right.pipeline.records,
        strict=True,
    ):
        if left_record.trade_plan == right_record.trade_plan:
            continue

        risk_changed = any(
            (
                left_record.risk.account_balance
                != right_record.risk.account_balance,
                left_record.risk.open_position_count
                != right_record.risk.open_position_count,
                left_record.risk.realized_pnl
                != right_record.risk.realized_pnl,
            )
        )
        classification = (
            MigrationClassification.EXPECTED_EXECUTION_MODEL_DIFFERENCE
            if risk_changed
            else MigrationClassification.POTENTIAL_REGRESSION
        )
        differences.append(
            _Difference(
                field=f"trade_plan@{left_record.risk.timestamp.isoformat()}",
                left=left_record.trade_plan,
                right=right_record.trade_plan,
                classification=classification,
                reason=(
                    "later risk probe differs only after realized balance or "
                    "open-position state diverges"
                    if risk_changed
                    else "TradePlan changed without an execution-derived risk cause"
                ),
            )
        )
    return tuple(differences)


def _execution_metric_differences(
    left: _RunMetrics,
    right: _RunMetrics,
) -> tuple[_Difference, ...]:
    differences: list[_Difference] = []
    for field in _RunMetrics.__dataclass_fields__:
        left_value = getattr(left, field)
        right_value = getattr(right, field)
        if left_value == right_value:
            continue
        differences.append(
            _Difference(
                field=field,
                left=left_value,
                right=right_value,
                classification=(
                    MigrationClassification.EXPECTED_EXECUTION_MODEL_DIFFERENCE
                ),
                reason="field is downstream of the versioned execution bar clock",
            )
        )
    return tuple(differences)


_REQUIRED_PROVENANCE_FIELDS = (
    "execution_model_id",
    "decision_clock",
    "decision_available_after_minutes",
    "entry_policy",
    "entry_clock",
    "lifecycle_clock",
    "lifecycle_bar_minutes",
    "closed_bar_consumption",
    "comparable_with_unversioned_results",
)


def _normalized_contract(
    artifact_name: str,
    payload: Mapping[str, object],
) -> dict[str, object]:
    nested = payload.get("execution_model")
    nested_contract = nested if isinstance(nested, Mapping) else {}

    if (
        "execution_model_id" in payload
        and "execution_model_id" in nested_contract
        and payload["execution_model_id"]
        != nested_contract["execution_model_id"]
    ):
        raise _ProvenanceValidationError(
            f"{artifact_name}: conflicting execution_model_id values"
        )

    contract: dict[str, object] = {}
    for field in _REQUIRED_PROVENANCE_FIELDS:
        top_value = payload.get(field)
        nested_value = nested_contract.get(field)
        if (
            top_value is not None
            and nested_value is not None
            and top_value != nested_value
        ):
            raise _ProvenanceValidationError(
                f"{artifact_name}: conflicting {field} values"
            )
        value = top_value if top_value is not None else nested_value
        if value is None:
            raise _ProvenanceValidationError(
                f"{artifact_name}: missing execution-model contract field {field}"
            )
        contract[field] = value

    if contract["comparable_with_unversioned_results"] is not False:
        raise _ProvenanceValidationError(
            f"{artifact_name}: versioned result marked comparable with unversioned"
        )
    return contract


def _validate_artifact_bundle(bundle: _ArtifactBundle) -> dict[str, object]:
    contracts = [
        (name, _normalized_contract(name, payload))
        for name, payload in bundle.items()
    ]
    expected_name, expected = contracts[0]
    for name, contract in contracts[1:]:
        if contract != expected:
            raise _ProvenanceValidationError(
                f"{name}: execution-model provenance conflicts with {expected_name}"
            )
    return expected


def _artifact_bundle(run: _MigrationRun, tmp_path: Path) -> _ArtifactBundle:
    # Use the production historical-window capture logic without invoking
    # BacktestRunner.run(), MultiTimeframeLoader.load(), or any MT5 history API.
    runner = object.__new__(BacktestRunner)
    runner.config = run.config
    runner.execution_profile = run.config.resolved_execution_profile()
    runner.engine = run.engine
    runner._capture_historical_window(
        context=run.context,
        requested_end_time=run.context.m5_bars[-1].timestamp,
        requested_bars=len(run.context.m5_bars),
    )
    historical_window = dict(runner._last_actual_window)

    output = tmp_path / run.model.value
    exporter = BacktestExporter(output)
    provenance = run.config.execution_model_provenance()
    summary_path = exporter.export_summary(
        run.result,
        execution_model_provenance=provenance,
    )
    statistics = StatisticsCalculator().calculate(run.result)
    statistics_path = exporter.export_statistics(
        asdict(statistics),
        execution_model_provenance=provenance,
    )

    trade = run.result.trades[0]
    trace = trade.metadata.get("execution_economics_trace")
    assert isinstance(trace, Mapping)
    return _ArtifactBundle(
        historical_window=historical_window,
        summary=json.loads(summary_path.read_text(encoding="utf-8")),
        statistics=json.loads(statistics_path.read_text(encoding="utf-8")),
        trade_metadata=dict(trade.metadata),
        execution_economics_trace=dict(trace),
    )


def _replace_artifact(
    bundle: _ArtifactBundle,
    name: str,
    payload: Mapping[str, object],
) -> _ArtifactBundle:
    values: dict[str, Mapping[str, object]] = {
        key: value for key, value in bundle.items()
    }
    values[name] = payload
    return _ArtifactBundle(
        historical_window=values["historical_window"],
        summary=values["summary"],
        statistics=values["statistics"],
        trade_metadata=values["trade_metadata"],
        execution_economics_trace=values["execution_economics_trace"],
    )


def test_v1_v2_migration_preserves_analytics_and_diverges_at_execution_only() -> None:
    v1 = _run_model(BacktestExecutionModel.M15_COMPLETED_OHLC_V1)
    v2 = _run_model(BacktestExecutionModel.M5_COMPLETED_OHLC_V2)

    # Invariant 1: exact same ordered M5 analytical observations.
    v1_timestamps = tuple(
        record.analytical.timestamp for record in v1.pipeline.records
    )
    v2_timestamps = tuple(
        record.analytical.timestamp for record in v2.pipeline.records
    )
    assert v1_timestamps == v2_timestamps
    assert v1_timestamps == tuple(bar.timestamp for bar in v1.context.m5_bars)

    # Invariants 2 and 6: no pre-risk analytical differences anywhere.
    analytical_differences = _analytical_differences(v1, v2)
    assert analytical_differences == ()

    # Invariant 3: first common approved plan is bit-for-bit equal before the
    # simulator sees it, including its timestamp, signal, geometry, and sizing.
    common_plans = _common_approved_plans(v1, v2)
    assert len(common_plans) == 1
    first_plan_timestamp, first_plan = common_plans[0]
    assert first_plan_timestamp == START
    assert first_plan.decision is RiskDecision.APPROVE
    assert first_plan.position_size == pytest.approx(0.10)
    assert first_plan.entry_price == pytest.approx(100.0)
    assert first_plan.stop_loss == pytest.approx(95.0)
    assert first_plan.take_profit == pytest.approx(105.0)

    # Invariant 4: both simulators begin from the same approved observation;
    # the first non-provenance divergence is the selected execution bar clock.
    assert v1.simulator.begin_observations == [START]
    assert v2.simulator.begin_observations == [START]
    assert v1.simulator.processed_execution_bars[0] == START + timedelta(minutes=15)
    assert v2.simulator.processed_execution_bars[0] == START + timedelta(minutes=5)

    # Invariant 5: later TradePlan differences are allowed only where the
    # execution lifecycle has already changed exposure/balance/risk state.
    risk_differences = _risk_plan_differences(v1, v2)
    assert risk_differences
    assert all(
        difference.classification
        is MigrationClassification.EXPECTED_EXECUTION_MODEL_DIFFERENCE
        for difference in risk_differences
    )
    first_risk_difference = risk_differences[0]
    assert first_risk_difference.field == (
        f"trade_plan@{(START + timedelta(minutes=5)).isoformat()}"
    )
    v1_at_1005 = v1.pipeline.records[1].risk
    v2_at_1005 = v2.pipeline.records[1].risk
    assert v1_at_1005.account_balance == pytest.approx(INITIAL_BALANCE)
    assert v2_at_1005.account_balance == pytest.approx(INITIAL_BALANCE)
    assert v1_at_1005.open_position_count == 0
    assert v2_at_1005.open_position_count == 1

    # Execution metrics are compared, but equality is not required. Every
    # observed difference is downstream of the deliberately different clocks.
    metric_differences = _execution_metric_differences(v1.metrics, v2.metrics)
    assert metric_differences
    assert all(
        difference.classification
        is MigrationClassification.EXPECTED_EXECUTION_MODEL_DIFFERENCE
        for difference in metric_differences
    )

    # Required metric coverage and expected deterministic fixture outcomes.
    assert v1.metrics.eligible_m5_observations == v2.metrics.eligible_m5_observations
    assert v1.metrics.analytical_snapshot_count == v2.metrics.analytical_snapshot_count
    assert v1.metrics.approved_plan_count == v2.metrics.approved_plan_count == 1
    assert (
        v1.metrics.simulator_begin_attempts
        == v2.metrics.simulator_begin_attempts
        == 1
    )
    assert v1.metrics.completed_trades == v2.metrics.completed_trades == 1
    assert v1.metrics.entry_timestamps == (START + timedelta(minutes=15),)
    assert v2.metrics.entry_timestamps == (START + timedelta(minutes=5),)
    assert v1.metrics.entry_reference_prices == pytest.approx((102.0,))
    assert v2.metrics.entry_reference_prices == pytest.approx((100.0,))
    assert v1.metrics.exit_timestamps == (START + timedelta(minutes=15),)
    assert v2.metrics.exit_timestamps == (START + timedelta(minutes=10),)
    assert v1.metrics.exit_prices == pytest.approx((97.0,))
    assert v2.metrics.exit_prices == pytest.approx((105.0,))
    assert v1.metrics.holding_bars == (1,)
    assert v2.metrics.holding_bars == (2,)
    assert v1.metrics.holding_durations == (timedelta(0),)
    assert v2.metrics.holding_durations == (timedelta(minutes=5),)
    assert v1.metrics.stop_exits == 1
    assert v2.metrics.stop_exits == 0
    assert v1.metrics.target_exits == 0
    assert v2.metrics.target_exits == 1
    assert v1.metrics.breakeven_exits == v2.metrics.breakeven_exits == 0
    assert v1.metrics.actual_stop_and_target_ambiguity_count == 1
    assert v2.metrics.actual_stop_and_target_ambiguity_count == 0
    assert v1.metrics.end_of_data_exits == v2.metrics.end_of_data_exits == 0
    assert v1.metrics.gross_pnl == pytest.approx(-50.0)
    assert v2.metrics.gross_pnl == pytest.approx(50.0)
    assert v1.metrics.spread_cost == v2.metrics.spread_cost == pytest.approx(0.0)
    assert v1.metrics.commission == v2.metrics.commission == pytest.approx(0.0)
    assert v1.metrics.net_pnl == pytest.approx(-50.0)
    assert v2.metrics.net_pnl == pytest.approx(50.0)
    assert v1.metrics.ending_balance == pytest.approx(9_950.0)
    assert v2.metrics.ending_balance == pytest.approx(10_050.0)
    assert v1.metrics.max_drawdown == pytest.approx(50.0)
    assert v2.metrics.max_drawdown == pytest.approx(0.0)
    assert v1.metrics.win_rate == pytest.approx(0.0)
    assert v2.metrics.win_rate == pytest.approx(100.0)
    assert v1.metrics.profit_factor == pytest.approx(0.0)
    assert v2.metrics.profit_factor == pytest.approx(0.0)

    # No profitability inference belongs in migration validation. These are
    # deterministic execution-model outcomes only.
    assert v1.model is BacktestExecutionModel.M15_COMPLETED_OHLC_V1
    assert v2.model is BacktestExecutionModel.M5_COMPLETED_OHLC_V2


def test_v2_never_uses_decision_candle_and_never_fabricates_missing_m5() -> None:
    run = _run_model(
        BacktestExecutionModel.M5_COMPLETED_OHLC_V2,
        context=_missing_m5_context(),
    )

    trade = run.result.trades[0]
    decision_available_at = START + timedelta(minutes=5)
    assert run.simulator.begin_observations == [START]
    assert run.simulator.processed_execution_bars[0] == START + timedelta(minutes=10)
    assert START + timedelta(minutes=5) not in tuple(
        bar.timestamp for bar in run.context.m5_bars
    )
    assert trade.entry_time == START + timedelta(minutes=10)
    assert trade.entry_time >= decision_available_at
    assert trade.entry_time != START
    assert trade.metadata["decision_available_at"] == decision_available_at.isoformat()
    assert trade.metadata["entry_reference_timestamp"] == trade.entry_time.isoformat()
    assert trade.metadata["execution_model_id"] == "M5_COMPLETED_OHLC_V2"


def test_v1_frozen_fixture_is_reproducible() -> None:
    first = _run_model(BacktestExecutionModel.M15_COMPLETED_OHLC_V1)
    second = _run_model(BacktestExecutionModel.M15_COMPLETED_OHLC_V1)

    assert first.metrics == second.metrics
    assert tuple(
        record.analytical for record in first.pipeline.records
    ) == tuple(record.analytical for record in second.pipeline.records)

    # Frozen deterministic V1 migration anchor. Any change requires explicit
    # review because V1 is the accepted compatibility model.
    metrics = first.metrics
    assert metrics.eligible_m5_observations == 8
    assert metrics.analytical_snapshot_count == 8
    assert metrics.approved_plan_count == 1
    assert metrics.simulator_begin_attempts == 1
    assert metrics.completed_trades == 1
    assert metrics.entry_timestamps == (START + timedelta(minutes=15),)
    assert metrics.entry_reference_prices == pytest.approx((102.0,))
    assert metrics.exit_timestamps == (START + timedelta(minutes=15),)
    assert metrics.exit_prices == pytest.approx((97.0,))
    assert metrics.holding_bars == (1,)
    assert metrics.holding_durations == (timedelta(0),)
    assert metrics.stop_exits == 1
    assert metrics.target_exits == 0
    assert metrics.breakeven_exits == 0
    assert metrics.actual_stop_and_target_ambiguity_count == 1
    assert metrics.end_of_data_exits == 0
    assert metrics.gross_pnl == pytest.approx(-50.0)
    assert metrics.spread_cost == pytest.approx(0.0)
    assert metrics.commission == pytest.approx(0.0)
    assert metrics.net_pnl == pytest.approx(-50.0)
    assert metrics.ending_balance == pytest.approx(9_950.0)
    assert metrics.max_drawdown == pytest.approx(50.0)
    assert metrics.win_rate == pytest.approx(0.0)
    assert metrics.profit_factor == pytest.approx(0.0)


def test_versioned_provenance_is_consistent_and_unversioned_is_rejected(
    tmp_path: Path,
) -> None:
    v1 = _run_model(BacktestExecutionModel.M15_COMPLETED_OHLC_V1)
    v2 = _run_model(BacktestExecutionModel.M5_COMPLETED_OHLC_V2)
    v1_bundle = _artifact_bundle(v1, tmp_path)
    v2_bundle = _artifact_bundle(v2, tmp_path)

    v1_contract = _validate_artifact_bundle(v1_bundle)
    v2_contract = _validate_artifact_bundle(v2_bundle)
    assert v1_contract["execution_model_id"] == "M15_COMPLETED_OHLC_V1"
    assert v2_contract["execution_model_id"] == "M5_COMPLETED_OHLC_V2"
    assert v1_contract != v2_contract
    assert v1_contract["entry_clock"] == "M15"
    assert v2_contract["entry_clock"] == "M5"
    assert v1_contract["lifecycle_clock"] == "M15_COMPLETED"
    assert v2_contract["lifecycle_clock"] == "M5_COMPLETED"

    # Missing ID plus missing contract must fail closed. It must not be inferred
    # as V1 simply because BacktestConfig defaults to V1.
    unversioned_summary = dict(v1_bundle.summary)
    unversioned_summary.pop("execution_model_id", None)
    unversioned_summary.pop("execution_model", None)
    with pytest.raises(_ProvenanceValidationError, match="missing") as unversioned:
        _validate_artifact_bundle(
            _replace_artifact(v1_bundle, "summary", unversioned_summary)
        )
    assert (
        unversioned.value.classification
        is MigrationClassification.PROVENANCE_MISMATCH
    )

    # A top-level ID that conflicts with the nested contract is invalid.
    conflicting_id = dict(v1_bundle.statistics)
    conflicting_id["execution_model_id"] = "M5_COMPLETED_OHLC_V2"
    with pytest.raises(_ProvenanceValidationError, match="conflicting"):
        _validate_artifact_bundle(
            _replace_artifact(v1_bundle, "statistics", conflicting_id)
        )

    # Clock metadata must agree across every artifact in one run.
    conflicting_clock = dict(v1_bundle.trade_metadata)
    conflicting_clock["lifecycle_clock"] = "M5_COMPLETED"
    with pytest.raises(_ProvenanceValidationError, match="conflicts"):
        _validate_artifact_bundle(
            _replace_artifact(v1_bundle, "trade_metadata", conflicting_clock)
        )

    # One run cannot mix V1 and V2 provenance across artifacts.
    mixed_trace = dict(v1_bundle.execution_economics_trace)
    mixed_trace["execution_model_id"] = "M5_COMPLETED_OHLC_V2"
    mixed_trace["entry_policy"] = "NEXT_AVAILABLE_M5_OPEN"
    mixed_trace["entry_clock"] = "M5"
    mixed_trace["lifecycle_clock"] = "M5_COMPLETED"
    mixed_trace["lifecycle_bar_minutes"] = 5
    with pytest.raises(_ProvenanceValidationError, match="conflicts"):
        _validate_artifact_bundle(
            _replace_artifact(
                v1_bundle,
                "execution_economics_trace",
                mixed_trace,
            )
        )
