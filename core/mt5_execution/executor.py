"""
MT5 Execution Engine.
"""

from __future__ import annotations

from datetime import UTC, datetime

import MetaTrader5 as mt5

from .config import MT5ExecutionConfig
from .models import OrderRequest, OrderResult
from .orders import send_order
from .state import MT5ExecutionState


class MT5Executor:
    """
    Manages the MT5 connection lifecycle.
    """

    def __init__(
        self,
        config: MT5ExecutionConfig,
    ) -> None:

        self.config = config

        self.state = MT5ExecutionState()

    def initialize(self) -> bool:
        """
        Initialize the MT5 terminal connection.
        """

        if not mt5.initialize():

            self.state.error_count += 1

            return False

        self.state.initialized = True

        self.state.connected = True

        self.state.last_connection_time = datetime.now(UTC)

        return True

    def execute_order(
        self,
        request: OrderRequest,
    ) -> OrderResult:
        """
        Execute an approved trading order.
        """

        if not self.state.connected:
            raise RuntimeError(
                "MT5Executor is not connected."
            )

        return send_order(
            request=request,
            config=self.config,
        )

    def is_connected(self) -> bool:
        """
        Return MT5 connection status.
        """

        return self.state.connected

    def shutdown(self) -> None:
        """
        Close the MT5 connection.
        """

        mt5.shutdown()

        self.state.connected = False

        self.state.last_disconnection_time = datetime.now(UTC)

        self.state.initialized = False