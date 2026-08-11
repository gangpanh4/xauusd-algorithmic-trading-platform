"""Dedicated one-shot authorized MT5 demo-canary launcher.

This module is intentionally separate from the ordinary indefinite live mode.
It enables execution controls only inside this short-lived process, requires an
existing durable one-shot demo authorization, waits for a genuine production
APPROVE TradePlan, permits at most one executor invocation, and then terminates.
"""

from __future__ import annotations

import argparse
import json
import time
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

from .config import LiveTradingConfig
from .connected_demo_canary_preflight import (
    ConnectedDemoCanaryPreflightEvidence,
    collect_connected_demo_canary_preflight_evidence,
)
from .demo_execution_authorization import (
    DemoExecutionAuthorization,
    DemoExecutionAuthorizationError,
    load_demo_execution_authorization,
    validate_demo_execution_authorization_scope,
    validate_demo_execution_authorization_time_window,
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


def _load_wait_authorization(
    path: Path,
    initial: DemoExecutionAuthorization,
    *,
    now: datetime,
) -> DemoExecutionAuthorization:
    current = load_demo_execution_authorization(path)
    if current.consumed:
        return current
    validate_demo_execution_authorization_time_window(current, now=now)
    if current != initial:
        raise DemoCanaryLauncherError(
            "Demo execution authorization changed while the canary was waiting."
        )
    return current


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


def _sleep_without_crossing_expiry(
    config: LiveTradingConfig,
    authorization: DemoExecutionAuthorization,
    *,
    now: datetime,
) -> None:
    remaining = (
        authorization.expires_at.astimezone(UTC) - now.astimezone(UTC)
    ).total_seconds()
    if remaining <= 0.0:
        return
    time.sleep(min(float(config.poll_interval_seconds), remaining))


def _expired_result(
    engine: LiveTradingEngine,
    exc: DemoExecutionAuthorizationError,
) -> DemoCanaryLaunchResult:
    return _terminal_result(
        engine,
        outcome="AUTHORIZATION_EXPIRED_NO_SUBMISSION",
        authorization_consumed=False,
        last_error=str(exc),
    )


def _run_one_shot_demo_canary(
    safe_config: LiveTradingConfig,
) -> DemoCanaryLaunchResult:
    """Run one dedicated canary using an existing durable authorization."""

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

    initial_authorization = load_demo_execution_authorization(
        safe_config.demo_authorization_path
    )
    _validate_initial_authorization(
        initial_authorization,
        now=_utc_now(),
    )

    initialized = False
    engine: LiveTradingEngine | None = None
    try:
        if not mt5.initialize():
            raise DemoCanaryLauncherError(
                f"Unable to initialize MT5: {mt5.last_error()}"
            )
        initialized = True

        preflight = collect_connected_demo_canary_preflight_evidence(
            config=safe_config,
            lookback_hours=24,
        )
        _validate_preflight_binding(preflight, initial_authorization)

        account = get_account_info()
        if (
            account.login != preflight.account_login
            or account.server != preflight.account_server
            or account.trade_mode != preflight.account_trade_mode
        ):
            raise DemoCanaryLauncherError(
                "Connected account changed after the safe-disabled preflight."
            )

        active_config = _build_active_canary_config(
            safe_config,
            initial_authorization,
        )
        validate_demo_execution_authorization_scope(
            initial_authorization,
            config=active_config,
            account=account,
            now=_utc_now(),
        )

        services = _build_services(active_config)
        engine = LiveTradingEngine(active_config)
        engine.start()

        services[Timeframe.M5].validate_clock_alignment()
        engine.record_clock_normalization_validated()
        _establish_parity_validation(engine, active_config)

        _require_runtime_clear(engine)

        bootstrap_m5 = services[Timeframe.M5].get_latest_closed_bar()
        if bootstrap_m5 is None:
            raise DemoCanaryLauncherError(
                "No completed M5 bootstrap boundary is available."
            )
        histories, capacities = _load_aligned_live_histories(
            services=services,
            latest_m5=bootstrap_m5,
            analysis_window_bars=active_config.history_window_bars,
        )
        buffer = LiveMultiTimeframeBuffer(
            window_bars=active_config.history_window_bars,
            source_capacity_bars=capacities,
        )
        for timeframe, history in histories.items():
            buffer.load(timeframe, history)

        account = get_account_info()
        engine.reconcile_realized_deals(
            account_balance=account.balance,
            initialize_only=True,
        )
        engine.pipeline.synchronize_account_balance(account.balance)

        symbol_spec: LiveSymbolSpecification = get_live_symbol_specification(
            active_config.symbol
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
            try:
                current_authorization = _load_wait_authorization(
                    active_config.demo_authorization_path,
                    initial_authorization,
                    now=_utc_now(),
                )
            except DemoExecutionAuthorizationError as exc:
                if "expired" in str(exc).lower():
                    return _expired_result(engine, exc)
                raise
            if current_authorization.consumed:
                return _terminal_result(
                    engine,
                    outcome="AUTHORIZATION_CONSUMED_DURING_BOOTSTRAP",
                    authorization_consumed=True,
                )

            boundary = m5_bar.timestamp + timedelta(minutes=5)
            snapshot = buffer.snapshot(boundary)
            if snapshot is not None:
                warmup_snapshots.append(snapshot)

        if len(warmup_snapshots) < active_config.warmup_bars:
            raise DemoCanaryLauncherError(
                "Insufficient complete synchronized M5 warm-up snapshots: "
                f"required={active_config.warmup_bars} "
                f"available={len(warmup_snapshots)}."
            )

        for snapshot in warmup_snapshots:
            try:
                current_authorization = _load_wait_authorization(
                    active_config.demo_authorization_path,
                    initial_authorization,
                    now=_utc_now(),
                )
            except DemoExecutionAuthorizationError as exc:
                if "expired" in str(exc).lower():
                    return _expired_result(engine, exc)
                raise
            if current_authorization.consumed:
                return _terminal_result(
                    engine,
                    outcome="AUTHORIZATION_CONSUMED_DURING_WARMUP",
                    authorization_consumed=True,
                )
            engine.process_multi_timeframe(
                snapshot,
                account_balance=account.balance,
                stop_loss_distance=symbol_spec.minimum_stop_distance,
                pip_value=symbol_spec.tick_value_per_lot,
                tick_size=symbol_spec.tick_size,
                lot_step=symbol_spec.lot_step,
                minimum_lot=symbol_spec.minimum_lot,
                maximum_lot=symbol_spec.maximum_lot,
                warmup=True,
            )

        while True:
            now = _utc_now()
            try:
                current_authorization = _load_wait_authorization(
                    active_config.demo_authorization_path,
                    initial_authorization,
                    now=now,
                )
            except DemoExecutionAuthorizationError as exc:
                if "expired" in str(exc).lower():
                    return _expired_result(engine, exc)
                raise

            if current_authorization.consumed:
                return _terminal_result(
                    engine,
                    outcome="AUTHORIZATION_CONSUMED",
                    authorization_consumed=True,
                )

            _require_runtime_clear(engine)

            m5_bar = services[Timeframe.M5].get_latest_closed_bar()
            if m5_bar is None:
                _sleep_without_crossing_expiry(
                    active_config,
                    current_authorization,
                    now=now,
                )
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
                _sleep_without_crossing_expiry(
                    active_config,
                    current_authorization,
                    now=now,
                )
                continue

            boundary = m5_bar.timestamp + timedelta(minutes=5)
            snapshot = buffer.snapshot(boundary)
            if snapshot is None:
                _sleep_without_crossing_expiry(
                    active_config,
                    current_authorization,
                    now=now,
                )
                continue

            account = get_account_info()
            if (
                account.login != active_config.approved_account_login
                or account.server != active_config.approved_account_server
                or account.trade_mode != 0
            ):
                raise DemoCanaryLauncherError(
                    "Connected demo account identity changed while waiting."
                )

            engine.reconcile_realized_deals(
                account_balance=account.balance,
                as_of=boundary,
            )
            _require_runtime_clear(engine)

            result = engine.process_multi_timeframe(
                snapshot,
                account_balance=account.balance,
                stop_loss_distance=symbol_spec.minimum_stop_distance,
                pip_value=symbol_spec.tick_value_per_lot,
                tick_size=symbol_spec.tick_size,
                lot_step=symbol_spec.lot_step,
                minimum_lot=symbol_spec.minimum_lot,
                maximum_lot=symbol_spec.maximum_lot,
            )

            execution_result = result.execution_result
            if engine.state.order_submissions_this_session > 0:
                consumed = load_demo_execution_authorization(
                    active_config.demo_authorization_path
                ).consumed
                return _terminal_result(
                    engine,
                    outcome="ONE_SUBMISSION_ATTEMPT_COMPLETED",
                    authorization_consumed=consumed,
                    execution_status=(
                        None
                        if execution_result is None
                        else execution_result.status.value
                    ),
                    trade_executed=result.trade_executed,
                    last_error=engine.state.last_error,
                )

            post_authorization = load_demo_execution_authorization(
                active_config.demo_authorization_path
            )
            if post_authorization.consumed:
                return _terminal_result(
                    engine,
                    outcome="AUTHORIZATION_CONSUMED_WITHOUT_EXECUTOR_ATTEMPT",
                    authorization_consumed=True,
                    last_error=engine.state.last_error,
                )

            trade_plan = result.pipeline_result.trade_plan
            if (
                trade_plan is not None
                and trade_plan.decision is RiskDecision.APPROVE
                and engine.state.last_error
            ):
                return _terminal_result(
                    engine,
                    outcome="SAFETY_ABORT_AFTER_GENUINE_APPROVAL",
                    authorization_consumed=False,
                    last_error=engine.state.last_error,
                )

            _sleep_without_crossing_expiry(
                active_config,
                post_authorization,
                now=_utc_now(),
            )

    finally:
        if engine is not None:
            engine.stop()
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
