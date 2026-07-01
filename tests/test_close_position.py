from core.mt5_execution.close_position import (
    close_position,
)
from core.mt5_execution.config import (
    MT5ExecutionConfig,
)
from core.mt5_execution.executor import (
    MT5Executor,
)


def test_close_position():

    executor = MT5Executor(
        MT5ExecutionConfig(),
    )

    if not executor.initialize():

        print("Connection failed.")

        return

    ticket = int(
        input("Position Ticket: ")
    )

    result = close_position(
        ticket,
        executor.config,
    )

    print()

    print("=" * 60)
    print("CLOSE POSITION RESULT")
    print("=" * 60)

    print(f"Status  : {result.status.value}")
    print(f"Ticket  : {result.ticket}")
    print(f"Price   : {result.executed_price}")
    print(f"Message : {result.message}")

    print("=" * 60)

    executor.shutdown()


if __name__ == "__main__":
    test_close_position()