"""
core/mt5_connector.py
─────────────────────
Handles all MetaTrader 5 communication:
  • Connect / disconnect
  • Fetch OHLCV candle data (primary + HTF + MTF trigger)
  • Fetch account info
  • Query live open positions (Fix #1)
  • Duplicate position check (Fix #2)
  • Preserve simulated SL changes for legacy offline workflows
  • Fetch closed deal history by magic number (Features #4, #6)
  • Fail closed for all connected legacy broker mutations
"""

import logging
import threading
from datetime import datetime, UTC
from typing import Optional
from unittest import result
import pandas as pd
from requests import request

logger = logging.getLogger(__name__)

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    logger.warning("MetaTrader5 package not installed. Running in DEMO/backtest mode.")


class LegacyBrokerMutationQuarantinedError(RuntimeError):
    """Raised when quarantined legacy code attempts a broker mutation."""


class MT5Connector:
    """
    Wraps MetaTrader 5 operations.
    Falls back to demo/simulated data if MT5 is not installed.
    """

    def __init__(self, login: int, password: str, server: str):
        self.login     = login
        self.password  = password
        self.server    = server
        self.connected = False
        # Concurrency fix: the MT5 Python API is not documented as
        # thread-safe. The main signal loop and the TrailManager's fast
        # loop both call into this connector from separate threads, so
        # every direct mt5.* call is serialized through this lock.
        self._lock     = threading.Lock()

        # ── Simulated broker state (demo / no-MT5 mode only) ──────────
        # Populated by place_order() and consumed by get_open_positions(),
        # has_open_position(), and get_open_trade_count() so that duplicate
        # guards and risk limits behave consistently in demo mode instead of
        # always seeing zero open positions.
        self._sim_positions: list[dict] = []
        self._sim_next_ticket: int      = 900001  # avoids collision with live ticket range

    # ── Connection ────────────────────────────────────────────

    def connect(self) -> bool:
        if not MT5_AVAILABLE:
            logger.info("MT5 not available — using simulated data mode.")
            self.connected = False
            return False

        with self._lock:
            if not mt5.initialize():
                logger.error(f"MT5 initialize() failed: {mt5.last_error()}")
                return False

            authorized = mt5.login(self.login, password=self.password, server=self.server)
            if not authorized:
                logger.error(f"MT5 login failed: {mt5.last_error()}")
                mt5.shutdown()
                return False

            info = mt5.account_info()

        self.connected = True
        logger.info(f"Connected to MT5 | Account: {info.login} | Balance: ${info.balance:.2f}")
        return True

    def disconnect(self):
        if MT5_AVAILABLE and self.connected:
            with self._lock:
                mt5.shutdown()
            logger.info("MT5 disconnected.")
        self.connected = False

    # ── Market Data ───────────────────────────────────────────

    def get_candles(self, symbol: str, timeframe_const: int,
                    count: int = 300) -> Optional[pd.DataFrame]:
        """Fetch OHLCV candles from MT5 as a DataFrame."""
        if not self.connected or not MT5_AVAILABLE:
            return self._simulated_candles(count)

        with self._lock:
            rates = mt5.copy_rates_from_pos(symbol, timeframe_const, 0, count)

        if rates is None or len(rates) == 0:
            logger.error(f"No rates returned for {symbol} tf={timeframe_const}")
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.rename(columns={'tick_volume': 'volume', 'real_volume': 'real_vol'},
                  inplace=True)
        df.set_index('time', inplace=True)
        logger.debug(f"Fetched {len(df)} candles for {symbol} tf={timeframe_const}")
        return df

    def get_account_info(self) -> dict:
        """Return live account balance/equity, or defaults if not connected."""
        if not self.connected or not MT5_AVAILABLE:
            return {"balance": 10000.0, "equity": 10000.0,
                    "margin_free": 9000.0, "currency": "USD"}
        with self._lock:
            info = mt5.account_info()
        return {
            "balance":     info.balance,
            "equity":      info.equity,
            "margin_free": info.margin_free,
            "currency":    info.currency,
        }

    def get_symbol_info(self, symbol: str) -> dict:
        """Fetch tick size, pip value, and spread for position sizing."""
        if not self.connected or not MT5_AVAILABLE:
            return {"trade_tick_size": 0.01, "trade_tick_value": 0.01,
                    "volume_min": 0.01, "spread": 30, "digits": 2}
        with self._lock:
            info = mt5.symbol_info(symbol)
        return {
            "trade_tick_size":  info.trade_tick_size,
            "trade_tick_value": info.trade_tick_value,
            "volume_min":       info.volume_min,
            "volume_max":       info.volume_max,
            "spread":           info.spread,
            "digits":           info.digits,
        }

    # ── Fix #1 & #2: Live Position Queries ───────────────────

    def get_open_positions(self, symbol: str = "", magic: int = 0) -> list[dict]:
        """
        Fix #1 — Query MT5 directly for open positions every cycle.
        Never rely on internal counters; always read the live state.

        Returns a list of position dicts with keys:
          ticket, symbol, type ('BUY'|'SELL'), volume, open_price,
          sl, tp, profit, magic, comment
        """
        if not self.connected or not MT5_AVAILABLE:
            # Demo mode: return positions accumulated by simulated place_order()
            # calls so that duplicate guards and trade counts work correctly.
            with self._lock:
                logger.info(
                    f"SIM positions queried: {len(self._sim_positions)}"
                )

                return [
                    p for p in self._sim_positions
                    if (not symbol or p["symbol"] == symbol)
                    and (not magic  or p["magic"]  == magic)
                ]

        with self._lock:
            if symbol:
                raw = mt5.positions_get(symbol=symbol)
            else:
                raw = mt5.positions_get()

        if raw is None:
            logger.debug("mt5.positions_get() returned None (no open positions).")
            return []

        logger.debug(
            f"get_open_positions: raw={len(raw)} pre-filter for symbol={symbol or 'all'}, "
            f"magic_filter={magic}"
        )

        positions = []
        for p in raw:
            # Filter by magic number if provided so we only see this bot's trades
            if magic and p.magic != magic:
                continue
            positions.append({
                "ticket":      p.ticket,
                "symbol":      p.symbol,
                "type":        "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL",
                "volume":      p.volume,
                "open_price":  p.price_open,
                "sl":          p.sl,
                "tp":          p.tp,
                "profit":      p.profit,
                "magic":       p.magic,
                "comment":     p.comment,
            })

        logger.debug(f"Live open positions for {symbol or 'all'}: {len(positions)}")
        return positions

    def get_open_trade_count(self, symbol: str = "", magic: int = 0) -> int:
        """
        Fix #1 — Authoritative open trade count from MT5.
        Use this in RiskManager instead of the internal counter.
        """
        return len(self.get_open_positions(symbol=symbol, magic=magic))

    def has_open_position(self, symbol: str, direction: str, magic: int = 0) -> bool:
        """
        Fix #2 — Returns True if a position already exists for this
        symbol in the same direction. Prevents duplicate trades.

        direction: 'BUY' or 'SELL'
        """
        positions = self.get_open_positions(symbol=symbol, magic=magic)
        for p in positions:
            if p["type"] == direction:
                logger.info(
                    f"Duplicate guard: {direction} position already open on "
                    f"{symbol} (ticket #{p['ticket']}). Skipping."
                )
                return True
        return False

    # ── Feature #1: Trailing Stop — Live Price / ATR Helpers ──

    def get_current_price(self, symbol: str, direction: str) -> Optional[float]:
        """
        Return the price relevant to a position's unrealized P&L.
        For a BUY position, MT5 closes at bid. For a SELL, it closes at ask.
        """
        if not self.connected or not MT5_AVAILABLE:
            logger.debug(
                f"get_current_price({symbol}): skipped — connected={self.connected} "
                f"MT5_AVAILABLE={MT5_AVAILABLE}"
            )
            return None
        with self._lock:
            tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            logger.warning(f"get_current_price({symbol}): symbol_info_tick() returned None")
            return None
        price = tick.bid if direction == "BUY" else tick.ask
        logger.debug(f"get_current_price({symbol}, {direction}) -> {price}")
        return price

    def get_latest_atr(self, cfg) -> Optional[float]:
        """
        Fetch a small batch of recent candles and compute ATR fresh, for use
        by the trail manager's fast loop (independent of the main H1 cycle).
        """
        from core.indicators import add_atr  # local import avoids a cycle
        tf = cfg.TIMEFRAMES.get(cfg.TIMEFRAME, 16385)
        df = self.get_candles(cfg.SYMBOL, tf, max(cfg.ATR_PERIOD * 3, 50))
        if df is None:
            logger.warning("get_latest_atr: get_candles() returned None")
            return None
        if len(df) < cfg.ATR_PERIOD + 1:
            logger.warning(
                f"get_latest_atr: only {len(df)} candles, need >{cfg.ATR_PERIOD}"
            )
            return None
        df = add_atr(df, cfg.ATR_PERIOD)
        last_atr = df['atr'].iloc[-1]
        if last_atr != last_atr:  # NaN check
            logger.warning("get_latest_atr: computed ATR is NaN")
            return None
        logger.debug(f"get_latest_atr -> {float(last_atr):.4f}")
        return float(last_atr)

    # ── Feature #1: Trailing Stop — SL Modification ───────────

    def modify_sl(self, ticket: int, symbol: str, new_sl: float, tp: float) -> dict:
        """
        Modify only the stop loss of an existing position (trailing stop).
        TP is re-sent unchanged since MT5's TRADE_ACTION_SLTP requires both.
        """
        if not self.connected:
            logger.info(f"[SIMULATED SL MODIFY] ticket={ticket} {symbol} new_sl={new_sl:.2f}")
            return {"retcode": 0, "simulated": True}

        raise LegacyBrokerMutationQuarantinedError(
            "Connected legacy stop-loss modification is quarantined."
        )

        request = {
            "action":   mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol":   symbol,
            "sl":       new_sl,
            "tp":       tp,
        }
        with self._lock:
            result = mt5.order_send(request)

        if result is None:
            error = mt5.last_error()
            logger.error(
                f"MT5 order_send() returned None. Last error: {error}"
                )
            return {
                "retcode": -1,
                "error": str(error),
                }

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(
                f"Order failed: retcode={result.retcode} | {result.comment}"
        )
            return result._asdict()
        else:
            logger.info(
                f"SL modified: ticket={ticket} | {symbol} | new SL={new_sl}"
            )

        return result._asdict()

    # ── Feature #4 & #6: Closed Deal History ──────────────────

    def get_history_deals(self, magic: int, from_date: datetime,
                           to_date: Optional[datetime] = None) -> list[dict]:
        """
        Fetch closed deals (history_deals_get) filtered by MAGIC_NUMBER.
        Returns only the closing ("out") deals of this bot's trades, each with:
          ticket, symbol, type ('BUY'|'SELL'), volume, price, profit,
          time (datetime), position_id, magic
        Used to reconstruct daily P&L / consecutive-loss state from MT5
        itself, so restarts never lose track of real trading history.
        """
        if not self.connected or not MT5_AVAILABLE:
            return []

        to_date = to_date or datetime.now(UTC)
        with self._lock:
            raw = mt5.history_deals_get(from_date, to_date)

        if raw is None:
            logger.debug("mt5.history_deals_get() returned None (no deals).")
            return []

        deals = []
        for d in raw:
            if magic and d.magic != magic:
                continue
            # entry == 1 means DEAL_ENTRY_OUT (a position-closing deal).
            # We only want closing deals since those carry realized profit.
            if d.entry != mt5.DEAL_ENTRY_OUT:
                continue
            deals.append({
                "ticket":      d.ticket,
                "position_id": d.position_id,
                "symbol":      d.symbol,
                "type":        "SELL" if d.type == mt5.DEAL_TYPE_SELL else "BUY",
                "volume":      d.volume,
                "price":       d.price,
                "profit":      d.profit,
                "time":        datetime.fromtimestamp(d.time, tz=UTC),
                "magic":       d.magic,
            })

        deals.sort(key=lambda x: x["time"])
        logger.debug(f"Fetched {len(deals)} closed deals (magic={magic}).")
        return deals

    # ── Order Execution (activated when LIVE_TRADING=True) ────

    def place_order(self, symbol: str, action: str, lot: float,
                    sl: float, tp: float, magic: int, comment: str = "") -> dict:
        """
        Place a live market order on MT5.
        Guarded by has_open_position() in main.py before this is called.
        """
        if not self.connected:
            with self._lock:
                ticket = self._sim_next_ticket
                self._sim_next_ticket += 1
                # Simulate entry at the mid-price of the last simulated candle.
                # Using a fixed mid keeps position sizing and TrailManager 1R
                # calculations deterministic — no live tick available in demo.
                sim_price = 2300.0
                self._sim_positions.append({
                    "ticket":     ticket,
                    "symbol":     symbol,
                    "type":       action,          # 'BUY' or 'SELL'
                    "volume":     lot,
                    "open_price": sim_price,
                    "sl":         sl,
                    "tp":         tp,
                    "profit":     0.0,
                    "magic":      magic,
                    "comment": "BOT",
                })
            logger.info(
                f"SIM positions after order: {len(self._sim_positions)}"
            )
            logger.info(
                f"[SIMULATED ORDER] {action} {lot} lots {symbol} "
                f"@ {sim_price:.2f}  SL={sl:.2f}  TP={tp:.2f}  "
                f"ticket=#{ticket}"
            )
            return {"retcode": 10009, "order": ticket, "simulated": True}

        raise LegacyBrokerMutationQuarantinedError(
            "Connected legacy order placement is quarantined."
        )

        order_type = (mt5.ORDER_TYPE_BUY if action == "BUY"
                      else mt5.ORDER_TYPE_SELL)

        with self._lock:
            tick = mt5.symbol_info_tick(symbol)
            price = tick.ask if action == "BUY" else tick.bid

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": lot,
                "type": order_type,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": 20,
                "magic": magic,

                # TEMP TEST
                "comment": "BOT",

                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            logger.warning(f"ORDER COMMENT = [BOT]")
            logger.warning(request)

            result = mt5.order_send(request)

        if result is None:
            error = mt5.last_error()
            logger.error(
                f"MT5 order_send() returned None. Last error: {error}"
            )
            return {
                "retcode": -1,
                "error": str(error),
            }

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(
                f"Order failed: retcode={result.retcode} | {result.comment}"
            )
        else:
            logger.info(
                f"Order placed: ticket={result.order} | {action} {lot} {symbol}"
            )

        return result._asdict()

    # ── Simulated Data (fallback / testing) ───────────────────

    @staticmethod
    def _simulated_candles(count: int = 300) -> pd.DataFrame:
        """
        Generates synthetic XAUUSD-like OHLCV data for offline testing.
        Seed is time-based so each call produces fresh data.
        """
        import numpy as np
        rng    = np.random.default_rng(int(datetime.now(UTC).timestamp()) % 10000)
        dates  = pd.date_range(end=datetime.now(UTC), periods=count, freq='h')
        close = 2300 + np.cumsum(rng.standard_normal(count) * 3)

        # Realistic OHLC generation
        open_ = np.empty(count)
        open_[0] = close[0]
        open_[1:] = close[:-1]

        high = (
            np.maximum(open_, close)
            + np.abs(rng.standard_normal(count) * 2)
        )

        low = (
            np.minimum(open_, close)
            - np.abs(rng.standard_normal(count) * 2)
        )

        volume = rng.integers(500, 5000, count).astype(float)
        df = pd.DataFrame(
            {'open': open_, 'high': high, 'low': low,
             'close': close, 'volume': volume},
            index=dates
        )
        logger.info(f"Generated {count} simulated XAUUSD candles.")
        return df
