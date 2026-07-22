from __future__ import annotations

import csv
from datetime import UTC, datetime, timedelta

from core.backtesting.config import BacktestConfig
from core.backtesting.engine import BacktestingEngine
from core.backtesting.exporter import BacktestExporter
from core.backtesting.models import (
    BacktestResult,
    BacktestTrade,
    ExitReason,
    TradeOutcome,
)
from core.confluence_engine.models import ConfluenceFactor, ConfluenceResult
from core.data.models import MarketBar as DataMarketBar
from core.decision_engine.models import DecisionResult, DecisionType
from core.fair_value_gap_detector.enums import FairValueGapStatus, FairValueGapType
from core.fair_value_gap_detector.models import FairValueGapCandidate
from core.feature_engineering.models import Feature, FeatureVector
from core.market_structure.enums import (
    BreakType,
    OrderBlockType,
    SwingType,
    TrendDirection,
)
from core.market_structure.models import (
    BOSEvent,
    CHOCHEvent,
    LiquidityLevel,
    LiquiditySweepEvent,
    SwingPoint,
)
from core.order_block_detector.models import OrderBlockCandidate
from core.probability_engine.models import EvidenceScore, ProbabilityResult
from core.regime_detector.models import (
    ConfidenceTier,
    MarketBar,
    MarketRegime,
    RegimeLabel,
    StatusFlag,
)
from core.risk_manager.models import RiskDecision, TradePlan
from core.signal_generator.models import (
    SignalDirection,
    SignalStrength,
    TradingSignal,
)
from core.trade_quality.models import QualityLevel, TradeQuality
from core.trading_pipeline.models import PipelineResult


class _StubSimulator:
    def __init__(self, trade: BacktestTrade) -> None:
        self.trade = trade

    def simulate(self, **_: object) -> BacktestTrade:
        return self.trade


class _StubPipeline:
    def __init__(self) -> None:
        self.opened = 0

    def register_position_opened(self, count: int = 1) -> None:
        self.opened += count


def _timestamp(minutes: int = 0) -> datetime:
    return datetime(2025, 1, 6, 10, 0, tzinfo=UTC) + timedelta(minutes=minutes)


def _engine_with_stub_trade() -> tuple[BacktestingEngine, BacktestTrade, _StubPipeline]:
    engine = BacktestingEngine(BacktestConfig())
    trade = BacktestTrade(
        entry_time=_timestamp(15),
        exit_time=_timestamp(45),
        direction="BUY",
        entry_price=2001.0,
        exit_price=2006.0,
        position_size=0.1,
        gross_profit=50.0,
        net_profit=49.0,
        outcome=TradeOutcome.WIN,
        exit_reason=ExitReason.TAKE_PROFIT,
        metadata={"simulator_key": "preserved"},
    )
    pipeline = _StubPipeline()
    engine.simulator = _StubSimulator(trade)
    engine.pipeline = pipeline
    return engine, trade, pipeline


