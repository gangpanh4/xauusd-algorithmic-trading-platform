"""
XAUUSD Algorithmic Trading Platform

Platform Engine Package

This package provides the top-level orchestration layer for the
entire trading platform.

The Platform Engine coordinates platform lifecycle,
execution modes, and subsystem initialization.

Business logic remains inside the dedicated core modules.
"""

from .engine import TradingPlatform
from .engine import TradingPlatform
from .modes import PlatformMode



__all__ = ["TradingPlatform"]

__all__ = [
    "TradingPlatform",
    "PlatformMode",
]



