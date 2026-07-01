from core.mt5_execution.config import MT5ExecutionConfig
from core.mt5_execution.executor import MT5Executor
from core.mt5_execution.positions import get_position


def test_get_position():

    executor = MT5Executor(
        MT5ExecutionConfig(),
    )

    if not executor.initialize():
        print("Connection failed.")
        return

    ticket = int(input("Enter MT5 ticket: "))

    position = get_position(ticket)

    print()

    if position is None:
        print("Position not found.")
    else:
        print("=" * 50)
        print("POSITION")
        print("=" * 50)
        print(position)
        print("=" * 50)

    executor.shutdown()


if __name__ == "__main__":
    test_get_position()