from core.mt5_execution.account import (
    get_account_info,
)

from core.mt5_execution.config import (
    MT5ExecutionConfig,
)

from core.mt5_execution.executor import (
    MT5Executor,
)


def test_account():

    executor = MT5Executor(
        MT5ExecutionConfig(),
    )

    if not executor.initialize():

        print("Connection failed.")

        return

    account = get_account_info()

    print()
    print("=" * 50)
    print("MT5 ACCOUNT INFORMATION")
    print("=" * 50)

    print(f"Login       : {account.login}")
    print(f"Server      : {account.server}")
    print(f"Balance     : {account.balance:.2f}")
    print(f"Equity      : {account.equity:.2f}")
    print(f"Margin      : {account.margin:.2f}")
    print(f"Free Margin : {account.free_margin:.2f}")
    print(f"Leverage    : {account.leverage}")
    print(f"Currency    : {account.currency}")

    print("=" * 50)

    executor.shutdown()


if __name__ == "__main__":
    test_account()