"""Connected MT5 demo-account read-only reconciliation probe."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import MetaTrader5 as mt5

from core.mt5_execution.account import get_account_info
from core.mt5_execution.active_orders import get_active_orders
from core.mt5_execution.deal_history import get_execution_deals
from core.mt5_execution.models import (
    AccountInfo,
    ActiveOrderInfo,
    ExecutionDealInfo,
    HistoricalOrderInfo,
    PositionInfo,
)
from core.mt5_execution.order_history import get_historical_orders
from core.mt5_execution.positions import get_open_positions

from .config import LiveTradingConfig
from .execution_intent_reconciliation import (
    ExecutionIntentReconciliationError,
    reconcile_execution_intent,
)
from .execution_intent_store import ExecutionIntentStore

_DEMO_TRADE_MODE = int(getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", 0))


class ConnectedReconciliationProbeError(RuntimeError):
    """Raised when the connected read-only probe cannot run safely."""


@dataclass(frozen=True, slots=True)
class ConnectedReconciliationProbeResult:
    """Non-authoritative evidence from one connected read-only probe."""

    recorded_at: datetime
    symbol: str
    account_login: int
    account_server: str
    account_trade_mode: int
    demo_account_confirmed: bool
    live_execution_enabled: bool
    shadow_only: bool
    order_submission_attempted: bool
    trade_executed: bool
    persisted_intent_present: bool
    persisted_intent_key: str | None
    persisted_intent_status_before: str | None
    reconciled_intent_status: str | None
    reconciliation_disposition: str
    reconciliation_reason: str
    matching_order_ticket: int | None
    matching_deal_tickets: tuple[int, ...]
    active_order_count: int
    historical_order_count: int
    execution_deal_count: int
    open_position_count: int
    validation_passed: bool

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["recorded_at"] = self.recorded_at.astimezone(UTC).isoformat()
        payload["matching_deal_tickets"] = list(self.matching_deal_tickets)
        return payload


def run_connected_demo_read_only_probe(
    *,
    config: LiveTradingConfig,
    lookback_hours: int = 24,
    as_of: datetime | None = None,
    account_reader: Callable[[], AccountInfo] = get_account_info,
    active_order_reader: Callable[[str], Sequence[ActiveOrderInfo]] = (
        get_active_orders
    ),
    historical_order_reader: Callable[
        ..., Sequence[HistoricalOrderInfo]
    ] = get_historical_orders,
    deal_reader: Callable[..., Sequence[ExecutionDealInfo]] = (
        get_execution_deals
    ),
    position_reader: Callable[[str], Sequence[PositionInfo]] = (
        get_open_positions
    ),
) -> ConnectedReconciliationProbeResult:
    """Query broker evidence and reconcile without persisting or submitting."""

    if config.live_execution_enabled:
        raise ConnectedReconciliationProbeError(
            "Read-only probe requires live_execution_enabled=False."
        )
    if isinstance(lookback_hours, bool) or not isinstance(lookback_hours, int):
        raise TypeError("lookback_hours must be an integer")
    if lookback_hours <= 0:
        raise ValueError("lookback_hours must be greater than zero")

    end = datetime.now(UTC) if as_of is None else _aware_utc(as_of, "as_of")
    start = end - timedelta(hours=lookback_hours)
    account = account_reader()

    demo_confirmed = account.trade_mode == _DEMO_TRADE_MODE
    if not demo_confirmed:
        raise ConnectedReconciliationProbeError(
            "Connected account is not confirmed as an MT5 demo account."
        )

    active_orders = tuple(active_order_reader(config.symbol))
    historical_orders = tuple(
        historical_order_reader(
            date_from=start,
            date_to=end,
            symbol=config.symbol,
        )
    )
    execution_deals = tuple(
        deal_reader(
            date_from=start,
            date_to=end,
            symbol=config.symbol,
        )
    )
    open_positions = tuple(position_reader(config.symbol))

    intent = ExecutionIntentStore(config.execution_intent_state_path).load()
    if intent is None:
        return ConnectedReconciliationProbeResult(
            recorded_at=end,
            symbol=config.symbol,
            account_login=account.login,
            account_server=account.server,
            account_trade_mode=account.trade_mode,
            demo_account_confirmed=True,
            live_execution_enabled=False,
            shadow_only=True,
            order_submission_attempted=False,
            trade_executed=False,
            persisted_intent_present=False,
            persisted_intent_key=None,
            persisted_intent_status_before=None,
            reconciled_intent_status=None,
            reconciliation_disposition="NO_PERSISTED_INTENT",
            reconciliation_reason=(
                "No persisted execution intent exists; broker evidence was "
                "queried read-only."
            ),
            matching_order_ticket=None,
            matching_deal_tickets=(),
            active_order_count=len(active_orders),
            historical_order_count=len(historical_orders),
            execution_deal_count=len(execution_deals),
            open_position_count=len(open_positions),
            validation_passed=True,
        )

    try:
        reconciliation = reconcile_execution_intent(
            intent=intent,
            active_orders=active_orders,
            historical_orders=historical_orders,
            execution_deals=execution_deals,
            open_positions=open_positions,
            as_of=end,
        )
    except ExecutionIntentReconciliationError as exc:
        return ConnectedReconciliationProbeResult(
            recorded_at=end,
            symbol=config.symbol,
            account_login=account.login,
            account_server=account.server,
            account_trade_mode=account.trade_mode,
            demo_account_confirmed=True,
            live_execution_enabled=False,
            shadow_only=True,
            order_submission_attempted=False,
            trade_executed=False,
            persisted_intent_present=True,
            persisted_intent_key=intent.intent_key,
            persisted_intent_status_before=intent.status.value,
            reconciled_intent_status=intent.status.value,
            reconciliation_disposition="FAILED_CLOSED",
            reconciliation_reason=str(exc),
            matching_order_ticket=intent.ticket,
            matching_deal_tickets=(),
            active_order_count=len(active_orders),
            historical_order_count=len(historical_orders),
            execution_deal_count=len(execution_deals),
            open_position_count=len(open_positions),
            validation_passed=True,
        )

    return ConnectedReconciliationProbeResult(
        recorded_at=end,
        symbol=config.symbol,
        account_login=account.login,
        account_server=account.server,
        account_trade_mode=account.trade_mode,
        demo_account_confirmed=True,
        live_execution_enabled=False,
        shadow_only=True,
        order_submission_attempted=False,
        trade_executed=False,
        persisted_intent_present=True,
        persisted_intent_key=intent.intent_key,
        persisted_intent_status_before=intent.status.value,
        reconciled_intent_status=reconciliation.intent.status.value,
        reconciliation_disposition=reconciliation.disposition.value,
        reconciliation_reason=reconciliation.reason,
        matching_order_ticket=reconciliation.matching_order_ticket,
        matching_deal_tickets=reconciliation.matching_deal_tickets,
        active_order_count=len(active_orders),
        historical_order_count=len(historical_orders),
        execution_deal_count=len(execution_deals),
        open_position_count=len(open_positions),
        validation_passed=True,
    )


def export_connected_probe_result(
    path: str | Path,
    result: ConnectedReconciliationProbeResult,
) -> Path:
    """Write one deterministic JSON report."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(result.to_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def main() -> int:
    """Run the connected demo-account probe from the command line."""

    parser = argparse.ArgumentParser(
        description=(
            "Query a signed-in MT5 demo account read-only and reconcile any "
            "persisted execution intent without saving or submitting."
        )
    )
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--lookback-hours", type=int, default=24)
    parser.add_argument(
        "--output",
        default=(
            "output/live_execution_reconciliation/"
            "connected_demo_read_only_probe.json"
        ),
    )
    args = parser.parse_args()

    initialized = False
    try:
        if not mt5.initialize():
            raise ConnectedReconciliationProbeError(
                f"Unable to initialize MT5: {mt5.last_error()}"
            )
        initialized = True
        result = run_connected_demo_read_only_probe(
            config=LiveTradingConfig(
                symbol=args.symbol,
                live_execution_enabled=False,
            ),
            lookback_hours=args.lookback_hours,
        )
        output = export_connected_probe_result(args.output, result)
        print(json.dumps(result.to_payload(), indent=2, sort_keys=True))
        print(f"Read-only probe exported to {output}")
        return 0 if result.validation_passed else 1
    except (
        ConnectedReconciliationProbeError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"Read-only probe failed closed: {exc}")
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
