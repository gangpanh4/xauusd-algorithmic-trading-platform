from __future__ import annotations

from core.backtesting.config import BacktestConfig
from core.backtesting.methodology_variant_b_shadow_trades import (
    MethodologyVariantBShadowTrades,
)
from core.backtesting.runner import BacktestRunner


def test_runner_initializes_variant_b_shadow_trades(tmp_path) -> None:
    config = BacktestConfig(output_directory=str(tmp_path))
    runner = BacktestRunner(config)

    assert isinstance(
        runner.methodology_variant_b_shadow_trades,
        MethodologyVariantBShadowTrades,
    )
    assert runner.methodology_variant_b_shadow_trades.config is config
    assert runner.methodology_variant_b_shadow_trades.tick_size == (
        runner.engine.tick_size
    )
