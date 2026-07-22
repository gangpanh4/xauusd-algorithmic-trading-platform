from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.data.models import MarketBar
from core.market_structure.models import MarketStructureResult
from core.trading_pipeline.config import TradingPipelineConfig
from core.trading_pipeline.pipeline import TradingPipeline


def test_pipeline_passes_current_market_structure_to_signal_generator(
    monkeypatch: Any,
) -> None:
    pipeline = TradingPipeline(TradingPipelineConfig())
    captured: dict[str, MarketStructureResult | None] = {}
    original_generate_signal = pipeline.signal_generator.generate_signal

    def capture_generate_signal(*args: Any, **kwargs: Any) -> Any:
        captured["market_structure"] = kwargs.get("market_structure")
        return original_generate_signal(*args, **kwargs)

    monkeypatch.setattr(
        pipeline.signal_generator,
        "generate_signal",
        capture_generate_signal,
    )

    bar = MarketBar(
        timestamp=datetime(2026, 1, 5, 12, 0, tzinfo=UTC),
        open=2_650.0,
        high=2_652.0,
        low=2_648.0,
        close=2_651.0,
        tick_volume=1_000,
    )

    result = pipeline.process_bar(
        bar,
        account_balance=10_000.0,
        stop_loss_distance=2.5,
        pip_value=1.0,
    )

    structure = captured["market_structure"]
    assert isinstance(structure, MarketStructureResult)
    assert result.bos_event is structure.last_bos
    assert result.choch_event is structure.last_choch
    assert result.liquidity_event is structure.last_liquidity
