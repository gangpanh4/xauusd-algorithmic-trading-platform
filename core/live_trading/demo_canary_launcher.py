"""Signal-gated one-shot MT5 demo-canary launcher.

The process warms and waits for a genuine production APPROVE while execution
remains disabled. Only after that exact approved observation exists may the
operator acknowledge one demo order, a fresh short-lived authorization be
created, and the frozen approved result enter the ordinary execution safety
path.
"""

from __future__ import annotations

import argparse
import json
import time
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from math import isclose, isfinite
from pathlib import Path

import MetaTrader5 as mt5

from core.data.market_data import MarketDataService
from core.data.models import MarketBar
from core.mt5_execution.account import get_account_info
from core.mt5_execution.symbol_specification import (
    LiveSymbolSpecification,
    get_live_symbol_specification,
)
from core.multi_timeframe.enums import Timeframe
from core.multi_timeframe.history_alignment import (
    clip_history,
    required_bar_count,
    utc_week_start,
    visible_bars,
)
from core.risk_manager.models import RiskDecision
from core.trading_pipeline.models import PipelineResult

from .config import LiveTradingConfig
from .connected_demo_canary_preflight import (
    ConnectedDemoCanaryPreflightEvidence,
    collect_connected_demo_canary_preflight_evidence,
    export_connected_demo_canary_preflight_evidence,
)
from .demo_execution_authorization import (
    DemoExecutionAuthorization,
    DemoExecutionAuthorizationError,
    load_demo_execution_authorization,
    validate_demo_execution_authorization_scope,
    validate_demo_execution_authorization_time_window,
)
from .demo_execution_authorization_prepare import (
    prepare_fresh_demo_authorization_from_preflight,
)
from .engine import LiveTradingEngine
from .execution_intent_store import ExecutionIntentStateError
from .multi_timeframe_buffer import LiveMultiTimeframeBuffer
from .parity_validation_attestation import (
    ParityValidationAttestationError,
    verify_parity_validation_attestation,
)
from .partial_fill_store import PartialFillStateError

_CANARY_SYMBOL = "XAUUSD"
_CANARY_VOLUME = 0.01
_VOLUME_TOLERANCE = 1e-12
_REQUIRED_ACKNOWLEDGEMENT = "I AUTHORIZE ONE DEMO ORDER"
_APPROVED_CANDIDATE_MAX_AGE_SECONDS = 120.0
_PREFLIGHT_PATH = Path("output/live_execution_reconciliation/connected_demo_canary_preflight.json")

_CLEAR_RECONCILIATION_STATES = {
    "",
    "NO_PERSISTED_INTENT",
    "NO_INTENT",
    "RECONCILED_CLEAR",
    "ALREADY_RESOLVED",
    "FILLED_CONFIRMED",
    "REJECTED_CONFIRMED",
    "CANCELLED_CONFIRMED",
    "TERMINAL_CONFIRMED",
}


class DemoCanaryLauncherError(RuntimeError):
    """Raised when the dedicated demo-canary launcher must fail closed."""


@dataclass(frozen=True, slots=True)
class DemoCanaryLaunchResult:
    """Terminal result of one dedicated canary process."""

    finished_at: datetime
    outcome: str
    submission_attempted: bool
    authorization_consumed: bool
    trade_executed: bool
    execution_status: str | None
    last_error: str

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["finished_at"] = self.finished_at.astimezone(UTC).isoformat()
        return payload


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _validate_initial_authorization(
    authorization: DemoExecutionAuthorization,
    *,
    now: datetime,
) -> None:
    """Reject any authorization that is not exactly the canary scope."""

    validate_demo_execution_authorization_time_window(
        authorization,
        now=now,
    )
    if authorization.consumed:
        raise DemoCanaryLauncherError(
            "Demo execution authorization has already been consumed."
        )
    if not authorization.demo_only or not authorization.one_shot:
        raise DemoCanaryLauncherError(
            "Demo canary requires a demo-only one-shot authorization."
        )
    if authorization.symbol != _CANARY_SYMBOL:
        raise DemoCanaryLauncherError(
            "Demo canary authorization must be bound to XAUUSD."
        )
    if authorization.maximum_submissions != 1:
        raise DemoCanaryLauncherError(
            "Demo canary authorization must permit exactly one submission."
        )
    if (
        not isfinite(float(authorization.maximum_volume))
        or not isclose(
            float(authorization.maximum_volume),
            _CANARY_VOLUME,
            rel_tol=0.0,
            abs_tol=_VOLUME_TOLERANCE,
        )
    ):
        raise DemoCanaryLauncherError(
            "Demo canary authorization maximum volume must be exactly 0.01 lot."
        )


