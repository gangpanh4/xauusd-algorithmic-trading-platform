from core.mt5_execution.models import (
    OrderRequest,
    OrderSide,
)
from core.mt5_execution.orders import (
    validate_order,
)
from core.mt5_execution.symbols import (
    get_symbol_info,
)
from core.mt5_execution.config import (
    MT5ExecutionConfig,
)
from core.mt5_execution.executor import (
    MT5Executor,
)


def test_validation():

    executor = MT5Executor(
        MT5ExecutionConfig(),
    )

    if not executor.initialize():
        print("Connection failed.")
        return

    symbol = get_symbol_info("XAUUSD")

    request = OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=0.01,
        entry_price=0.0,
        stop_loss=3350.00,
        take_profit=3370.00,
        comment="Validation Test",
    )

    valid, message = validate_order(
        request,
        symbol,
    )

    print()
    print("=" * 50)
    print("ORDER VALIDATION")
    print("=" * 50)

    print(f"Valid   : {valid}")
    print(f"Message : {message}")

    print("=" * 50)

    executor.shutdown()


if __name__ == "__main__":
    test_validation()