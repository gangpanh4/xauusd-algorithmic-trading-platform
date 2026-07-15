"""
Unit tests for the Order Block package exports.
"""

from __future__ import annotations

from core.order_block_detector import (
    OrderBlock,
    OrderBlockAnalysis,
    OrderBlockCandidate,
    OrderBlockDetector,
    OrderBlockDetectorConfig,
    OrderBlockDetectorState,
    OrderBlockEvent,
    OrderBlockValidator,
)


def test_package_exports() -> None:
    """
    The package should export all public API objects.
    """

    assert OrderBlock is not None
    assert OrderBlockAnalysis is not None
    assert OrderBlockCandidate is not None

    assert OrderBlockDetector is not None
    assert OrderBlockDetectorConfig is not None
    assert OrderBlockDetectorState is not None

    assert OrderBlockEvent is not None
    assert OrderBlockValidator is not None