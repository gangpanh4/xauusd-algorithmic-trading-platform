"""
main.py — XAUUSD AI Trading Signal Generator
═════════════════════════════════════════════
Orchestrates the full signal pipeline:

  MT5 (H4 + H1 + M15) → Indicators → HTF Bias → Time Filter → News Filter →
  Candle-Close Guard → MTF Trigger → Signal Engine → Risk Check →
  Duplicate Guard → Output / Alert

All fixes applied in this version:
  Fix #1 — Open trades always queried live from MT5 (never internal counters)
  Fix #2 — Duplicate position guard before any order is sent
  Fix #3 — Daily starting balance anchored at first run, persisted across restarts
  Fix #4 — Rebalanced confidence weights (trend 40%, MACD 25%, RSI 20%, BB 10%, vol 5%)
  Fix #5 — H4 EMA 200 used as mandatory higher-timeframe filter
  Fix #6 — Dynamic TP targeting swing highs/lows (ATR floor maintained)

New features in this version:
  Feature #1 — ATR trailing stop (breakeven at +1R, ATR×1.5 trail from +2R),
               run continuously by a fast loop independent of the H1 cycle
  Feature #2 — Trading session / time filter (07:00–21:00 UTC, configurable)
  Feature #3 — Candle-close-only signals (no duplicate signals within one H1 candle)
  Feature #4 — Position synchronization on startup (PositionManager)
  Feature #5 — Daily trade limit (MAX_TRADES_PER_DAY)
  Feature #6 — Consecutive-loss kill switch (halts until next UTC day)
  Feature #7 — Richer Telegram messages + lifecycle updates (breakeven / closed)
  Feature #8 — Multi-timeframe entry: H4 trend → H1 setup → M15 MACD trigger

Usage:
  python main.py            # Single signal check
  python main.py --loop     # Poll every 60 seconds (default)
  python main.py --demo     # Simulated data, no MT5 required
  python main.py --stats    # Print saved signal history
"""

from asyncio.log import logger
import signal
import sys
import time
import argparse
import logging
import threading
from datetime import datetime, UTC

# Windows UTF-8 console fix
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import config as cfg
from core.mt5_connector     import MT5Connector
from core.indicators        import (add_all_indicators, add_htf_ema200,
                                    get_htf_bias, get_latest_snapshot,
                                    get_mtf_trigger)
from core.position_manager  import PositionManager
from signals.signal_engine  import SignalEngine
from news.news_filter       import NewsFilter
from risk.risk_manager      import RiskManager
from risk.trail_manager     import TrailManager
from utils.logger           import setup_logging, save_signal, signals_summary
from utils.telegram_alert   import send_signal_alert
from utils.candle_guard     import CandleCloseGuard


