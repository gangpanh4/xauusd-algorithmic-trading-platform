"""
risk/risk_manager.py
─────────────────────
Enforces all risk management rules before a signal is acted on.

Changes in this version:
  Fix #1     — open_trades sourced live from MT5 via connector, not internal counter
  Fix #3     — daily starting balance captured once on first run per day (real account)
  Feature #5 — MAX_TRADES_PER_DAY: blocks further entries once today's trade count is reached
  Feature #6 — Consecutive-loss kill switch: halts trading after N consecutive losses
               until the next UTC day
  Both #5/#6 reconstruct their counters from MT5 closed-deal history
  (history_deals_get, filtered by MAGIC_NUMBER) on startup/restart, so a
  restart never resets the limits — only a genuine new UTC day does.

Rules enforced:
  • Daily loss limit against real starting balance
  • Max concurrent open trades (from live MT5 query)
  • Max trades per day (Feature #5)
  • Consecutive loss kill-switch (Feature #6)
  • Lot size boundaries
"""

import logging
import os
import json
from datetime import datetime, UTC, date, timezone
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_STATE_FILE = "output/daily_state.json"   # Persists starting balance across restarts


def _utc_today() -> date:
    """
    Timezone fix: returns the current date in UTC, not the local machine's
    date. RiskManager's daily resets, starting-balance anchor, and history
    sync window must all line up with broker/UTC day boundaries (and with
    MT5Connector, which already uses datetime.now(UTC) / utcfromtimestamp()
    — naive-UTC throughout). Using date.today() here would silently shift
    every "daily" boundary by the local UTC offset.
    """
    return datetime.now(timezone.utc).date()


@dataclass
class DailyStats:
    date:          str   = field(default_factory=lambda: _utc_today().isoformat())
    starting_balance: float = 0.0          # Fix #3 — real balance at day start
    trades_taken:  int   = 0
    signals_seen:  int   = 0
    no_trades:     int   = 0
    buys:          int   = 0
    sells:         int   = 0
    # Feature #5 / #6 — derived from MT5 closed-deal history
    closed_trades_today: int = 0           # Feature #5 — counts toward MAX_TRADES_PER_DAY
    consecutive_losses:  int = 0           # Feature #6
    kill_switch_active:  bool = False      # Feature #6 — set once losses hit the limit
    last_synced_deal_time: str = ""        # ISO timestamp of the newest deal already counted