def _full_pipeline_result() -> tuple[PipelineResult, MarketBar, list[MarketBar]]:
    observation = _timestamp()
    signal = TradingSignal(
        timestamp=observation,
        direction=SignalDirection.BUY,
        strength=SignalStrength.STRONG,
        confidence=0.84,
        decision_score=0.79,
        reasons=["all gates passed"],
        metadata={"strategy_id": "bos_pullback_v1", "event_id": "bos-42"},
    )
    trade_plan = TradePlan(
        timestamp=observation,
        signal=signal,
        decision=RiskDecision.APPROVE,
        position_size=0.1,
        entry_price=2000.0,
        stop_loss=1997.5,
        take_profit=2005.0,
        risk_percent=0.005,
        reward_percent=0.01,
        risk_reward_ratio=2.0,
        reason="approved",
        probability=0.68,
        confidence=0.73,
        feature_count=2,
        evidence_count=2,
        regime="TRENDING_BULL",
    )
    probability = ProbabilityResult(
        probability=0.68,
        confidence=0.73,
        accepted=True,
        reasons=["above threshold"],
        evidence=[
            EvidenceScore("structure", 0.7, 0.8),
            EvidenceScore("liquidity", 0.6, 0.7),
        ],
    )
    features = FeatureVector(
        features=[
            Feature(
                name="bos_break_distance",
                value=1.2,
                confidence=0.8,
                normalized=True,
                family="structure",
                source="bos",
            ),
            Feature(
                name="liquidity_atr_multiple",
                value=0.5,
                confidence=0.7,
                normalized=True,
                family="liquidity",
                source="sweep",
            ),
        ]
    )
    quality = TradeQuality(
        timestamp=observation,
        score=82.0,
        level=QualityLevel.HIGH,
        approved=True,
        confidence=0.76,
        reasons=["passed quality"],
        metadata={"trend_score": 0.8},
    )
    regime = MarketRegime(
        primary_regime=RegimeLabel.TRENDING_BULL,
        confidence=0.81,
        observation_timestamp=observation,
        computation_timestamp=observation,
        confidence_tier=ConfidenceTier.HIGH,
        status_flags=frozenset({StatusFlag.STRUCTURAL_BREAK_DETECTED}),
        trend_score=0.9,
        momentum_score=0.7,
        volatility_score=0.6,
        ema_score=0.8,
        choppiness_score=0.2,
        total_score=0.75,
    )
    confluence = ConfluenceResult(
        score=3.5,
        maximum_score=5.0,
        confidence=0.7,
        approved=True,
        factors=[
            ConfluenceFactor(
                name="structure",
                passed=True,
                score=0.8,
                weight=1.0,
                reason="aligned",
            )
        ],
    )
    decision = DecisionResult(
        timestamp=observation,
        decision=DecisionType.BUY,
        approved=True,
        confidence=0.72,
        decision_score=0.74,
        regime_confidence=0.81,
        confluence_score=0.7,
    )
    swing_high = SwingPoint(
        timestamp=_timestamp(-30),
        index=10,
        price=1999.0,
        swing_type=SwingType.HIGH,
        confirmation_index=12,
        distance_from_previous=3.0,
        atr_multiple=1.2,
        pivot_dominance=0.8,
        confirmation_strength=0.9,
    )
    swing_low = SwingPoint(
        timestamp=_timestamp(-45),
        index=8,
        price=1995.0,
        swing_type=SwingType.LOW,
        confirmation_index=10,
        distance_from_previous=2.0,
        atr_multiple=0.8,
        pivot_dominance=0.7,
        confirmation_strength=0.85,
    )
    bos = BOSEvent(
        timestamp=observation,
        break_type=BreakType.BOS,
        direction=TrendDirection.BULLISH,
        swing_point=swing_high,
        break_price=2000.0,
        confirmation_index=20,
        break_distance=1.0,
        quality=0.8,
        strength=0.75,
        power_score=0.7,
        structure_score=0.9,
        age=1,
    )
    choch = CHOCHEvent(
        timestamp=_timestamp(-15),
        break_type=BreakType.CHOCH,
        direction=TrendDirection.BULLISH,
        swing_point=swing_low,
        break_price=1998.0,
        confirmation_index=18,
        break_distance=0.8,
        quality=0.7,
        strength=0.65,
        power_score=0.6,
        structure_score=0.75,
        age=2,
    )
    liquidity_level = LiquidityLevel(
        timestamp=_timestamp(-60),
        price=1994.5,
        swing_point=swing_low,
        is_buy_side=False,
    )
    liquidity = LiquiditySweepEvent(
        timestamp=_timestamp(-15),
        liquidity_level=liquidity_level,
        sweep_price=1994.0,
        confirmation_index=18,
        sweep_distance=0.5,
        atr_multiple=0.4,
        sweep_strength=0.6,
        reaction_strength=0.7,
        reclaim_strength=0.8,
        density=0.5,
        quality=0.72,
        age=2,
    )
    order_block = OrderBlockCandidate(
        timestamp=_timestamp(-30),
        block_type=OrderBlockType.BULLISH,
        top_price=1998.5,
        bottom_price=1997.5,
        origin_swing=swing_low,
        trigger_break=bos,
        trigger_liquidity=liquidity,
        creation_index=16,
        origin_bar_score=0.77,
    )
    fvg_bars = [
        DataMarketBar(_timestamp(-30), 1997.0, 1998.0, 1996.5, 1997.5, 100),
        DataMarketBar(_timestamp(-15), 1997.6, 1999.2, 1997.5, 1999.0, 120),
        DataMarketBar(observation, 1999.5, 2001.0, 1999.4, 2000.0, 130),
    ]
    fvg = FairValueGapCandidate(
        timestamp=observation,
        gap_type=FairValueGapType.BULLISH,
        top_price=1999.4,
        bottom_price=1998.0,
        first_bar=fvg_bars[0],
        middle_bar=fvg_bars[1],
        third_bar=fvg_bars[2],
        equilibrium_price=1998.7,
        is_discount_zone=True,
        quality_score=0.74,
        age=1,
        status=FairValueGapStatus.ACTIVE,
    )
    bar = MarketBar(
        timestamp=observation,
        open=1999.0,
        high=2001.0,
        low=1998.0,
        close=2000.0,
        volume=100.0,
    )
    future = [
        MarketBar(
            timestamp=_timestamp(15),
            open=2001.0,
            high=2002.0,
            low=2000.0,
            close=2001.5,
            volume=100.0,
        )
    ]
    return (
        PipelineResult(
            regime=regime,
            bos_event=bos,
            choch_event=choch,
            liquidity_event=liquidity,
            order_block=order_block,
            fair_value_gap=fvg,
            features=features,
            probability=probability,
            decision=decision,
            trade_quality=quality,
            confluence=confluence,
            signal=signal,
            trade_plan=trade_plan,
        ),
        bar,
        future,
    )


