from core.mt5_execution.config import MT5ExecutionConfig
from core.mt5_execution.executor import MT5Executor


def test_close_position():
    """
    Integration test.

    Requires:
    - MT5 terminal
    - Logged in account
    - Existing open position

    This test is intentionally skipped during automated pytest runs.
    """

    # Skip interactive integration test.
    return

    executor = MT5Executor(MT5ExecutionConfig())

    assert executor.initialize()

    ticket = 123456789

    result = executor.close_position(ticket)

    assert result is not None