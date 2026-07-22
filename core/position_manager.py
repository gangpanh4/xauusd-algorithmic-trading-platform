"""
core/position_manager.py
──────────────────────────
Feature #4 — Position Synchronization.

On startup, scans MT5 for open positions carrying this bot's MAGIC_NUMBER
and reconstructs internal bot state from them, so a restart never "loses
track" of trades it already has open (or that were opened in a previous
session before a crash/restart).

Specifically, on sync this:
  • Registers each open position with the TrailManager (Feature #1) so
    trailing-stop tracking resumes correctly.
  • Returns a summary the caller can log / alert on.

It does NOT touch RiskManager's daily counters directly — those are
reconstructed from MT5's closed-deal history instead (see RiskManager's
sync_from_history()), since open positions don't tell you about trades
that already closed today.
"""

import logging

logger = logging.getLogger(__name__)


class PositionManager:
    """
    Reconstructs bot state from live MT5 positions tagged with
    cfg.MAGIC_NUMBER. Call sync() once at startup, before the main loop.
    """

    def __init__(self, cfg, connector, trail_manager=None):
        self.cfg            = cfg
        self.connector       = connector
        self.trail_manager   = trail_manager

    def sync(self) -> dict:
        """
        Scan MT5 for this bot's open positions and reconstruct state.
        Returns a summary dict: {count, positions, buys, sells}.
        Safe to call even if MT5 isn't connected (returns an empty summary).
        """
        cfg = self.cfg
        if not getattr(cfg, "POSITION_SYNC_ON_STARTUP", True):
            logger.info("Position sync disabled (POSITION_SYNC_ON_STARTUP=False).")
            return {"count": 0, "positions": [], "buys": 0, "sells": 0}

        positions = self.connector.get_open_positions(symbol=cfg.SYMBOL, magic=cfg.MAGIC_NUMBER)

        if not positions:
            logger.info(
                f"Position sync: no open positions found for magic={cfg.MAGIC_NUMBER}. "
                "Starting with a clean slate."
            )
            return {"count": 0, "positions": [], "buys": 0, "sells": 0}

        buys  = sum(1 for p in positions if p["type"] == "BUY")
        sells = sum(1 for p in positions if p["type"] == "SELL")

        logger.info(
            f"Position sync: found {len(positions)} open position(s) for "
            f"magic={cfg.MAGIC_NUMBER} (BUY: {buys} | SELL: {sells}). Reconstructing state..."
        )

        for p in positions:
            logger.info(
                f"  • ticket={p['ticket']} {p['type']} {p['volume']} lots "
                f"@ {p['open_price']:.2f} | SL={p['sl']:.2f} TP={p['tp']:.2f} "
                f"| P&L=${p['profit']:.2f}"
            )
            # Hand each position to the trail manager so trailing-stop
            # tracking resumes (1R will be approximated from current SL
            # if this position predates the current bot session).
            if self.trail_manager is not None:
                self.trail_manager._ensure_tracked(p)

        return {
            "count":     len(positions),
            "positions": positions,
            "buys":      buys,
            "sells":     sells,
        }
