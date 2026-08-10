from __future__ import annotations

import json
import runpy
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE_TEST = Path(__file__).with_name(
    "test_backtest_execution_model_bounded_parity.py"
)
DECISION_START = datetime(2026, 8, 6, 1, 0, tzinfo=UTC)
DECISION_END = datetime(2026, 8, 6, 12, 55, tzinfo=UTC)

RISK_POLICY_REASONS = {
    "Position size must be greater than zero.",
    "Position size below minimum.",
    "Position size above maximum.",
    "Risk/Reward ratio must be greater than zero.",
    "Risk/Reward ratio too low.",
    "Emergency stop is active.",
    "Account balance is required for emergency-stop validation.",
    "Account balance is at or below the emergency stop balance.",
    "Multiple positions are disabled.",
    "Maximum open positions reached.",
    "Proposed risk must be greater than zero.",
    "Proposed risk exceeds maximum risk per trade.",
    "Daily loss limit has already been reached.",
    "Daily start balance is required for daily-loss validation.",
    "Daily loss limit reached.",
}


def _load_base() -> dict[str, Any]:
    return runpy.run_path(str(BASE_TEST))


def _pairs(value: object) -> dict[str, object]:
    if not isinstance(value, tuple):
        return {}
    result: dict[str, object] = {}
    for item in value:
        if (
            isinstance(item, tuple)
            and len(item) == 2
            and isinstance(item[0], str)
        ):
            result[item[0]] = item[1]
    return result


def _enum_text(value: object) -> str:
    if value is None:
        return "NONE"
    return str(value)


