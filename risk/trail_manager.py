"""
risk/trail_manager.py
──────────────────────
Feature #1 — ATR-based trailing stop.

Runs independently from the H1 signal cycle (see main.py's fast loop) so that
profit protection reacts within seconds, not once per 60s/H1 cycle.

Rules:
  • 1R is defined as the ORIGINAL risk distance: |entry_price - original_sl|,
    captured at the moment the position is opened.
  • Once price reaches +1R profit → move SL to breakeven (entry price).
  • Once price reaches +2R profit → trail SL using ATR × TRAIL_ATR_MULTI.
  • SL only ever moves in the direction of profit. Never widened, never reduced
    in the sense of giving back protection (BUY: SL only moves up;
    SELL: SL only moves down).
  • Modifications smaller than TRAIL_MIN_STEP_ATR × ATR are skipped, to avoid
    spamming MT5 with negligible SL changes.
  • Only touches positions matching cfg.MAGIC_NUMBER. Never opens or closes
    positions — SL modification only.

Since MT5 does not return the ORIGINAL stop loss once it has already been
moved, the original 1R distance is captured the first time each position
ticket is seen and cached in memory (and persisted to disk so it survives
bot restarts).
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_TRAIL_STATE_FILE = "output/trail_state.json"


class TrailManager:
    """
    Tracks each open position's original risk (1R) and steps its stop loss
    through breakeven and ATR-trailing phases as profit grows.
    """

    def __init__(self, cfg, connector):
        self.cfg       = cfg
        self.connector = connector
        # ticket -> {"entry": float, "original_sl": float, "r_distance": float,
        #            "direction": "BUY"/"SELL", "phase": "initial"/"breakeven"/"trailing"}
        self._state: dict[int, dict] = self._load_state()

    # ── State persistence ─────────────────────────────────────

    def _load_state(self) -> dict:
        if os.path.exists(_TRAIL_STATE_FILE):
            try:
                with open(_TRAIL_STATE_FILE) as f:
                    raw = json.load(f)
                # JSON keys are strings — convert back to int tickets
                return {int(k): v for k, v in raw.items()}
            except Exception as e:
                logger.warning(f"Could not load trail state: {e}. Starting fresh.")
        return {}

    def _save_state(self):
        try:
            Path(_TRAIL_STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
            with open(_TRAIL_STATE_FILE, "w") as f:
                json.dump(self._state, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save trail state: {e}")

    def forget(self, ticket: int):
        """Drop state for a ticket once its position is closed."""
        if ticket in self._state:
            del self._state[ticket]
            self._save_state()

    def _notify_closed(self, ticket: int):
        """
        Feature #7 — Look up the closing deal for a ticket that just
        disappeared from open positions, and send a Telegram update
        reporting profit or loss.
        """
        cfg = self.cfg
        if not getattr(cfg, "TELEGRAM_ENABLED", False):
            return

        state = self._state.get(ticket)
        if state is None:
            return

        try:
            from datetime import datetime, timedelta, UTC
            from utils.telegram_alert import send_trade_closed_alert

            # Closing deals share the position's ticket as position_id
            deals = self.connector.get_history_deals(
                magic=cfg.MAGIC_NUMBER,
                from_date=datetime.now(UTC) - timedelta(days=1),
            )
            match = next((d for d in deals if d.get("position_id") == ticket), None)
            if match is None:
                logger.debug(f"No closing deal found yet for ticket={ticket}; skipping alert.")
                return

            send_trade_closed_alert(
                cfg,
                ticket    = ticket,
                direction = state["direction"],
                symbol    = match["symbol"],
                profit    = match["profit"],
            )
        except Exception as e:
            logger.debug(f"Trade-closed Telegram alert skipped for ticket={ticket}: {e}")

    # ── Registration ──────────────────────────────────────────

    def register_new_position(self, ticket: int, entry: float,
                               original_sl: float, direction: str):
        """
        Call this right after a position is opened, while the true original
        SL is still known, so 1R is captured accurately.
        """
        r_distance = abs(entry - original_sl)
        self._state[ticket] = {
            "entry":       entry,
            "original_sl": original_sl,
            "r_distance":  r_distance,
            "direction":   direction,
            "phase":       "initial",
        }
        self._save_state()
        logger.info(
            f"TrailManager: registered ticket={ticket} {direction} "
            f"entry={entry:.2f} SL={original_sl:.2f} (1R={r_distance:.2f})"
        )

    def _ensure_tracked(self, position: dict):
        """
        If a position isn't in our state (e.g. bot restarted after the
        position was opened, or PositionManager reconstructed it), seed its
        1R from the position's CURRENT sl. This is the best information
        available — if SL was already trailed before a restart, 1R will be
        approximated from whatever SL is in place at sync time.
        """
        ticket = position["ticket"]
        if ticket in self._state:
            return
        self._state[ticket] = {
            "entry":       position["open_price"],
            "original_sl": position["sl"],
            "r_distance":  abs(position["open_price"] - position["sl"]) or 0.01,
            "direction":   position["type"],
            "phase":       "initial",
        }
        self._save_state()
        logger.info(
            f"TrailManager: adopted untracked ticket={ticket} "
            f"({position['type']}) — 1R approximated from current SL."
        )

    # ── Main tick ─────────────────────────────────────────────

    def update_all(self, current_price: Optional[float] = None,
                   atr: Optional[float] = None):
        """
        Call this on every fast-loop tick (e.g. every TRAIL_CHECK_SECONDS).
        Pulls live MT5 positions for MAGIC_NUMBER and steps each one's SL.

        current_price / atr: optional overrides, mainly for testing. If not
        given, current_price comes from each position's own bid/ask via the
        connector's latest tick, and ATR is fetched fresh.
        """
        cfg = self.cfg
        if not cfg.TRAILING_STOP_ENABLED:
            logger.debug("TrailManager: TRAILING_STOP_ENABLED is False — skipping tick.")
            return

        logger.debug(
            f"TrailManager tick: connected={getattr(self.connector, 'connected', '?')} "
            f"symbol={cfg.SYMBOL} magic={cfg.MAGIC_NUMBER}"
        )

        positions = self.connector.get_open_positions(symbol=cfg.SYMBOL, magic=cfg.MAGIC_NUMBER)
        live_tickets = {p["ticket"] for p in positions}

        # Drop state for tickets that no longer exist (closed/hit SL/TP),
        # and fire a Telegram "closed" alert with the realized outcome.
        for ticket in list(self._state.keys()):
            if ticket not in live_tickets:
                self._notify_closed(ticket)
                self.forget(ticket)

        if not positions:
            logger.debug(
                f"TrailManager: no open positions for symbol={cfg.SYMBOL} "
                f"magic={cfg.MAGIC_NUMBER} — nothing to trail this tick."
            )
            return

        atr_value = atr if atr is not None else self.connector.get_latest_atr(cfg)
        if atr_value is None:
            logger.debug(
                "TrailManager: ATR unavailable this tick — breakeven phase still "
                "active, ATR-trailing phase will be skipped."
            )

        for position in positions:
            self._ensure_tracked(position)
            self._update_one(position, atr_value, current_price)

    def _update_one(self, position: dict, atr: Optional[float],
                     current_price: Optional[float]):
        cfg    = self.cfg
        ticket = position["ticket"]
        state  = self._state[ticket]

        direction   = state["direction"]
        entry       = state["entry"]
        r_distance  = state["r_distance"]
        current_sl  = position["sl"]

        if r_distance <= 0:
            logger.warning(
                f"TrailManager: ticket={ticket} has invalid r_distance={r_distance} — "
                f"skipping (can't compute R-multiples)."
            )
            return  # can't compute R-multiples without a valid risk distance

        price = current_price if current_price is not None else self.connector.get_current_price(
            cfg.SYMBOL, direction
        )
        if price is None:
            logger.warning(
                f"TrailManager: ticket={ticket} — get_current_price() returned None, "
                f"skipping this tick."
            )
            return

        # Profit in price terms, then expressed in R multiples
        profit_dist = (price - entry) if direction == "BUY" else (entry - price)
        r_multiple  = profit_dist / r_distance

        logger.debug(
            f"TrailManager: ticket={ticket} {direction} price={price:.2f} entry={entry:.2f} "
            f"r_distance={r_distance:.2f} r_multiple={r_multiple:.3f} "
            f"phase={state['phase']} current_sl={current_sl:.2f} atr={atr}"
        )

        new_sl = current_sl

        # ── Phase 1: Breakeven at +1R ──────────────────────────
        # Concurrency/correctness fix: compute the WOULD-BE new phase into a
        # local variable only. Do NOT write it into `state["phase"]` here —
        # if modify_sl() below fails, the in-memory phase must stay exactly
        # as it was, or the breakeven Telegram alert (gated on "was this
        # transition new") would be silently skipped forever on a later
        # successful retry.
        was_initial = state["phase"] == "initial"
        new_phase   = state["phase"]
        if r_multiple >= cfg.TRAIL_BREAKEVEN_R:
            breakeven_sl = entry
            if direction == "BUY" and breakeven_sl > current_sl:
                new_sl = breakeven_sl
            elif direction == "SELL" and breakeven_sl < current_sl:
                new_sl = breakeven_sl
            if was_initial:
                new_phase = "breakeven"

        # ── Phase 2: ATR trail at +2R ───────────────────────────
        if r_multiple >= cfg.TRAIL_ACTIVATE_R and atr:
            trail_distance = atr * cfg.TRAIL_ATR_MULTI
            if direction == "BUY":
                candidate = price - trail_distance
                if candidate > new_sl:
                    new_sl = candidate
            else:
                candidate = price + trail_distance
                if candidate < new_sl:
                    new_sl = candidate
            new_phase = "trailing"

        # ── Never widen / reduce protection ─────────────────────
        if direction == "BUY" and new_sl <= current_sl:
            logger.debug(
                f"TrailManager: ticket={ticket} BUY — candidate SL {new_sl:.2f} not "
                f"above current {current_sl:.2f}, nothing to do."
            )
            return
        if direction == "SELL" and new_sl >= current_sl:
            logger.debug(
                f"TrailManager: ticket={ticket} SELL — candidate SL {new_sl:.2f} not "
                f"below current {current_sl:.2f}, nothing to do."
            )
            return

        # ── Skip negligible modifications ───────────────────────
        if atr:
            min_step = cfg.TRAIL_MIN_STEP_ATR * atr
            if abs(new_sl - current_sl) < min_step:
                logger.debug(
                    f"TrailManager: ticket={ticket} — move {abs(new_sl - current_sl):.4f} "
                    f"smaller than min_step={min_step:.4f}, skipping."
                )
                return

        result = self.connector.modify_sl(
            ticket  = ticket,
            symbol  = position["symbol"],
            new_sl  = round(new_sl, 2),
            tp      = position["tp"],
        )
        if result.get("retcode") == 0 or result.get("simulated"):
            # Only now — after MT5 confirmed the SL change — commit the
            # phase transition to state and persist it.
            became_breakeven = was_initial and new_phase == "breakeven"
            state["phase"] = new_phase
            logger.info(
                f"Trail: ticket={ticket} {direction} phase={state['phase']} "
                f"R={r_multiple:.2f} SL {current_sl:.2f} → {new_sl:.2f}"
            )
            self._save_state()

            # Feature #7 — Telegram update on the breakeven milestone only
            # (fires once per position, exactly when SL first reaches entry,
            # and only once the SL modify has actually been confirmed)
            if became_breakeven:
                try:
                    from utils.telegram_alert import send_breakeven_alert
                    send_breakeven_alert(
                        cfg, ticket, direction, position["symbol"], entry,
                    )
                except Exception as e:
                    logger.debug(f"Breakeven Telegram alert skipped: {e}")
        else:
            # modify_sl failed — state["phase"] is untouched, so the next
            # successful retry will still correctly detect this as the
            # first breakeven transition and fire the alert then.
            logger.warning(f"Trail: SL modify failed for ticket={ticket}: {result}")