def _build_active_canary_config(
    safe_config: LiveTradingConfig,
    authorization: DemoExecutionAuthorization,
) -> LiveTradingConfig:
    """Build process-local active controls from safe defaults and authorization."""

    if safe_config.symbol != _CANARY_SYMBOL:
        raise DemoCanaryLauncherError("Demo canary is restricted to XAUUSD.")
    if (
        safe_config.live_execution_enabled
        or safe_config.demo_execution_approved
        or not safe_config.execution_kill_switch_enabled
    ):
        raise DemoCanaryLauncherError(
            "Demo canary must start from the safe-disabled production defaults."
        )

    active = replace(
        safe_config,
        live_execution_enabled=True,
        demo_execution_approved=True,
        execution_kill_switch_enabled=False,
        approved_account_login=authorization.account_login,
        approved_account_server=authorization.account_server,
        maximum_order_submissions_per_session=1,
        shadow_recording_enabled=False,
        parity_recording_enabled=False,
    )
    if not isclose(
        float(active.execution.allowed_order_volume),
        _CANARY_VOLUME,
        rel_tol=0.0,
        abs_tol=_VOLUME_TOLERANCE,
    ):
        raise DemoCanaryLauncherError(
            "MT5 execution safety lock must remain exactly 0.01 lot."
        )
    return active


def _validate_preflight_binding(
    evidence: ConnectedDemoCanaryPreflightEvidence,
    authorization: DemoExecutionAuthorization,
) -> None:
    if not evidence.validation_passed:
        raise DemoCanaryLauncherError(
            "Fresh connected demo-canary preflight did not pass: "
            + "; ".join(evidence.reasons)
        )
    if not evidence.demo_account_confirmed:
        raise DemoCanaryLauncherError("Connected account is not confirmed demo.")
    if evidence.symbol != _CANARY_SYMBOL:
        raise DemoCanaryLauncherError("Connected preflight symbol is not XAUUSD.")
    if (
        evidence.account_login != authorization.account_login
        or evidence.account_server != authorization.account_server
    ):
        raise DemoCanaryLauncherError(
            "Connected account identity does not match durable authorization."
        )
    if evidence.active_order_count != 0 or evidence.open_position_count != 0:
        raise DemoCanaryLauncherError(
            "Existing broker order or position blocks the one-shot canary."
        )
    if evidence.unresolved_partial_fill or not evidence.reconciliation_clear:
        raise DemoCanaryLauncherError(
            "Reconciliation or partial-fill state blocks the one-shot canary."
        )
    if evidence.persisted_intent_present and evidence.persisted_intent_status in {
        "PREPARED",
        "PENDING",
        "PARTIALLY_FILLED",
    }:
        raise DemoCanaryLauncherError(
            "An unresolved execution intent blocks the one-shot canary."
        )
    if evidence.authorization_consumed:
        raise DemoCanaryLauncherError(
            "Demo execution authorization has already been consumed."
        )

    volume_min = float(evidence.symbol_volume_min)
    volume_max = float(evidence.symbol_volume_max)
    volume_step = float(evidence.symbol_volume_step)
    if (
        not isfinite(volume_min)
        or not isfinite(volume_max)
        or not isfinite(volume_step)
        or volume_step <= 0.0
        or _CANARY_VOLUME < volume_min - _VOLUME_TOLERANCE
        or _CANARY_VOLUME > volume_max + _VOLUME_TOLERANCE
    ):
        raise DemoCanaryLauncherError(
            "Connected symbol specification does not permit 0.01 lot."
        )
    steps = (_CANARY_VOLUME - volume_min) / volume_step
    if not isclose(steps, round(steps), rel_tol=0.0, abs_tol=1e-9):
        raise DemoCanaryLauncherError(
            "0.01 lot is not aligned to the connected symbol volume step."
        )