def test_record_trade_copies_complete_pipeline_evidence() -> None:
    engine, trade, pipeline = _engine_with_stub_trade()
    result, bar, future = _full_pipeline_result()

    engine._record_trade(result=result, entry_bar=bar, future_bars=future)

    assert engine.state.active_trade is trade
    assert pipeline.opened == 1
    metadata = trade.metadata
    assert metadata["simulator_key"] == "preserved"
    assert metadata["probability"] == 0.68
    assert metadata["probability_accepted"] is True
    assert metadata["probability_evidence"][0]["family"] == "structure"
    assert metadata["feature_values"]["bos_break_distance"] == 1.2
    assert metadata["trade_quality_level"] == "HIGH"
    assert metadata["trade_quality_approved"] is True
    assert metadata["regime"] == "TRENDING_BULL"
    assert metadata["regime_status_flags"] == ["STRUCTURAL_BREAK_DETECTED"]
    assert metadata["confluence_approved"] is True
    assert metadata["decision"] == "BUY"
    assert metadata["signal_direction"] == "BUY"
    assert metadata["strategy_id"] == "bos_pullback_v1"
    assert metadata["bos_present"] is True
    assert metadata["bos_direction"] == "BULLISH"
    assert metadata["choch_present"] is True
    assert metadata["liquidity_present"] is True
    assert metadata["liquidity_side"] == "SELL_SIDE"
    assert metadata["order_block_present"] is True
    assert metadata["fair_value_gap_present"] is True
    assert metadata["fair_value_gap"]["first_bar"]["tick_volume"] == 100


def test_absent_optional_evidence_is_not_fabricated() -> None:
    engine, trade, _ = _engine_with_stub_trade()
    result, bar, future = _full_pipeline_result()
    result.bos_event = None
    result.choch_event = None
    result.liquidity_event = None
    result.order_block = None
    result.fair_value_gap = None
    result.confluence = None

    engine._record_trade(result=result, entry_bar=bar, future_bars=future)

    metadata = trade.metadata
    assert metadata["bos_present"] is False
    assert metadata["choch_present"] is False
    assert metadata["liquidity_present"] is False
    assert metadata["order_block_present"] is False
    assert metadata["fair_value_gap_present"] is False
    assert metadata["confluence_score"] is None
    assert metadata["confluence_approved"] is None


def test_exporter_writes_pipeline_evidence_columns(tmp_path) -> None:
    engine, trade, _ = _engine_with_stub_trade()
    result, bar, future = _full_pipeline_result()
    engine._record_trade(result=result, entry_bar=bar, future_bars=future)

    backtest_result = BacktestResult(
        total_trades=1,
        winning_trades=1,
        losing_trades=0,
        breakeven_trades=0,
        net_profit=trade.net_profit,
        win_rate=100.0,
        max_drawdown=0.0,
        trades=[trade],
    )
    path = BacktestExporter(tmp_path).export_trade_log(backtest_result)

    with path.open(newline="", encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))

    assert row["Probability Accepted"] == "True"
    assert row["Trade Quality Approved"] == "True"
    assert row["BOS Present"] == "True"
    assert row["BOS Direction"] == "BULLISH"
    assert row["CHOCH Present"] == "True"
    assert row["Liquidity Present"] == "True"
    assert row["Strategy ID"] == "bos_pullback_v1"
    assert row["Metadata:feature_values.bos_break_distance"] == "1.2"
