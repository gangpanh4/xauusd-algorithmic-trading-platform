from __future__ import annotations

from datetime import UTC, datetime
from types import MethodType

import pytest

from core.feature_engineering.models import FeatureVector
from core.multi_timeframe.enums import MarketBias, Timeframe, TimeframeAlignment
from core.multi_timeframe.models import MultiTimeframeResult, TimeframeState
from core.regime_detector.models import MarketBar
from core.risk_manager.config import RiskManagerConfig
from core.trade_quality.evidence import TradeQualityEvidence
from core.trading_pipeline.config import TradingPipelineConfig
from core.trading_pipeline.pipeline import TradingPipeline


def _state(
    timeframe: Timeframe,
    *,
    confidence: float = 0.8,
    metadata: dict[str, object] | None = None,
) -> TimeframeState:
    return TimeframeState(
        timeframe=timeframe,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        bias=MarketBias.BULLISH,
        alignment=TimeframeAlignment.ALIGNED,
        confidence=confidence,
        metadata={} if metadata is None else metadata,
    )


def _mtf_result(
    *,
    metadata_by_timeframe: dict[Timeframe, dict[str, object]] | None = None,
) -> MultiTimeframeResult:
    metadata_by_timeframe = metadata_by_timeframe or {}
    states = {
        timeframe: _state(
            timeframe,
            metadata=metadata_by_timeframe.get(timeframe),
        )
        for timeframe in Timeframe
    }
    return MultiTimeframeResult(
        weekly=states[Timeframe.WEEKLY],
        daily=states[Timeframe.DAILY],
        h4=states[Timeframe.H4],
        h1=states[Timeframe.H1],
        m15=states[Timeframe.M15],
        m5=states[Timeframe.M5],
        overall_bias=MarketBias.BULLISH,
        overall_alignment=TimeframeAlignment.ALIGNED,
        confidence=0.8,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _bar() -> MarketBar:
    return MarketBar(
        timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        open=2400.0,
        high=2402.0,
        low=2398.0,
        close=2401.0,
        volume=1_000,
    )


class _RecordingEvidenceBuilder:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] | None = None

    def build(self, **kwargs: object) -> TradeQualityEvidence:
        self.kwargs = kwargs
        return TradeQualityEvidence(
            trend_score=5.0,
            momentum_score=5.0,
            volatility_score=5.0,
            risk_reward_ratio=float(kwargs["risk_reward_ratio"]),
        )


def test_pipeline_passes_configured_reward_risk_explicitly() -> None:
    config = TradingPipelineConfig(
        risk_manager=RiskManagerConfig(minimum_risk_reward_ratio=2.75)
    )
    pipeline = TradingPipeline(config)
    recorder = _RecordingEvidenceBuilder()
    pipeline.trade_quality_evidence = recorder

    pipeline.process_bar(
        _bar(),
        account_balance=10_000.0,
        stop_loss_distance=2.5,
        pip_value=1.0,
    )

    assert recorder.kwargs is not None
    assert recorder.kwargs["risk_reward_ratio"] == 2.75


def test_missing_mtf_metadata_does_not_fabricate_features() -> None:
    vector = FeatureVector()

    TradingPipeline._append_multi_timeframe_quality_features(
        feature_vector=vector,
        multi_timeframe_result=_mtf_result(),
    )

    assert vector.by_family("momentum") == []
    assert vector.by_family("volatility") == []


def test_real_mtf_metadata_is_exposed_as_independent_features() -> None:
    vector = FeatureVector()
    result = _mtf_result(
        metadata_by_timeframe={
            Timeframe.H1: {"momentum": 0.8, "volatility": 0.4},
            Timeframe.M15: {"momentum": 0.6},
            Timeframe.M5: {"atr_percentile": 0.8},
        }
    )

    TradingPipeline._append_multi_timeframe_quality_features(
        feature_vector=vector,
        multi_timeframe_result=result,
    )

    momentum = vector.get("multi_timeframe_momentum")
    volatility = vector.get("multi_timeframe_volatility")

    assert momentum is not None
    assert momentum.value == pytest.approx(0.7)
    assert momentum.confidence == pytest.approx(0.8)
    assert momentum.family == "momentum"
    assert momentum.source == "multi_timeframe_metadata"

    assert volatility is not None
    assert volatility.value == pytest.approx(0.6)
    assert volatility.confidence == pytest.approx(0.8)
    assert volatility.family == "volatility"


def test_invalid_mtf_metadata_fails_closed_without_probability_fallback() -> None:
    vector = FeatureVector()
    result = _mtf_result(
        metadata_by_timeframe={Timeframe.H1: {"momentum": 1.5}}
    )

    with pytest.raises(ValueError, match="within \\[0, 1\\]"):
        TradingPipeline._append_multi_timeframe_quality_features(
            feature_vector=vector,
            multi_timeframe_result=result,
        )

    assert vector.features == []


def test_process_forwards_exact_mtf_result_to_single_bar_path() -> None:
    pipeline = TradingPipeline(TradingPipelineConfig())
    result = _mtf_result()
    captured: dict[str, object] = {}

    class _Coordinator:
        @staticmethod
        def process(_bars_by_timeframe):
            return result

    class _Confluence:
        @staticmethod
        def evaluate_multi_timeframe(value):
            assert value is result
            return object()

    def _record_process_bar(self, bar, **kwargs):
        captured["bar"] = bar
        captured.update(kwargs)
        return "sentinel"

    pipeline.multi_timeframe = _Coordinator()
    pipeline.confluence_engine = _Confluence()
    pipeline.process_bar = MethodType(_record_process_bar, pipeline)

    bars = {timeframe: [_bar()] for timeframe in Timeframe}
    returned = pipeline.process(
        bars_by_timeframe=bars,
        account_balance=10_000.0,
        stop_loss_distance=2.5,
        pip_value=1.0,
    )

    assert returned == "sentinel"
    assert captured["multi_timeframe_result"] is result
    assert captured["bar"] is bars[Timeframe.M5][-1]
