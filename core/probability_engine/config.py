"""
Probability Engine configuration.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ProbabilityEngineConfig:
    """
    Configuration for the Probability Engine.
    """

    minimum_probability: float = 0.60

    minimum_confidence: float = 0.50

    #
    # Baseline Structure Weights
    #

    structure_confidence_weight: float = 0.40

    trend_weight: float = 0.25

    bos_weight: float = 0.20

    choch_weight: float = 0.10

    liquidity_weight: float = 0.05