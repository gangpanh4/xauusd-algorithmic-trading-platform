"""
State management for the MT5 Execution Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .models import OrderResult


@dataclass
class MT5ExecutionState:
    """
    Maintains runtime state for the execution engine.
    """

    initialized: bool = False

    connected: bool = False

    account_loaded: bool = False

    last_order: OrderResult | None = None

    open_position_count: int = 0

    total_orders_sent: int = 0

    last_connection_time: datetime | None = None

    last_disconnection_time: datetime | None = None

    error_count: int = 0

    metadata: dict[str, str] = field(
        default_factory=dict,
    )

    def reset(self) -> None:
        """
        Reset runtime state.
        """

        self.initialized = False

        self.connected = False

        self.account_loaded = False

        self.last_order = None

        self.open_position_count = 0

        self.total_orders_sent = 0

        self.last_connection_time = None

        self.last_disconnection_time = None

        self.error_count = 0

        self.metadata.clear()