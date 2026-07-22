"""
Shared models for the Intelligence Pipeline.

The Intelligence Pipeline is responsible only for analysing the market.
It never makes trading or risk decisions.

This module defines the contract between the Intelligence Pipeline and
the Trading Pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class IntelligenceResult:
    """
    Complete market intelligence produced by the Intelligence Pipeline.

    Each field represents analysed market information only.
    No trade decisions, risk management or execution information
    belongs here.
    """

    regime: object
    liquidity: object
    directional_liquidity: object

    h4_bias: object
    h1_structure: object

    m15_setup: object
    m5_entry: object

    confluence: object
    opportunity: object
    expectancy: object

    microstructure: object

    feedback: object | None = None
    meta_weights: object | None = None