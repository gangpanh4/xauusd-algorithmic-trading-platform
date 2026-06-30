from core.mt5_execution.config import (
    MT5ExecutionConfig,
)
from core.mt5_execution.executor import (
    MT5Executor,
)
from core.mt5_execution.positions import (
    get_open_positions,
)


def test_positions():

    executor = MT5Executor(
        MT5ExecutionConfig(),
    )

    if not executor.initialize():

        print("Connection failed.")

        return

    positions = get_open_positions()

    print()
    print("=" * 60)
    print("OPEN POSITIONS")
    print("=" * 60)

    if not positions:

        print("No open positions.")

    else:

        for position in positions:

            print()

            print(f"Ticket     : {position.ticket}")
            print(f"Symbol     : {position.symbol}")
            print(f"Direction  : {position.side.value}")
            print(f"Volume     : {position.volume}")
            print(f"Open Price : {position.open_price}")
            print(f"Stop Loss  : {position.stop_loss}")
            print(f"Take Profit: {position.take_profit}")
            print(f"Profit     : {position.profit:.2f}")

    print("=" * 60)

    executor.shutdown()


if __name__ == "__main__":
    test_positions()