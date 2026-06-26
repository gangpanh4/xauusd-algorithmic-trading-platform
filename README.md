# XAUUSD AI Trading Signal Generator

A professional-grade signal generator for **Gold (XAU/USD)** on **MetaTrader 5**,
built to be extended into a fully automated trading bot.

---

## ✅ Features

| Component | Description |
|---|---|
| **EMA 200 Trend Filter** | Primary trend direction — only trade with the trend |
| **EMA 50 Cross** | Secondary confirmation of momentum |
| **RSI (14)** | Avoids overbought buys / oversold sells |
| **MACD** | Histogram crossover for entry timing |
| **Bollinger Bands** | Warns if price is stretched to extremes |
| **ATR Stop Loss** | Dynamic SL/TP sized to current volatility |
| **News Filter** | Blocks trades 30 min before/after high-impact events |
| **Risk Manager** | Daily loss limit, max positions, lot size calculator |
| **Confidence Score** | Weighted 0–100% score; below 60% = NO TRADE |
| **Telegram Alerts** | Optional real-time signal push notifications |

---

## 📁 Project Structure

```
xauusd_signal_bot/
├── main.py                  ← Entry point
├── config.py                ← All parameters (edit here first)
├── requirements.txt
│
├── core/
│   ├── mt5_connector.py     ← MT5 data fetch + order execution
│   └── indicators.py        ← EMA, RSI, ATR, MACD, BB
│
├── signals/
│   └── signal_engine.py     ← BUY / SELL / NO TRADE logic + confidence
│
├── news/
│   └── news_filter.py       ← ForexFactory calendar blackout
│
├── risk/
│   └── risk_manager.py      ← Daily loss guard, position limits
│
├── utils/
│   ├── logger.py            ← File + console logging, signal JSON export
│   └── telegram_alert.py    ← Push notifications
│
├── logs/                    ← signal_bot.log (auto-created)
└── output/                  ← signals.json (auto-created)
```

---

## 🚀 Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
# For live MT5 (Windows only):
pip install MetaTrader5
```

### 2. Run in demo mode (no MT5 needed)
```bash
python main.py --demo
```

### 3. Run once with live MT5 data
Edit `config.py` → set `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`
```bash
python main.py
```

### 4. Run continuously (poll every 60 seconds)
```bash
python main.py --loop --interval 60
```

### 5. View signal history
```bash
python main.py --stats
```

---

## ⚙️ Configuration (`config.py`)

Key settings to adjust:

```python
SYMBOL            = "XAUUSD"
TIMEFRAME         = "H1"          # M15 / H1 / H4 / D1

RISK_PER_TRADE_PCT = 1.0          # % of balance per trade
MAX_DAILY_LOSS_PCT = 3.0          # Kill switch
MIN_CONFIDENCE     = 0.60         # Below this = NO TRADE
MIN_RISK_REWARD    = 1.5          # Skip if R:R too low

NEWS_FILTER_ENABLED   = True
NEWS_BLACKOUT_MINUTES = 30

LIVE_TRADING = False              # ← Set True to enable auto-execution
```

---

## 📊 Signal Output Example

```
============================================================
  XAUUSD Signal  |  2024-01-15T09:30:00
============================================================
  Signal     : BUY
  Confidence : 82.0%
  Entry      : 2025.40
  Stop Loss  : 2019.20  (6.2 pips)
  Take Profit: 2035.70
  R:R Ratio  : 1:1.66
  Lot Size   : 0.15
────────────────────────────────────────────────────────────
  Reasoning:
    ✓ Price above EMA 200 → Bullish trend
    ✓ EMA 50 above EMA 200 → Double confirmation bullish
    ✓ RSI (54.2) in healthy bullish zone (40–65)
    ✓ MACD fresh crossover ↑ confirms bullish momentum
    ✓ R:R ratio 1:1.66 ≥ minimum 1:1.5
  Warnings:
    ⚠ Volume 0.8× below average — low conviction
============================================================
```

---

## 🤖 Upgrade Path: Full Auto-Bot

This project is designed to be upgraded step-by-step:

| Step | Change | File |
|---|---|---|
| 1 | Set `LIVE_TRADING = True` | `config.py` |
| 2 | Fill in MT5 credentials | `config.py` |
| 3 | Enable Telegram alerts | `config.py` |
| 4 | Enable loop mode | `python main.py --loop` |
| 5 | Add trailing stop logic | `core/mt5_connector.py` → `modify_order()` |
| 6 | Add multi-timeframe confirmation | `core/indicators.py` + `main.py` |
| 7 | Add ML confidence model | `signals/ml_model.py` (new file) |

---

## ⚠️ Disclaimer

This software is for **educational purposes only**. Forex and gold trading
carries significant risk. Always test on a **demo account** before using
real capital. Past signal performance does not guarantee future results.
