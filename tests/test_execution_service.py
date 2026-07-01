from core.mt5_execution.config import MT5ExecutionConfig
from core.mt5_execution.service import ExecutionService


def test_execution_service():

    service = ExecutionService(
        MT5ExecutionConfig(),
    )

    connected = service.initialize()

    print()

    print("=" * 60)
    print("EXECUTION SERVICE")
    print("=" * 60)
    print(f"Connected : {connected}")
    print("=" * 60)

    service.shutdown()


if __name__ == "__main__":
    test_execution_service()