from __future__ import annotations

import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from core.backtesting.exporter import BacktestExporter
from core.backtesting.strategy_comparison import (
    BacktestStrategyComparison,
    BacktestStrategyComparisonBuilder,
)
from core.strategies.context import StrategyObservation
from core.strategies.enums import SetupDirection, SetupStatus


SETUP_ID = UUID("11111111-1111-1111-1111-111111111111")
DETECTED_AT = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _setup(*, status: SetupStatus = SetupStatus.ACTIVE):
    return SimpleNamespace(
        setup_id=SETUP_ID,
        strategy_id="XAUUSD_BOS_CHOCH_V1",
        direction=SetupDirection.BUY,
        detected_at=DETECTED_AT,
        expires_at=DETECTED_AT + timedelta(minutes=45),
        status=status,
    )


def _observation(
    *,
    minute: int,
    reason_code: str,
    status: SetupStatus = SetupStatus.ACTIVE,
    candidate: bool = False,
) -> StrategyObservation:
    return StrategyObservation(
        timestamp=DETECTED_AT + timedelta(minutes=minute),
        setup=_setup(status=status),
        trigger=None,
        candidate_trade=(object() if candidate else None),
        reason_code=reason_code,
        reason=reason_code,
    )


def test_builder_aggregates_one_lifecycle_per_setup() -> None:
    observations = (
        _observation(minute=0, reason_code="SETUP_DETECTED"),
        _observation(minute=5, reason_code="NO_M5_STRUCTURE_EVENT"),
        _observation(minute=10, reason_code="M5_EVENT_NOT_FRESH"),
        _observation(minute=15, reason_code="M5_DIRECTION_MISMATCH"),
        _observation(minute=20, reason_code="INVALID_TRADE_GEOMETRY"),
        _observation(
            minute=25,
            reason_code="CANDIDATE_CREATED",
            status=SetupStatus.CONSUMED,
            candidate=True,
        ),
    )

    lifecycles = BacktestStrategyComparisonBuilder._build_setup_lifecycles(
        observations
    )

    assert len(lifecycles) == 1
    lifecycle = lifecycles[0]
    assert lifecycle.setup_id == str(SETUP_ID)
    assert lifecycle.active_observation_count == 4
    assert lifecycle.no_m5_event_count == 1
    assert lifecycle.stale_m5_event_count == 1
    assert lifecycle.direction_mismatch_count == 1
    assert lifecycle.index_mismatch_count == 0
    assert lifecycle.invalid_trade_geometry_count == 1
    assert lifecycle.candidate_created is True
    assert lifecycle.candidate_created_at == DETECTED_AT + timedelta(minutes=25)
    assert lifecycle.terminal_status == "CONSUMED"
    assert lifecycle.terminal_timestamp == DETECTED_AT + timedelta(minutes=25)


def test_exporter_writes_setup_lifecycle_csv(tmp_path: Path) -> None:
    observations = (
        _observation(minute=0, reason_code="SETUP_DETECTED"),
        _observation(minute=5, reason_code="M5_EVENT_NOT_FRESH"),
        _observation(
            minute=45,
            reason_code="EXPIRED",
            status=SetupStatus.EXPIRED,
        ),
    )
    lifecycles = BacktestStrategyComparisonBuilder._build_setup_lifecycles(
        observations
    )
    comparison = BacktestStrategyComparison(
        pipeline_observation_count=0,
        pipeline_approval_count=0,
        executed_trade_count=0,
        strategy_observation_count=len(observations),
        strategy_setup_count=1,
        strategy_candidate_count=0,
        pipeline_reason_counts=(),
        strategy_reason_counts=(),
        events=(),
        setup_lifecycles=lifecycles,
    )

    path = BacktestExporter(tmp_path).export_strategy_setup_lifecycles(comparison)

    with path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    assert path.name == "strategy_setup_lifecycles.csv"
    assert len(rows) == 1
    assert rows[0]["Setup ID"] == str(SETUP_ID)
    assert rows[0]["Stale M5 Event Count"] == "1"
    assert rows[0]["Candidate Created"] == "False"
    assert rows[0]["Terminal Status"] == "EXPIRED"
