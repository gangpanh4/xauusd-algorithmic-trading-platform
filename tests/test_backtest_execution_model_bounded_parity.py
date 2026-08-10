from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path

import pytest

from core.backtesting.config import BacktestConfig, BacktestExecutionModel
from core.backtesting.engine import BacktestingEngine
from core.backtesting.exporter import BacktestExporter
from core.backtesting.models import (
    BacktestReplayContext,
    BacktestReplayWindow,
    BacktestResult,
    ExitReason,
    TradeOutcome,
)
from core.backtesting.runner import BacktestRunner
from core.backtesting.simulator import (
    IncrementalTradeSimulation,
    TradeSimulator,
)
from core.backtesting.statistics import StatisticsCalculator
from core.execution_economics.profiles import pinned_xauusd_research_profile
from core.regime_detector.models import MarketBar, MarketRegime
from core.risk_manager.models import RiskDecision, TradePlan
from core.signal_generator.models import TradingSignal
from core.trading_pipeline.models import PipelineResult
from core.trading_pipeline.pipeline import TradingPipeline

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "phase8_group4d_xauusd_parity_20260806.json"
)
INITIAL_BALANCE = 10_000.0
DECISION_START = datetime(2026, 8, 6, 1, 0, tzinfo=UTC)
DECISION_END = datetime(2026, 8, 6, 12, 55, tzinfo=UTC)
DECISION_CLOSE_BOUNDARY = datetime(2026, 8, 6, 13, 0, tzinfo=UTC)
ANALYSIS_WINDOW_BARS = 140
REQUIRED_WARMUP_SNAPSHOTS = 200


class MigrationClassification(str, Enum):
    EXPECTED_EXECUTION_MODEL_DIFFERENCE = (
        "EXPECTED_EXECUTION_MODEL_DIFFERENCE"
    )
    UNEXPECTED_ANALYTICAL_DIFFERENCE = (
        "UNEXPECTED_ANALYTICAL_DIFFERENCE"
    )
    PROVENANCE_MISMATCH = "PROVENANCE_MISMATCH"
    POTENTIAL_REGRESSION = "POTENTIAL_REGRESSION"


@dataclass(frozen=True)
class _AnalyticalSnapshot:
    timestamp: datetime
    regime: object
    market_structure: object
    features: object
    probability: object
    trade_quality: object
    confluence: object
    decision: object
    signal: object


@dataclass(frozen=True)
class _RiskSnapshot:
    timestamp: datetime
    account_balance: float
    virtual_balance: float
    open_position_count: int
    total_net_pnl: float
    daily_profit: float
    daily_loss: float
    daily_drawdown: float
    current_drawdown: float
    max_drawdown: float
    completed_trade_count: int
    consecutive_wins: int
    consecutive_losses: int
    emergency_stop: bool
    daily_loss_limit_hit: bool


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
class _EntryEvent:
    observation_timestamp: datetime
    execution_bar_timestamp: datetime


@dataclass(frozen=True)
class _RunMetrics:
    eligible_m5_observations: int
    analytical_snapshot_count: int
    eligible_analytical_snapshot_count: int
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
    context: BacktestReplayContext
    pipeline: _RecordingPipeline
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


class _ProvenanceValidationError(AssertionError):
    classification = MigrationClassification.PROVENANCE_MISMATCH


