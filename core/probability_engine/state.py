"""
Probability Engine runtime state.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import ProbabilityResult


@dataclass(slots=True)
class ProbabilityEngineState:
    """
    Runtime state.
    """

    latest_result: ProbabilityResult | None = None

    processed_count: int = 0