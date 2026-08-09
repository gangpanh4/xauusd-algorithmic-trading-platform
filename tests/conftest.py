"""Pytest safety and import configuration for the offline test suite."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-broker-tests",
        action="store_true",
        default=False,
        help="Run tests marked broker that may contact MetaTrader 5.",
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
    """Skip explicitly marked broker tests unless the user opts in."""

    if config.getoption("--run-broker-tests"):
        return

    skip_broker = pytest.mark.skip(
        reason=(
            "requires an explicitly authorized MT5 or broker connection; "
            "pass --run-broker-tests to opt in"
        )
    )
    for item in items:
        if item.get_closest_marker("broker") is not None:
            item.add_marker(skip_broker)
