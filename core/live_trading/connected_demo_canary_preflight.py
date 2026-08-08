"""Connected read-only demo-canary preflight evidence.

This module may initialize MT5 only from its CLI entry point. It never consumes
an authorization, never clears the kill switch, never enables execution, and
never submits an order.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import MetaTrader5 as mt5

from core.mt5_execution.models import SymbolInfo
from core.mt5_execution.symbols import get_symbol_info

from .config import LiveTradingConfig
from .connected_reconciliation_probe import (
    ConnectedReconciliationProbeResult,
    run_connected_demo_read_only_probe,
)
from .execution_intent_store import ExecutionIntentStore
from .partial_fill_store import PartialFillStateStore


class ConnectedDemoCanaryPreflightError(RuntimeError):
    """Raised when connected preflight evidence cannot be produced safely."""


@dataclass(frozen=True, slots=True)
class ConnectedDemoCanaryPreflightEvidence:
    """Read-only evidence captured from the connected MT5 demo account."""

    recorded_at: datetime
    symbol: str
    account_login: int
    account_server: str
    account_trade_mode: int
    demo_account_confirmed: bool
    symbol_specification_loaded: bool
    symbol_trade_allowed: bool
    symbol_volume_min: float
    symbol_volume_max: float
    symbol_volume_step: float
    symbol_tick_size: float
    symbol_minimum_stop_distance: float
    active_order_count: int
    historical_order_count: int
    execution_deal_count: int
    open_position_count: int
    persisted_intent_present: bool
    persisted_intent_status: str | None
    reconciliation_disposition: str
    reconciliation_clear: bool
    unresolved_partial_fill: bool
    unresolved_partial_ticket: int | None
    live_execution_enabled: bool
    demo_execution_approved: bool
    execution_kill_switch_enabled: bool
    order_submission_attempted: bool
    authorization_consumed: bool
    trade_executed: bool
    validation_passed: bool
    reasons: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["recorded_at"] = self.recorded_at.astimezone(UTC).isoformat()
        payload["reasons"] = list(self.reasons)
        return payload


def collect_connected_demo_canary_preflight_evidence(
    *,
    config: LiveTradingConfig,
    lookback_hours: int = 24,
    as_of: datetime | None = None,
    probe_runner: Callable[..., ConnectedReconciliationProbeResult] = (
        run_connected_demo_read_only_probe
    ),
    symbol_reader: Callable[[str], SymbolInfo] = get_symbol_info,
) -> ConnectedDemoCanaryPreflightEvidence:
    """Collect connected evidence while preserving all execution interlocks."""

    if config.live_execution_enabled:
        raise ConnectedDemoCanaryPreflightError(
            "Connected canary preflight requires live_execution_enabled=False."
        )
    if config.demo_execution_approved:
        raise ConnectedDemoCanaryPreflightError(
            "Connected canary preflight requires demo_execution_approved=False."
        )
    if not config.execution_kill_switch_enabled:
        raise ConnectedDemoCanaryPreflightError(
            "Connected canary preflight requires the kill switch to remain enabled."
        )

    observed_at = datetime.now(UTC) if as_of is None else _aware_utc(as_of, "as_of")
    probe = probe_runner(
        config=config,
        lookback_hours=lookback_hours,
        as_of=observed_at,
    )
    symbol = symbol_reader(config.symbol)
    partial = PartialFillStateStore(config.partial_fill_state_path).load()
    intent = ExecutionIntentStore(config.execution_intent_state_path).load()

    reasons: list[str] = []
    reconciliation_clear = probe.reconciliation_disposition in {
        "NO_PERSISTED_INTENT",
        "NO_INTENT",
        "RECONCILED_CLEAR",
        "TERMINAL_CONFIRMED",
    }

    if not probe.demo_account_confirmed:
        reasons.append("Connected account is not confirmed as demo.")
    if symbol.name != config.symbol:
        reasons.append("Loaded symbol specification does not match configured symbol.")
    if not symbol.trade_allowed:
        reasons.append("Configured symbol is not trade-allowed by the broker.")
    if probe.active_order_count != 0:
        reasons.append("Active broker orders exist.")
    if probe.open_position_count != 0:
        reasons.append("Open broker positions exist.")
    if partial is not None:
        reasons.append("An unresolved persisted partial fill exists.")
    if not reconciliation_clear:
        reasons.append("Execution-intent reconciliation is not clear.")
    if intent is not None and intent.unresolved:
        reasons.append("A persisted unresolved execution intent exists.")

    validation_passed = not reasons
    return ConnectedDemoCanaryPreflightEvidence(
        recorded_at=observed_at,
        symbol=config.symbol,
        account_login=probe.account_login,
        account_server=probe.account_server,
        account_trade_mode=probe.account_trade_mode,
        demo_account_confirmed=probe.demo_account_confirmed,
        symbol_specification_loaded=True,
        symbol_trade_allowed=symbol.trade_allowed,
        symbol_volume_min=float(symbol.volume_min),
        symbol_volume_max=float(symbol.volume_max),
        symbol_volume_step=float(symbol.volume_step),
        symbol_tick_size=float(symbol.tick_size),
        symbol_minimum_stop_distance=float(symbol.minimum_stop_distance),
        active_order_count=probe.active_order_count,
        historical_order_count=probe.historical_order_count,
        execution_deal_count=probe.execution_deal_count,
        open_position_count=probe.open_position_count,
        persisted_intent_present=probe.persisted_intent_present,
        persisted_intent_status=probe.reconciled_intent_status,
        reconciliation_disposition=probe.reconciliation_disposition,
        reconciliation_clear=reconciliation_clear,
        unresolved_partial_fill=partial is not None,
        unresolved_partial_ticket=None if partial is None else partial.ticket,
        live_execution_enabled=False,
        demo_execution_approved=False,
        execution_kill_switch_enabled=True,
        order_submission_attempted=False,
        authorization_consumed=False,
        trade_executed=False,
        validation_passed=validation_passed,
        reasons=tuple(reasons),
    )


def export_connected_demo_canary_preflight_evidence(
    path: str | Path,
    evidence: ConnectedDemoCanaryPreflightEvidence,
) -> Path:
    """Write one deterministic JSON evidence artifact."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(evidence.to_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def main() -> int:
    """Run the connected read-only canary preflight from PowerShell."""

    parser = argparse.ArgumentParser(
        description=(
            "Capture connected MT5 demo-canary preflight evidence without "
            "consuming authorization or submitting orders."
        )
    )
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--lookback-hours", type=int, default=24)
    parser.add_argument(
        "--output",
        default=(
            "output/live_execution_reconciliation/"
            "connected_demo_canary_preflight.json"
        ),
    )
    args = parser.parse_args()

    initialized = False
    config = LiveTradingConfig(
        symbol=args.symbol,
        live_execution_enabled=False,
        demo_execution_approved=False,
        execution_kill_switch_enabled=True,
    )
    try:
        if not mt5.initialize():
            raise ConnectedDemoCanaryPreflightError(
                f"Unable to initialize MT5: {mt5.last_error()}"
            )
        initialized = True
        evidence = collect_connected_demo_canary_preflight_evidence(
            config=config,
            lookback_hours=args.lookback_hours,
        )
        output = export_connected_demo_canary_preflight_evidence(
            args.output,
            evidence,
        )
        print(json.dumps(evidence.to_payload(), indent=2, sort_keys=True))
        print(f"Connected demo-canary preflight exported to {output}")
        return 0 if evidence.validation_passed else 1
    except (
        ConnectedDemoCanaryPreflightError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"Connected demo-canary preflight failed closed: {exc}")
        return 2
    finally:
        if initialized:
            mt5.shutdown()


def _aware_utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


if __name__ == "__main__":
    raise SystemExit(main())
