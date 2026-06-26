"""
core/indicators.py
──────────────────
Computes all technical indicators on a candle DataFrame.
All functions are pure (no side effects) and independently testable.

Changes in this version:
  Fix #5 — add_htf_ema200() computes H4 EMA 200 from a separate DataFrame
  Fix #6 — find_dynamic_tp() targets swing highs/lows instead of fixed ATR multiple
"""

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


def add_all_indicators(df: pd.DataFrame, cfg) -> pd.DataFrame:
    """Master function — adds every indicator column to the primary (H1) DataFrame."""
    df = df.copy()
    df = add_ema(df, cfg.EMA_FAST, f"ema_{cfg.EMA_FAST}")
    df = add_ema(df, cfg.EMA_SLOW, f"ema_{cfg.EMA_SLOW}")
    df = add_rsi(df, cfg.RSI_PERIOD)
    df = add_atr(df, cfg.ATR_PERIOD)
    df = add_macd(df, cfg.MACD_FAST, cfg.MACD_SLOW, cfg.MACD_SIGNAL)
    df = add_bollinger(df, cfg.BB_PERIOD, cfg.BB_STD)
    df = add_candle_features(df)
    df.dropna(inplace=True)
    logger.debug(f"Indicators computed. Usable rows: {len(df)}")
    return df


# ── Trend ─────────────────────────────────────────────────────

def add_ema(df: pd.DataFrame, period: int, col_name: str) -> pd.DataFrame:
    """Exponential Moving Average."""
    df[col_name] = df['close'].ewm(span=period, adjust=False).mean()
    return df


# ── Fix #5 — Higher Timeframe EMA 200 ────────────────────────

def add_htf_ema200(df_htf: pd.DataFrame, period: int = 200) -> pd.DataFrame:
    """
    Compute EMA 200 on a separate higher-timeframe DataFrame (e.g. H4).
    Returns the same DataFrame with a new column 'htf_ema200'.
    Used as a trend filter: only take H1 longs if H4 price > H4 EMA 200.
    """
    df_htf = df_htf.copy()
    df_htf['htf_ema200'] = df_htf['close'].ewm(span=period, adjust=False).mean()
    return df_htf


def get_htf_bias(df_htf: pd.DataFrame) -> dict:
    """
    Extract the current H4 trend bias from the HTF DataFrame.
    Returns dict: { 'htf_close', 'htf_ema200', 'htf_bullish', 'htf_bearish' }
    """
    # Patch: iloc[-1] is the still-forming H4 candle (MT5 copy_rates_from_pos
    # convention — position 0 / the last row is always the live, incomplete
    # bar). Use iloc[-2], the last fully CLOSED H4 candle, so the bias can't
    # flip mid-bar on partial data.
    if df_htf is None or len(df_htf) < 2 or 'htf_ema200' not in df_htf.columns:
        return {"htf_close": None, "htf_ema200": None,
                "htf_bullish": None, "htf_bearish": None}

    last        = df_htf.iloc[-2]
    htf_close   = last['close']
    htf_ema200  = last['htf_ema200']

    if pd.isna(htf_ema200):
        return {"htf_close": htf_close, "htf_ema200": None,
                "htf_bullish": None, "htf_bearish": None}

    return {
        "htf_close":   round(htf_close, 2),
        "htf_ema200":  round(htf_ema200, 2),
        "htf_bullish": htf_close > htf_ema200,
        "htf_bearish": htf_close < htf_ema200,
    }


# ── Momentum ──────────────────────────────────────────────────

def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Relative Strength Index."""
    delta    = df['close'].diff()
    gain     = delta.clip(lower=0)
    loss     = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs       = avg_gain / avg_loss.replace(0, np.nan)
    df['rsi'] = 100 - (100 / (1 + rs))
    return df


def add_macd(df: pd.DataFrame, fast: int, slow: int, signal: int) -> pd.DataFrame:
    """MACD line, signal line, and histogram."""
    ema_fast          = df['close'].ewm(span=fast,   adjust=False).mean()
    ema_slow          = df['close'].ewm(span=slow,   adjust=False).mean()
    df['macd']        = ema_fast - ema_slow
    df['macd_signal'] = df['macd'].ewm(span=signal, adjust=False).mean()
    df['macd_hist']   = df['macd'] - df['macd_signal']
    return df


# ── Volatility ────────────────────────────────────────────────

def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Average True Range — used for stop loss and dynamic TP sizing."""
    hl  = df['high'] - df['low']
    hpc = (df['high'] - df['close'].shift(1)).abs()
    lpc = (df['low']  - df['close'].shift(1)).abs()
    tr  = pd.concat([hl, hpc, lpc], axis=1).max(axis=1)
    df['atr'] = tr.ewm(com=period - 1, min_periods=period).mean()
    return df


