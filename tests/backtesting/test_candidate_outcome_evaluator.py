from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from core.backtesting.candidate_outcome_evaluator import (
    CandidateOutcomeEvaluator,
)
from core.backtesting.candidate_outcome_models import CandidateOutcome
from core.data.models import MarketBar
from core.market_structure.enums import MarketTrend
from core.market_structure.models import StructureState
from core.multi_timeframe.enums import Timeframe
from core.strategies import (
    CandidateTrade,
    EntryTrigger,
    EntryTriggerStatus,
    EntryTriggerType,
    PriceReference,
    PriceReferenceType,
    SetupDirection,
    SetupStatus,
    TradingSetup,
)


def _candidate(
    direction: SetupDirection = SetupDirection.BUY,
) -> CandidateTrade:
    created = datetime(2026, 1, 1, tzinfo=UTC)
    buy = direction is SetupDirection.BUY
    entry = 3300.0
    stop = 3290.0 if buy else 3310.0
    targets = (3320.0, 3330.0) if buy else (3280.0, 3270.0)
    setup = TradingSetup(
        setup_id=uuid4(),
        strategy_id="XAUUSD_BOS_CHOCH_V1",
        direction=direction,
        status=SetupStatus.TRIGGERED,
        setup_timeframe=Timeframe.M15,
        trigger_timeframe=Timeframe.M5,
        detected_at=created - timedelta(minutes=5),
        expires_at=created + timedelta(minutes=45),
        structure_state=StructureState(
            timestamp=created,
            current_bar_index=10,
            trend=(
                MarketTrend.BULLISH
                if buy
                else MarketTrend.BEARISH
            ),
        ),
        invalidation=PriceReference(
            reference_type=PriceReferenceType.SETUP_INVALIDATION,
            price=stop,
            timeframe=Timeframe.M15,
            source="test",
        ),
        stop_reference=PriceReference(
            reference_type=PriceReferenceType.PROTECTED_SWING,
            price=stop,
            timeframe=Timeframe.M15,
            source="test",
        ),
        target_references=tuple(
            PriceReference(
                reference_type=(
                    PriceReferenceType.HIGHER_TIMEFRAME_LEVEL
                ),
                price=target,
                timeframe=Timeframe.H1,
                source="test",
            )
            for target in targets
        ),
        required_conditions=("test",),
    )
    trigger = EntryTrigger(
        setup_id=setup.setup_id,
        trigger_type=EntryTriggerType.BOS_CONFIRMATION,
        status=EntryTriggerStatus.CONFIRMED,
        timeframe=Timeframe.M5,
        observed_at=created,
        trigger_price=entry,
        confirmation_bar_index=10,
        reason="test",
    )
    return CandidateTrade(
        setup=setup,
        trigger=trigger,
        created_at=created,
        entry_price=entry,
        stop_loss_price=stop,
        take_profit_prices=targets,
    )


def _bar(
    minutes: int,
    *,
    high: float,
    low: float,
) -> MarketBar:
    return MarketBar(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC)
        + timedelta(minutes=minutes),
        open=3300.0,
        high=high,
        low=low,
        close=3300.0,
        tick_volume=100,
    )


def test_buy_candidate_target_outcome_and_excursions() -> None:
    evaluation = CandidateOutcomeEvaluator().evaluate(
        _candidate(),
        (
            _bar(5, high=3310.0, low=3298.0),
            _bar(10, high=3322.0, low=3297.0),
        ),
    )

    assert evaluation.outcome is CandidateOutcome.TARGET_REACHED
    assert evaluation.outcome_timestamp == _bar(
        10,
        high=3322.0,
        low=3297.0,
    ).timestamp
    assert evaluation.highest_target_index_reached == 0
    assert evaluation.maximum_favorable_excursion == 22.0
    assert evaluation.maximum_adverse_excursion == 3.0
    assert evaluation.maximum_favorable_r_multiple == 2.2
    assert evaluation.maximum_adverse_r_multiple == 0.3


def test_same_bar_stop_and_target_is_ambiguous() -> None:
    evaluation = CandidateOutcomeEvaluator().evaluate(
        _candidate(),
        (_bar(5, high=3321.0, low=3289.0),),
    )

    assert evaluation.outcome is CandidateOutcome.AMBIGUOUS_SAME_BAR
    assert evaluation.highest_target_index_reached == 0


def test_sell_candidate_stop_outcome() -> None:
    candidate = _candidate(SetupDirection.SELL)
    evaluation = CandidateOutcomeEvaluator().evaluate(
        candidate,
        (_bar(5, high=3311.0, low=3295.0),),
    )

    assert evaluation.outcome is CandidateOutcome.STOP_REACHED
    assert evaluation.maximum_favorable_excursion == 5.0
    assert evaluation.maximum_adverse_excursion == 11.0


def test_created_bar_is_excluded_and_horizon_can_limit_evaluation() -> None:
    candidate = _candidate()
    created_bar = replace(
        _bar(5, high=3325.0, low=3285.0),
        timestamp=candidate.created_at,
    )

    evaluation = CandidateOutcomeEvaluator().evaluate(
        candidate,
        (
            created_bar,
            _bar(5, high=3310.0, low=3298.0),
            _bar(10, high=3325.0, low=3298.0),
        ),
        maximum_bars=1,
    )

    assert evaluation.outcome is CandidateOutcome.UNRESOLVED
    assert evaluation.bars_evaluated == 1
    assert evaluation.evaluated_through == _bar(
        5,
        high=3310.0,
        low=3298.0,
    ).timestamp
