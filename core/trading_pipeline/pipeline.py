"""
Trading Pipeline orchestrator.
"""

from __future__ import annotations

from core.regime_detector.detector import (
    MarketRegimeDetector,
)

from core.regime_detector.models import (
    MarketBar,
)

from core.signal_generator.detector import (
    SignalGenerator,
)

from core.risk_manager.manager import (
    RiskManager,
)

from .config import TradingPipelineConfig
from .models import PipelineResult


class TradingPipeline:
    """
    Coordinates the trading decision workflow.
    """

    def __init__(
        self,
        config: TradingPipelineConfig,
    ) -> None:

        self.config = config

        self.regime_detector = MarketRegimeDetector(
            config.regime_detector,
        )

        self.signal_generator = SignalGenerator(
            config.signal_generator,
        )

        self.risk_manager = RiskManager(
            config.risk_manager,
        )

    def process_bar(
        self,
        bar: MarketBar,
        *,
        account_balance: float,
        stop_loss_distance: float,
        pip_value: float,
    ) -> PipelineResult:
        """
        Process one completed market bar through the entire
        trading pipeline.
        """

        regime = self.regime_detector.process_bar(
            bar,
        )

        signal = self.signal_generator.generate_signal(
            regime,
        )

        trade_plan = self.risk_manager.evaluate_signal(
            signal=signal,
            account_balance=account_balance,
            stop_loss_distance=stop_loss_distance,
            pip_value=pip_value,
            )

        return PipelineResult(
            regime=regime,
            signal=signal,
            trade_plan=trade_plan,
        )
