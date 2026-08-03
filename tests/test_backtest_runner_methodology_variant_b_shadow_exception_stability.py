from __future__ import annotations

from core.backtesting.config import BacktestConfig
from core.backtesting.methodology_variant_b_shadow_exception_stability import (
    MethodologyVariantBShadowExceptionStability,
)
from core.backtesting.runner import BacktestRunner


def test_runner_initializes_shadow_exception_stability(tmp_path) -> None:
    runner = BacktestRunner(BacktestConfig(output_directory=str(tmp_path)))
    assert isinstance(
        runner.methodology_variant_b_shadow_exception_stability,
        MethodologyVariantBShadowExceptionStability,
    )
