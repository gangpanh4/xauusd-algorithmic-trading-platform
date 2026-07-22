from core.mt5_execution.config import MT5ExecutionConfig
from core.mt5_execution.executor import MT5Executor


def test_get_position():
    """
    Manual integration test.

    Requires:
    - Running MT5 terminal
    - Logged in account
    - Existing open position

    Skipped during automated pytest.
    """

    return

    executor = MT5Executor(MT5ExecutionConfig())

    assert executor.initialize()

    ticket = 123456789

    position = executor.get_position(ticket)

    assert position is not None