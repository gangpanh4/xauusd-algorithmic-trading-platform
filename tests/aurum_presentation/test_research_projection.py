from dataclasses import replace
from datetime import UTC, datetime

from core.aurum_presentation import (
    AurumDataMode,
    AurumReadModelBuilder,
    ResearchProvenanceV1,
)
from core.backtesting.models import BacktestResult
from core.backtesting.strategy_comparison import (
    BacktestStrategyComparison,
    StrategyComparisonEvent,
)

from .conftest import T, make_inputs


def _research_inputs():
    result = BacktestResult(
        total_trades=10,
        winning_trades=6,
        losing_trades=3,
        breakeven_trades=1,
        net_profit=120.0,
        win_rate=0.6,
        max_drawdown=50.0,
        gross_profit=200.0,
        gross_loss=80.0,
        profit_factor=2.5,
        expectancy=12.0,
        average_probability=0.7,
        average_confidence=0.75,
        average_feature_count=8.0,
        average_trade_quality=72.0,
        average_trade_quality_confidence=0.74,
        high_quality_trades=6,
    )
    comparison = BacktestStrategyComparison(
        pipeline_observation_count=100,
        pipeline_approval_count=10,
        executed_trade_count=10,
        strategy_observation_count=50,
        strategy_setup_count=7,
        strategy_candidate_count=3,
        pipeline_reason_counts=(("APPROVED", 10), ("PROBABILITY_REJECTED", 90)),
        strategy_reason_counts=(("SETUP_DETECTED", 7),),
        events=(StrategyComparisonEvent(T, "PIPELINE", "APPROVED"),),
    )
    provenance = ResearchProvenanceV1(
        run_id="run-1",
        dataset_identity="dataset-1",
        configuration_fingerprint="config-1",
        artifact_id="artifact-1",
        artifact_sha256="a" * 64,
        source_commit="7fbb0dc",
        generated_at_utc=datetime(2026, 8, 16, 9, 0, tzinfo=UTC),
    )
    return result, comparison, provenance


def test_complete_research_projection_is_available() -> None:
    base = make_inputs(mode=AurumDataMode.RESEARCH_REPLAY)
    result, comparison, provenance = _research_inputs()
    inputs = replace(
        base,
        research_result=result,
        research_comparison=comparison,
        research_provenance=provenance,
    )
    model = AurumReadModelBuilder.build(inputs)
    assert model.research.available is True
    assert model.research.complete is True
    assert model.research.summary.total_trades == 10
    assert model.research.comparison.pipeline_approval_count == 10
    assert model.research.provenance.dataset_identity == "dataset-1"


def test_incomplete_provenance_makes_research_unavailable() -> None:
    base = make_inputs(mode=AurumDataMode.RESEARCH_REPLAY)
    result, comparison, provenance = _research_inputs()
    provenance = replace(provenance, dataset_identity="")
    inputs = replace(
        base,
        research_result=result,
        research_comparison=comparison,
        research_provenance=provenance,
    )
    model = AurumReadModelBuilder.build(inputs)
    assert model.research.available is False
    assert model.research.complete is False
    assert model.research.summary is None


def test_invalid_provenance_checksum_is_unavailable() -> None:
    base = make_inputs(mode=AurumDataMode.RESEARCH_REPLAY)
    result, comparison, provenance = _research_inputs()
    provenance = replace(provenance, artifact_sha256="not-a-sha256")
    inputs = replace(
        base,
        research_result=result,
        research_comparison=comparison,
        research_provenance=provenance,
    )
    model = AurumReadModelBuilder.build(inputs)
    assert model.research.available is False
