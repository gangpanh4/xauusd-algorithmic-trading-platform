from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from core.backtesting.models import BacktestResult, BacktestTrade
from core.backtesting.strategy_comparison import (
    BacktestStrategyComparisonBuilder,
)
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
    StrategyObservation,
    TradingSetup,
)
from core.trading_pipeline.models import (
    PipelineDisposition,
    PipelineObservationAudit,
    PipelineStage,
)


def _setup(timestamp: datetime) -> TradingSetup:
    setup_id = uuid4()
    invalidation = PriceReference(
        reference_type=PriceReferenceType.SETUP_INVALIDATION,
        price=3280.0,
        timeframe=Timeframe.M15,
        source='test',
    )
    return TradingSetup(
        setup_id=setup_id,
        strategy_id='XAUUSD_BOS_CHOCH_V1',
        direction=SetupDirection.BUY,
        status=SetupStatus.ACTIVE,
        setup_timeframe=Timeframe.M15,
        trigger_timeframe=Timeframe.M5,
        detected_at=timestamp,
        expires_at=timestamp + timedelta(minutes=45),
        structure_state=StructureState(
            timestamp=timestamp,
            current_bar_index=10,
            trend=MarketTrend.BULLISH,
        ),
        invalidation=invalidation,
        stop_reference=PriceReference(
            reference_type=PriceReferenceType.PROTECTED_SWING,
            price=3280.0,
            timeframe=Timeframe.M15,
            source='test',
        ),
        target_references=(
            PriceReference(
                reference_type=PriceReferenceType.HIGHER_TIMEFRAME_LEVEL,
                price=3340.0,
                timeframe=Timeframe.H1,
                source='test',
            ),
        ),
        required_conditions=('test condition',),
    )


def test_comparison_reports_pipeline_strategy_and_execution_counts() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    setup = _setup(start)
    triggered = TradingSetup(
        **{
            **{field: getattr(setup, field) for field in setup.__dataclass_fields__},
            'status': SetupStatus.TRIGGERED,
        }
    )
    trigger = EntryTrigger(
        setup_id=setup.setup_id,
        trigger_type=EntryTriggerType.BOS_CONFIRMATION,
        status=EntryTriggerStatus.CONFIRMED,
        timeframe=Timeframe.M5,
        observed_at=start + timedelta(minutes=5),
        trigger_price=3300.0,
        confirmation_bar_index=11,
        reason='test trigger',
    )
    candidate = CandidateTrade(
        setup=triggered,
        trigger=trigger,
        created_at=trigger.observed_at,
        entry_price=3300.0,
        stop_loss_price=3280.0,
        take_profit_prices=(3340.0,),
    )

    audits = (
        PipelineObservationAudit(
            timestamp=start,
            disposition=PipelineDisposition.REJECTED,
            stage_reached=PipelineStage.PROBABILITY,
            rejection_stage=PipelineStage.PROBABILITY,
            reason_code='PROBABILITY_REJECTED',
        ),
        PipelineObservationAudit(
            timestamp=start + timedelta(minutes=5),
            disposition=PipelineDisposition.ACCEPTED,
            stage_reached=PipelineStage.APPROVED,
            risk_approved=True,
        ),
    )
    observations = (
        StrategyObservation(
            timestamp=start,
            setup=setup,
            trigger=None,
            candidate_trade=None,
            reason_code='SETUP_DETECTED',
            reason='setup',
        ),
        StrategyObservation(
            timestamp=start + timedelta(minutes=5),
            setup=triggered,
            trigger=trigger,
            candidate_trade=candidate,
            reason_code='CANDIDATE_CREATED',
            reason='candidate',
        ),
    )
    trade = BacktestTrade(
        entry_time=start + timedelta(minutes=10),
        exit_time=start + timedelta(minutes=20),
        direction='BUY',
        entry_price=3301.0,
        exit_price=3310.0,
        position_size=0.1,
    )
    result = BacktestResult(
        total_trades=1,
        winning_trades=1,
        losing_trades=0,
        breakeven_trades=0,
        net_profit=10.0,
        win_rate=100.0,
        max_drawdown=0.0,
        trades=[trade],
    )

    comparison = BacktestStrategyComparisonBuilder.build(
        backtest_result=result,
        pipeline_audits=audits,
        strategy_observations=observations,
    )

    assert comparison.pipeline_observation_count == 2
    assert comparison.pipeline_approval_count == 1
    assert comparison.executed_trade_count == 1
    assert comparison.strategy_observation_count == 2
    assert comparison.strategy_setup_count == 1
    assert comparison.strategy_candidate_count == 1
    assert dict(comparison.pipeline_reason_counts) == {
        'APPROVED': 1,
        'PROBABILITY_REJECTED': 1,
    }
    assert dict(comparison.strategy_reason_counts) == {
        'CANDIDATE_CREATED': 1,
        'SETUP_DETECTED': 1,
    }
    assert [event.event_type for event in comparison.events] == [
        'SETUP_DETECTED',
        'APPROVED',
        'CANDIDATE_CREATED',
        'TRADE_ENTRY',
    ]
