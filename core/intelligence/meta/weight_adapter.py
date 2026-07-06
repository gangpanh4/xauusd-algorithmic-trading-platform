from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class MetaWeightState:
    liquidity: float = 0.25
    structure: float = 0.25
    confluence: float = 0.25
    microstructure: float = 0.25

    history_score: float = 0.0
    adjustment_rate: float = 0.05


class MetaAdaptiveEngine:
    """
    Sprint 4 — Meta Adaptive Engine

    PURPOSE:
        Dynamically adjust engine weights based on recent performance feedback.

    KEY IDEA:
        What works more gets more influence.
    """

    def __init__(self):
        self.state = MetaWeightState()

    # --------------------------------------------------
    # MAIN UPDATE LOOP
    # --------------------------------------------------
    def update(self, feedback_score: float, micro_success: float):

        combined_signal = (feedback_score + micro_success) / 2

        self.state.history_score = (
            self.state.history_score * 0.9 +
            combined_signal * 0.1
        )

        self._adjust_weights()

    # --------------------------------------------------
    # WEIGHT ADJUSTMENT LOGIC
    # --------------------------------------------------
    def _adjust_weights(self):

        score = self.state.history_score
        r = self.state.adjustment_rate

        # liquidity adapts to short-term structure reliability
        self.state.liquidity += r * (score - 0.5)

        # structure stabilizes medium-term behavior
        self.state.structure += r * (score - 0.5)

        # confluence becomes more strict in bad conditions
        self.state.confluence -= r * (0.5 - score)

        # microstructure increases in noisy markets
        self.state.microstructure += r * (1.0 - abs(score - 0.5))

        self._normalize()

    # --------------------------------------------------
    # NORMALIZATION
    # --------------------------------------------------
    def _normalize(self):

        total = (
            self.state.liquidity +
            self.state.structure +
            self.state.confluence +
            self.state.microstructure
        )

        if total == 0:
            return

        self.state.liquidity /= total
        self.state.structure /= total
        self.state.confluence /= total
        self.state.microstructure /= total