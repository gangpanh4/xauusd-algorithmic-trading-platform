"""
XAUUSD Algorithmic Trading Platform

Main Entry Point

Usage
-----

Backtesting
    python main.py backtest

Live Trading
    python main.py live

Research
    python main.py research
"""

from __future__ import annotations

import argparse
import logging
import sys

from core.platform import PlatformMode, TradingPlatform


logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """
    Build the command-line interface.
    """
    parser = argparse.ArgumentParser(
        prog="XAUUSD Trading Platform",
        description="Professional quantitative trading platform.",
    )

    parser.add_argument(
        "mode",
        choices=[mode.value for mode in PlatformMode],
        help="Execution mode.",
    )

    return parser


def main() -> int:
    """
    Platform entry point.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    parser = build_parser()
    args = parser.parse_args()

    platform = TradingPlatform()

    try:

        platform.initialize()

        mode = PlatformMode(args.mode)

        logger.info("Selected mode: %s", mode.value)

        if mode is PlatformMode.BACKTEST:
            platform.run_backtest()

        elif mode is PlatformMode.LIVE:
            platform.run_live()

        elif mode is PlatformMode.RESEARCH:
            platform.run_research()

        else:
            parser.error(f"Unsupported mode: {mode}")

        return 0

    except KeyboardInterrupt:

        logger.warning("Interrupted by user.")
        return 130

    except Exception:

        logger.exception("Platform execution failed.")
        return 1

    finally:

        platform.shutdown()


if __name__ == "__main__":
    sys.exit(main())