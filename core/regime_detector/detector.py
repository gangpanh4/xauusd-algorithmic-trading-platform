"""
Market Regime Detection Engine.
"""

from __future__ import annotations

from .config import RegimeDetectorConfig
from .models import MarketBar, MarketRegime
from .state import DetectorState

class MarketRegimeDetector:
    """
    Core engine responsible for detecting the current market regime.
    """

    def __init__(
        self,
        config: RegimeDetectorConfig,
    ) -> None:
        self.config = config
        self.state = DetectorState()

    def process_bar(
        self,
        bar: MarketBar,
    ) -> MarketRegime:
        """
        Process one validated market bar and return the detected regime.
        """

        self._validate_input(bar)

        raise NotImplementedError(
            "Regime detection pipeline is not implemented yet."
        )
    
    def _validate_input(
        self,
        bar: MarketBar,
    ) -> None:
        """
        Validate an incoming market bar.
        """

        if bar is None:
            raise ValueError("MarketBar cannot be None.")
        

    def _compute_features(
        self,
        bar: MarketBar,
    ) -> None:
        """
        Compute all features required for regime detection.
        """
        raise NotImplementedError

    def _evaluate_regime(
        self,
    ) -> MarketRegime:
        """
        Evaluate the current market regime from computed features.
        """
        raise NotImplementedError

    def _update_state(
        self,
        regime: MarketRegime,
    ) -> None:
        """
        Update the detector state after a confirmed regime evaluation.
        """
        raise NotImplementedError