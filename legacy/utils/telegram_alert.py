"""
utils/telegram_alert.py
────────────────────────
Send signal alerts to a Telegram bot (optional).

Setup:
  1. Create a bot via @BotFather → get TELEGRAM_TOKEN
  2. Get your chat ID by messaging @userinfobot
  3. Set config.TELEGRAM_ENABLED = True and fill in the token/chat_id

Feature #7 — Telegram Position Updates
  • send_signal_alert(): richer entry message
      "SELL XAUUSD / Entry / SL / TP / Lot / Confidence"
    instead of just "SELL signal".
  • send_breakeven_alert(): sent once a position's SL is moved to breakeven
    by the TrailManager.
  • send_trade_closed_alert(): sent when a position closes, reporting
    profit or loss in dollars depending on outcome.
"""

import logging

logger = logging.getLogger(__name__)

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


def _send(cfg, text: str) -> bool:
    """Shared low-level sender used by all alert functions below."""
    if not cfg.TELEGRAM_ENABLED:
        return False
    if not REQUESTS_AVAILABLE:
        logger.warning("requests not installed — Telegram alerts disabled.")
        return False

    url     = f"https://api.telegram.org/bot{cfg.TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id":    cfg.TELEGRAM_CHAT_ID,
        "text":       text,
        "parse_mode": "Markdown",
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Telegram alert sent successfully.")
        return True
    except Exception as e:
        logger.error(f"Telegram alert failed: {e}")
        return False


def send_signal_alert(signal_result, cfg) -> bool:
    """
    Send a formatted signal entry message to Telegram, e.g.:

      🔴 SELL XAUUSD
      Entry: 4137.00
      SL: 4166.00
      TP: 4090.00
      Lot: 0.35
      Confidence: 82%
    """
    if signal_result.signal == "NO TRADE":
        return False  # Feature #7 — only alert on actionable signals

    emoji = {"BUY": "🟢", "SELL": "🔴"}.get(signal_result.signal, "⚪")
    conf  = f"{signal_result.confidence:.0%}"

    msg = (
        f"{emoji} *{signal_result.signal} {cfg.SYMBOL}*\n"
        f"Entry: `{signal_result.entry:.2f}`\n"
        f"SL: `{signal_result.stop_loss:.2f}`\n"
        f"TP: `{signal_result.take_profit:.2f}`\n"
        f"Lot: `{signal_result.lot_size}`\n"
        f"Confidence: `{conf}`\n\n"
        f"*Reasoning:*\n" +
        "\n".join(f"• {r}" for r in signal_result.reasoning[:3])
    )
    return _send(cfg, msg)


def send_breakeven_alert(cfg, ticket: int, direction: str, symbol: str,
                          entry: float) -> bool:
    """
    Feature #7 — Sent once the TrailManager moves a position's SL to
    breakeven (the +1R milestone).
    """
    msg = (
        f"🔒 *Move SL to Breakeven*\n"
        f"{direction} {symbol} (ticket `{ticket}`)\n"
        f"SL moved to entry: `{entry:.2f}`"
    )
    return _send(cfg, msg)


def send_trade_closed_alert(cfg, ticket: int, direction: str, symbol: str,
                             profit: float, reason: str = "") -> bool:
    """
    Feature #7 — Sent when a position closes (TP hit, SL hit, or manual close).

    reason: optional hint such as "TP hit" or "SL hit" if known; if empty,
    the message is phrased generically based on the profit sign.
    """
    if profit >= 0:
        emoji = "✅"
        label = reason or "TP hit"
        amount_line = f"Profit: `+${profit:,.2f}`"
    else:
        emoji = "🛑"
        label = reason or "SL hit"
        amount_line = f"Loss: `-${abs(profit):,.2f}`"

    msg = (
        f"{emoji} *{label}*\n"
        f"{direction} {symbol} (ticket `{ticket}`)\n"
        f"{amount_line}"
    )
    return _send(cfg, msg)