class RiskManager:
    """
    Gate-keeper that validates every signal before execution.

    open_trades is no longer tracked internally.
    It is always queried live from MT5 via connector.get_open_trade_count()
    so it can never drift out of sync with reality (Fix #1).

    closed_trades_today / consecutive_losses (Features #5, #6) are
    reconstructed from MT5's closed-deal history on startup via
    sync_from_history(), so they survive restarts without manual bookkeeping.
    """

    def __init__(self, cfg):
        self.cfg   = cfg
        self.stats = self._load_or_init_daily_stats()

    # ── Fix #3 — Daily State Persistence ─────────────────────

    def _load_or_init_daily_stats(self) -> DailyStats:
        """
        Load today's state from disk if the bot was restarted mid-day.
        This ensures starting_balance is never accidentally reset.
        """
        today = _utc_today().isoformat()
        Path(_STATE_FILE).parent.mkdir(parents=True, exist_ok=True)

        if os.path.exists(_STATE_FILE):
            try:
                with open(_STATE_FILE) as f:
                    saved = json.load(f)
                if saved.get("date") == today:
                    logger.info(
                        f"Loaded daily state for {today}. "
                        f"Starting balance: ${saved['starting_balance']:.2f}"
                    )
                    return DailyStats(**saved)
            except Exception as e:
                logger.warning(f"Could not load daily state: {e}. Starting fresh.")

        # New day (or no file) — return empty stats; balance set on first call
        return DailyStats(date=today)

    def _save_daily_stats(self):
        """Persist stats so restarts within the same day retain starting balance."""
        try:
            with open(_STATE_FILE, "w") as f:
                json.dump(self.stats.__dict__, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save daily state: {e}")

    def _check_day_rollover(self):
        today = _utc_today().isoformat()
        if self.stats.date != today:
            logger.info(f"Day rollover detected. Resetting daily stats for {today}.")
            if self.stats.kill_switch_active:
                logger.info("Consecutive-loss kill switch reset for the new trading day.")
            self.stats = DailyStats(date=today)
            # starting_balance will be set on next is_trade_allowed() call

    # ── Features #5 & #6 — Reconstruct Counters from MT5 History ──

    def sync_from_history(self, connector):
        """
        Feature #5/#6 — Pull today's closed deals for this bot's
        MAGIC_NUMBER from MT5 and rebuild closed_trades_today and
        consecutive_losses from them. Call this once at startup (after
        register_starting_balance) and optionally once per cycle to stay
        current with trades that closed since the last check.

        Only deals from today (UTC) are considered — a genuine new day
        resets everything via _check_day_rollover(), matching the
        existing daily-loss/balance reset behaviour.
        """
        self._check_day_rollover()
        cfg = self.cfg

        # Timezone fix: build the window boundary from the UTC date, not
        # the local machine's date. get_history_deals() / MT5's
        # history_deals_get() compare this against deal timestamps that
        # are naive-UTC (see MT5Connector.get_history_deals, which uses
        # datetime.now(UTC) and datetime.utcfromtimestamp()). A local-date
        # midnight would shift this window by the local UTC offset,
        # causing deals to be missed or double-counted near midnight.
        today_start = datetime.combine(_utc_today(), datetime.min.time())
        deals = connector.get_history_deals(
            magic=cfg.MAGIC_NUMBER,
            from_date=today_start,
        )

        if not deals:
            logger.debug("History sync: no closed deals found for today yet.")
            return

        # Recompute fully from today's deals (idempotent — safe to call repeatedly)
        closed_count = len(deals)
        consecutive  = 0
        for d in deals:  # already sorted oldest → newest by the connector
            if d["profit"] < 0:
                consecutive += 1
            elif d["profit"] > 0:
                consecutive = 0
            # profit == 0 (breakeven) does not reset or extend the streak

        self.stats.closed_trades_today = closed_count
        self.stats.consecutive_losses  = consecutive
        self.stats.last_synced_deal_time = deals[-1]["time"].isoformat()

        if consecutive >= cfg.MAX_CONSECUTIVE_LOSSES:
            if not self.stats.kill_switch_active:
                logger.warning(
                    f"Consecutive-loss kill switch TRIGGERED: {consecutive} losses in a row "
                    f"(limit {cfg.MAX_CONSECUTIVE_LOSSES}). Trading halted until next UTC day."
                )
            self.stats.kill_switch_active = True
        else:
            self.stats.kill_switch_active = False

        logger.info(
            f"History sync: {closed_count} closed trade(s) today, "
            f"{consecutive} consecutive loss(es) "
            f"(kill switch: {'ACTIVE' if self.stats.kill_switch_active else 'off'})."
        )
        self._save_daily_stats()

    # ── Fix #3 — Starting Balance Registration ────────────────

    def register_starting_balance(self, balance: float):
        """
        Called once per day (first cycle) to anchor the starting balance.
        Subsequent calls within the same day are silently ignored so that
        a restart mid-day does not overwrite the morning balance.
        """
        self._check_day_rollover()
        if self.stats.starting_balance <= 0:
            self.stats.starting_balance = balance
            logger.info(f"Daily starting balance set: ${balance:.2f}")
            self._save_daily_stats()

    # ── Validation ────────────────────────────────────────────

    def is_trade_allowed(
        self,
        balance: float,
        open_trade_count: int,          # Fix #1 — passed in from live MT5 query
    ) -> tuple[bool, str]:
        """
        Returns (allowed: bool, reason: str).
        open_trade_count must come from connector.get_open_trade_count(),
        NOT from any internal counter.
        """
        self._check_day_rollover()
        cfg = self.cfg

        # ── Daily loss check (Fix #3) ─────────────────────────
        starting = self.stats.starting_balance
        if starting > 0:
            daily_loss_pct = max(0.0, (starting - balance) / starting * 100)
            if daily_loss_pct >= cfg.MAX_DAILY_LOSS_PCT:
                reason = (
                    f"Daily loss limit reached: {daily_loss_pct:.2f}% "
                    f"≥ max {cfg.MAX_DAILY_LOSS_PCT}% "
                    f"(started at ${starting:.2f}, now ${balance:.2f}). "
                    f"Trading halted for today."
                )
                logger.warning(reason)
                return False, reason
        else:
            logger.warning("Starting balance not registered yet — skipping daily loss check.")

        # ── Max open trades (Fix #1) ──────────────────────────
        if open_trade_count >= cfg.MAX_OPEN_TRADES:
            reason = (
                f"Max open trades reached: {open_trade_count} live position(s) "
                f"/ limit {cfg.MAX_OPEN_TRADES}."
            )
            logger.info(reason)
            return False, reason

        # ── Feature #5: Daily trade limit ─────────────────────
        # Concurrency/correctness fix: closed_trades_today (from MT5 history)
        # and trades_taken (incremented when the bot sends an order) both
        # end up counting the SAME trade once it closes. Use max() instead
        # of summing them so a single trade is never counted twice.
        trades_today = max(self.stats.closed_trades_today, self.stats.trades_taken)
        if trades_today >= cfg.MAX_TRADES_PER_DAY:
            reason = (
                f"Daily trade limit reached: "
                f"{trades_today} "
                f"/ limit {cfg.MAX_TRADES_PER_DAY} trades today. No further entries."
            )
            logger.info(reason)
            return False, reason

        # ── Feature #6: Consecutive-loss kill switch ──────────
        if self.stats.kill_switch_active or self.stats.consecutive_losses >= cfg.MAX_CONSECUTIVE_LOSSES:
            reason = (
                f"Consecutive-loss kill switch active: {self.stats.consecutive_losses} "
                f"losses in a row (limit {cfg.MAX_CONSECUTIVE_LOSSES}). "
                "Trading halted until the next UTC day."
            )
            logger.info(reason)
            return False, reason

        return True, "OK"

    def validate_lot(self, lot: float) -> float:
        """Clamp lot size to configured bounds."""
        return round(max(self.cfg.LOT_SIZE_MIN, min(lot, self.cfg.LOT_SIZE_MAX)), 2)

    # ── Tracking (stats only, no trade-count logic) ───────────

    def record_signal(self, signal_type: str):
        self._check_day_rollover()
        self.stats.signals_seen += 1
        if signal_type == "BUY":
            self.stats.buys += 1
        elif signal_type == "SELL":
            self.stats.sells += 1
        else:
            self.stats.no_trades += 1
        self._save_daily_stats()

    def on_trade_opened(self):
        """Record that a trade was sent (stats only — live count comes from MT5)."""
        self.stats.trades_taken += 1
        self._save_daily_stats()
        logger.info(f"Trade recorded. Total trades today: {self.stats.trades_taken}")

    # ── Reporting ─────────────────────────────────────────────

    def get_daily_loss_pct(self, balance: float) -> float:
        starting = self.stats.starting_balance
        if starting <= 0:
            return 0.0
        return round(max(0.0, (starting - balance) / starting * 100), 3)

    def get_stats(self, balance: float = 0, open_trades: int = 0) -> dict:
        self._check_day_rollover()
        return {
            "date":              self.stats.date,
            "starting_balance":  round(self.stats.starting_balance, 2),
            "current_balance":   round(balance, 2),
            "daily_loss_pct":    self.get_daily_loss_pct(balance),
            "signals_seen":      self.stats.signals_seen,
            "trades_taken":      self.stats.trades_taken,
            "buys":              self.stats.buys,
            "sells":             self.stats.sells,
            "no_trades":         self.stats.no_trades,
            "open_trades_live":  open_trades,    # always from MT5
            "closed_trades_today": self.stats.closed_trades_today,    # Feature #5
            "consecutive_losses":  self.stats.consecutive_losses,     # Feature #6
            "kill_switch_active":  self.stats.kill_switch_active,     # Feature #6
        }

    def summary(self, balance: float = 0, open_trades: int = 0) -> str:
        s = self.get_stats(balance, open_trades)
        loss_pct = s["daily_loss_pct"]
        loss_str = f"{loss_pct:.2f}%" if loss_pct else "—"
        kill_str = "🛑 ACTIVE" if s["kill_switch_active"] else "off"
        return (
            f"\n── Risk Stats ({s['date']}) ──\n"
            f"  Starting balance : ${s['starting_balance']:,.2f}\n"
            f"  Current balance  : ${s['current_balance']:,.2f}  "
            f"(daily loss: {loss_str})\n"
            f"  Signals seen     : {s['signals_seen']}\n"
            f"  Trades taken     : {s['trades_taken']}  "
            f"(BUY: {s['buys']} | SELL: {s['sells']} | NO TRADE: {s['no_trades']})\n"
            f"  Open trades (MT5): {s['open_trades_live']} / {self.cfg.MAX_OPEN_TRADES}\n"
            f"  Closed today     : {s['closed_trades_today']} / {self.cfg.MAX_TRADES_PER_DAY} "
            f"(daily trade limit)\n"
            f"  Consecutive loss : {s['consecutive_losses']} / {self.cfg.MAX_CONSECUTIVE_LOSSES} "
            f"(kill switch: {kill_str})\n"
        )
