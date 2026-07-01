"""
High-level MT5 execution service.
"""

from __future__ import annotations

from requests import request

from .config import MT5ExecutionConfig
from .executor import MT5Executor

from .models import (
    OrderRequest,
    OrderResult,
)

from .orders import (
    send_order,
)


class ExecutionService:
    """
    High-level interface for MT5 trade execution.
    """

    def __init__(
        self,
        config: MT5ExecutionConfig,
    ) -> None:

        self.config = config

        self.executor = MT5Executor(
            config,
        )

    
    def execute_trade(
        self,
        request: OrderRequest,
    ) -> OrderResult:
        """
        Execute a validated trade request.
        """

        return send_order(
            request,
            self.config,
        )


    def initialize(
        self,
    ) -> bool:
        """
        Initialize the MT5 execution service.
        """

        return self.executor.initialize()

    def shutdown(
        self,
    ) -> None:
        """
        Shutdown the MT5 execution service.
        """

        self.executor.shutdown()