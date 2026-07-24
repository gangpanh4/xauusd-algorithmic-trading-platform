"""Comparison reporting for the active pipeline and observational strategy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.strategies import SetupDirection, StrategyObservation
from core.trading_pipeline.models import PipelineObservationAudit

from .models import BacktestResult
from .post_expiry_trigger_tracker import PostExpiryTriggerRecord


@dataclass(slots=True, frozen=True)
class StrategyComparisonEvent:
    """One timestamped pipeline or strategy milestone."""

    timestamp: datetime
    source: str
    event_type: str
    direction: str | None = None
    identifier: str | None = None


@dataclass(slots=True, frozen=True)
class StrategySetupLifecycle:
    """Aggregated observational lifecycle for one detected strategy setup."""

    setup_id: str
    strategy_id: str
    direction: str
    detected_at: datetime
    expires_at: datetime
    active_observation_count: int
    no_m5_event_count: int
    stale_m5_event_count: int
    direction_mismatch_count: int
    index_mismatch_count: int
    invalid_trade_geometry_count: int
    candidate_created: bool
    candidate_created_at: datetime | None
    terminal_status: str
    terminal_timestamp: datetime | None


@dataclass(slots=True, frozen=True)
class BacktestStrategyComparison:
    """Read-only comparison between pipeline activity and strategy activity."""

    pipeline_observation_count: int
    pipeline_approval_count: int
    executed_trade_count: int
    strategy_observation_count: int
    strategy_setup_count: int
    strategy_candidate_count: int
    pipeline_reason_counts: tuple[tuple[str, int], ...]
    strategy_reason_counts: tuple[tuple[str, int], ...]
    events: tuple[StrategyComparisonEvent, ...]
    setup_lifecycles: tuple[StrategySetupLifecycle, ...] = ()
    post_expiry_triggers: tuple[PostExpiryTriggerRecord, ...] = ()


class BacktestStrategyComparisonBuilder:
    """Build factual counts and timestamps without changing execution behavior."""

    @classmethod
    def build(
        cls,
        *,
        backtest_result: BacktestResult,
        pipeline_audits: tuple[PipelineObservationAudit, ...],
        strategy_observations: tuple[StrategyObservation, ...],
        post_expiry_triggers: tuple[PostExpiryTriggerRecord, ...] = (),
    ) -> BacktestStrategyComparison:
        if not isinstance(backtest_result, BacktestResult):
            raise TypeError('backtest_result must be BacktestResult')
        if any(
            not isinstance(audit, PipelineObservationAudit)
            for audit in pipeline_audits
        ):
            raise TypeError(
                'pipeline_audits must contain PipelineObservationAudit instances'
            )
        if any(
            not isinstance(observation, StrategyObservation)
            for observation in strategy_observations
        ):
            raise TypeError(
                'strategy_observations must contain StrategyObservation instances'
            )

        pipeline_reason_counts = cls._count_pipeline_reasons(pipeline_audits)
        strategy_reason_counts = cls._count_strategy_reasons(
            strategy_observations
        )
        pipeline_approvals = sum(
            audit.accepted
            for audit in pipeline_audits
        )
        strategy_setups = sum(
            observation.reason_code == 'SETUP_DETECTED'
            for observation in strategy_observations
        )
        strategy_candidates = sum(
            observation.candidate_trade is not None
            for observation in strategy_observations
        )

        events = cls._build_events(
            backtest_result=backtest_result,
            pipeline_audits=pipeline_audits,
            strategy_observations=strategy_observations,
        )
        setup_lifecycles = cls._build_setup_lifecycles(strategy_observations)

        return BacktestStrategyComparison(
            pipeline_observation_count=len(pipeline_audits),
            pipeline_approval_count=pipeline_approvals,
            executed_trade_count=backtest_result.total_trades,
            strategy_observation_count=len(strategy_observations),
            strategy_setup_count=strategy_setups,
            strategy_candidate_count=strategy_candidates,
            pipeline_reason_counts=tuple(pipeline_reason_counts.items()),
            strategy_reason_counts=tuple(strategy_reason_counts.items()),
            events=events,
            setup_lifecycles=setup_lifecycles,
            post_expiry_triggers=post_expiry_triggers,
        )

    @staticmethod
    def _count_pipeline_reasons(
        audits: tuple[PipelineObservationAudit, ...],
    ) -> dict[str, int]:
        counts: dict[str, int] = {}
        for audit in audits:
            key = audit.reason_code or 'APPROVED'
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items()))

    @staticmethod
    def _count_strategy_reasons(
        observations: tuple[StrategyObservation, ...],
    ) -> dict[str, int]:
        counts: dict[str, int] = {}
        for observation in observations:
            key = observation.reason_code
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items()))

    @staticmethod
    def _build_setup_lifecycles(
        observations: tuple[StrategyObservation, ...],
    ) -> tuple[StrategySetupLifecycle, ...]:
        """Aggregate exact per-setup diagnostic counts from observations."""

        tracked: dict[str, dict[str, object]] = {}

        for observation in observations:
            setup = observation.setup
            if setup is None:
                continue

            setup_id = str(setup.setup_id)
            record = tracked.get(setup_id)
            if record is None:
                record = {
                    "setup_id": setup_id,
                    "strategy_id": setup.strategy_id,
                    "direction": setup.direction.value,
                    "detected_at": setup.detected_at,
                    "expires_at": setup.expires_at,
                    "active_observation_count": 0,
                    "no_m5_event_count": 0,
                    "stale_m5_event_count": 0,
                    "direction_mismatch_count": 0,
                    "index_mismatch_count": 0,
                    "invalid_trade_geometry_count": 0,
                    "candidate_created": False,
                    "candidate_created_at": None,
                    "terminal_status": setup.status.value,
                    "terminal_timestamp": None,
                }
                tracked[setup_id] = record

            code = observation.reason_code
            if code not in {
                "SETUP_DETECTED",
                "EXPIRED",
                "INVALIDATED",
                "CANDIDATE_CREATED",
            }:
                record["active_observation_count"] = (
                    int(record["active_observation_count"]) + 1
                )

            counter_by_reason = {
                "NO_M5_STRUCTURE_EVENT": "no_m5_event_count",
                "M5_EVENT_NOT_FRESH": "stale_m5_event_count",
                "M5_DIRECTION_MISMATCH": "direction_mismatch_count",
                "M5_CONFIRMATION_INDEX_MISMATCH": "index_mismatch_count",
                "INVALID_TRADE_GEOMETRY": "invalid_trade_geometry_count",
            }
            counter = counter_by_reason.get(code)
            if counter is not None:
                record[counter] = int(record[counter]) + 1

            if observation.candidate_trade is not None:
                record["candidate_created"] = True
                record["candidate_created_at"] = observation.timestamp

            if code in {"EXPIRED", "INVALIDATED", "CANDIDATE_CREATED"}:
                record["terminal_status"] = (
                    "CONSUMED" if code == "CANDIDATE_CREATED" else code
                )
                record["terminal_timestamp"] = observation.timestamp
            else:
                record["terminal_status"] = setup.status.value

        return tuple(
            StrategySetupLifecycle(**record)
            for _, record in sorted(
                tracked.items(),
                key=lambda item: (
                    item[1]["detected_at"],
                    item[0],
                ),
            )
        )

    @classmethod
    def _build_events(
        cls,
        *,
        backtest_result: BacktestResult,
        pipeline_audits: tuple[PipelineObservationAudit, ...],
        strategy_observations: tuple[StrategyObservation, ...],
    ) -> tuple[StrategyComparisonEvent, ...]:
        events: list[StrategyComparisonEvent] = []

        for audit in pipeline_audits:
            event_type = audit.reason_code or 'APPROVED'
            if event_type == 'APPROVED':
                events.append(
                    StrategyComparisonEvent(
                        timestamp=audit.timestamp,
                        source='PIPELINE',
                        event_type='APPROVED',
                    )
                )

        for observation in strategy_observations:
            if observation.reason_code not in {
                'SETUP_DETECTED',
                'INVALIDATED',
                'EXPIRED',
                'CANDIDATE_CREATED',
            }:
                continue
            setup = observation.setup
            direction = (
                cls._direction_label(setup.direction)
                if setup is not None
                else None
            )
            identifier = (
                str(setup.setup_id)
                if setup is not None
                else None
            )
            events.append(
                StrategyComparisonEvent(
                    timestamp=observation.timestamp,
                    source='STRATEGY',
                    event_type=observation.reason_code,
                    direction=direction,
                    identifier=identifier,
                )
            )

        for trade in backtest_result.trades:
            events.append(
                StrategyComparisonEvent(
                    timestamp=trade.entry_time,
                    source='EXECUTION',
                    event_type='TRADE_ENTRY',
                    direction=trade.direction,
                )
            )

        return tuple(
            sorted(
                events,
                key=lambda event: (
                    event.timestamp,
                    event.source,
                    event.event_type,
                ),
            )
        )

    @staticmethod
    def _direction_label(direction: SetupDirection) -> str:
        return direction.value
