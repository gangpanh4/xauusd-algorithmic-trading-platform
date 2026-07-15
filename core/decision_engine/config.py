"""
Decision Engine configuration.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DecisionEngineConfig:
    """
    Configuration for the Decision Engine.

    These values define the quantitative policy used when
    converting market analysis into a trading decision.
    """

    #
    # Minimum overall score required before a trade
    # can be approved.
    #
    minimum_decision_score: float = 0.70

    #
    # Relative importance of the Market Regime.
    #
    regime_weight: float = 0.50

    #
    # Relative importance of Confluence.
    #
    confluence_weight: float = 0.50