# ─────────────────────────────────────────────────────────────
def run_once(
    connector:     MT5Connector,
    engine:        SignalEngine,
    news:          NewsFilter,
    risk:          RiskManager,
    candle_guard:  CandleCloseGuard,
    trail_mgr:     TrailManager,
    execute_trades: bool = False,
) -> None:
    """Execute one complete signal generation cycle."""
    logger = logging.getLogger("xauusd_bot")
    now    = datetime.now(UTC)
    logger.info(f"-- Cycle: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC --")

    # ── 1. Fetch H1 Candles ───────────────────────────────────
    tf_h1    = cfg.TIMEFRAMES.get(cfg.TIMEFRAME, 16385)
    df_h1    = connector.get_candles(cfg.SYMBOL, tf_h1, cfg.CANDLES_REQUIRED)

    if df_h1 is None or len(df_h1) < cfg.EMA_SLOW + 10:
        logger.error("Insufficient H1 candle data. Skipping cycle.")
        return

    # ── Feature #3: Candle-Close-Only Guard ───────────────────
    # The most recent CLOSED H1 candle is df_h1.index[-2] in MT5's
    # copy_rates_from_pos convention (index -1 is the live, still-forming
    # candle). Only proceed if that closed candle is new since last check.
    if cfg.CANDLE_CLOSE_ONLY:
        last_closed_time = df_h1.index[-2] if len(df_h1) >= 2 else df_h1.index[-1]
        if not candle_guard.is_new_candle(last_closed_time):
            logger.debug(
                f"Candle-close guard: no new H1 candle since {last_closed_time}. Skipping cycle."
            )
            return

    # ── 2. Compute H1 Indicators ─────────────────────────────
    df_h1    = add_all_indicators(df_h1, cfg)
    snapshot = get_latest_snapshot(df_h1, cfg)

    # ── 3. Fix #5 — Fetch H4 and compute HTF EMA 200 ─────────
    htf_bias = None
    if cfg.HTF_FILTER_ENABLED:
        tf_h4 = cfg.TIMEFRAMES.get(cfg.HTF, 16388)
        df_h4 = connector.get_candles(cfg.SYMBOL, tf_h4, cfg.HTF_CANDLES)
        if df_h4 is not None and len(df_h4) >= 200:
            df_h4    = add_htf_ema200(df_h4, period=cfg.EMA_SLOW)
            htf_bias = get_htf_bias(df_h4)
            logger.info(
                f"HTF ({cfg.HTF}) bias: "
                f"close={htf_bias.get('htf_close')}, "
                f"EMA200={htf_bias.get('htf_ema200')}, "
                f"bullish={htf_bias.get('htf_bullish')}"
            )
        else:
            logger.warning("Could not fetch H4 data — HTF filter will be skipped this cycle.")

    # ── 4. News Filter ────────────────────────────────────────
    news_blocked, upcoming = news.is_news_blocked()
    if news_blocked:
        for e in upcoming:
            logger.warning(f"  NEWS BLOCK: {e['title']} in {e['minutes_away']:.0f} min")

    # ── Feature #8: Fetch M15 and compute MACD trigger ────────
    mtf_trigger = None
    if cfg.MTF_ENTRY_ENABLED:
        tf_m15 = cfg.TIMEFRAMES.get(cfg.MTF_TRIGGER_TF, 15)
        df_m15 = connector.get_candles(cfg.SYMBOL, tf_m15, cfg.MTF_CANDLES)
        if df_m15 is not None and len(df_m15) >= 30:
            mtf_trigger = get_mtf_trigger(df_m15)
            logger.info(
                f"M15 trigger: cross_up={mtf_trigger.get('macd_cross_up')}, "
                f"cross_dn={mtf_trigger.get('macd_cross_dn')}, "
                f"hist={mtf_trigger.get('macd_hist')}"
            )
        else:
            logger.warning("Could not fetch M15 data — MTF trigger will be skipped this cycle.")

    # ── 5. Account Info + Fix #3 Register Starting Balance ────
    account = connector.get_account_info()
    balance = account["balance"]
    risk.register_starting_balance(balance)   # No-op after first call each day

    # ── Features #5 & #6: Sync daily trade count / consecutive losses
    #     from MT5 closed-deal history before evaluating risk gates ──
    risk.sync_from_history(connector)

    # ── 6. Fix #1 — Query live open position count from MT5 ───
    live_open_count = connector.get_open_trade_count(
        symbol=cfg.SYMBOL, magic=cfg.MAGIC_NUMBER
    )
    logger.info(f"Live open positions on {cfg.SYMBOL}: {live_open_count}")

    # ── 7. Generate Signal ────────────────────────────────────
    signal = engine.generate(
        snapshot        = snapshot,
        account_balance = balance,
        df              = df_h1,       # passed for dynamic TP swing detection
        news_blocked    = news_blocked,
        htf_bias        = htf_bias,
        mtf_trigger     = mtf_trigger,
    )


    logger.warning(
    f"ENGINE OUTPUT => {signal.signal} | "
    f"Conf={signal.confidence:.1%}"
    )
    # ── 8. Risk Gate (Fix #1 — uses live count, Fix #3 — real balance) ──
    if signal.signal in ("BUY", "SELL"):
        allowed, reason = risk.is_trade_allowed(
            balance          = balance,
            open_trade_count = live_open_count,   # Fix #1
        )
        if not allowed:
            signal.signal = "NO TRADE"
            signal.warnings.append(f"Risk gate: {reason}")

    # ── C4 fix: record the FINAL signal (post risk-gate mutation), not
    #     the pre-gate value, so risk bookkeeping reflects what actually
    #     happened this cycle ────────────────────────────────────────
    risk.record_signal(signal.signal)

    # ── C2 fix: mark this H1 candle as processed only after the signal
    #     has been fully generated and gated, so a candle is never
    #     marked "done" until the cycle's decision is final ───────────
    if cfg.CANDLE_CLOSE_ONLY:
        candle_guard.mark_processed(last_closed_time)

    # ── 9. Print Signal ───────────────────────────────────────
    print(signal.summary())

    # ── 10. Persist & Alert ───────────────────────────────────
    save_signal(signal, cfg.SIGNAL_LOG)
    send_signal_alert(signal, cfg)

    # ── 11. Execute Trade ─────────────────────────────────────
    # execute_trades is True when LIVE_TRADING=True (real orders) or when
    # running with --demo (simulated orders). connector.connected is NOT
    # checked here — demo mode intentionally runs disconnected.
    if signal.signal in ("BUY", "SELL") and execute_trades:

        live_open_count = connector.get_open_trade_count(
            symbol=cfg.SYMBOL,
            magic=cfg.MAGIC_NUMBER
        )
        
        # Re-validate risk with authoritative live count
        allowed, reason = risk.is_trade_allowed(
            balance          = balance,
            open_trade_count = live_open_count,
        )
        if not allowed:
            logger.warning(f"Live trade blocked by risk manager: {reason}")

        # Fix #2 — Duplicate position guard
        elif connector.has_open_position(cfg.SYMBOL, signal.signal, cfg.MAGIC_NUMBER):
            logger.warning(
                f"Duplicate guard: {signal.signal} position already exists on "
                f"{cfg.SYMBOL}. Skipping order."
            )

        else:
            result = connector.place_order(
                symbol  = cfg.SYMBOL,
                action  = signal.signal,
                lot     = signal.lot_size,
                sl      = signal.stop_loss,
                tp      = signal.take_profit,
                magic   = cfg.MAGIC_NUMBER,
                comment = (
                    f"Bot|{signal.signal}|conf={signal.confidence:.0%}"
                    f"|tp={signal.tp_method}"
                ),
            )
            if result.get("retcode") == 10009 or result.get("simulated"):
                risk.on_trade_opened()
                logger.info(f"Trade opened successfully: {result}")
                # Feature #1 — register with TrailManager using the TRUE
                # entry/SL just sent, so 1R is exact (not approximated later)
                ticket = result.get("order") or result.get("deal")
                if ticket:
                    trail_mgr.register_new_position(
                        ticket=ticket,
                        entry=result.get("price") or signal.entry,
                        original_sl = signal.stop_loss,
                        direction   = signal.signal,
                    )
            else:
                logger.error(f"Order send failed: {result}")

    # ── 12. Summary ───────────────────────────────────────────
    logger.info(
        f"Signal: {signal.signal} | Conf: {signal.confidence:.1%} | "
        f"HTF: {'OK' if signal.htf_aligned else 'FAIL' if signal.htf_aligned is False else '-'} | "
        f"TP: {signal.tp_method}"
    )
    print(risk.summary(balance=balance, open_trades=live_open_count))


