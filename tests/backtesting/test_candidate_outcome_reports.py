from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from uuid import uuid4

from core.backtesting.candidate_outcome_exporter import (
    CandidateOutcomeExporter,
)
from core.backtesting.candidate_outcome_models import (
    CandidateOutcome,
    CandidateOutcomeEvaluation,
)
from core.backtesting.models import BacktestResult
from core.backtesting.run_output import BacktestRunOutput
from core.backtesting.runner import BacktestRunner
from core.backtesting.strategy_comparison import BacktestStrategyComparison


def _evaluation() -> CandidateOutcomeEvaluation:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    return CandidateOutcomeEvaluation(
        setup_id=uuid4(),
        candidate_created_at=timestamp,
        evaluated_through=timestamp,
        outcome=CandidateOutcome.UNRESOLVED,
        outcome_timestamp=None,
        entry_price=3300.0,
        stop_loss_price=3290.0,
        take_profit_prices=(3320.0, 3330.0),
        highest_target_index_reached=None,
        bars_evaluated=0,
        maximum_favorable_excursion=0.0,
        maximum_adverse_excursion=0.0,
        maximum_favorable_r_multiple=0.0,
        maximum_adverse_r_multiple=0.0,
    )


def _result() -> BacktestResult:
    return BacktestResult(
        total_trades=0,
        winning_trades=0,
        losing_trades=0,
        breakeven_trades=0,
        net_profit=0.0,
        win_rate=0.0,
        max_drawdown=0.0,
    )


def _comparison() -> BacktestStrategyComparison:
    return BacktestStrategyComparison(
        pipeline_observation_count=0,
        pipeline_approval_count=0,
        executed_trade_count=0,
        strategy_observation_count=0,
        strategy_setup_count=0,
        strategy_candidate_count=0,
        pipeline_reason_counts=(),
        strategy_reason_counts=(),
        events=(),
    )


def test_candidate_outcome_exporter_writes_summary_and_csv(
    tmp_path,
) -> None:
    exporter = CandidateOutcomeExporter(tmp_path)
    evaluation = _evaluation()

    summary_path = exporter.export_summary(
        {
            "TARGET_REACHED": 0,
            "STOP_REACHED": 0,
            "AMBIGUOUS_SAME_BAR": 0,
            "UNRESOLVED": 1,
        }
    )
    detail_path = exporter.export_evaluations((evaluation,))

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["UNRESOLVED"] == 1

    with detail_path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 1
    assert rows[0]["Setup ID"] == str(evaluation.setup_id)
    assert rows[0]["Outcome"] == "UNRESOLVED"
    assert rows[0]["Outcome Timestamp"] == ""
    assert rows[0]["Take Profit Prices"] == "[3320.0,3330.0]"


def test_generate_composite_reports_exports_candidate_research() -> None:
    runner = object.__new__(BacktestRunner)
    evaluation = _evaluation()
    output = BacktestRunOutput(
        result=_result(),
        strategy_comparison=_comparison(),
        candidate_outcome_evaluations=(evaluation,),
        candidate_outcome_summary={"UNRESOLVED": 1},
    )
    calls: list[tuple[str, object]] = []

    runner.generate_reports = lambda value: calls.append(
        ("reports", value)
    )
    runner.exporter = type(
        "ComparisonExporterSpy",
        (),
        {
            "export_strategy_comparison_summary": (
                lambda self, value: calls.append(("comparison", value))
            ),
            "export_strategy_comparison_events": (
                lambda self, value: calls.append(("events", value))
            ),
        },
    )()
    runner.candidate_outcome_exporter = type(
        "CandidateExporterSpy",
        (),
        {
            "export_summary": (
                lambda self, value: calls.append(("summary", value))
            ),
            "export_evaluations": (
                lambda self, value: calls.append(("evaluations", value))
            ),
        },
    )()

    runner.generate_composite_reports(output)

    assert calls == [
        ("reports", output.result),
        ("comparison", output.strategy_comparison),
        ("events", output.strategy_comparison),
        ("summary", output.candidate_outcome_summary),
        ("evaluations", output.candidate_outcome_evaluations),
    ]
