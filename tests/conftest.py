"""Pytest safety and import configuration for the offline test suite."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_BROKER_TEST_FILES = frozenset(
    {
        "test_execution_service.py",
        "test_mt5_account.py",
        "test_mt5_connection.py",
        "test_mt5_positions.py",
        "test_mt5_symbol.py",
        "test_order_execution.py",
        "test_order_validation.py",
    }
)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-broker-tests",
        action="store_true",
        default=False,
        help="Run tests that may initialize MetaTrader 5 or contact a broker.",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Make project imports deterministic before test modules are imported."""

    root_text = str(_PROJECT_ROOT)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)

    # Duplicate test basenames exist in separate package folders. Importlib
    # mode avoids loading them under the same top-level module name.
    config.option.importmode = "importlib"
    config.addinivalue_line(
        "markers",
        "broker: requires an explicitly authorized MT5 or broker connection",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Skip broker-facing tests unless the user explicitly opts in."""

    if config.getoption("--run-broker-tests"):
        return

    skip_broker = pytest.mark.skip(
        reason="broker-facing test disabled; pass --run-broker-tests to opt in"
    )
    for item in items:
        if Path(str(item.path)).name in _BROKER_TEST_FILES:
            item.add_marker(skip_broker)