def _reasons(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return tuple(str(item) for item in value)
    if isinstance(value, list):
        return tuple(str(item) for item in value)
    return (str(value),)


def _funnel(records: tuple[object, ...]) -> dict[str, object]:
    decision_counts: Counter[str] = Counter()
    signal_counts: Counter[str] = Counter()
    plan_counts: Counter[str] = Counter()
    plan_reasons: Counter[str] = Counter()
    probability_reasons: Counter[str] = Counter()
    trade_quality_reasons: Counter[str] = Counter()
    confluence_reasons: Counter[str] = Counter()

    probability_rejected = 0
    trade_quality_rejected = 0
    confluence_rejected = 0
    confluence_available = 0

    for record in records:
        analytical = record.analytical

        decision = _pairs(analytical.decision)
        decision_counts[_enum_text(decision.get("decision"))] += 1

        signal = _pairs(analytical.signal)
        if analytical.signal is None:
            signal_counts["HOLD_OR_NO_SIGNAL"] += 1
        else:
            direction = signal.get("direction", signal.get("signal"))
            signal_counts[_enum_text(direction)] += 1

        plan = record.trade_plan
        plan_counts[plan.decision.value] += 1
        plan_reasons[str(plan.reason)] += 1

        probability = _pairs(analytical.probability)
        if probability and probability.get("accepted") is False:
            probability_rejected += 1
            for reason in _reasons(probability.get("reasons")):
                probability_reasons[reason] += 1

        quality = _pairs(analytical.trade_quality)
        if quality and quality.get("approved") is False:
            trade_quality_rejected += 1
            for reason in _reasons(quality.get("reasons")):
                trade_quality_reasons[reason] += 1

        confluence = _pairs(analytical.confluence)
        if confluence:
            confluence_available += 1
            if confluence.get("approved") is False:
                confluence_rejected += 1
                factors = confluence.get("factors")
                if isinstance(factors, tuple):
                    for raw_factor in factors:
                        factor = _pairs(raw_factor)
                        if factor.get("passed") is False:
                            reason = factor.get("reason")
                            if reason is not None:
                                confluence_reasons[str(reason)] += 1

    calculation_rejections = Counter(
        {
            reason: count
            for reason, count in plan_reasons.items()
            if reason.startswith("Risk calculation rejected:")
        }
    )
    policy_rejections = Counter(
        {
            reason: count
            for reason, count in plan_reasons.items()
            if reason in RISK_POLICY_REASONS
        }
    )

    return {
        "observations": len(records),
        "decision": dict(sorted(decision_counts.items())),
        "signal": dict(sorted(signal_counts.items())),
        "trade_plan": dict(sorted(plan_counts.items())),
        "trade_plan_reasons": dict(sorted(plan_reasons.items())),
        "risk_calculation_rejections": dict(
            sorted(calculation_rejections.items())
        ),
        "risk_policy_rejections": dict(sorted(policy_rejections.items())),
        "probability_rejected_observations": probability_rejected,
        "probability_rejection_reasons": dict(
            sorted(probability_reasons.items())
        ),
        "trade_quality_rejected_observations": trade_quality_rejected,
        "trade_quality_rejection_reasons": dict(
            sorted(trade_quality_reasons.items())
        ),
        "confluence_available_observations": confluence_available,
        "confluence_rejected_observations": confluence_rejected,
        "confluence_rejection_reasons": dict(
            sorted(confluence_reasons.items())
        ),
    }


def _classification(funnel: Mapping[str, object]) -> str:
    decisions = funnel["decision"]
    signals = funnel["signal"]
    plans = funnel["trade_plan"]
    assert isinstance(decisions, Mapping)
    assert isinstance(signals, Mapping)
    assert isinstance(plans, Mapping)

    approvals = int(plans.get("APPROVE", 0))
    directional_decisions = int(decisions.get("BUY", 0)) + int(
        decisions.get("SELL", 0)
    )
    directional_signals = int(signals.get("BUY", 0)) + int(
        signals.get("SELL", 0)
    )
    rejects = int(plans.get("REJECT", 0))
    skips = int(plans.get("SKIP", 0))

    if approvals > 0:
        return "APPROVAL_EXISTS"
    if directional_decisions == 0:
        return "NO_DIRECTIONAL_DECISIONS"
    if directional_signals == 0:
        return "DIRECTIONAL_DECISIONS_BUT_NO_SIGNAL"
    if rejects == 0 and skips > 0:
        return "SIGNALS_EXIST_BUT_ALL_SKIPPED"
    if rejects > 0 and skips == 0:
        return "SIGNALS_EXIST_BUT_ALL_REJECTED"
    return "MIXED_FUNNEL_WITH_ZERO_APPROVAL"


def _records_between(
    pipeline: object,
    start: datetime,
    end: datetime,
) -> tuple[object, ...]:
    return tuple(
        record
        for record in pipeline.records
        if start <= record.analytical.timestamp <= end
    )


def test_group4d_decision_funnel_diagnostic() -> None:
    base = _load_base()
    context = base["_context_from_fixture"]()
    run_model = base["_run_model"]
    v1_model = base["BacktestExecutionModel"].M15_COMPLETED_OHLC_V1
    v2_model = base["BacktestExecutionModel"].M5_COMPLETED_OHLC_V2

    v1 = run_model(v1_model, context)
    v2 = run_model(v2_model, context)

    v1_records = tuple(v1.pipeline.records)
    v2_records = tuple(v2.pipeline.records)

    if len(v1_records) != len(v2_records):
        raise AssertionError("V1/V2 total analytical record counts differ")

    for left, right in zip(v1_records, v2_records, strict=True):
        if left.analytical != right.analytical:
            raise AssertionError(
                "UNEXPECTED_ANALYTICAL_DIFFERENCE at "
                f"{left.analytical.timestamp.isoformat()}"
            )
        if left.trade_plan.decision != right.trade_plan.decision:
            raise AssertionError(
                "V1/V2 TradePlan decision differs before execution at "
                f"{left.analytical.timestamp.isoformat()}"
            )
        if left.trade_plan.reason != right.trade_plan.reason:
            raise AssertionError(
                "V1/V2 TradePlan reason differs before execution at "
                f"{left.analytical.timestamp.isoformat()}"
            )

    warmup_v1 = tuple(
        record
        for record in v1_records
        if record.analytical.timestamp < DECISION_START
    )
    warmup_v2 = tuple(
        record
        for record in v2_records
        if record.analytical.timestamp < DECISION_START
    )
    active_v1 = _records_between(
        v1.pipeline,
        DECISION_START,
        DECISION_END,
    )
    active_v2 = _records_between(
        v2.pipeline,
        DECISION_START,
        DECISION_END,
    )

    assert len(warmup_v1) == len(warmup_v2) == 200
    assert len(active_v1) == len(active_v2) == 144

    warmup_funnel_v1 = _funnel(warmup_v1)
    warmup_funnel_v2 = _funnel(warmup_v2)
    active_funnel_v1 = _funnel(active_v1)
    active_funnel_v2 = _funnel(active_v2)

    assert warmup_funnel_v1 == warmup_funnel_v2
    assert active_funnel_v1 == active_funnel_v2

    print(
        "GROUP4D_DIAGNOSTIC_WARMUP="
        + json.dumps(warmup_funnel_v1, sort_keys=True)
    )
    print(
        "GROUP4D_DIAGNOSTIC_ACTIVE="
        + json.dumps(active_funnel_v1, sort_keys=True)
    )
    print(
        "GROUP4D_DIAGNOSTIC_CLASSIFICATION="
        + json.dumps(_classification(active_funnel_v1))
    )
    print(
        "GROUP4D_DIAGNOSTIC_IDENTITY="
        + json.dumps(
            {
                "v1_v2_total_records_identical": True,
                "v1_v2_warmup_funnel_identical": True,
                "v1_v2_active_funnel_identical": True,
                "v1_v2_trade_plan_decisions_reasons_identical": True,
            },
            sort_keys=True,
        )
    )

    assert warmup_funnel_v1["observations"] == 200
    assert warmup_funnel_v1["decision"] == {"HOLD": 200}
    assert warmup_funnel_v1["signal"] == {"HOLD": 200}
    assert warmup_funnel_v1["trade_plan"] == {"SKIP": 200}
    assert warmup_funnel_v1["trade_plan_reasons"] == {
        "No trading opportunity.": 200
    }
    assert warmup_funnel_v1["probability_rejected_observations"] == 141
    assert warmup_funnel_v1["trade_quality_rejected_observations"] == 200
    assert warmup_funnel_v1["confluence_rejected_observations"] == 198

    assert active_funnel_v1["observations"] == 144
    assert active_funnel_v1["decision"] == {"BUY": 3, "HOLD": 141}
    assert active_funnel_v1["signal"] == {"HOLD": 144}
    assert active_funnel_v1["trade_plan"] == {"SKIP": 144}
    assert active_funnel_v1["trade_plan_reasons"] == {
        "No trading opportunity.": 144
    }
    assert active_funnel_v1["risk_calculation_rejections"] == {}
    assert active_funnel_v1["risk_policy_rejections"] == {}
    assert active_funnel_v1["probability_rejected_observations"] == 102
    assert active_funnel_v1["probability_rejection_reasons"] == {}
    assert active_funnel_v1["trade_quality_rejected_observations"] == 144
    assert active_funnel_v1["confluence_rejected_observations"] == 143
    assert _classification(active_funnel_v1) == (
        "DIRECTIONAL_DECISIONS_BUT_NO_SIGNAL"
    )

    execution_migration_status = (
        "EXECUTION_MIGRATION_EMPIRICALLY_DEFERRED_"
        "ON_AVAILABLE_LOCAL_CAPTURE"
    )
    assert execution_migration_status == (
        "EXECUTION_MIGRATION_EMPIRICALLY_DEFERRED_"
        "ON_AVAILABLE_LOCAL_CAPTURE"
    )
