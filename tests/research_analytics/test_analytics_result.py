from __future__ import annotations

from core.research_analytics.analytics_result import (
    ResearchAnalyticsResult,
)


def test_research_analytics_result_creation() -> None:
    """
    ResearchAnalyticsResult should correctly store
    all computed research statistics.
    """

    result = ResearchAnalyticsResult(
        total_trades=100,
        winning_trades=55,
        losing_trades=40,
        breakeven_trades=5,
        win_rate=0.55,
        average_profit=1.25,
        average_probability=0.84,
        average_confidence=0.91,
    )

    assert result.total_trades == 100
    assert result.winning_trades == 55
    assert result.losing_trades == 40
    assert result.breakeven_trades == 5
    assert result.win_rate == 0.55
    assert result.average_profit == 1.25
    assert result.average_probability == 0.84
    assert result.average_confidence == 0.91


def test_research_analytics_result_zero_values() -> None:
    """
    ResearchAnalyticsResult should support
    empty research sessions.
    """

    result = ResearchAnalyticsResult(
        total_trades=0,
        winning_trades=0,
        losing_trades=0,
        breakeven_trades=0,
        win_rate=0.0,
        average_profit=0.0,
        average_probability=0.0,
        average_confidence=0.0,
    )

    assert result.total_trades == 0
    assert result.winning_trades == 0
    assert result.losing_trades == 0
    assert result.breakeven_trades == 0
    assert result.win_rate == 0.0
    assert result.average_profit == 0.0
    assert result.average_probability == 0.0
    assert result.average_confidence == 0.0