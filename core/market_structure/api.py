"""
Market Structure API

Coordinates all Market Structure detectors and produces an immutable
MarketStructureResult for each completed MarketBar.

Author: Trading Intelligence Platform
"""

from __future__ import annotations

from core.data.models import MarketBar

from .context import MarketStructureContext
from .detector_result import DetectorResult
from .feature_models import Feature
from .interfaces import (
    IFeatureExtractor,
    IMarketStructureAPI,
    IMarketStructureDetector,
)
from .measurement_models import Measurement
from .result import MarketStructureResult


class MarketStructureAPI(IMarketStructureAPI):
    """
    Default implementation of the Market Structure Engine.
    """

    def __init__(
        self,
        detectors: tuple[IMarketStructureDetector, ...],
        feature_extractor: IFeatureExtractor,
    ) -> None:
        """
        Initialize the Market Structure API.

        Parameters
        ----------
        detectors:
            Ordered detector pipeline.

        feature_extractor:
            Converts measurements into engineered features.
        """

        self._detectors = detectors

        self._feature_extractor = feature_extractor

        self._latest_result = MarketStructureResult()

    def process(
        self,
        bar: MarketBar,
    ) -> MarketStructureResult:
        """
        Process a completed market bar through every
        registered detector.
        """

        context = MarketStructureContext(
            bar=bar,
        )

        measurements: list[Measurement] = []

        detector_results: list[DetectorResult] = []

        for detector in self._detectors:

            result = detector.process(
                context,
            )

            detector_results.append(result)

            measurements.extend(result.measurements)

        features: tuple[Feature, ...] = (
            self._feature_extractor.extract(
                tuple(measurements),
            )
        )

        self._latest_result = MarketStructureResult(
            context=context,
            detector_results=tuple(detector_results),
            measurements=tuple(measurements),
            features=features,
        )

        return self._latest_result

    @property
    def latest_result(
        self,
    ) -> MarketStructureResult:
        """
        Return the latest Market Structure result.
        """

        return self._latest_result

    def reset(
        self,
    ) -> None:
        """
        Reset all detectors and clear the latest result.
        """

        for detector in self._detectors:
            detector.reset()

        self._latest_result = MarketStructureResult()