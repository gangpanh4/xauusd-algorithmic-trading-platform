"""
utils/candle_guard.py
──────────────────────
Feature #3 — Only generate signals when a new H1 candle has closed.

Without this guard, running the bot in --loop mode with a short interval
(or restarting it several times within the same hour) can produce multiple
signals from the SAME H1 candle, since the indicator snapshot wouldn't
change until the next candle closes anyway — but downstream systems
(Telegram, MT5 orders) would still see duplicate signal emissions.

State (the timestamp of the last candle a signal was generated for) is
persisted to disk so a bot restart mid-candle does not re-fire.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class CandleCloseGuard:
    """
    Tracks the timestamp of the last H1 candle a signal was generated for,
    and reports whether the current candle is "new" (i.e. closed since the
    last check).
    """

    def __init__(self, state_file: str = "output/last_candle_state.json"):
        self.state_file = state_file
        self._last_candle_time: Optional[str] = self._load()

    def _load(self) -> Optional[str]:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file) as f:
                    data = json.load(f)
                return data.get("last_candle_time")
            except Exception as e:
                logger.warning(f"Could not load candle-close state: {e}")
        return None

    def _save(self):
        try:
            Path(self.state_file).parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, "w") as f:
                json.dump({"last_candle_time": self._last_candle_time}, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save candle-close state: {e}")

    def is_new_candle(self, latest_candle_time) -> bool:
        """
        latest_candle_time: the index/timestamp of the most recent CLOSED
        candle in the fetched DataFrame (df.index[-1]).

        Returns True if this candle's timestamp differs from the last one
        we generated a signal for (i.e. a fresh candle has closed).
        """
        current = str(latest_candle_time)
        if current == self._last_candle_time:
            return False
        return True

    def mark_processed(self, latest_candle_time):
        """Call this once a signal has actually been generated for the candle."""
        self._last_candle_time = str(latest_candle_time)
        self._save()
