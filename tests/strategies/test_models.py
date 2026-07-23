from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

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


def _reference(
    reference_type: PriceReferenceType,
    price: float,
    timeframe: Timeframe,
) -> PriceReference:
    return PriceReference(
        reference_type=reference_type,
        price=price,
        timeframe=timeframe,
        source="test",
    )


def _setup(
    *,
    status: SetupStatus = SetupStatus.ACTIVE,
    direction: SetupDirection = SetupDirection.BUY,
) -> TradingSetup:
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    if direction is SetupDirection.BUY:
        invalidation = _reference(
            PriceReferenceType.SETUP_INVALIDATION,
            3280.0,
            Timeframe.M15,
        )
        stop = _reference(
            PriceReferenceType.PROTECTED_SWING,
            3279.5,
            Timeframe.M15,
        )
        targets = (
            _reference(
                PriceReferenceType.OPPOSING_LIQUIDITY,
                3320.0,
                Timeframe.H1,
            ),
        )
    else:
        invalidation = _reference(
            PriceReferenceType.SETUP_INVALIDATION,
            3320.0,
            Timeframe.M15,
        )
        stop = _reference(
            PriceReferenceType.PROTECTED_SWING,
            3320.5,
            Timeframe.M15,
        )
        targets = (
            _reference(
                PriceReferenceType.OPPOSING_LIQUIDITY,
                3280.0,
                Timeframe.H1,
            ),
        )

    return TradingSetup(
        setup_id=uuid4(),
        strategy_id="XAUUSD_BOS_CHOCH_V1",
        direction=direction,
        status=status,
        setup_timeframe=Timeframe.M15,
        trigger_timeframe=Timeframe.M5,
        detected_at=now,
        expires_at=now + timedelta(minutes=45),
        structure_state=StructureState(
            timestamp=now,
            current_bar_index=100,
            trend=MarketTrend.BULLISH,
        ),
        invalidation=invalidation,
        stop_reference=stop,
        target_references=targets,
        required_conditions=(
            "H1 bias aligned",
            "M15 structure setup confirmed",
        ),
    )


def test_active_setup_respects_expiration_and_cooldown() -> None:
    setup = _setup()
    assert setup.is_active_at(setup.detected_at)
    assert not setup.is_active_at(setup.expires_at)


def test_candidate_trade_requires_confirmed_matching_trigger() -> None:
    setup = _setup(status=SetupStatus.TRIGGERED)
    trigger = EntryTrigger(
        setup_id=setup.setup_id,
        trigger_type=EntryTriggerType.CONFIRMATION_CLOSE,
        status=EntryTriggerStatus.CONFIRMED,
        timeframe=Timeframe.M5,
        observed_at=setup.detected_at + timedelta(minutes=5),
        trigger_price=3300.0,
        confirmation_bar_index=101,
        reason="M5 confirmation close",
    )

    candidate = CandidateTrade(
        setup=setup,
        trigger=trigger,
        created_at=trigger.observed_at,
        entry_price=3300.0,
        stop_loss_price=3279.5,
        take_profit_prices=(3320.0, 3340.0),
    )

    assert candidate.initial_risk_distance == pytest.approx(20.5)
    assert candidate.reward_risk_ratios == pytest.approx(
        (20.0 / 20.5, 40.0 / 20.5)
    )


def test_candidate_trade_rejects_unconfirmed_trigger() -> None:
    setup = _setup(status=SetupStatus.TRIGGERED)
    trigger = EntryTrigger(
        setup_id=setup.setup_id,
        trigger_type=EntryTriggerType.CONFIRMATION_CLOSE,
        status=EntryTriggerStatus.PENDING,
        timeframe=Timeframe.M5,
        observed_at=setup.detected_at + timedelta(minutes=5),
        trigger_price=3300.0,
        confirmation_bar_index=101,
        reason="waiting for candle close",
    )

    with pytest.raises(ValueError, match="CONFIRMED trigger"):
        CandidateTrade(
            setup=setup,
            trigger=trigger,
            created_at=trigger.observed_at,
            entry_price=3300.0,
            stop_loss_price=3279.5,
            take_profit_prices=(3320.0,),
        )


def test_buy_candidate_rejects_stop_above_entry() -> None:
    setup = _setup(status=SetupStatus.TRIGGERED)
    trigger = EntryTrigger(
        setup_id=setup.setup_id,
        trigger_type=EntryTriggerType.CONFIRMATION_CLOSE,
        status=EntryTriggerStatus.CONFIRMED,
        timeframe=Timeframe.M5,
        observed_at=setup.detected_at + timedelta(minutes=5),
        trigger_price=3300.0,
        confirmation_bar_index=101,
        reason="M5 confirmation close",
    )

    with pytest.raises(ValueError, match="below entry_price"):
        CandidateTrade(
            setup=setup,
            trigger=trigger,
            created_at=trigger.observed_at,
            entry_price=3300.0,
            stop_loss_price=3301.0,
            take_profit_prices=(3320.0,),
        )
