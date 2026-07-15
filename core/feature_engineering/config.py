"""
Configuration for the Feature Engineering module.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class FeatureEngineeringConfig:
    """
    Configuration for feature engineering.

    Version 1 intentionally keeps the configuration
    minimal. Additional feature engineering options
    will be introduced as the Probability Engine
    matures.
    """

    enabled: bool = True

    normalize_features: bool = True

    minimum_confidence: float = 0.0