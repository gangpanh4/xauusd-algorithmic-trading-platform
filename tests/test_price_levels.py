from core.mt5_execution.models import (
    OrderSide,
)

from core.mt5_execution.price_levels import (
    calculate_price_levels,
)

from core.mt5_execution.orders import (
    get_market_price,
)


def test_price_levels():

    levels = calculate_price_levels(
        entry_price=3360.50,
        side=OrderSide.BUY,
        stop_loss_distance=2.0,
        risk_reward_ratio=2.0,
    )

    print()

    print("=" * 50)
    print("PRICE LEVELS")
    print("=" * 50)

    print(f"Stop Loss  : {levels.stop_loss:.2f}")
    print(f"Take Profit: {levels.take_profit:.2f}")

    print("=" * 50)


if __name__ == "__main__":
    test_price_levels()