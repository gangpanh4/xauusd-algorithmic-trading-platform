from core.mt5_execution.config import (
    MT5ExecutionConfig,
)

from core.mt5_execution.executor import (
    MT5Executor,
)

from core.mt5_execution.price_levels import (
    calculate_price_levels,
)

from core.mt5_execution.models import (
    OrderRequest,
    OrderSide,
)

from core.mt5_execution.orders import (
    get_market_price,
    send_order,
)



def test_order_execution():

    executor = MT5Executor(
        MT5ExecutionConfig(),
    )

    if not executor.initialize():

        print("Connection failed.")

        return

    entry_price = get_market_price(
        "XAUUSD",
        OrderSide.BUY,
    )

    levels = calculate_price_levels(
        entry_price=entry_price,
        side=OrderSide.BUY,
        stop_loss_distance=2.0,
        risk_reward_ratio=2.0,
    )

    request = OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=0.01,
        entry_price=entry_price,
        stop_loss=levels.stop_loss,
        take_profit=levels.take_profit,
        comment="Version 3.1 Execution Test",
    )

    print()
    print("=" * 60)
    print("ORDER LEVELS")
    print("=" * 60)
    print(f"Entry Price : {entry_price:.2f}")
    print(f"Stop Loss  : {levels.stop_loss:.2f}")
    print(f"Take Profit: {levels.take_profit:.2f}")
    print("=" * 60)

    result = send_order(
        request,
        executor.config,
    )

    print()

    print("=" * 60)
    print("ORDER EXECUTION RESULT")
    print("=" * 60)

    print(f"Status   : {result.status.value}")
    print(f"Ticket   : {result.ticket}")
    print(f"Price    : {result.executed_price}")
    print(f"Message  : {result.message}")

    print("=" * 60)

    executor.shutdown()


if __name__ == "__main__":
    test_order_execution()