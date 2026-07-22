from core.mt5_execution.config import (
    MT5ExecutionConfig,
)

from core.mt5_execution.executor import (
    MT5Executor,
)


def test_connection():

    executor = MT5Executor(
        MT5ExecutionConfig()
    )

    if executor.initialize():

        print()
        print("=" * 50)
        print("MT5 CONNECTION SUCCESS")
        print("=" * 50)

        executor.shutdown()

    else:

        print()
        print("=" * 50)
        print("MT5 CONNECTION FAILED")
        print("=" * 50)


if __name__ == "__main__":
    test_connection()