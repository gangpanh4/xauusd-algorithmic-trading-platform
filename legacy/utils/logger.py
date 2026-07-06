"""
utils/logger.py
───────────────
Sets up structured logging and persists signals to JSON.
"""

import logging
import json
import os
import sys
from datetime import datetime, UTC
from pathlib import Path


def setup_logging(log_file: str = "logs/signal_bot.log", level: str = "INFO"):
    """Configure file + console logging."""

    # Windows UTF-8 console fix
    if sys.platform.startswith("win"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=fmt,
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ]
    )

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    return logging.getLogger("xauusd_bot")


def save_signal(signal_result, output_file: str = "output/signals.json"):
    """Append a signal to the JSON signals log."""
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    records = []
    if os.path.exists(output_file):
        try:
            with open(output_file, encoding="utf-8") as f:
                records = json.load(f)
        except Exception:
            records = []

    records.append(signal_result.to_dict())

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, default=str)


def load_signals(output_file: str = "output/signals.json") -> list:
    """Load all saved signals."""
    if not os.path.exists(output_file):
        return []
    with open(output_file, encoding="utf-8") as f:
        return json.load(f)


def signals_summary(output_file: str = "output/signals.json") -> str:
    """Print a quick performance breakdown of saved signals."""
    signals = load_signals(output_file)
    if not signals:
        return "No signals saved yet."

    total  = len(signals)
    buys   = sum(1 for s in signals if s["signal"] == "BUY")
    sells  = sum(1 for s in signals if s["signal"] == "SELL")
    no_t   = sum(1 for s in signals if s["signal"] == "NO TRADE")
    avg_conf = sum(s["confidence"] for s in signals) / total if total else 0

    return (
        f"\n── Signal History Summary ──\n"
        f"  Total signals  : {total}\n"
        f"  BUY signals    : {buys}\n"
        f"  SELL signals   : {sells}\n"
        f"  NO TRADE       : {no_t}\n"
        f"  Avg confidence : {avg_conf:.1%}\n"
    )
