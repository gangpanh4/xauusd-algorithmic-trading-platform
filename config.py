# ============================================================
#  Quarantined legacy signal-generator configuration
#  The current platform does not import or depend on this module.
# ============================================================

import os

# ── MetaTrader 5 Connection ──────────────────────────────────
# Backward compatibility for offline/legacy consumers only. These values are
# intentionally absent unless an operator explicitly supplies the quarantined
# legacy environment variables.
MT5_LOGIN    = int(os.getenv("XAUUSD_LEGACY_MT5_LOGIN", "0"))
MT5_PASSWORD = os.getenv("XAUUSD_LEGACY_MT5_PASSWORD", "")
MT5_SERVER   = os.getenv("XAUUSD_LEGACY_MT5_SERVER", "")

# ── Symbol & Timeframe ───────────────────────────────────────
SYMBOL     = "XAUUSD"
TIMEFRAME  = "H1"          # Primary entry timeframe
HTF        = "H4"          # Higher timeframe for trend filter (Fix #5)
TIMEFRAMES = {             # MT5 timeframe constants
    "M5":  5,
    "M15": 15,
    "M30": 30,
    "H1":  16385,
    "H4":  16388,
    "D1":  16408,
}

# ── Indicator Parameters ─────────────────────────────────────
EMA_FAST        = 50
EMA_SLOW        = 200
RSI_PERIOD      = 14
RSI_OVERBOUGHT  = 70
RSI_OVERSOLD    = 30
ATR_PERIOD      = 14
ATR_SL_MULTI    = 1.5      # Stop loss = ATR × this multiplier

# Fix #6 — Dynamic TP: ATR_TP_MULTI is the FLOOR only.
# Actual TP targets swing highs/lows; ATR multiplier is minimum.
ATR_TP_MULTI    = 2.0      # Minimum TP = ATR × this (floor)
ATR_TP_MAX      = 4.0      # Maximum TP = ATR × this (ceiling, avoids overreach)
SWING_LOOKBACK  = 20       # Candles to look back for swing high/low

# ── MACD Parameters ──────────────────────────────────────────
MACD_FAST   = 12
MACD_SLOW   = 26
MACD_SIGNAL = 9

# ── Bollinger Bands ──────────────────────────────────────────
BB_PERIOD = 20
BB_STD    = 2.0

# ── Risk Management ──────────────────────────────────────────
RISK_PER_TRADE_PCT    = 1.0      # % of balance risked per trade
MAX_DAILY_LOSS_PCT    = 3.0      # Kill-switch: stop trading today
MAX_OPEN_TRADES       = 3        # Concurrent trade limit
MIN_RISK_REWARD       = 1.2      # Skip signal if R:R < this
LOT_SIZE_MIN          = 0.01
LOT_SIZE_MAX          = 5.0

# ── News Filter ──────────────────────────────────────────────
NEWS_FILTER_ENABLED   = True
NEWS_BLACKOUT_MINUTES = 30       # No trades X mins before/after
HIGH_IMPACT_KEYWORDS  = [
    "Federal Reserve", "Fed Rate", "FOMC", "NFP",
    "Non-Farm Payroll", "CPI", "Inflation", "GDP",
    "Interest Rate", "Powell", "ECB", "BOE",
    "Gold", "XAUUSD", "Geopolitical", "War", "Crisis"
]

# ── Signal Confidence Scoring Weights (Fix #4) ───────────────
# Rebalanced for XAUUSD characteristics:
#   • Trend is the primary edge — highest weight
#   • MACD momentum matters more than tick volume for gold
#   • MT5 tick volume is unreliable → Volume weight reduced to 5%
WEIGHT_TREND    = 0.40   # EMA 50/200 direction + HTF alignment
WEIGHT_RSI      = 0.20   # RSI momentum confirmation
WEIGHT_MACD     = 0.25   # MACD histogram / crossover
WEIGHT_BB       = 0.10   # Bollinger Band position
WEIGHT_VOLUME   = 0.05   # Volume (low weight — MT5 tick vol unreliable)
MIN_CONFIDENCE  = 0.60   # Below this → NO TRADE

# ── HTF Filter (Fix #5) ──────────────────────────────────────
HTF_FILTER_ENABLED = True   # Require H4 EMA200 alignment before H1 entry
HTF_CANDLES        = 300    # H4 candles to fetch for HTF EMA 200

# ── Candle Data ──────────────────────────────────────────────
CANDLES_REQUIRED = 300   # Enough for EMA 200 + warmup

# ── Logging ──────────────────────────────────────────────────
LOG_FILE     = "logs/signal_bot.log"
SIGNAL_LOG   = "output/signals.json"
LOG_LEVEL    = "DEBUG"

# ── Legacy Live Trading Gate (permanently fail-closed by default) ──
LIVE_TRADING = False
MAGIC_NUMBER = 20240101   # Unique ID for this bot's orders

# ── Telegram Alerts (optional) ───────────────────────────────
TELEGRAM_ENABLED = False
TELEGRAM_TOKEN   = ""
TELEGRAM_CHAT_ID = ""

# ── Feature #1: ATR Trailing Stop ─────────────────────────────
TRAILING_STOP_ENABLED   = False
TRAIL_CHECK_SECONDS     = 10     # How often the trail manager loop runs
TRAIL_BREAKEVEN_R       = 1.0    # Move SL to breakeven once price reaches +1R
TRAIL_ACTIVATE_R        = 2.0    # Start ATR trailing once price reaches +2R
TRAIL_ATR_MULTI         = 1.5    # Trail distance = ATR × this, once activated
TRAIL_MIN_STEP_ATR      = 0.1    # Ignore SL modifications smaller than this × ATR

# ── Feature #2: Trading Session / Time Filter ─────────────────
TIME_FILTER_ENABLED   = True
TRADING_START_HOUR_UTC = 7        # Inclusive
TRADING_END_HOUR_UTC   = 21       # Inclusive (signals allowed up to 21:59:59 UTC)

# ── Feature #3: Candle-Close-Only Signals ─────────────────────
# Only generate a new signal once a fresh H1 candle has closed.
# State is persisted so restarts don't immediately refire on the same candle.
CANDLE_CLOSE_ONLY        = False
LAST_CANDLE_STATE_FILE   = "output/last_candle_state.json"

# ── Feature #5: Daily Trade Limit ──────────────────────────────
MAX_TRADES_PER_DAY = 20     # RiskManager blocks further entries once reached

# ── Feature #6: Consecutive Loss Kill-Switch ───────────────────
MAX_CONSECUTIVE_LOSSES = 3     # Stop trading after N consecutive losses
# Cool-down lasts until the next calendar day (UTC), same as the daily reset.

# ── Feature #4: Position Synchronization ───────────────────────
POSITION_SYNC_ON_STARTUP = True

# ── Feature #8: Multi-Timeframe Entry (H4 + H1 + M15) ──────────
MTF_ENTRY_ENABLED = False   # Require M15 MACD crossover trigger before entry
MTF_TRIGGER_TF     = "M15"
MTF_CANDLES        = 150   # M15 candles to fetch for the trigger check

# ── BOS Detector Configuration ───────────────────────────────
BOS_DETECTOR_CONFIG = {
    "param1": 10,
    "param2": 0.75
}
