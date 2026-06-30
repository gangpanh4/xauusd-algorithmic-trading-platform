"""
State management for the Market Regime Detection module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .models import (
    MarketRegime,
    RegimeLabel,
    TransitionRecord,
)

@dataclass
class DetectorState:
    """
    Maintains the internal state of the Market Regime Detector.
    """

    current_regime: RegimeLabel = RegimeLabel.UNKNOWN
    previous_regime: RegimeLabel = RegimeLabel.UNKNOWN

    pending_regime: RegimeLabel = RegimeLabel.UNKNOWN
    pending_regime_count: int = 0

    last_transition_time: datetime | None = None
    current_regime_start: datetime | None = None
    last_observation_time: datetime | None = None

    last_result: MarketRegime | None = None

    initialized: bool = False

    warmup_complete: bool = False

    trend_confirmation_count: int = 0
    range_confirmation_count: int = 0
    crisis_confirmation_count: int = 0

    bars_in_current_regime: int = 0

    transition_history: list[TransitionRecord] = field(default_factory=list)

    processed_bar_count: int = 0


    def reset(self) -> None:
        """
        Reset the detector to its initial state.
        """

        self.current_regime = RegimeLabel.UNKNOWN
        self.previous_regime = RegimeLabel.UNKNOWN
        self.pending_regime = RegimeLabel.UNKNOWN
        self.pending_regime_count = 0
        self.last_transition_time = None

        self.current_regime_start = None
        self.last_observation_time = None
        self.last_result = None

        self.initialized = False
        self.warmup_complete = False

        self.trend_confirmation_count = 0
        self.range_confirmation_count = 0
        self.crisis_confirmation_count = 0

        self.bars_in_current_regime = 0

        self.transition_history.clear()
        
        self.processed_bar_count = 0