# ─────────────────────────────────────────────────────────────
def _trail_loop(trail_mgr: TrailManager, interval: int, stop_event: threading.Event):
    """
    Feature #1 — Fast loop running independently of the H1 signal cycle.
    Checks all open bot positions every `interval` seconds and steps their
    stop loss through the breakeven / ATR-trail phases. Never opens or
    closes positions — SL modification only.
    """
    logger = logging.getLogger("xauusd_bot.trail")
    logger.info(f"Trail manager loop started (every {interval}s).")
    while not stop_event.is_set():
        try:
            trail_mgr.update_all()
        except Exception as e:
            logger.error(f"Trail loop error: {e}")
        stop_event.wait(interval)
    logger.info("Trail manager loop stopped.")


def main():
    parser = argparse.ArgumentParser(description="XAUUSD AI Signal Generator")
    parser.add_argument("--loop",     action="store_true",
                        help="Run continuously (default interval 60s)")
    parser.add_argument("--demo",     action="store_true",
                        help="Use simulated data — no MT5 required")
    parser.add_argument("--stats",    action="store_true",
                        help="Print saved signal history and exit")
    parser.add_argument("--interval", type=int, default=60,
                        help="Loop interval in seconds (default: 60)")
    args = parser.parse_args()

    logger = setup_logging(cfg.LOG_FILE, cfg.LOG_LEVEL)
    logger.info("=" * 62)
    logger.info("  XAUUSD AI Signal Generator — v3 (all fixes + new features)")
    logger.info(
        f"  Weights → TREND:{cfg.WEIGHT_TREND:.0%}  MACD:{cfg.WEIGHT_MACD:.0%}  "
        f"RSI:{cfg.WEIGHT_RSI:.0%}  BB:{cfg.WEIGHT_BB:.0%}  VOL:{cfg.WEIGHT_VOLUME:.0%}"
    )
    logger.info(f"  HTF filter: {cfg.HTF} EMA 200 ({'ON' if cfg.HTF_FILTER_ENABLED else 'OFF'})")
    logger.info(f"  Dynamic TP: swing high/low (floor: {cfg.ATR_TP_MULTI}×ATR)")
    logger.info(
        f"  MTF entry: H4 trend → H1 setup → {cfg.MTF_TRIGGER_TF} MACD trigger "
        f"({'ON' if cfg.MTF_ENTRY_ENABLED else 'OFF'})"
    )
    logger.info(
        f"  Time filter: {cfg.TRADING_START_HOUR_UTC:02d}:00–{cfg.TRADING_END_HOUR_UTC:02d}:00 UTC "
        f"({'ON' if cfg.TIME_FILTER_ENABLED else 'OFF'})"
    )
    logger.info(
        f"  Trailing stop: breakeven @ +{cfg.TRAIL_BREAKEVEN_R}R, "
        f"ATR×{cfg.TRAIL_ATR_MULTI} trail @ +{cfg.TRAIL_ACTIVATE_R}R "
        f"({'ON' if cfg.TRAILING_STOP_ENABLED else 'OFF'})"
    )
    logger.info(
        f"  Daily trade limit: {cfg.MAX_TRADES_PER_DAY}  |  "
        f"Consecutive-loss kill switch: {cfg.MAX_CONSECUTIVE_LOSSES}"
    )
    logger.info("═" * 62)

    if args.stats:
        print(signals_summary(cfg.SIGNAL_LOG))
        return

    # ── Initialise components ─────────────────────────────────
    connector    = MT5Connector(cfg.MT5_LOGIN, cfg.MT5_PASSWORD, cfg.MT5_SERVER)
    engine       = SignalEngine(cfg)
    news         = NewsFilter(cfg)
    risk         = RiskManager(cfg)
    trail_mgr    = TrailManager(cfg, connector)
    candle_guard = CandleCloseGuard(cfg.LAST_CANDLE_STATE_FILE)
    position_mgr = PositionManager(cfg, connector, trail_manager=trail_mgr)

    if not args.demo:
        connected = connector.connect()
        if not connected:
            logger.info("MT5 not connected — running in simulated data mode.")
    else:
        logger.info("Demo mode: using synthetic XAUUSD data. "
                    "HTF filter will use same simulated feed.")

    # ── Feature #4: Position Synchronization on startup ───────
    sync_summary = position_mgr.sync()
    if sync_summary["count"] > 0:
        print(
            f"Position sync: {sync_summary['count']} open position(s) reconstructed "
            f"(BUY: {sync_summary['buys']} | SELL: {sync_summary['sells']})."
        )

    # ── Features #5 & #6: Rebuild today's trade/loss counters
    #     from MT5 closed-deal history before the first cycle ──
    if connector.connected:
        risk.sync_from_history(connector)

    print(news.upcoming_events_str())

    # ── Feature #1: Start the fast trailing-stop loop ─────────
    stop_event  = threading.Event()
    trail_thread = None
    if cfg.TRAILING_STOP_ENABLED:
        trail_thread = threading.Thread(
            target=_trail_loop,
            args=(trail_mgr, cfg.TRAIL_CHECK_SECONDS, stop_event),
            daemon=True,
        )
        trail_thread.start()

    # execute_trades drives the order execution gate in run_once().
    # True for real live orders (LIVE_TRADING) or simulated demo orders (--demo).
    # Keeping these two concerns separate means LIVE_TRADING=False in config
    # still allows the full simulated order path to be exercised with --demo.
    execute_trades = cfg.LIVE_TRADING or args.demo

    # ── Run ───────────────────────────────────────────────────
    try:
        if args.loop:
            logger.info(f"Loop mode: every {args.interval}s. Ctrl+C to stop.")
            while True:
                run_once(connector, engine, news, risk, candle_guard, trail_mgr,
                         execute_trades=execute_trades)
                logger.info(f"Sleeping {args.interval}s...")
                time.sleep(args.interval)
        else:
            run_once(connector, engine, news, risk, candle_guard, trail_mgr,
                     execute_trades=execute_trades)
    except KeyboardInterrupt:
        logger.info("Signal bot stopped by user.")
    finally:
        stop_event.set()
        if trail_thread is not None:
            trail_thread.join(timeout=5)
        connector.disconnect()
        logger.info("Done.")


if __name__ == "__main__":
    main()
