"""
Average Directional Index (ADX) indicator implementation.

This module computes the ADX trend-strength indicator used by the
Market Regime Detector.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

@dataclass(frozen=True)
class ADXResult:
    """
    Result returned after computing the ADX indicator.
    """

    adx: float
    plus_di: float
    minus_di: float
    trend_strength: float

class ADXIndicator:
    """
    Stateful ADX calculator.

    Future versions will maintain rolling history so the detector
    does not need to recompute historical values every candle.
    """

    def __init__(
        self,
        period: int = 14,
    ) -> None:

        self._period = period

        self._history = deque(maxlen=period)

        self._smoothed_tr = 0.0

        self._smoothed_plus_dm = 0.0

        self._smoothed_minus_dm = 0.0

        self._adx = 0.0

        self._dx_history = deque(maxlen=period)


    def update(
        self,
        high: float,
        low: float,
        close: float,
    ) -> ADXResult:
        """
        Update the indicator with one completed market bar.
        """

        self._history.append(
            (
                high,
                low,
                close,
            )
        )

        return ADXResult(
            adx=0.0,
            plus_di=0.0,
            minus_di=0.0,
            trend_strength=0.0,
        )
    

    def is_ready(self) -> bool:
        """
        Return True when enough history exists to compute ADX.
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
    def _directional_movement(
        previous_high: float,
        previous_low: float,
        current_high: float,
        current_low: float,
    ) -> tuple[float, float]:
        """
        Compute the positive and negative directional movement.
        """

        up_move = current_high - previous_high
        down_move = previous_low - current_low

        plus_dm = 0.0
        minus_dm = 0.0

        if up_move > down_move and up_move > 0.0:
            plus_dm = up_move

        if down_move > up_move and down_move > 0.0:
            minus_dm = down_move

        return plus_dm, minus_dm
    



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
    

    @staticmethod
    def _calculate_di(
        smoothed_dm: float,
        smoothed_tr: float,
    ) -> float:
        """
        Calculate a Directional Indicator (+DI or -DI).
        """

        if smoothed_tr <= 0.0:
            return 0.0

        return 100.0 * (smoothed_dm / smoothed_tr)
    

    @staticmethod
    def _calculate_dx(
        plus_di: float,
        minus_di: float,
    ) -> float:
        """
        Calculate the Directional Index (DX).
        """

        denominator = plus_di + minus_di

        if denominator <= 0.0:
            return 0.0

        return (
            abs(plus_di - minus_di)
            / denominator
        ) * 100.0