def _establish_parity_validation(
    engine: LiveTradingEngine,
    config: LiveTradingConfig,
) -> None:
    """Verify the pre-authorization parity proof before recording runtime state."""

    try:
        verify_parity_validation_attestation(config=config)
    except ParityValidationAttestationError as exc:
        raise DemoCanaryLauncherError(
            "Pre-authorization parity attestation validation did not pass."
        ) from exc
    engine.record_parity_validation_passed()


def _build_services(
    config: LiveTradingConfig,
) -> dict[Timeframe, MarketDataService]:
    return {
        Timeframe.M5: MarketDataService(
            symbol=config.symbol,
            timeframe=mt5.TIMEFRAME_M5,
            server_utc_offset_hours=config.mt5_server_utc_offset_hours,
            max_clock_skew_seconds=config.mt5_clock_max_skew_seconds,
        ),
        Timeframe.M15: MarketDataService(
            symbol=config.symbol,
            timeframe=mt5.TIMEFRAME_M15,
            server_utc_offset_hours=config.mt5_server_utc_offset_hours,
            max_clock_skew_seconds=config.mt5_clock_max_skew_seconds,
        ),
        Timeframe.H1: MarketDataService(
            symbol=config.symbol,
            timeframe=mt5.TIMEFRAME_H1,
            server_utc_offset_hours=config.mt5_server_utc_offset_hours,
            max_clock_skew_seconds=config.mt5_clock_max_skew_seconds,
        ),
        Timeframe.H4: MarketDataService(
            symbol=config.symbol,
            timeframe=mt5.TIMEFRAME_H4,
            server_utc_offset_hours=config.mt5_server_utc_offset_hours,
            max_clock_skew_seconds=config.mt5_clock_max_skew_seconds,
        ),
    }


def _load_aligned_live_histories(
    *,
    services: dict[Timeframe, MarketDataService],
    latest_m5: MarketBar,
    analysis_window_bars: int,
) -> tuple[
    dict[Timeframe, list[MarketBar]],
    dict[Timeframe, int],
]:
    """Use the same completed-bar alignment contract as ordinary live mode."""

    boundary = latest_m5.timestamp + timedelta(minutes=5)
    pilot_h4 = visible_bars(
        services[Timeframe.H4].get_historical_bars(
            analysis_window_bars + 2
        ),
        timeframe=Timeframe.H4,
        boundary=boundary,
    )
    if len(pilot_h4) < analysis_window_bars:
        raise DemoCanaryLauncherError(
            "Insufficient completed H4 history at the canary bootstrap boundary."
        )
    source_start = (
        utc_week_start(pilot_h4[-analysis_window_bars].timestamp)
        - timedelta(days=7)
    )
    required = (
        Timeframe.M5,
        Timeframe.M15,
        Timeframe.H1,
        Timeframe.H4,
    )
    capacities = {
        timeframe: required_bar_count(
            start=source_start,
            end=boundary,
            timeframe=timeframe,
        )
        for timeframe in required
    }
    histories: dict[Timeframe, list[MarketBar]] = {}
    for timeframe in required:
        loaded = services[timeframe].get_historical_bars(
            capacities[timeframe]
        )
        clipped = list(
            clip_history(
                loaded,
                timeframe=timeframe,
                start=source_start,
                end=boundary,
            )
        )
        if not clipped:
            raise DemoCanaryLauncherError(
                f"No completed {timeframe.value} history overlaps the "
                "canary bootstrap window."
            )
        histories[timeframe] = clipped

    if histories[Timeframe.M5][-1] != latest_m5:
        raise DemoCanaryLauncherError(
            "The captured M5 bootstrap boundary changed during history loading."
        )
    return histories, capacities


