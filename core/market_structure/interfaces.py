"""
Market Structure Interfaces

This module defines the behavioral contracts used throughout the
Market Structure Engine.

The interfaces specify how detectors, the Market Structure API,
and Feature Engineering communicate without exposing implementation
details.

Author: Trading Intelligence Platform
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from core.data.models import MarketBar

from .context import MarketStructureContext
from .detector_result import DetectorResult
from .measurement_models import Measurement
from .feature_models import Feature
from .result import MarketStructureResult
from .state import MarketStructureState


# ============================================================================
# Market Structure Detector
# ============================================================================


@runtime_checkable
class IMarketStructureDetector(Protocol):
    """
    Common interface implemented by every Market Structure detector.

    Examples
    --------
    - SwingDetector
    - BOSDetector
    - CHOCHDetector
    - LiquidityDetector
    - OrderBlockDetector
    """

    def initialize(self) -> None:
        """Initialize detector resources."""

    def reset(self) -> None:
        """Reset detector runtime state."""

    def process(
        self,
        context: MarketStructureContext,
    ) -> DetectorResult:
        """
        Process one completed MarketBar.

        Parameters
        ----------
        context:
            Immutable processing context for the current bar.
        """

    def get_state(self) -> MarketStructureState:
        """
        Return detector runtime state.
        """

    def get_measurements(self) -> tuple[Measurement, ...]:
        """
        Return published immutable measurements.
        """


# ============================================================================
# Market Structure API
# ============================================================================


@runtime_checkable
class IMarketStructureAPI(Protocol):
    """
    Public interface for the Market Structure Engine.
    """

    def process(
        self,
        bar: MarketBar,
    ) -> MarketStructureResult:
        """
        Process one completed MarketBar.
        """

    def reset(self) -> None:
        """
        Reset the Market Structure Engine.
        """

    def get_result(self) -> MarketStructureResult:
        """
        Return the latest processing result.
        """


# ============================================================================
# Feature Extraction
# ============================================================================


@runtime_checkable
class IFeatureExtractor(Protocol):
    """
    Converts Measurements into Features.
    """

    def extract(
        self,
        measurements: tuple[Measurement, ...],
    ) -> tuple[Feature, ...]:
        """
        Produce immutable engineered features.
        """


# ============================================================================
# Measurement Publisher
# ============================================================================


@runtime_checkable
class IMeasurementPublisher(Protocol):
    """
    Implemented by components that publish Measurements.
    """

    def publish(self) -> tuple[Measurement, ...]:
        """
        Publish immutable measurements.
        """