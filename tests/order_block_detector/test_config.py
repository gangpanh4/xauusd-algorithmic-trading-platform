"""
Unit tests for the Order Block detector configuration.
"""

from __future__ import annotations

from dataclasses import fields

from core.order_block_detector.config import (
    OrderBlockDetectorConfig,
)


def test_default_configuration() -> None:
    """
    The default configuration should be constructible.
    """

    config = OrderBlockDetectorConfig()

    assert config is not None


def test_configuration_is_mutable() -> None:
    """
    Configuration fields should be mutable.
    """

    config = OrderBlockDetectorConfig()

    changed = False

    for field in fields(config):

        value = getattr(config, field.name)

        if isinstance(value, bool):
            setattr(config, field.name, not value)
            changed = True

        elif isinstance(value, int):
            setattr(config, field.name, value + 1)
            changed = True

        elif isinstance(value, float):
            setattr(config, field.name, value + 0.1)
            changed = True

    assert changed