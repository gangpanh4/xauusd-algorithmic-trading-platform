"""Runtime state for the Risk Management package.

The state object is broker independent. It tracks account balances, daily
sessions, realized trade statistics, drawdown, position exposure, and safety
flags. All monetary values use account currency; losses are stored as positive
amounts in the dedicated loss fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
import math

from .models import TradePlan


@dataclass
class RiskManagerState:
    """Maintain deterministic runtime state for risk decisions.

    Daily accounting uses UTC calendar dates until the platform introduces an
    explicit broker-session clock. ``daily_profit`` and ``daily_loss`` are gross
    realized amounts. ``daily_drawdown`` is the net decline from the balance at
    the start of the current UTC trading day.
    """

    # Initialization
    initialized: bool = False

    # Last processed decision/trade
    last_trade_plan: TradePlan | None = None
    last_decision_time: datetime | None = None
    last_trade_close_time: datetime | None = None
    last_balance_update_time: datetime | None = None

    # Decision statistics
    processed_signal_count: int = 0
    approved_trade_count: int = 0
    rejected_trade_count: int = 0
    skipped_trade_count: int = 0

    # Completed-trade statistics
    completed_trade_count: int = 0
    breakeven_trade_count: int = 0

    # Account state
    virtual_balance: float = 0.0
    peak_balance: float = 0.0
    starting_balance: float = 0.0

    # Daily session state
    current_trading_date: date | None = None
    daily_start_balance: float = 0.0
    daily_profit: float = 0.0
    daily_loss: float = 0.0

    # Lifetime realized statistics
    total_profit: float = 0.0
    total_loss: float = 0.0

    consecutive_wins: int = 0
    consecutive_losses: int = 0

    largest_win: float = 0.0
    largest_loss: float = 0.0

    # Exposure
    open_position_count: int = 0

    # Drawdown
    current_drawdown: float = 0.0
    max_drawdown: float = 0.0

    # Safety
    emergency_stop: bool = False
    daily_loss_limit_hit: bool = False

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def total_net_pnl(self) -> float:
        """Return cumulative realized net P&L in account currency."""

        return self.total_profit - self.total_loss

    @property
    def daily_net_pnl(self) -> float:
        """Return realized net P&L for the current UTC trading day."""

        return self.daily_profit - self.daily_loss

    @property
    def daily_drawdown(self) -> float:
        """Return the net decline from the current daily starting balance."""

        if not self.initialized or self.daily_start_balance <= 0:
            return 0.0

        return max(0.0, self.daily_start_balance - self.virtual_balance)

    @property
    def daily_drawdown_fraction(self) -> float:
        """Return current daily drawdown as a decimal fraction."""

        if self.daily_start_balance <= 0:
            return 0.0

        return self.daily_drawdown / self.daily_start_balance

    @property
    def current_drawdown_fraction(self) -> float:
        """Return current peak-to-balance drawdown as a decimal fraction."""

        if self.peak_balance <= 0:
            return 0.0

        return self.current_drawdown / self.peak_balance

    def initialize_account(
        self,
        balance: float,
        *,
        timestamp: datetime | None = None,
    ) -> None:
        """Initialize account and daily baselines from an authoritative balance."""

        if self.initialized:
            raise RuntimeError(
                "risk state is already initialized; use synchronize_account_balance"
            )

        normalized_balance = self._require_positive_finite(balance, "balance")
        resolved_time = self._resolve_timestamp(timestamp)

        self.initialized = True
        self.starting_balance = normalized_balance
        self.virtual_balance = normalized_balance
        self.peak_balance = normalized_balance

        self.current_trading_date = resolved_time.date()
        self.daily_start_balance = normalized_balance
        self.daily_profit = 0.0
        self.daily_loss = 0.0
        self.daily_loss_limit_hit = False

        self.current_drawdown = 0.0
        self.max_drawdown = 0.0
        self.last_balance_update_time = resolved_time

    def synchronize_account_balance(
        self,
        balance: float,
        *,
        timestamp: datetime | None = None,
    ) -> None:
        """Synchronize state with an authoritative account balance.

        The first synchronization initializes the state. A UTC date change
        starts a new daily session using the supplied balance as its baseline.
        """

        normalized_balance = self._require_non_negative_finite(
            balance,
            "balance",
        )
        resolved_time = self._resolve_timestamp(timestamp)

        if not self.initialized:
            if normalized_balance <= 0:
                raise ValueError("initial account balance must be greater than zero")
            self.initialize_account(normalized_balance, timestamp=resolved_time)
            return

        if self.current_trading_date != resolved_time.date():
            if normalized_balance <= 0:
                raise ValueError(
                    "daily starting balance must be greater than zero"
                )
            self.reset_daily(
                balance=normalized_balance,
                timestamp=resolved_time,
            )

        self.virtual_balance = normalized_balance
        self.last_balance_update_time = resolved_time
        self._update_drawdown()

    def reset(self) -> None:
        """Reset runtime statistics while preserving the account baseline."""

        baseline = self.starting_balance

        self.initialized = False

        self.last_trade_plan = None
        self.last_decision_time = None
        self.last_trade_close_time = None
        self.last_balance_update_time = None

        self.processed_signal_count = 0
        self.approved_trade_count = 0
        self.rejected_trade_count = 0
        self.skipped_trade_count = 0

        self.completed_trade_count = 0
        self.breakeven_trade_count = 0

        self.virtual_balance = baseline
        self.peak_balance = baseline

        self.current_trading_date = None
        self.daily_start_balance = baseline
        self.daily_profit = 0.0
        self.daily_loss = 0.0

        self.total_profit = 0.0
        self.total_loss = 0.0

        self.consecutive_wins = 0
        self.consecutive_losses = 0

        self.largest_win = 0.0
        self.largest_loss = 0.0

        self.open_position_count = 0

        self.current_drawdown = 0.0
        self.max_drawdown = 0.0

        self.emergency_stop = False
        self.daily_loss_limit_hit = False

    def reset_daily(
        self,
        *,
        balance: float | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        """Start a new UTC trading day without resetting lifetime statistics."""

        if not self.initialized:
            raise RuntimeError("risk state must be initialized first")

        resolved_time = self._resolve_timestamp(timestamp)
        baseline = self.virtual_balance if balance is None else balance
        normalized_balance = self._require_positive_finite(
            baseline,
            "balance",
        )

        self.current_trading_date = resolved_time.date()
        self.daily_start_balance = normalized_balance
        self.daily_profit = 0.0
        self.daily_loss = 0.0
        self.daily_loss_limit_hit = False

    def ensure_daily_session(
        self,
        *,
        timestamp: datetime | None = None,
    ) -> None:
        """Create or roll the daily session for the supplied UTC timestamp."""

        if not self.initialized:
            raise RuntimeError("risk state must be initialized first")

        resolved_time = self._resolve_timestamp(timestamp)
        if self.current_trading_date != resolved_time.date():
            self.reset_daily(
                balance=self.virtual_balance,
                timestamp=resolved_time,
            )

    def register_trade(
        self,
        pnl: float,
        *,
        timestamp: datetime | None = None,
        balance_after: float | None = None,
    ) -> None:
        """Register one completed trade using net account-currency P&L.

        ``pnl`` must include all realized trading costs. ``balance_after`` is an
        optional authoritative post-trade balance. When omitted, the balance is
        advanced by ``pnl``.
        """

        normalized_pnl = self._require_finite(pnl, "pnl")
        resolved_time = self._resolve_timestamp(timestamp)

        if not self.initialized:
            if balance_after is None:
                raise RuntimeError(
                    "risk state must be initialized before registering a trade"
                )

            normalized_balance_after = self._require_non_negative_finite(
                balance_after,
                "balance_after",
            )
            implied_start_balance = normalized_balance_after - normalized_pnl
            if implied_start_balance <= 0:
                raise ValueError(
                    "cannot infer a positive starting balance from trade result"
                )
            self.initialize_account(
                implied_start_balance,
                timestamp=resolved_time,
            )

        self.ensure_daily_session(timestamp=resolved_time)

        if balance_after is None:
            updated_balance = self.virtual_balance + normalized_pnl
        else:
            updated_balance = self._require_non_negative_finite(
                balance_after,
                "balance_after",
            )

        if updated_balance < 0:
            raise ValueError("completed trade cannot produce a negative balance")

        self.completed_trade_count += 1
        self.last_trade_close_time = resolved_time

        if normalized_pnl > 0:
            self.total_profit += normalized_pnl
            self.daily_profit += normalized_pnl

            self.consecutive_wins += 1
            self.consecutive_losses = 0
            self.largest_win = max(self.largest_win, normalized_pnl)

        elif normalized_pnl < 0:
            loss = abs(normalized_pnl)
            self.total_loss += loss
            self.daily_loss += loss

            self.consecutive_losses += 1
            self.consecutive_wins = 0
            self.largest_loss = max(self.largest_loss, loss)

        else:
            self.breakeven_trade_count += 1
            self.consecutive_wins = 0
            self.consecutive_losses = 0

        self.virtual_balance = updated_balance
        self.last_balance_update_time = resolved_time
        self._update_drawdown()

    def register_realized_pnl(
        self,
        pnl: float,
        *,
        timestamp: datetime | None = None,
        balance_after: float | None = None,
    ) -> None:
        """Apply deal-level P&L without counting a completed strategy trade."""

        normalized_pnl = self._require_finite(pnl, "pnl")
        resolved_time = self._resolve_timestamp(timestamp)

        if not self.initialized:
            if balance_after is None:
                raise RuntimeError(
                    "risk state must be initialized before realized P&L"
                )
            normalized_balance = self._require_non_negative_finite(
                balance_after,
                "balance_after",
            )
            implied_start = normalized_balance - normalized_pnl
            if implied_start <= 0:
                raise ValueError(
                    "cannot infer a positive starting balance from realized P&L"
                )
            self.initialize_account(implied_start, timestamp=resolved_time)

        self.ensure_daily_session(timestamp=resolved_time)

        updated_balance = (
            self.virtual_balance + normalized_pnl
            if balance_after is None
            else self._require_non_negative_finite(
                balance_after,
                "balance_after",
            )
        )

        if normalized_pnl > 0:
            self.total_profit += normalized_pnl
            self.daily_profit += normalized_pnl
        elif normalized_pnl < 0:
            loss = abs(normalized_pnl)
            self.total_loss += loss
            self.daily_loss += loss

        self.virtual_balance = updated_balance
        self.last_balance_update_time = resolved_time
        self._update_drawdown()

    def set_open_position_count(self, count: int) -> None:
        """Synchronize the number of currently open positions."""

        self.open_position_count = self._require_non_negative_integer(
            count,
            "count",
        )

    def register_position_opened(self, count: int = 1) -> None:
        """Increase tracked open-position exposure."""

        increment = self._require_positive_integer(count, "count")
        self.open_position_count += increment

    def register_position_closed(self, count: int = 1) -> None:
        """Decrease tracked open-position exposure without underflow."""

        decrement = self._require_positive_integer(count, "count")
        if decrement > self.open_position_count:
            raise ValueError("cannot close more positions than are open")

        self.open_position_count -= decrement

    def set_emergency_stop(self, active: bool = True) -> None:
        """Explicitly activate or clear the emergency-stop state."""

        if not isinstance(active, bool):
            raise TypeError("active must be a boolean")

        self.emergency_stop = active

    def refresh_daily_loss_limit(self, max_daily_loss_fraction: float) -> bool:
        """Update and return the daily-loss-limit flag.

        The limit is evaluated using net daily drawdown rather than gross losing
        trades, so profitable trades within the same session offset losses.
        """

        if not self.initialized:
            raise RuntimeError("risk state must be initialized first")

        limit = self._require_finite(
            max_daily_loss_fraction,
            "max_daily_loss_fraction",
        )
        if limit <= 0 or limit > 1.0:
            raise ValueError(
                "max_daily_loss_fraction must be greater than zero and at most 1.0"
            )

        self.daily_loss_limit_hit = self.daily_drawdown_fraction >= limit
        return self.daily_loss_limit_hit

    def _update_drawdown(self) -> None:
        if self.virtual_balance > self.peak_balance:
            self.peak_balance = self.virtual_balance

        self.current_drawdown = max(
            0.0,
            self.peak_balance - self.virtual_balance,
        )
        self.max_drawdown = max(self.max_drawdown, self.current_drawdown)

    @staticmethod
    def _resolve_timestamp(timestamp: datetime | None) -> datetime:
        resolved = datetime.now(UTC) if timestamp is None else timestamp
        if not isinstance(resolved, datetime):
            raise TypeError("timestamp must be a datetime")
        if resolved.tzinfo is None or resolved.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")

        return resolved.astimezone(UTC)

    @classmethod
    def _require_positive_finite(cls, value: float, name: str) -> float:
        normalized = cls._require_finite(value, name)
        if normalized <= 0:
            raise ValueError(f"{name} must be greater than zero")
        return normalized

    @classmethod
    def _require_non_negative_finite(cls, value: float, name: str) -> float:
        normalized = cls._require_finite(value, name)
        if normalized < 0:
            raise ValueError(f"{name} cannot be negative")
        return normalized

    @staticmethod
    def _require_finite(value: float, name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be a real number")

        normalized = float(value)
        if not math.isfinite(normalized):
            raise ValueError(f"{name} must be finite")

        return normalized

    @classmethod
    def _require_positive_integer(cls, value: int, name: str) -> int:
        normalized = cls._require_non_negative_integer(value, name)
        if normalized == 0:
            raise ValueError(f"{name} must be greater than zero")
        return normalized

    @staticmethod
    def _require_non_negative_integer(value: int, name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{name} must be an integer")
        if value < 0:
            raise ValueError(f"{name} cannot be negative")
        return value
