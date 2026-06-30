"""
news/news_filter.py
───────────────────
Detects high-impact news events near the current time.

Sources supported:
  1. ForexFactory JSON feed (free, no API key)
  2. Manual event injection for testing

Returns True (block trading) / False (safe to trade).

UPGRADE PATH:
  • Swap to a paid news API (e.g. Benzinga, Refinitiv) for real-time data
  • Add sentiment scoring on news headlines using Claude API
"""

import logging
from datetime import datetime, UTC, timedelta, timezone
from typing import Optional
import json

logger = logging.getLogger(__name__)

# Attempt to import requests (optional dependency)
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class NewsFilter:
    """
    Checks whether trading should be blocked due to nearby
    high-impact economic events for XAUUSD (USD & gold news).
    """

    FOREXFACTORY_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

    def __init__(self, cfg):
        self.cfg      = cfg
        self._cache   = []
        self._last_fetch: Optional[datetime] = None
        self._cache_ttl_minutes = 60

    def is_news_blocked(self, now: Optional[datetime] = None) -> tuple[bool, list[dict]]:
        """
        Returns (blocked: bool, upcoming_events: list).
        blocked=True means trading should be paused.
        """
        if not self.cfg.NEWS_FILTER_ENABLED:
            return False, []

        now = now or datetime.now(tz=timezone.utc)
        events = self._get_events()
        blackout = timedelta(minutes=self.cfg.NEWS_BLACKOUT_MINUTES)
        nearby   = []

        for event in events:
            event_time = event.get("dt")
            if event_time is None:
                continue
            delta = abs(now - event_time)
            if delta <= blackout:
                nearby.append({**event, "minutes_away": round(delta.total_seconds() / 60, 1)})

        blocked = len(nearby) > 0
        if blocked:
            titles = [e.get("title", "Unknown") for e in nearby]
            logger.warning(f"News blackout active. Events: {titles}")
        else:
            logger.debug("No high-impact news events nearby. Safe to trade.")

        return blocked, nearby

    # ── Data Fetching ─────────────────────────────────────────

    def _get_events(self) -> list[dict]:
        """Fetch (or return cached) this week's high-impact events."""
        now = datetime.now(tz=timezone.utc)

        if (self._last_fetch is not None and
                (now - self._last_fetch) < timedelta(minutes=self._cache_ttl_minutes)):
            return self._cache

        events = self._fetch_forexfactory()
        if not events:
            events = self._fallback_events()

        self._cache      = events
        self._last_fetch = now
        return events

    def _fetch_forexfactory(self) -> list[dict]:
        """Try to get ForexFactory calendar data."""
        if not REQUESTS_AVAILABLE:
            logger.debug("requests not installed — skipping ForexFactory fetch.")
            return []

        try:
            resp = requests.get(self.FOREXFACTORY_URL, timeout=5)
            resp.raise_for_status()
            raw = resp.json()
            return self._parse_ff(raw)
        except Exception as e:
            logger.warning(f"ForexFactory fetch failed: {e}")
            return []

    def _parse_ff(self, raw: list) -> list[dict]:
        """Parse ForexFactory JSON into normalised event dicts."""
        parsed = []
        for item in raw:
            impact   = item.get("impact", "").upper()
            currency = item.get("currency", "").upper()
            title    = item.get("title", "")

            # Only keep HIGH impact events affecting USD or Gold
            if impact != "HIGH":
                continue
            if currency not in ("USD", "XAU"):
                continue
            if not any(kw.lower() in title.lower()
                       for kw in self.cfg.HIGH_IMPACT_KEYWORDS):
                continue

            try:
                raw_date = item.get("date", "")   # e.g. "06-23-2025"
                raw_time = item.get("time", "")   # e.g. "8:30am"
                if not raw_time or raw_time.lower() in ("all day", "tentative", ""):
                    dt_str = raw_date + " 12:00pm"
                else:
                    dt_str = raw_date + " " + raw_time
                dt = datetime.strptime(dt_str, "%m-%d-%Y %I:%M%p")
                dt = dt.replace(tzinfo=timezone.utc)
            except Exception:
                dt = None

            parsed.append({"title": title, "currency": currency, "impact": impact, "dt": dt})

        logger.info(f"Loaded {len(parsed)} high-impact news events from ForexFactory.")
        return parsed

    def _fallback_events(self) -> list[dict]:
        """
        Fallback: load from a local JSON file if present.
        Create 'news/events.json' with manual entries for testing.
        """
        try:
            with open("news/events.json") as f:
                data = json.load(f)
            events = []
            for item in data:
                item["dt"] = datetime.fromisoformat(item["dt"]).replace(tzinfo=timezone.utc)
                events.append(item)
            logger.info(f"Loaded {len(events)} events from local events.json")
            return events
        except Exception:
            logger.debug("No local events.json found.")
            return []

    def upcoming_events_str(self, n: int = 5) -> str:
        """Return a readable string of the next N events."""
        events = [e for e in self._get_events() if e.get("dt")]
        events.sort(key=lambda x: x["dt"])
        now = datetime.now(tz=timezone.utc)
        future = [e for e in events if e["dt"] > now][:n]
        if not future:
            return "No upcoming high-impact events found."
        lines = ["Upcoming High-Impact Events:"]
        for e in future:
            delta = e["dt"] - now
            hrs   = int(delta.total_seconds() // 3600)
            mins  = int((delta.total_seconds() % 3600) // 60)
            lines.append(f"  [{e['currency']}] {e['title']} — in {hrs}h {mins}m")
        return "\n".join(lines)