class _RecordingPipeline:
    """Record semantic pipeline outputs while delegating to production."""

    def __init__(self, delegate: TradingPipeline) -> None:
        self._delegate = delegate
        self.records: list[_ObservationRecord] = []

    def __getattr__(self, name: str) -> object:
        return getattr(self._delegate, name)

    def process_bar(
        self,
        bar: MarketBar,
        **kwargs: object,
    ) -> PipelineResult:
        risk_state = self._delegate.risk_manager.state
        risk = _RiskSnapshot(
            timestamp=bar.timestamp.astimezone(UTC),
            account_balance=float(kwargs["account_balance"]),
            virtual_balance=float(risk_state.virtual_balance),
            open_position_count=int(risk_state.open_position_count),
            total_net_pnl=float(risk_state.total_net_pnl),
            daily_profit=float(risk_state.daily_profit),
            daily_loss=float(risk_state.daily_loss),
            daily_drawdown=float(risk_state.daily_drawdown),
            current_drawdown=float(risk_state.current_drawdown),
            max_drawdown=float(risk_state.max_drawdown),
            completed_trade_count=int(risk_state.completed_trade_count),
            consecutive_wins=int(risk_state.consecutive_wins),
            consecutive_losses=int(risk_state.consecutive_losses),
            emergency_stop=bool(risk_state.emergency_stop),
            daily_loss_limit_hit=bool(risk_state.daily_loss_limit_hit),
        )
        market_structure = kwargs.get("market_structure_result")
        result = self._delegate.process_bar(bar, **kwargs)

        expected_available_at = bar.timestamp + timedelta(minutes=5)
        if result.regime.observation_timestamp != bar.timestamp:
            raise AssertionError(
                "regime observation timestamp changed from candle-open time"
            )
        if result.regime.computation_timestamp != expected_available_at:
            raise AssertionError(
                "regime computation timestamp is not completed-M5 availability"
            )
        if (
            result.trade_quality is not None
            and result.trade_quality.timestamp != expected_available_at
        ):
            raise AssertionError(
                "trade-quality timestamp is not completed-M5 availability"
            )
        if (
            result.decision is not None
            and result.decision.timestamp != expected_available_at
        ):
            raise AssertionError(
                "decision timestamp is not completed-M5 availability"
            )
        if (
            result.signal is not None
            and result.signal.timestamp != bar.timestamp
        ):
            raise AssertionError(
                "signal timestamp changed from market-observation time"
            )

        analytical = _AnalyticalSnapshot(
            timestamp=bar.timestamp.astimezone(UTC),
            regime=_stable_regime(result.regime),
            market_structure=_stable_value(market_structure),
            features=_stable_value(result.features),
            probability=_stable_value(result.probability),
            trade_quality=_stable_trade_quality(result.trade_quality),
            confluence=_stable_value(result.confluence),
            decision=_stable_decision(result.decision),
            signal=_stable_signal(result.signal),
        )
        plan = result.trade_plan
        if plan is None:
            raise AssertionError("production pipeline returned no TradePlan")
        self.records.append(
            _ObservationRecord(
                analytical=analytical,
                risk=risk,
                trade_plan=plan,
            )
        )
        return result


