from core.mt5_execution.account import get_account_info
from core.mt5_execution.config import MT5ExecutionConfig
from core.mt5_execution.executor import MT5Executor
from core.mt5_execution.symbols import get_symbol_info


def test_symbol():

    executor = MT5Executor(
        MT5ExecutionConfig(),
    )

    if not executor.initialize():

        print("Connection failed.")

        return

    symbol = get_symbol_info("XAUUSD")

    print()
    print("=" * 50)
    print("SYMBOL INFORMATION")
    print("=" * 50)

    print(f"Name         : {symbol.name}")
    print(f"Digits       : {symbol.digits}")
    print(f"Point        : {symbol.point}")
    print(f"Spread       : {symbol.spread}")
    print(f"Minimum Lot  : {symbol.volume_min}")
    print(f"Maximum Lot  : {symbol.volume_max}")
    print(f"Lot Step     : {symbol.volume_step}")
    print(f"Trade Enabled: {symbol.trade_allowed}")

    print("=" * 50)

    executor.shutdown()


if __name__ == "__main__":
    test_symbol()