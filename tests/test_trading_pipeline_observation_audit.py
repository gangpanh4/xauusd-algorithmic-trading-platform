from __future__ import annotations

from datetime import UTC, datetime

import pytest

from core.confluence_engine.models import ConfluenceResult
from core.decision_engine.models import DecisionResult, DecisionType
from core.feature_engineering.models import Feature, FeatureVector
from core.probability_engine.models import ProbabilityResult
from core.regime_detector.models import MarketRegime, RegimeLabel
from core.risk_manager.models import RiskDecision, TradePlan
from core.signal_generator.models import SignalDirection, TradingSignal
from core.trade_quality.models import TradeQuality
from core.trading_pipeline.models import (
    PipelineDisposition,
    PipelineResult,
    PipelineStage,
)
from core.trading_pipeline.pipeline import TradingPipeline


NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _result(
    *,
    regime: RegimeLabel = RegimeLabel.TRENDING_BULL,
    probability_accepted: bool = True,
    quality_approved: bool = True,
    confluence_approved: bool = True,
    decision_approved: bool = True,
    signal_direction: SignalDirection = SignalDirection.BUY,
    risk_decision: RiskDecision = RiskDecision.APPROVE,
) -> PipelineResult:
    probability = ProbabilityResult(
        probability=0.72,
        confidence=0.81,
        accepted=probability_accepted,
        reasons=[] if probability_accepted else ["below threshold"],
    )
    quality = TradeQuality(
        timestamp=NOW,
        score=74.0,
        approved=quality_approved,
        confidence=0.75,
        reasons=[] if quality_approved else ["quality rejected"],
    )
    confluence = ConfluenceResult(
        score=0.75,
        maximum_score=1.0,
        confidence=0.75,
        approved=confluence_approved,
    )
    decision = DecisionResult(
        timestamp=NOW,
        decision=(DecisionType.BUY if decision_approved else DecisionType.HOLD),
        approved=decision_approved,
        confidence=0.70,
        decision_score=0.70,
    )
    signal = TradingSignal(
        timestamp=NOW,
        direction=signal_direction,
        reason="test signal",
    )
    trade_plan = TradePlan(
        timestamp=NOW,
        signal=signal,
        decision=risk_decision,
        reason=("approved" if risk_decision is RiskDecision.APPROVE else "risk blocked"),
    )
    return PipelineResult(
        regime=MarketRegime(
            primary_regime=regime,
            confidence=0.80 if regime is not RegimeLabel.UNKNOWN else 0.0,
            observation_timestamp=NOW,
            computation_timestamp=NOW,
        ),
        bos_event=object(),  # scalar presence is all the audit consumes
        features=FeatureVector(
            features=[Feature("x", 0.5, confidence=0.8, normalized=True)]
        ),
        probability=probability,
        decision=decision,
        trade_quality=quality,
        confluence=confluence,
        signal=signal,
        trade_plan=trade_plan,
    )


def test_accepted_observation_records_all_final_facts() -> None:
    audit = TradingPipeline._build_observation_audit(
        timestamp=NOW,
        result=_result(),
    )

    assert audit.disposition is PipelineDisposition.ACCEPTED
    assert audit.stage_reached is PipelineStage.APPROVED
    assert audit.reason_code is None
    assert audit.regime_confirmed is True
    assert audit.bos_present is True
    assert audit.feature_count == 1
    assert audit.probability_value == pytest.approx(0.72)
    assert audit.trade_quality_score == pytest.approx(0.74)
    assert audit.confluence_score == pytest.approx(0.75)
    assert audit.signal_generated is True
    assert audit.risk_approved is True


@pytest.mark.parametrize(
    ("changes", "stage", "code"),
    [
        ({"regime": RegimeLabel.UNKNOWN}, PipelineStage.REGIME, "REGIME_UNCONFIRMED"),
        ({"probability_accepted": False}, PipelineStage.PROBABILITY, "PROBABILITY_REJECTED"),
        ({"quality_approved": False}, PipelineStage.TRADE_QUALITY, "TRADE_QUALITY_REJECTED"),
        ({"confluence_approved": False}, PipelineStage.CONFLUENCE, "CONFLUENCE_REJECTED"),
        ({"decision_approved": False}, PipelineStage.SIGNAL, "DECISION_REJECTED"),
        ({"signal_direction": SignalDirection.HOLD}, PipelineStage.SIGNAL, "SIGNAL_NOT_GENERATED"),
        ({"risk_decision": RiskDecision.REJECT}, PipelineStage.RISK, "RISK_REJECTED"),
    ],
)
def test_rejection_precedence_identifies_the_first_active_gate(
    changes: dict[str, object],
    stage: PipelineStage,
    code: str,
) -> None:
    audit = TradingPipeline._build_observation_audit(
        timestamp=NOW,
        result=_result(**changes),
    )

    assert audit.disposition is PipelineDisposition.REJECTED
    assert audit.stage_reached is PipelineStage.RISK
    assert audit.rejection_stage is stage
    assert audit.reason_code == code
    assert audit.reason


def test_probability_rejection_has_precedence_over_later_rejections() -> None:
    audit = TradingPipeline._build_observation_audit(
        timestamp=NOW,
        result=_result(
            probability_accepted=False,
            quality_approved=False,
            confluence_approved=False,
            decision_approved=False,
            signal_direction=SignalDirection.HOLD,
            risk_decision=RiskDecision.SKIP,
        ),
    )

    assert audit.reason_code == "PROBABILITY_REJECTED"
    assert audit.reason == "below threshold"


def test_missing_confluence_is_recorded_as_unavailable_not_rejected() -> None:
    result = _result(risk_decision=RiskDecision.REJECT)
    result.confluence = None

    audit = TradingPipeline._build_observation_audit(
        timestamp=NOW,
        result=result,
    )

    assert audit.confluence_available is False
    assert audit.confluence_approved is False
    assert audit.reason_code == "RISK_REJECTED"


def test_quality_score_accepts_normalized_and_percentage_scales() -> None:
    assert TradingPipeline._normalize_quality_score(0.74) == pytest.approx(0.74)
    assert TradingPipeline._normalize_quality_score(74.0) == pytest.approx(0.74)

    with pytest.raises(ValueError, match="within"):
        TradingPipeline._normalize_quality_score(101.0)
