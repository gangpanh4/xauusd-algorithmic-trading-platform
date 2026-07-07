# ============================================================
#  Market Structure Engine Configuration
#  Upgrade path: Ensure all components are configured correctly
# ============================================================

# ── Swing Detection Configuration ────────────────────────────
SWING_DETECTOR_ENABLED = True
SWING_DETECTOR_CONFIG = {
    "pivot_left": 3,
    "pivot_right": 3,
    "minimum_swing_distance": 0.0,
    "equal_high_tolerance": 0.0,
    "equal_low_tolerance": 0.0,
    "atr_validation": True,
    "atr_period": 14,
    "atr_multiplier": 1.0,
    "maximum_history": 5000,
    "debug_logging": False
}

# ── BOS Configuration ────────────────────────────────────────
BOS_ENABLED = True

# ── CHoCH Configuration ──────────────────────────────────────
CHOCH_ENABLED = True

# ── Liquidity Configuration ──────────────────────────────────
LIQUIDITY_ENABLED = True

# ── Order Blocks Configuration ───────────────────────────────
ORDER_BLOCKS_ENABLED = True

# ── Fair Value Gaps Configuration ────────────────────────────
FAIR_VALUE_GAPS_ENABLED = True

# ── Logging ──────────────────────────────────────────────────
LOG_FILE = "logs/market_structure.log"
LOG_LEVEL = "DEBUG"

# ── Live Trading Gate (set True to enable auto-execution) ────
LIVE_TRADING = False
MAGIC_NUMBER = 20240101   # Unique ID for this bot's orders

# ── Telegram Alerts (optional) ───────────────────────────────
TELEGRAM_ENABLED = False
TELEGRAM_TOKEN = ""
TELEGRAM_CHAT_ID = ""

# ── Feature: Daily Trade Limit ──────────────────────────────
MAX_TRADES_PER_DAY = 20     # RiskManager blocks further entries once reached

# ── Feature: Consecutive Loss Kill-Switch ───────────────────
MAX_CONSECUTIVE_LOSSES = 3     # Stop trading after N consecutive losses
# Cool-down lasts until the next calendar day (UTC), same as the daily reset.
