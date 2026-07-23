"""
Configuration for the MT5 Execution Engine.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MT5ExecutionConfig:
    """
    Configuration for MT5 execution.
    """

    magic_number: int = 30001

    default_slippage: int = 10

    allowed_order_volume: float = 0.01

    max_retry_attempts: int = 3

    connection_timeout_seconds: int = 10

    enable_auto_reconnect: bool = False

    debug_logging: bool = False

    order_comment: str = "XAUUSD Platform v3.1"