def _require_runtime_clear(engine: LiveTradingEngine) -> None:
    partial = engine.partial_fill_store.load()
    if partial is not None:
        raise DemoCanaryLauncherError(
            "An unresolved persisted partial fill blocks the one-shot canary."
        )

    intent = engine.execution_intent_store.load()
    if intent is not None and intent.unresolved:
        raise DemoCanaryLauncherError(
            "An unresolved execution intent blocks the one-shot canary."
        )

    reconciliation = (
        engine.state.execution_intent_reconciliation_status.strip().upper()
    )
    if reconciliation not in _CLEAR_RECONCILIATION_STATES:
        raise DemoCanaryLauncherError(
            "Execution-intent reconciliation is not clear."
        )

    if engine.synchronize_open_positions() != 0:
        raise DemoCanaryLauncherError(
            "An open position appeared before canary submission."
        )
    if engine.synchronize_active_orders() != 0:
        raise DemoCanaryLauncherError(
            "An active broker order appeared before canary submission."
        )


def _terminal_result(
    engine: LiveTradingEngine,
    *,
    outcome: str,
    authorization_consumed: bool,
    execution_status: str | None = None,
    trade_executed: bool = False,
    last_error: str = "",
) -> DemoCanaryLaunchResult:
    return DemoCanaryLaunchResult(
        finished_at=_utc_now(),
        outcome=outcome,
        submission_attempted=(
            engine.state.order_submissions_this_session > 0
        ),
        authorization_consumed=authorization_consumed,
        trade_executed=trade_executed,
        execution_status=execution_status,
        last_error=last_error,
    )


def _build_canary_execution_candidate(
    pipeline_result: PipelineResult,
) -> PipelineResult:
    """Freeze one approved result and cap demo exposure to exactly 0.01 lot."""

    signal = pipeline_result.signal
    trade_plan = pipeline_result.trade_plan
    if signal is None or trade_plan is None:
        raise DemoCanaryLauncherError(
            "Genuine canary approval requires a signal and trade plan."
        )
    if trade_plan.decision is not RiskDecision.APPROVE:
        raise DemoCanaryLauncherError(
            "Only a genuine RiskDecision.APPROVE may enter the canary handoff."
        )

    original_volume = float(trade_plan.position_size)
    if (
        not isfinite(original_volume)
        or original_volume <= 0.0
        or original_volume < _CANARY_VOLUME - _VOLUME_TOLERANCE
    ):
        raise DemoCanaryLauncherError(
            "Approved risk size is below the fixed 0.01-lot canary volume."
        )

    candidate = deepcopy(pipeline_result)
    candidate_plan = candidate.trade_plan
    if candidate_plan is None:
        raise DemoCanaryLauncherError(
            "Frozen canary candidate lost its approved trade plan."
        )
    metadata = dict(candidate_plan.metadata)
    metadata.update(
        {
            "demo_canary_original_position_size": original_volume,
            "demo_canary_execution_volume": _CANARY_VOLUME,
            "demo_canary_volume_capped": (
                original_volume > _CANARY_VOLUME + _VOLUME_TOLERANCE
            ),
        }
    )
    candidate_plan.metadata = metadata
    candidate_plan.position_size = _CANARY_VOLUME
    return candidate


def _require_fresh_approved_candidate(
    observation_bar: MarketBar,
    *,
    now: datetime,
) -> None:
    decision_available_at = observation_bar.timestamp.astimezone(UTC) + timedelta(
        minutes=5
    )
    age_seconds = (now.astimezone(UTC) - decision_available_at).total_seconds()
    if age_seconds < 0.0:
        raise DemoCanaryLauncherError(
            "Approved canary observation is not causally available yet."
        )
    if age_seconds > _APPROVED_CANDIDATE_MAX_AGE_SECONDS:
        raise DemoCanaryLauncherError(
            "Approved canary observation became stale before authorization."
        )


def _require_same_latest_m5(
    service: MarketDataService,
    approved_bar: MarketBar,
) -> None:
    latest = service.get_latest_closed_bar()
    if latest is None or latest.timestamp != approved_bar.timestamp:
        raise DemoCanaryLauncherError(
            "A newer completed M5 bar appeared before canary submission."
        )


