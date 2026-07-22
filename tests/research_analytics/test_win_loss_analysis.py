from __future__ import annotations

import pytest

from core.research_analytics.win_loss_analysis import (
    WinLossAnalysis,
)


def make_analysis() -> WinLossAnalysis:
    """
    Create a sample WinLossAnalysis object.
    """

    return WinLossAnalysis(
        winning_probability=0.91,
        losing_probability=0.73,
        winning_structure=0.84,
        losing_structure=0.51,
        winning_liquidity=0.88,
        losing_liquidity=0.42,
    )


def test_probability_gap() -> None:
    """
    Probability gap should equal the difference
    between winning and losing probability.
    """

    analysis = make_analysis()

    assert analysis.probability_gap == pytest.approx(0.18)


def test_structure_gap() -> None:
    """
    Structure gap should equal the difference
    between winning and losing structure.
    """

    analysis = make_analysis()

    assert analysis.structure_gap == pytest.approx(0.33)


def test_liquidity_gap() -> None:
    """
    Liquidity gap should equal the difference
    between winning and losing liquidity.
    """

    analysis = make_analysis()

    assert analysis.liquidity_gap == pytest.approx(0.46)


def test_values_are_stored() -> None:
    """
    Constructor should correctly store
    supplied statistics.
    """

    analysis = make_analysis()

    assert analysis.winning_probability == 0.91
    assert analysis.losing_probability == 0.73

    assert analysis.winning_structure == 0.84
    assert analysis.losing_structure == 0.51

    assert analysis.winning_liquidity == 0.88
    assert analysis.losing_liquidity == 0.42


def test_zero_values() -> None:
    """
    Empty analysis should produce zero gaps.
    """

    analysis = WinLossAnalysis(
        winning_probability=0.0,
        losing_probability=0.0,
        winning_structure=0.0,
        losing_structure=0.0,
        winning_liquidity=0.0,
        losing_liquidity=0.0,
    )

    assert analysis.probability_gap == 0.0
    assert analysis.structure_gap == 0.0
    assert analysis.liquidity_gap == 0.0