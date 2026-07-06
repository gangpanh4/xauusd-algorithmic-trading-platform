"""
Platform Execution Modes.
"""

from enum import Enum


class PlatformMode(str, Enum):
    """
    Supported execution modes for the trading platform.
    """

    BACKTEST = "backtest"
    LIVE = "live"
    RESEARCH = "research"