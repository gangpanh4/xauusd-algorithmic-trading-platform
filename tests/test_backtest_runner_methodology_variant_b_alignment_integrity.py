from __future__ import annotations

from core.backtesting.config import BacktestConfig
from core.backtesting.methodology_variant_b_alignment_integrity import (
    MethodologyVariantBAlignmentIntegrity,
)
from core.backtesting.runner import BacktestRunner


def test_runner_initializes_variant_b_alignment_integrity(tmp_path) -> None:
    runner = BacktestRunner(
        BacktestConfig(output_directory=str(tmp_path))
    )

    assert isinstance(
        runner.methodology_variant_b_alignment_integrity,
        MethodologyVariantBAlignmentIntegrity,
    )
