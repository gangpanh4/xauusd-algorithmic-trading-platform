"""
Test the MT5 History Loader.
"""

from __future__ import annotations

import MetaTrader5 as mt5

from core.backtesting.history_loader import (
    HistoryLoader,
)


def main() -> None:
    """
    Test loading historical market data from MT5.
    """

    if not mt5.initialize():
        raise RuntimeError(
            f"MT5 initialization failed: {mt5.last_error()}"
        )

    loader = HistoryLoader()

    history = loader.load_history(
        symbol="XAUUSD",
        timeframe=mt5.TIMEFRAME_M5,
        bars=100,
    )

    print()
    print("=" * 60)
    print("HISTORY LOADER")
    print("=" * 60)
    print(f"Bars Loaded : {len(history)}")

    if history:
        print(f"First Bar   : {history[0].timestamp}")
        print(f"Last Bar    : {history[-1].timestamp}")

    print("=" * 60)
    print()

    mt5.shutdown()


if __name__ == "__main__":
    main()