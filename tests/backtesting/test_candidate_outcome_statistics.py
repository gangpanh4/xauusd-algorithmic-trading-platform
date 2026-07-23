from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from core.backtesting.candidate_outcome_models import (
    CandidateOutcome,
    CandidateOutcomeEvaluation,
)
from core.backtesting.candidate_outcome_statistics import (
    CandidateOutcomeStatisticsCalculator,
)


def _evaluation(
    *,
    outcome: CandidateOutcome,
    mfe_r: float,
    mae_r: float,
    bars: int,
    target_index: int | None = None,
) -> CandidateOutcomeEvaluation:
    created = datetime(2026, 1, 1, tzinfo=UTC)
    terminal = outcome is not CandidateOutcome.UNRESOLVED
    return CandidateOutcomeEvaluation(
        setup_id=uuid4(),
        candidate_created_at=created,
        evaluated_through=created + timedelta(minutes=bars * 5),
        outcome=outcome,
        outcome_timestamp=(
            created + timedelta(minutes=bars * 5)
            if terminal
            else None
        ),
        entry_price=3300.0,
        stop_loss_price=3290.0,
        take_profit_prices=(3320.0, 3330.0),
        highest_target_index_reached=target_index,
        bars_evaluated=bars,
        maximum_favorable_excursion=mfe_r * 10.0,
        maximum_adverse_excursion=mae_r * 10.0,
        maximum_favorable_r_multiple=mfe_r,
        maximum_adverse_r_multiple=mae_r,
    )


def test_calculates_candidate_validation_statistics() -> None:
    statistics = CandidateOutcomeStatisticsCalculator.calculate(
        (
            _evaluation(
                outcome=CandidateOutcome.TARGET_REACHED,
                mfe_r=2.0,
                mae_r=0.2,
                bars=4,
                target_index=0,
            ),
            _evaluation(
                outcome=CandidateOutcome.STOP_REACHED,
                mfe_r=0.5,
                mae_r=1.0,
                bars=2,
            ),
            _evaluation(
                outcome=CandidateOutcome.AMBIGUOUS_SAME_BAR,
                mfe_r=2.5,
                mae_r=1.1,
                bars=1,
                target_index=1,
            ),
            _evaluation(
                outcome=CandidateOutcome.UNRESOLVED,
                mfe_r=0.8,
                mae_r=0.3,
                bars=8,
            ),
        )
    )

    assert statistics.total_candidates == 4
    assert statistics.resolved_candidates == 3
    assert statistics.target_reached_count == 1
    assert statistics.stop_reached_count == 1
    assert statistics.ambiguous_same_bar_count == 1
    assert statistics.unresolved_count == 1
    assert statistics.target_hit_rate == 0.25
    assert statistics.stop_rate == 0.25
    assert statistics.ambiguous_same_bar_rate == 0.25
    assert statistics.unresolved_rate == 0.25
    assert statistics.average_mfe_r == pytest.approx(1.45)
    assert statistics.median_mfe_r == pytest.approx(1.4)
    assert statistics.average_mae_r == pytest.approx(0.65)
    assert statistics.median_mae_r == pytest.approx(0.65)
    assert statistics.average_bars_evaluated == pytest.approx(3.75)
    assert statistics.average_bars_to_terminal_outcome == pytest.approx(
        7 / 3
    )
    assert statistics.target_index_hit_counts == ((0, 1), (1, 1))


def test_empty_evaluations_return_zero_statistics() -> None:
    statistics = CandidateOutcomeStatisticsCalculator.calculate(())

    assert statistics.total_candidates == 0
    assert statistics.resolved_candidates == 0
    assert statistics.target_hit_rate == 0.0
    assert statistics.average_mfe_r == 0.0
    assert statistics.average_bars_to_terminal_outcome == 0.0
    assert statistics.target_index_hit_counts == ()


def test_rejects_invalid_evaluation_collection() -> None:
    with pytest.raises(TypeError, match="sequence"):
        CandidateOutcomeStatisticsCalculator.calculate("invalid")

    with pytest.raises(
        TypeError,
        match="CandidateOutcomeEvaluation",
    ):
        CandidateOutcomeStatisticsCalculator.calculate((object(),))