def add_bollinger(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
    """Bollinger Bands — middle, upper, lower bands + %B."""
    df['bb_mid']   = df['close'].rolling(period).mean()
    rolling_std    = df['close'].rolling(period).std()
    df['bb_upper'] = df['bb_mid'] + std_dev * rolling_std
    df['bb_lower'] = df['bb_mid'] - std_dev * rolling_std
    band_width     = df['bb_upper'] - df['bb_lower']
    df['bb_pct']   = (df['close'] - df['bb_lower']) / band_width.replace(0, np.nan)
    return df


# ── Candle Features ───────────────────────────────────────────

def add_candle_features(df: pd.DataFrame) -> pd.DataFrame:
    """Derived candle properties useful for signal logic."""
    df['body']      = (df['close'] - df['open']).abs()
    df['range']     = df['high'] - df['low']
    df['body_pct']  = df['body'] / df['range'].replace(0, np.nan)
    df['bullish']   = df['close'] > df['open']
    df['vol_ma20']  = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma20'].replace(0, np.nan)
    return df


# ── Fix #6 — Dynamic Take Profit ─────────────────────────────

def find_dynamic_tp(
    df: pd.DataFrame,
    direction: str,        # 'BUY' or 'SELL'
    entry: float,
    atr: float,
    sl_distance: float,
    cfg,
) -> tuple[float, str]:
    """
    Fix #6 — Choose TP based on recent swing high/low rather than a fixed ATR multiple.

    Logic:
      BUY  → target the nearest significant swing HIGH above entry
      SELL → target the nearest significant swing LOW below entry

    Constraints:
      • TP must achieve at least cfg.MIN_RISK_REWARD (floor)
      • TP cannot exceed cfg.ATR_TP_MAX × ATR from entry (ceiling)
      • If no swing level qualifies, falls back to ATR_TP_MULTI × ATR

    Returns (tp_price: float, method: str)
    """
    lookback = getattr(cfg, 'SWING_LOOKBACK', 20)
    min_rr   = cfg.MIN_RISK_REWARD
    tp_floor = entry + sl_distance * min_rr if direction == "BUY" else entry - sl_distance * min_rr
    tp_ceil_dist = atr * cfg.ATR_TP_MAX
    tp_ceil  = entry + tp_ceil_dist if direction == "BUY" else entry - tp_ceil_dist

    # Use last N candles for swing detection
    recent = df.tail(lookback + 1)

    if direction == "BUY":
        # Swing high: candle whose high is the local maximum
        swing_highs = []
        highs = recent['high'].values
        for i in range(1, len(highs) - 1):
            if highs[i] > highs[i - 1] and highs[i] > highs[i + 1]:
                swing_highs.append(highs[i])

        # Find the lowest qualifying swing high above entry
        candidates = sorted([h for h in swing_highs if h > tp_floor])
        if candidates:
            swing_tp = candidates[0]
            # Cap at ATR ceiling
            swing_tp = min(swing_tp, tp_ceil)
            if swing_tp > tp_floor:
                return round(swing_tp, 2), "swing_high"

    else:  # SELL
        swing_lows = []
        lows = recent['low'].values
        for i in range(1, len(lows) - 1):
            if lows[i] < lows[i - 1] and lows[i] < lows[i + 1]:
                swing_lows.append(lows[i])

        candidates = sorted([l for l in swing_lows if l < tp_floor], reverse=True)
        if candidates:
            swing_tp = candidates[0]
            swing_tp = max(swing_tp, tp_ceil)  # for SELL, ceiling is lower
            if swing_tp < tp_floor:
                return round(swing_tp, 2), "swing_low"

    # Fallback: ATR_TP_MULTI × ATR (guaranteed to meet min R:R)
    fallback_dist = atr * cfg.ATR_TP_MULTI
    fallback_tp   = (entry + fallback_dist if direction == "BUY"
                     else entry - fallback_dist)
    return round(fallback_tp, 2), "atr_fallback"


def is_within_trading_session(cfg, now=None) -> bool:
    """
    Feature #2 — Trading session / time filter.
    Returns True if the current UTC hour falls within
    [TRADING_START_HOUR_UTC, TRADING_END_HOUR_UTC] inclusive.
    If TIME_FILTER_ENABLED is False, always returns True.
    """
    if not getattr(cfg, "TIME_FILTER_ENABLED", False):
        return True

    from datetime import datetime, timezone
    now = now or datetime.now(tz=timezone.utc)
    hour = now.hour

    start = cfg.TRADING_START_HOUR_UTC
    end   = cfg.TRADING_END_HOUR_UTC

    if start <= end:
        return start <= hour <= end
    # Handles a session that wraps midnight (e.g. 21 → 7)
    return hour >= start or hour <= end


def get_mtf_trigger(df_m15: pd.DataFrame) -> dict:
    """
    Feature #8 — Multi-timeframe entry trigger.
    Checks the latest M15 candle for a MACD histogram crossover.

    H4 supplies the trend, H1 supplies the setup (existing logic), and M15
    supplies the final trigger: a MACD crossover confirms the entry timing.

    Expects df_m15 to already have MACD columns (via add_macd), or will
    compute them if missing using default MACD periods (12/26/9).

    Returns dict: { 'macd_cross_up', 'macd_cross_dn', 'macd_hist', 'available' }
    """
    # Patch: iloc[-1] is the still-forming M15 candle (same MT5 convention
    # as H1/H4). The crossover check must compare two CLOSED candles, or
    # "cross_up"/"cross_dn" can flicker true/false as the live bar's MACD
    # histogram moves before the candle actually closes. Shift back by one:
    # iloc[-2] = last closed candle, iloc[-3] = the one before it.
    if df_m15 is None or len(df_m15) < 3:
        return {"available": False, "macd_cross_up": False,
                "macd_cross_dn": False, "macd_hist": None}

    if 'macd_hist' not in df_m15.columns:
        df_m15 = add_macd(df_m15.copy(), 12, 26, 9)

    last = df_m15.iloc[-2]
    prev = df_m15.iloc[-3]

    if pd.isna(last['macd_hist']) or pd.isna(prev['macd_hist']):
        return {"available": False, "macd_cross_up": False,
                "macd_cross_dn": False, "macd_hist": None}

    cross_up = prev['macd_hist'] < 0 and last['macd_hist'] > 0
    cross_dn = prev['macd_hist'] > 0 and last['macd_hist'] < 0

    return {
        "available":     True,
        "macd_cross_up": bool(cross_up),
        "macd_cross_dn": bool(cross_dn),
        "macd_hist":     round(float(last['macd_hist']), 4),
    }


# ── Snapshot Helper ───────────────────────────────────────────

def get_latest_snapshot(df: pd.DataFrame, cfg=None) -> dict:
    """
    Returns the most recent candle's indicator values as a flat dict.
    Used by the signal engine to avoid passing the whole DataFrame around.
    """
    # Patch: iloc[-1] is the still-forming H1 candle (same MT5 convention
    # as H4/M15 — position 0 in copy_rates_from_pos is the live bar). The
    # signal engine must score a CLOSED candle, or RSI/MACD/BB values keep
    # shifting underneath it mid-bar. Shift back by one: iloc[-2] = last
    # closed candle, iloc[-3] = the one before it (for prev_macd_hist).
    row  = df.iloc[-2]
    prev = df.iloc[-3]

    ema_fast_col = f"ema_{cfg.EMA_FAST}"  if cfg else "ema_50"
    ema_slow_col = f"ema_{cfg.EMA_SLOW}"  if cfg else "ema_200"

    return {
        "close":       row['close'],
        "high":        row['high'],
        "low":         row['low'],
        "open":        row['open'],
        "volume":      row['volume'],

        # EMAs (H1)
        "ema_fast":    row.get(ema_fast_col, None),
        "ema_slow":    row.get(ema_slow_col, None),

        # RSI
        "rsi":         row['rsi'],

        # MACD
        "macd":        row['macd'],
        "macd_signal": row['macd_signal'],
        "macd_hist":   row['macd_hist'],
        "prev_macd_hist": prev['macd_hist'],

        # ATR
        "atr":         row['atr'],

        # Bollinger
        "bb_upper":    row['bb_upper'],
        "bb_lower":    row['bb_lower'],
        "bb_mid":      row['bb_mid'],
        "bb_pct":      row['bb_pct'],

        # Candle
        "bullish":     bool(row['bullish']),
        "body_pct":    row['body_pct'],
        "vol_ratio":   row['vol_ratio'],
    }
