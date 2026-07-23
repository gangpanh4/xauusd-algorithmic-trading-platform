from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from core.backtesting.candidate_outcome_models import (
    CandidateOutcome,
    CandidateOutcomeEvaluation,
)
from core.backtesting.candidate_outcome_segmentation import (
    CandidateOutcomeSegmentationCalculator,
)
from core.multi_timeframe.enums import Timeframe
from core.strategies import SetupDirection


def _evaluation(
    *,
    outcome: CandidateOutcome,
    direction: SetupDirection | None,
    strategy_id: str | None,
    setup_timeframe: Timeframe | None,
    trigger_timeframe: Timeframe | None,
    trigger_reason: str | None,
    mfe_r: float,
    mae_r: float,
    bars: int,
) -> CandidateOutcomeEvaluation:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    return CandidateOutcomeEvaluation(
        setup_id=uuid4(),
        candidate_created_at=timestamp,
        evaluated_through=timestamp,
        outcome=outcome,
        outcome_timestamp=(
            timestamp
            if outcome is not CandidateOutcome.UNRESOLVED
            else None
        ),
        entry_price=3300.0,
        stop_loss_price=3290.0,
        take_profit_prices=(3320.0,),
        highest_target_index_reached=(
            0
            if outcome is CandidateOutcome.TARGET_REACHED
            else None
        ),
        bars_evaluated=bars,
        maximum_favorable_excursion=mfe_r * 10.0,
        maximum_adverse_excursion=mae_r * 10.0,
        maximum_favorable_r_multiple=mfe_r,
        maximum_adverse_r_multiple=mae_r,
        strategy_id=strategy_id,
        direction=direction,
        setup_timeframe=setup_timeframe,
        trigger_timeframe=trigger_timeframe,
        trigger_reason=trigger_reason,
    )


def _as_dict(segments):
    return {
        segment.key: segment.statistics
        for segment in segments
    }


def test_segments_candidate_statistics_by_typed_provenance() -> None:
    evaluations = (
        _evaluation(
            outcome=CandidateOutcome.TARGET_REACHED,
            direction=SetupDirection.BUY,
            strategy_id="XAUUSD_BOS_CHOCH_V1",
            setup_timeframe=Timeframe.M15,
            trigger_timeframe=Timeframe.M5,
            trigger_reason="M5 BOS",
            mfe_r=2.0,
            mae_r=0.2,
            bars=4,
        ),
        _evaluation(
            outcome=CandidateOutcome.STOP_REACHED,
            direction=SetupDirection.BUY,
            strategy_id="XAUUSD_BOS_CHOCH_V1",
            setup_timeframe=Timeframe.M15,
            trigger_timeframe=Timeframe.M5,
            trigger_reason="M5 BOS",
            mfe_r=0.4,
            mae_r=1.0,
            bars=2,
        ),
        _evaluation(
            outcome=CandidateOutcome.UNRESOLVED,
            direction=SetupDirection.SELL,
            strategy_id="XAUUSD_BOS_CHOCH_V1",
            setup_timeframe=Timeframe.M15,
            trigger_timeframe=Timeframe.M5,
            trigger_reason="M5 CHOCH",
            mfe_r=0.8,
            mae_r=0.3,
            bars=8,
        ),
    )

    result = CandidateOutcomeSegmentationCalculator.calculate(evaluations)

    by_direction = _as_dict(result.by_direction)
    assert tuple(by_direction) == ("BUY", "SELL")
    assert by_direction["BUY"].total_candidates == 2
    assert by_direction["BUY"].target_reached_count == 1
    assert by_direction["BUY"].stop_reached_count == 1
    assert by_direction["BUY"].target_hit_rate == 0.5
    assert by_direction["BUY"].average_mfe_r == pytest.approx(1.2)

    by_reason = _as_dict(result.by_trigger_reason)
    assert by_reason["M5 BOS"].total_candidates == 2
    assert by_reason["M5 CHOCH"].unresolved_count == 1

    by_strategy = _as_dict(result.by_strategy_id)
    assert by_strategy["XAUUSD_BOS_CHOCH_V1"].total_candidates == 3

    by_setup_timeframe = _as_dict(result.by_setup_timeframe)
    assert by_setup_timeframe["M15"].total_candidates == 3

    by_trigger_timeframe = _as_dict(result.by_trigger_timeframe)
    assert by_trigger_timeframe["M5"].total_candidates == 3


def test_missing_provenance_is_grouped_as_unknown() -> None:
    result = CandidateOutcomeSegmentationCalculator.calculate(
        (
            _evaluation(
                outcome=CandidateOutcome.UNRESOLVED,
                direction=None,
                strategy_id=None,
                setup_timeframe=None,
                trigger_timeframe=None,
                trigger_reason=None,
                mfe_r=0.0,
                mae_r=0.0,
                bars=0,
            ),
        )
    )

    assert result.by_direction[0].key == "UNKNOWN"
    assert result.by_strategy_id[0].key == "UNKNOWN"
    assert result.by_setup_timeframe[0].key == "UNKNOWN"
    assert result.by_trigger_timeframe[0].key == "UNKNOWN"
    assert result.by_trigger_reason[0].key == "UNKNOWN"


def test_empty_evaluations_return_empty_segments() -> None:
    result = CandidateOutcomeSegmentationCalculator.calculate(())

    assert result.by_strategy_id == ()
    assert result.by_direction == ()
    assert result.by_setup_timeframe == ()
    assert result.by_trigger_timeframe == ()
    assert result.by_trigger_reason == ()


def test_rejects_invalid_evaluations() -> None:
    with pytest.raises(TypeError, match="sequence"):
        CandidateOutcomeSegmentationCalculator.calculate("invalid")

    with pytest.raises(
        TypeError,
        match="CandidateOutcomeEvaluation",
    ):
        CandidateOutcomeSegmentationCalculator.calculate((object(),))
