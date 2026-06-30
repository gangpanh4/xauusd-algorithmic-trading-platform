from pprint import pprint

from core.mt5_execution.models import (
    OrderRequest,
    OrderSide,
)
from core.mt5_execution.orders import (
    build_mt5_request,
)


def test_request():

    request = OrderRequest(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        volume=0.01,
        entry_price=3360.50,
        stop_loss=3355.00,
        take_profit=3370.00,
        comment="Version 3.1 Demo",
    )

    mt5_request = build_mt5_request(
        request,
        magic_number=30001,
        deviation=10,
    )

    print()

    print("=" * 60)
    print("MT5 REQUEST")
    print("=" * 60)

    pprint(mt5_request)

    print("=" * 60)


if __name__ == "__main__":
    test_request()