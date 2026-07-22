"""
Measurement Engine configuration.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class MeasurementConfig:
    """
    Configuration for measurement calculations.
    """

    maximum_history: int = 500