def _print_genuine_approval(
    observation_bar: MarketBar,
    pipeline_result: PipelineResult,
) -> None:
    signal = pipeline_result.signal
    trade_plan = pipeline_result.trade_plan
    if signal is None or trade_plan is None:
        raise DemoCanaryLauncherError(
            "Approved canary candidate is missing execution fields."
        )
    direction = getattr(signal.direction, "name", str(signal.direction))
    print(
        json.dumps(
            {
                "event": "GENUINE_PRODUCTION_APPROVAL_DETECTED",
                "observation_timestamp": observation_bar.timestamp.astimezone(
                    UTC
                ).isoformat(),
                "direction": direction,
                "decision": trade_plan.decision.value,
                "strategy_position_size": trade_plan.position_size,
                "canary_execution_volume": _CANARY_VOLUME,
                "entry_price": trade_plan.entry_price,
                "stop_loss": trade_plan.stop_loss,
                "take_profit": trade_plan.take_profit,
            },
            indent=2,
            sort_keys=True,
        )
    )


def _read_post_signal_acknowledgement() -> str:
    print(
        'Type exactly "I AUTHORIZE ONE DEMO ORDER" now to open the short '
        "one-shot demo authorization window."
    )
    return input("acknowledgement> ").strip()


def _run_one_shot_demo_canary(
    safe_config: LiveTradingConfig,
) -> DemoCanaryLaunchResult:
    """Wait safely for a genuine approval, then authorize and execute it."""

    if safe_config.symbol != _CANARY_SYMBOL:
        raise DemoCanaryLauncherError("Demo canary is restricted to XAUUSD.")
    if (
        safe_config.live_execution_enabled
        or safe_config.demo_execution_approved
        or not safe_config.execution_kill_switch_enabled
    ):
        raise DemoCanaryLauncherError(
            "Demo canary must begin from safe-disabled production controls."
        )

    initialized = False
    analysis_engine: LiveTradingEngine | None = None
    execution_engine: LiveTradingEngine | None = None
    try:
        if not mt5.initialize():
            raise DemoCanaryLauncherError(
                f"Unable to initialize MT5: {mt5.last_error()}"
            )
        initialized = True

        services = _build_services(safe_config)
        analysis_engine = LiveTradingEngine(safe_config)
        analysis_engine.start()

        services[Timeframe.M5].validate_clock_alignment()
        analysis_engine.record_clock_normalization_validated()
        _establish_parity_validation(analysis_engine, safe_config)
        _require_runtime_clear(analysis_engine)

        bootstrap_account = get_account_info()
        if bootstrap_account.trade_mode != 0:
            raise DemoCanaryLauncherError(
                "Signal-gated canary requires an MT5 demo account."
            )

        bootstrap_m5 = services[Timeframe.M5].get_latest_closed_bar()
        if bootstrap_m5 is None:
            raise DemoCanaryLauncherError(
                "No completed M5 bootstrap boundary is available."
            )
        histories, capacities = _load_aligned_live_histories(
            services=services,
            latest_m5=bootstrap_m5,
            analysis_window_bars=safe_config.history_window_bars,
        )
        buffer = LiveMultiTimeframeBuffer(
            window_bars=safe_config.history_window_bars,
            source_capacity_bars=capacities,
        )
        for timeframe, history in histories.items():
            buffer.load(timeframe, history)

        analysis_engine.reconcile_realized_deals(
            account_balance=bootstrap_account.balance,
            initialize_only=True,
        )
        analysis_engine.pipeline.synchronize_account_balance(
            bootstrap_account.balance
        )

        symbol_spec: LiveSymbolSpecification = get_live_symbol_specification(
            safe_config.symbol
        )
        if symbol_spec.symbol != _CANARY_SYMBOL:
            raise DemoCanaryLauncherError(
                "Live symbol specification does not match XAUUSD."
            )
        if (
            _CANARY_VOLUME < symbol_spec.minimum_lot - _VOLUME_TOLERANCE
            or _CANARY_VOLUME > symbol_spec.maximum_lot + _VOLUME_TOLERANCE
        ):
            raise DemoCanaryLauncherError(
                "Live risk specification does not permit 0.01 lot."
            )

        warmup_snapshots = []
        for m5_bar in buffer.histories[Timeframe.M5]:
            boundary = m5_bar.timestamp + timedelta(minutes=5)
            snapshot = buffer.snapshot(boundary)
            if snapshot is not None:
                warmup_snapshots.append(snapshot)

        if len(warmup_snapshots) < safe_config.warmup_bars:
            raise DemoCanaryLauncherError(
                "Insufficient complete synchronized M5 warm-up snapshots: "
                f"required={safe_config.warmup_bars} "
                f"available={len(warmup_snapshots)}."
            )

        for snapshot in warmup_snapshots:
            analysis_engine.process_multi_timeframe(
                snapshot,
                account_balance=bootstrap_account.balance,
                stop_loss_distance=symbol_spec.minimum_stop_distance,
                pip_value=symbol_spec.tick_value_per_lot,
                tick_size=symbol_spec.tick_size,
                lot_step=symbol_spec.lot_step,
                minimum_lot=symbol_spec.minimum_lot,
                maximum_lot=symbol_spec.maximum_lot,
                warmup=True,
            )

        print(
            "Signal-gated canary is armed in SAFE-DISABLED mode. "
            "No authorization exists and no order can be submitted while "
            "waiting for a genuine production APPROVE."
        )

        while True:
            _require_runtime_clear(analysis_engine)

            m5_bar = services[Timeframe.M5].get_latest_closed_bar()
            if m5_bar is None:
                time.sleep(float(safe_config.poll_interval_seconds))
                continue

            for timeframe in (
                Timeframe.M15,
                Timeframe.H1,
                Timeframe.H4,
            ):
                completed = services[timeframe].get_latest_closed_bar()
                if completed is not None:
                    buffer.append(timeframe, completed)

            if not buffer.append(Timeframe.M5, m5_bar):
                time.sleep(float(safe_config.poll_interval_seconds))
                continue

            boundary = m5_bar.timestamp + timedelta(minutes=5)
            snapshot = buffer.snapshot(boundary)
            if snapshot is None:
                time.sleep(float(safe_config.poll_interval_seconds))
                continue

            account = get_account_info()
            if (
                account.login != bootstrap_account.login
                or account.server != bootstrap_account.server
                or account.trade_mode != 0
            ):
                raise DemoCanaryLauncherError(
                    "Connected demo account identity changed while waiting."
                )

            analysis_engine.reconcile_realized_deals(
                account_balance=account.balance,
                as_of=boundary,
            )
            _require_runtime_clear(analysis_engine)

            analysis_result = analysis_engine.process_multi_timeframe(
                snapshot,
                account_balance=account.balance,
                stop_loss_distance=symbol_spec.minimum_stop_distance,
                pip_value=symbol_spec.tick_value_per_lot,
                tick_size=symbol_spec.tick_size,
                lot_step=symbol_spec.lot_step,
                minimum_lot=symbol_spec.minimum_lot,
                maximum_lot=symbol_spec.maximum_lot,
            )
            trade_plan = analysis_result.pipeline_result.trade_plan
            if trade_plan is None or trade_plan.decision is not RiskDecision.APPROVE:
                time.sleep(float(safe_config.poll_interval_seconds))
                continue

            audit = analysis_engine.pipeline.last_observation_audit
            if (
                audit is None
                or audit.timestamp != m5_bar.timestamp.astimezone(UTC)
                or not audit.accepted
            ):
                raise DemoCanaryLauncherError(
                    "Genuine approval is not backed by the matching accepted "
                    "pipeline audit."
                )

            _print_genuine_approval(m5_bar, analysis_result.pipeline_result)
            candidate = _build_canary_execution_candidate(
                analysis_result.pipeline_result
            )

            acknowledgement = _read_post_signal_acknowledgement()
            if acknowledgement != _REQUIRED_ACKNOWLEDGEMENT:
                return _terminal_result(
                    analysis_engine,
                    outcome="POST_SIGNAL_AUTHORIZATION_DECLINED",
                    authorization_consumed=False,
                    last_error="Exact demo authorization acknowledgement was not supplied.",
                )

            _require_fresh_approved_candidate(m5_bar, now=_utc_now())
            _require_same_latest_m5(services[Timeframe.M5], m5_bar)

            preflight = collect_connected_demo_canary_preflight_evidence(
                config=safe_config,
                lookback_hours=24,
            )
            export_connected_demo_canary_preflight_evidence(
                _PREFLIGHT_PATH,
                preflight,
            )
            if not preflight.validation_passed:
                raise DemoCanaryLauncherError(
                    "Post-signal connected preflight failed: "
                    + "; ".join(preflight.reasons)
                )

            _require_fresh_approved_candidate(m5_bar, now=_utc_now())
            _require_same_latest_m5(services[Timeframe.M5], m5_bar)

            preparation = prepare_fresh_demo_authorization_from_preflight(
                config=safe_config,
                preflight_path=_PREFLIGHT_PATH,
                acknowledgement=acknowledgement,
                now=_utc_now(),
            )
            authorization = preparation.authorization
            _validate_initial_authorization(authorization, now=_utc_now())
            _validate_preflight_binding(preflight, authorization)

            active_config = _build_active_canary_config(
                safe_config,
                authorization,
            )
            account = get_account_info()
            if (
                account.login != authorization.account_login
                or account.server != authorization.account_server
                or account.trade_mode != 0
            ):
                raise DemoCanaryLauncherError(
                    "Connected demo account changed after authorization."
                )
            validate_demo_execution_authorization_scope(
                authorization,
                config=active_config,
                account=account,
                now=_utc_now(),
            )

            execution_engine = LiveTradingEngine(active_config)
            execution_engine.start()
            services[Timeframe.M5].validate_clock_alignment()
            execution_engine.record_clock_normalization_validated()
            _establish_parity_validation(execution_engine, active_config)
            execution_engine.reconcile_realized_deals(
                account_balance=account.balance,
                initialize_only=True,
            )
            execution_engine.pipeline.synchronize_account_balance(account.balance)
            _require_runtime_clear(execution_engine)

            _require_fresh_approved_candidate(m5_bar, now=_utc_now())
            _require_same_latest_m5(services[Timeframe.M5], m5_bar)

            execution_result = execution_engine.execute_precomputed_approved_observation(
                observation_bar=m5_bar,
                pipeline_result=candidate,
            )

            broker_result = execution_result.execution_result
            if execution_engine.state.order_submissions_this_session > 0:
                consumed = load_demo_execution_authorization(
                    active_config.demo_authorization_path
                ).consumed
                return _terminal_result(
                    execution_engine,
                    outcome="ONE_SUBMISSION_ATTEMPT_COMPLETED",
                    authorization_consumed=consumed,
                    execution_status=(
                        None if broker_result is None else broker_result.status.value
                    ),
                    trade_executed=execution_result.trade_executed,
                    last_error=execution_engine.state.last_error,
                )

            post_authorization = load_demo_execution_authorization(
                active_config.demo_authorization_path
            )
            if post_authorization.consumed:
                return _terminal_result(
                    execution_engine,
                    outcome="AUTHORIZATION_CONSUMED_WITHOUT_EXECUTOR_ATTEMPT",
                    authorization_consumed=True,
                    last_error=execution_engine.state.last_error,
                )

            return _terminal_result(
                execution_engine,
                outcome="SAFETY_ABORT_AFTER_GENUINE_APPROVAL",
                authorization_consumed=False,
                last_error=execution_engine.state.last_error,
            )

    finally:
        if execution_engine is not None:
            execution_engine.stop()
        if analysis_engine is not None:
            analysis_engine.stop()
        if initialized:
            mt5.shutdown()


def run_one_shot_demo_canary() -> DemoCanaryLaunchResult:
    """Public dedicated launcher; no generic execution flags are accepted."""

    return _run_one_shot_demo_canary(
        LiveTradingConfig(
            symbol=_CANARY_SYMBOL,
            live_execution_enabled=False,
            demo_execution_approved=False,
            execution_kill_switch_enabled=True,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run exactly one authorized XAUUSD demo canary. No generic live "
            "execution flags or arbitrary volume controls are available."
        )
    )
    parser.parse_args()

    try:
        result = run_one_shot_demo_canary()
    except (
        DemoCanaryLauncherError,
        DemoExecutionAuthorizationError,
        ExecutionIntentStateError,
        PartialFillStateError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"One-shot demo canary failed closed: {exc}")
        return 2

    print(json.dumps(result.to_payload(), indent=2, sort_keys=True))
    print(
        "Run read-only reconciliation next with: "
        "python -m core.live_trading.connected_reconciliation_probe "
        "--symbol XAUUSD --lookback-hours 24"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