class _InstrumentedTradeSimulator(TradeSimulator):
    """Record entry clocks and pre-resolution SL/TP ambiguity."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.begin_observations: list[datetime] = []
        self.entry_events: list[_EntryEvent] = []
        self.ambiguity_observations: list[_AmbiguityObservation] = []

    def begin(
        self,
        trade_plan: TradePlan,
        observation_bar: MarketBar,
    ) -> IncrementalTradeSimulation:
        self.begin_observations.append(
            observation_bar.timestamp.astimezone(UTC)
        )
        return super().begin(trade_plan, observation_bar)

    def process_bar(
        self,
        simulation: IncrementalTradeSimulation,
        bar: MarketBar,
    ):
        was_pending = simulation.is_pending_entry
        completed = super().process_bar(simulation, bar)
        if was_pending and not simulation.is_pending_entry:
            self.entry_events.append(
                _EntryEvent(
                    observation_timestamp=(
                        simulation.observation_bar.timestamp.astimezone(UTC)
                    ),
                    execution_bar_timestamp=bar.timestamp.astimezone(UTC),
                )
            )
        return completed

    def _resolve_bar_exit(self, *, state, bar: MarketBar):
        if state.is_buy:
            stop_hit = float(bar.low) <= state.current_stop_loss
            target_hit = float(bar.high) >= state.take_profit
        else:
            stop_hit = float(bar.high) >= state.current_stop_loss
            target_hit = float(bar.low) <= state.take_profit
        self.ambiguity_observations.append(
            _AmbiguityObservation(
                timestamp=bar.timestamp.astimezone(UTC),
                stop_hit=stop_hit,
                target_hit=target_hit,
            )
        )
        return super()._resolve_bar_exit(state=state, bar=bar)


def _stable_value(value: object) -> object:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {
            str(key): _stable_value(item)
            for key, item in sorted(
                value.items(),
                key=lambda pair: str(pair[0]),
            )
        }
    if isinstance(value, (list, tuple)):
        return tuple(_stable_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return tuple(
            sorted(
                (_stable_value(item) for item in value),
                key=str,
            )
        )
    if hasattr(value, "__dataclass_fields__"):
        return tuple(
            (
                field.name,
                _stable_value(getattr(value, field.name)),
            )
            for field in fields(value)
        )
    attributes = getattr(value, "__dict__", None)
    if isinstance(attributes, Mapping):
        return _stable_value(attributes)
    return str(value)


def _stable_regime(regime: MarketRegime) -> object:
    return _stable_value(regime)


def _stable_trade_quality(trade_quality: object | None) -> object:
    return _stable_value(trade_quality)


def _stable_decision(decision: object | None) -> object:
    return _stable_value(decision)


def _stable_signal(signal: TradingSignal | None) -> object:
    if signal is None:
        return None
    return _stable_value(signal)


def _load_fixture_payload() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _to_bar(raw: Mapping[str, object]) -> MarketBar:
    timestamp = datetime.fromisoformat(str(raw["timestamp"])).astimezone(UTC)
    tick_volume = int(raw["tick_volume"])
    return MarketBar(
        timestamp=timestamp,
        open=float(raw["open"]),
        high=float(raw["high"]),
        low=float(raw["low"]),
        close=float(raw["close"]),
        volume=float(tick_volume),
        tick_volume=tick_volume,
    )


def _context_from_fixture() -> BacktestReplayContext:
    payload = _load_fixture_payload()
    selection = payload["selection"]
    counts = payload["fixture_bar_counts"]
    raw_histories = payload["bars_by_timeframe"]
    if not isinstance(selection, Mapping):
        raise TypeError("fixture selection must be a mapping")
    if not isinstance(counts, Mapping):
        raise TypeError("fixture bar counts must be a mapping")
    if not isinstance(raw_histories, Mapping):
        raise TypeError("fixture histories must be a mapping")

    histories: dict[str, list[MarketBar]] = {}
    for key in ("M5", "M15", "H1", "H4"):
        raw_values = raw_histories[key]
        if not isinstance(raw_values, list):
            raise TypeError(f"fixture {key} history must be a list")
        histories[key] = [_to_bar(value) for value in raw_values]

    source_start = min(
        history[0].timestamp
        for history in histories.values()
    )
    replay_window = BacktestReplayWindow(
        source_start=source_start,
        source_end=DECISION_CLOSE_BOUNDARY,
        first_eligible_m5_timestamp=DECISION_START,
        last_eligible_m5_timestamp=DECISION_END,
        requested_eligible_m5_bars=144,
        analysis_window_bars=ANALYSIS_WINDOW_BARS,
        required_warmup_snapshots=REQUIRED_WARMUP_SNAPSHOTS,
        available_warmup_snapshots=REQUIRED_WARMUP_SNAPSHOTS,
        requested_bar_counts=tuple(
            sorted(
                (
                    key.lower(),
                    int(counts[key]),
                )
                for key in ("M5", "M15", "H1", "H4")
            )
        ),
    )
    return BacktestReplayContext(
        current_bar=histories["M5"][-1],
        m5_bars=histories["M5"],
        m15_bars=histories["M15"],
        h1_bars=histories["H1"],
        h4_bars=histories["H4"],
        replay_window=replay_window,
    )


def _run_model(
    model: BacktestExecutionModel,
    context: BacktestReplayContext,
) -> _MigrationRun:
    profile = pinned_xauusd_research_profile()
    config = BacktestConfig(
        execution_model=model,
        execution_profile=profile,
        initial_balance=INITIAL_BALANCE,
        warmup_bars=REQUIRED_WARMUP_SNAPSHOTS,
        maximum_trades=None,
    )
    engine = BacktestingEngine(
        config,
        execution_profile=profile,
        progress_interval_bars=None,
        multi_timeframe_window_bars=ANALYSIS_WINDOW_BARS,
    )
    pipeline_holder: list[_RecordingPipeline] = []

    def create_pipeline() -> _RecordingPipeline:
        delegate = TradingPipeline(engine._build_pipeline_config())
        recording = _RecordingPipeline(delegate)
        pipeline_holder.append(recording)
        return recording

    engine._create_pipeline = create_pipeline  # type: ignore[method-assign]
    simulator = _InstrumentedTradeSimulator(
        execution_profile=profile,
        execution_model=model,
    )
    engine.simulator = simulator
    result = engine.run(context)
    if not pipeline_holder:
        raise AssertionError("recording pipeline was not created")
    pipeline = pipeline_holder[-1]
    metrics = _metrics(
        context=context,
        pipeline=pipeline,
        simulator=simulator,
        result=result,
    )
    return _MigrationRun(
        model=model,
        config=config,
        context=context,
        pipeline=pipeline,
        simulator=simulator,
        engine=engine,
        result=result,
        metrics=metrics,
    )


def _eligible_records(
    pipeline: _RecordingPipeline,
) -> tuple[_ObservationRecord, ...]:
    return tuple(
        record
        for record in pipeline.records
        if DECISION_START <= record.analytical.timestamp <= DECISION_END
    )


def _metrics(
    *,
    context: BacktestReplayContext,
    pipeline: _RecordingPipeline,
    simulator: _InstrumentedTradeSimulator,
    result: BacktestResult,
) -> _RunMetrics:
    del context
    trades = tuple(result.trades)
    eligible = _eligible_records(pipeline)
    return _RunMetrics(
        eligible_m5_observations=144,
        analytical_snapshot_count=len(pipeline.records),
        eligible_analytical_snapshot_count=len(eligible),
        approved_plan_count=sum(
            record.trade_plan.decision is RiskDecision.APPROVE
            for record in eligible
        ),
        simulator_begin_attempts=len(simulator.begin_observations),
        completed_trades=result.total_trades,
        entry_timestamps=tuple(
            trade.entry_time.astimezone(UTC)
            for trade in trades
        ),
        entry_reference_prices=tuple(
            float(trade.metadata["reference_entry_price"])
            for trade in trades
        ),
        exit_timestamps=tuple(
            trade.exit_time.astimezone(UTC)
            for trade in trades
        ),
        exit_prices=tuple(float(trade.exit_price) for trade in trades),
        holding_bars=tuple(trade.holding_bars for trade in trades),
        holding_durations=tuple(trade.holding_time for trade in trades),
        stop_exits=sum(
            trade.exit_reason is ExitReason.STOP_LOSS
            for trade in trades
        ),
        target_exits=sum(
            trade.exit_reason is ExitReason.TAKE_PROFIT
            for trade in trades
        ),
        breakeven_exits=sum(
            trade.outcome is TradeOutcome.BREAKEVEN
            for trade in trades
        ),
        actual_stop_and_target_ambiguity_count=sum(
            observation.ambiguous
            for observation in simulator.ambiguity_observations
        ),
        end_of_data_exits=sum(
            trade.exit_reason is ExitReason.END_OF_DATA
            for trade in trades
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


def _risk_state_changed(
    left: _RiskSnapshot,
    right: _RiskSnapshot,
) -> bool:
    return left != right


def _risk_plan_differences(
    left: _MigrationRun,
    right: _MigrationRun,
) -> tuple[_Difference, ...]:
    left_by_time = {
        record.analytical.timestamp: record
        for record in _eligible_records(left.pipeline)
    }
    right_by_time = {
        record.analytical.timestamp: record
        for record in _eligible_records(right.pipeline)
    }
    if left_by_time.keys() != right_by_time.keys():
        raise AssertionError("eligible analytical timestamp sets differ")

    differences: list[_Difference] = []
    for timestamp, left_record in left_by_time.items():
        right_record = right_by_time[timestamp]
        if left_record.trade_plan == right_record.trade_plan:
            continue
        risk_changed = _risk_state_changed(
            left_record.risk,
            right_record.risk,
        )
        classification = (
            MigrationClassification.EXPECTED_EXECUTION_MODEL_DIFFERENCE
            if risk_changed
            else MigrationClassification.POTENTIAL_REGRESSION
        )
        differences.append(
            _Difference(
                field=f"trade_plan@{timestamp.isoformat()}",
                left=left_record.trade_plan,
                right=right_record.trade_plan,
                classification=classification,
                reason=(
                    "execution-derived risk/exposure state differs"
                    if risk_changed
                    else "TradePlan differs without an execution-derived cause"
                ),
            )
        )
    return tuple(differences)


def _metric_differences(
    left: _RunMetrics,
    right: _RunMetrics,
) -> tuple[_Difference, ...]:
    differences: list[_Difference] = []
    for field in fields(_RunMetrics):
        left_value = getattr(left, field.name)
        right_value = getattr(right, field.name)
        if left_value == right_value:
            continue
        differences.append(
            _Difference(
                field=field.name,
                left=left_value,
                right=right_value,
                classification=(
                    MigrationClassification.EXPECTED_EXECUTION_MODEL_DIFFERENCE
                ),
                reason="field is downstream of the execution-model clock",
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
    top_id = payload.get("execution_model_id")
    nested_id = nested_contract.get("execution_model_id")
    if (
        top_id is not None
        and nested_id is not None
        and top_id != nested_id
    ):
        raise _ProvenanceValidationError(
            f"{artifact_name}: conflicting execution_model_id"
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
                f"{artifact_name}: conflicting {field}"
            )
        value = top_value if top_value is not None else nested_value
        if value is None:
            raise _ProvenanceValidationError(
                f"{artifact_name}: missing {field}"
            )
        contract[field] = value

    if contract["comparable_with_unversioned_results"] is not False:
        raise _ProvenanceValidationError(
            f"{artifact_name}: unversioned comparability enabled"
        )
    return contract


def _run_level_artifact_payloads(
    run: _MigrationRun,
    tmp_path: Path,
) -> tuple[tuple[str, Mapping[str, object]], ...]:
    """Return provenance that exists even when no trade is executed."""

    runner = object.__new__(BacktestRunner)
    runner.config = run.config
    runner.execution_profile = run.config.resolved_execution_profile()
    runner.engine = run.engine
    runner._capture_historical_window(
        context=run.context,
        requested_end_time=DECISION_CLOSE_BOUNDARY,
        requested_bars=144,
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
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    stats = json.loads(statistics_path.read_text(encoding="utf-8"))

    return (
        ("historical_window", historical_window),
        ("summary", summary),
        ("statistics", stats),
    )


def _validate_provenance(
    payloads: tuple[tuple[str, Mapping[str, object]], ...],
) -> dict[str, object]:
    contracts = [
        (name, _normalized_contract(name, payload))
        for name, payload in payloads
    ]
    expected_name, expected = contracts[0]
    for name, contract in contracts[1:]:
        if contract != expected:
            raise _ProvenanceValidationError(
                f"{name} conflicts with {expected_name}"
            )
    return expected


def _expected_execution_bar(
    *,
    model: BacktestExecutionModel,
    observation_timestamp: datetime,
    context: BacktestReplayContext,
) -> datetime:
    if model is BacktestExecutionModel.M5_COMPLETED_OHLC_V2:
        candidates = (
            bar.timestamp.astimezone(UTC)
            for bar in context.m5_bars
            if bar.timestamp.astimezone(UTC)
            >= observation_timestamp + timedelta(minutes=5)
        )
    else:
        candidates = (
            bar.timestamp.astimezone(UTC)
            for bar in context.m15_bars
            if bar.timestamp.astimezone(UTC) > observation_timestamp
        )
    try:
        return min(candidates)
    except ValueError as exc:
        raise AssertionError("approved observation has no execution bar") from exc


def _first_common_approved_plan(
    left: _MigrationRun,
    right: _MigrationRun,
) -> tuple[datetime, TradePlan]:
    for left_record, right_record in zip(
        _eligible_records(left.pipeline),
        _eligible_records(right.pipeline),
        strict=True,
    ):
        if (
            left_record.trade_plan.decision is RiskDecision.APPROVE
            and right_record.trade_plan.decision is RiskDecision.APPROVE
        ):
            assert left_record.trade_plan == right_record.trade_plan
            return left_record.analytical.timestamp, left_record.trade_plan
    raise AssertionError(
        "approved Group 4D decision window produced no common approved "
        "TradePlan; execution comparison cannot be completed"
    )


def _jsonable(value: object) -> object:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return {
            field.name: _jsonable(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, Mapping):
        return {
            str(key): _jsonable(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


@pytest.fixture(scope="module")
def migration_runs() -> tuple[_MigrationRun, _MigrationRun, _MigrationRun]:
    context = _context_from_fixture()
    v1 = _run_model(
        BacktestExecutionModel.M15_COMPLETED_OHLC_V1,
        context,
    )
    v2 = _run_model(
        BacktestExecutionModel.M5_COMPLETED_OHLC_V2,
        context,
    )
    v1_repeat = _run_model(
        BacktestExecutionModel.M15_COMPLETED_OHLC_V1,
        context,
    )
    return v1, v2, v1_repeat


def test_group4d_fixture_contract_and_warmup() -> None:
    payload = _load_fixture_payload()
    source = payload["source"]
    selection = payload["selection"]
    fixture_counts = payload["fixture_bar_counts"]
    assert isinstance(source, Mapping)
    assert isinstance(selection, Mapping)
    assert isinstance(fixture_counts, Mapping)

    assert source["artifact"] == "runtime/live_parity_evidence.jsonl"
    assert source["captured_at"] == "2026-08-06T14:25:05.318388+00:00"
    assert source["observation_timestamp"] == "2026-08-06T14:20:00+00:00"
    assert source["symbol"] == "XAUUSD"
    assert source["price_side"] == "UNKNOWN_SINGLE_PRICE"
    assert source["spread_history_available"] is False
    assert source["bid_ask_history_available"] is False
    assert source["provider_identity"] == "unknown"
    assert source["broker_server"] == "unknown"
    assert source["timezone"] == "UTC"
    assert source["source_record_number"] == 42
    assert source["source_file_sha256_at_extraction"] == (
        "76b5b1ae61f2566b144a022364894e0041db35b9be1e1b7afb46f1caab923814"
    )
    assert source["source_record_canonical_sha256"] == (
        "3b66ac6ce808a7b3a22b496b1a5c66feb6a37b7372dd0bd12d0b41fe9d4cf00c"
    )
    assert source["source_bar_counts"] == {
        "D1": 99,
        "H1": 500,
        "H4": 500,
        "M15": 500,
        "M5": 500,
        "W1": 16,
    }
    assert selection["decision_window_start"] == DECISION_START.isoformat()
    assert selection["decision_window_end"] == DECISION_END.isoformat()
    assert selection["analysis_window_bars"] == ANALYSIS_WINDOW_BARS
    assert selection["required_warmup_snapshots"] == 200
    assert selection["available_warmup_snapshots"] == 200
    assert selection["warmup_first_complete_snapshot"] == (
        "2026-08-05T06:20:00+00:00"
    )
    assert selection["warmup_last_snapshot"] == (
        "2026-08-06T00:55:00+00:00"
    )
    assert selection["no_synthetic_bars"] is True
    assert selection["h4_boundary_convention_utc"] == [
        "01:00",
        "05:00",
        "09:00",
        "13:00",
        "17:00",
        "21:00",
    ]
    assert fixture_counts == {
        "M5": 483,
        "M15": 495,
        "H1": 499,
        "H4": 500,
    }

    context = _context_from_fixture()
    eligible = [
        bar
        for bar in context.m5_bars
        if DECISION_START <= bar.timestamp <= DECISION_END
    ]
    assert len(eligible) == 144
    assert eligible[0].timestamp == DECISION_START
    assert eligible[-1].timestamp == DECISION_END


def test_group4d_real_capture_proves_analytical_parity_and_deferral(
    migration_runs: tuple[_MigrationRun, _MigrationRun, _MigrationRun],
) -> None:
    v1, v2, v1_repeat = migration_runs
    assert v1.context is v2.context
    assert v1.context is v1_repeat.context
    assert replace(
        v1.config,
        execution_model=BacktestExecutionModel.M5_COMPLETED_OHLC_V2,
    ) == v2.config
    assert v1.engine.multi_timeframe_window_bars == ANALYSIS_WINDOW_BARS
    assert v2.engine.multi_timeframe_window_bars == ANALYSIS_WINDOW_BARS

    v1_eligible = _eligible_records(v1.pipeline)
    v2_eligible = _eligible_records(v2.pipeline)
    v1_repeat_eligible = _eligible_records(v1_repeat.pipeline)

    assert tuple(
        record.analytical.timestamp for record in v1_eligible
    ) == tuple(
        record.analytical.timestamp for record in v2_eligible
    )
    assert len(v1_eligible) == len(v2_eligible) == 144
    assert len(v1.pipeline.records) == len(v2.pipeline.records) == 344

    analytical_differences = tuple(
        (
            left.analytical.timestamp,
            left.analytical,
            right.analytical,
        )
        for left, right in zip(v1_eligible, v2_eligible, strict=True)
        if left.analytical != right.analytical
    )
    assert analytical_differences == (), (
        MigrationClassification.UNEXPECTED_ANALYTICAL_DIFFERENCE,
        analytical_differences[:1],
    )

    assert tuple(
        (record.trade_plan.decision, record.trade_plan.reason)
        for record in v1.pipeline.records
    ) == tuple(
        (record.trade_plan.decision, record.trade_plan.reason)
        for record in v2.pipeline.records
    )
    assert all(
        record.trade_plan.decision is RiskDecision.SKIP
        for record in v1_eligible
    )
    assert all(
        record.trade_plan.reason == "No trading opportunity."
        for record in v1_eligible
    )

    for run in (v1, v2):
        assert run.metrics.approved_plan_count == 0
        assert run.metrics.simulator_begin_attempts == 0
        assert run.metrics.completed_trades == 0
        assert run.simulator.begin_observations == []
        assert run.simulator.entry_events == []
        assert run.result.trades == []

    # The capture proves analytical parity only. No production-approved plan
    # reaches either execution clock, so real-data execution migration is
    # empirically deferred rather than declared equivalent.
    execution_migration_status = (
        "EXECUTION_MIGRATION_EMPIRICALLY_DEFERRED_"
        "ON_AVAILABLE_LOCAL_CAPTURE"
    )
    assert execution_migration_status == (
        "EXECUTION_MIGRATION_EMPIRICALLY_DEFERRED_"
        "ON_AVAILABLE_LOCAL_CAPTURE"
    )

    assert v1.metrics == v1_repeat.metrics
    assert tuple(
        record.analytical for record in v1_eligible
    ) == tuple(
        record.analytical for record in v1_repeat_eligible
    )
    assert tuple(
        record.trade_plan for record in v1_eligible
    ) == tuple(
        record.trade_plan for record in v1_repeat_eligible
    )


def test_group4d_run_provenance_is_versioned_while_execution_is_deferred(
    migration_runs: tuple[_MigrationRun, _MigrationRun, _MigrationRun],
    tmp_path: Path,
) -> None:
    v1, v2, _ = migration_runs
    v1_payloads = _run_level_artifact_payloads(v1, tmp_path)
    v2_payloads = _run_level_artifact_payloads(v2, tmp_path)

    v1_contract = _validate_provenance(v1_payloads)
    v2_contract = _validate_provenance(v2_payloads)
    assert v1_contract["execution_model_id"] == "M15_COMPLETED_OHLC_V1"
    assert v2_contract["execution_model_id"] == "M5_COMPLETED_OHLC_V2"
    assert v1_contract != v2_contract
    assert v1_contract["entry_clock"] == "M15"
    assert v2_contract["entry_clock"] == "M5"

    unversioned = {
        key: value
        for key, value in dict(v1_payloads[1][1]).items()
        if key not in _REQUIRED_PROVENANCE_FIELDS
        and key != "execution_model"
    }
    with pytest.raises(_ProvenanceValidationError):
        _normalized_contract("unversioned", unversioned)

    conflicting = dict(v1_payloads[1][1])
    nested = dict(conflicting["execution_model"])
    nested["execution_model_id"] = "M5_COMPLETED_OHLC_V2"
    conflicting["execution_model"] = nested
    with pytest.raises(_ProvenanceValidationError):
        _normalized_contract("conflicting", conflicting)

    conflicting_clock = dict(v1_payloads[1][1])
    nested_clock = dict(conflicting_clock["execution_model"])
    nested_clock["entry_clock"] = "M5"
    conflicting_clock["execution_model"] = nested_clock
    conflicting_clock_payloads = list(v1_payloads)
    conflicting_clock_payloads[1] = (
        "conflicting_clock_summary",
        conflicting_clock,
    )
    with pytest.raises(_ProvenanceValidationError):
        _validate_provenance(tuple(conflicting_clock_payloads))

    mixed = list(v1_payloads)
    mixed[-1] = ("mixed_v2_statistics", v2_payloads[-1][1])
    with pytest.raises(_ProvenanceValidationError):
        _validate_provenance(tuple(mixed))

    # No trade metadata or execution-economics trace exists because neither
    # simulator begins. Group 3/4A deterministic fixtures remain the evidence
    # for trade-level execution-model separation and ambiguity behavior.
    for run in (v1, v2):
        assert run.result.trades == []
        assert run.simulator.begin_observations == []
        assert run.simulator.ambiguity_observations == []
        assert run.metrics.actual_stop_and_target_ambiguity_count == 0
