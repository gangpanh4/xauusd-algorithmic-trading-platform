from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StabilityState:
    volatility_cap: float = 0.15
    weight_drift_limit: float = 0.10
    confluence_cap: float = 0.85
    entropy_floor: float = 0.20


class StabilityGovernor:
    """
    Sprint 4.5 — Stability Governor

    PURPOSE:
        Prevent adaptive system from becoming unstable or over-reactive.

    KEY IDEA:
        Intelligence without control = noise amplifier.
        Intelligence + control = stable edge system.
    """

    def __init__(self):
        self.state = StabilityState()

    # --------------------------------------------------
    # CLAMP META WEIGHTS
    # --------------------------------------------------
    def clamp_weights(self, meta_state):

        meta_state.liquidity = self._clamp(meta_state.liquidity)
        meta_state.structure = self._clamp(meta_state.structure)
        meta_state.confluence = self._clamp(meta_state.confluence)
        meta_state.microstructure = self._clamp(meta_state.microstructure)

        return meta_state

    # --------------------------------------------------
    # CLAMP CONFLUENCE
    # --------------------------------------------------
    def clamp_confluence(self, score: float) -> float:

        return min(self.state.confluence_cap, max(0.0, score))

    # --------------------------------------------------
    # CLAMP VOLATILITY INPUT
    # --------------------------------------------------
    def clamp_volatility(self, value: float) -> float:

        return min(self.state.volatility_cap, max(0.0, value))

    # --------------------------------------------------
    # INTERNAL CLAMP
    # --------------------------------------------------
    def _clamp(self, value: float) -> float:

        drift = self.state.weight_drift_limit

        return min(1.0, max(drift, value))