from __future__ import annotations

from datetime import UTC, datetime

import pytest

from core.confluence_engine.models import ConfluenceResult
from core.decision_engine.models import DecisionResult, DecisionType
from core.feature_engineering.models import FeatureVector
from core.probability_engine.models import ProbabilityResult
from core.regime_detector.models import MarketRegime, RegimeLabel
from core.risk_manager.models import RiskDecision, TradePlan
from core.signal_generator.models import SignalDirection, TradingSignal
from core.trade_quality.models import TradeQuality
from core.trading_pipeline.models import PipelineResult, PipelineStage
from core.trading_pipeline.pipeline import TradingPipeline

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _rejected_result(code: str, reason: str) -> PipelineResult:
    signal = TradingSignal(
        timestamp=NOW,
        direction=SignalDirection.HOLD,
        reason="generic hold",
        metadata={
            "rejection_code": code,
            "rejection_reason": reason,
        },
    )
    probability = ProbabilityResult(
        probability=0.72,
        confidence=0.8,
        accepted=True,
    )
    quality = TradeQuality(
        timestamp=NOW,
        score=65.0,
        confidence=0.75,
        approved=True,
    )
    confluence = None
    decision = DecisionResult(
        timestamp=NOW,
        decision=DecisionType.BUY,
        approved=True,
        confidence=0.75,
        decision_score=0.75,
    )
    return PipelineResult(
        regime=MarketRegime(
            primary_regime=RegimeLabel.TRENDING_BULL,
            confidence=0.9,
            observation_timestamp=NOW,
            computation_timestamp=NOW,
        ),
        features=FeatureVector(),
        probability=probability,
        trade_quality=quality,
        confluence=confluence,
        decision=decision,
        signal=signal,
        trade_plan=TradePlan(
            timestamp=NOW,
            signal=signal,
            decision=RiskDecision.REJECT,
            reason="no signal",
        ),
    )


@pytest.mark.parametrize(
    "code",
    [
        "STRUCTURE_DIRECTION_CONFLICT",
        "DUPLICATE_SIGNAL",
        "SIGNAL_COOLDOWN",
        "SIGNAL_SCORE_BELOW_THRESHOLD",
        "DECISION_DIRECTION_MISMATCH",
        "NON_DIRECTIONAL_REGIME",
    ],
)
def test_audit_uses_specific_signal_rejection_code(code: str) -> None:
    reason = f"diagnostic for {code}"

    audit = TradingPipeline._build_observation_audit(
        timestamp=NOW,
        result=_rejected_result(code, reason),
    )

    assert audit.rejection_stage is PipelineStage.SIGNAL
    assert audit.reason_code == code
    assert audit.reason == reason
