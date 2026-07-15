"""
Unit tests for the Confluence Engine.
"""

from __future__ import annotations

from core.confluence_engine.engine import (
    ConfluenceEngine,
)


def test_engine_initializes() -> None:
    """
    Engine should initialize correctly.
    """

    engine = ConfluenceEngine()

    assert engine.state.processed_count == 0
    assert engine.state.approved_count == 0
    assert engine.state.rejected_count == 0
    assert engine.state.last_result is None
    assert engine.state.history == []


def test_reset() -> None:
    """
    Reset should restore runtime state.
    """

    engine = ConfluenceEngine()

    engine.state.processed_count = 5
    engine.state.approved_count = 2
    engine.state.rejected_count = 3

    engine.reset()

    assert engine.state.processed_count == 0
    assert engine.state.approved_count == 0
    assert engine.state.rejected_count == 0
    assert engine.state.history == []


def test_full_confluence_is_approved() -> None:
    """
    All factors passing should approve the setup.
    """

    engine = ConfluenceEngine()

    result = engine.evaluate(
        liquidity=True,
        bos=True,
        choch=True,
        order_block=True,
        fair_value_gap=True,
        trend=True,
    )

    assert result.approved
    assert result.score == result.maximum_score
    assert result.percentage == 100.0


def test_partial_confluence_is_rejected() -> None:
    """
    Weak confluence should be rejected.
    """

    engine = ConfluenceEngine()

    result = engine.evaluate(
        liquidity=False,
        bos=True,
        choch=False,
        order_block=False,
        fair_value_gap=False,
        trend=False,
    )

    assert not result.approved


def test_processed_counter() -> None:
    """
    Engine should count processed evaluations.
    """

    engine = ConfluenceEngine()

    engine.evaluate(
        liquidity=True,
        bos=True,
        choch=True,
        order_block=True,
        fair_value_gap=True,
        trend=True,
    )

    engine.evaluate(
        liquidity=False,
        bos=False,
        choch=False,
        order_block=False,
        fair_value_gap=False,
        trend=False,
    )

    assert engine.state.processed_count == 2


def test_history_is_updated() -> None:
    """
    Every evaluation should be stored.
    """

    engine = ConfluenceEngine()

    result = engine.evaluate(
        liquidity=True,
        bos=True,
        choch=True,
        order_block=True,
        fair_value_gap=True,
        trend=True,
    )

    assert engine.state.last_result is result
    assert len(engine.state.history) == 1


def test_factor_count() -> None:
    """
    Six confluence factors should always be evaluated.
    """

    engine = ConfluenceEngine()

    result = engine.evaluate(
        liquidity=True,
        bos=True,
        choch=True,
        order_block=True,
        fair_value_gap=True,
        trend=True,
    )

    assert len(result.factors) == 6