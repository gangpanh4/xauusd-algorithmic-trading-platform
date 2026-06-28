"""
Average True Range (ATR) indicator implementation.

This module computes the ATR volatility indicator used by the
Market Regime Detector.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class ATRResult:
    """
    Result returned after computing the ATR indicator.
    """

    atr: float

    normalized_atr: float


class ATRIndicator:
    """
    Stateful ATR calculator using Wilder's smoothing.
    """

    def __init__(
        self,
        period: int = 14,
    ) -> None:

        self._period = period

        self._history = deque(maxlen=period)

        self._smoothed_tr = 0.0

        self._atr = 0.0

        self._initialized = False


    def update(
        self,
        high: float,
        low: float,
        close: float,
    ) -> ATRResult:
        """
        Update the indicator with one completed market bar.
        """

        current_bar = (
            high,
            low,
            close,
        )

        self._history.append(current_bar)

        if not self.is_ready():
            return ATRResult(
                atr=0.0,
                normalized_atr=0.0,
            )

        previous_high, previous_low, previous_close = self._history[-2]

        current_high, current_low, current_close = self._history[-1]

        true_range = self._true_range(
            previous_close=previous_close,
            high=current_high,
            low=current_low,
        )

        if not self._initialized:
            self._smoothed_tr = true_range
            self._initialized = True

            return ATRResult(
                atr=0.0,
                normalized_atr=0.0,
            )

        self._smoothed_tr = self._wilder_smoothing(
            previous_value=self._smoothed_tr,
            new_value=true_range,
            period=self._period,
        )

        self._atr = self._smoothed_tr / self._period

        normalized_atr = 0.0

        if current_close > 0.0:
            normalized_atr = self._atr / current_close

        return ATRResult(
            atr=self._atr,
            normalized_atr=normalized_atr,
        )


    def is_ready(self) -> bool:
        """
        Return True when enough history exists to compute ATR.
        """

        return len(self._history) >= self._period


    def history_size(self) -> int:
        """
        Return the number of stored market bars.
        """

        return len(self._history)


    @staticmethod
    def _true_range(
        previous_close: float,
        high: float,
        low: float,
    ) -> float:
        """
        Compute the True Range for one market bar.
        """

        return max(
            high - low,
            abs(high - previous_close),
            abs(low - previous_close),
        )


    @staticmethod
    def _wilder_smoothing(
        previous_value: float,
        new_value: float,
        period: int,
    ) -> float:
        """
        Apply Wilder's smoothing method.
        """

        return previous_value - (
            previous_value / period
        ) + new_value