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

        # Need period + 1 bars to compute period TR/DM values.
        self._history = deque(maxlen=period + 1)

        self._smoothed_tr = 0.0
        self._smoothed_plus_dm = 0.0
        self._smoothed_minus_dm = 0.0

        self._adx = 0.0

        self._initialized = False

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


        current_bar = (
            high,
            low,
            close,
        )

        self._history.append(current_bar)


        if not self.is_ready():
            return ADXResult(
                adx=0.0,
                plus_di=0.0,
                minus_di=0.0,
                trend_strength=0.0,
            )
    

        previous_high, previous_low, previous_close = self._history[-2]

        current_high, current_low, _ = self._history[-1]

        true_range = self._true_range(
            previous_close=previous_close,
            high=current_high,
            low=current_low,
        )

        plus_dm, minus_dm = self._directional_movement(
            previous_high=previous_high,
            previous_low=previous_low,
            current_high=current_high,
            current_low=current_low,
        )


        if not self._initialized:
            self._initialize_smoothing()

            plus_di = self._calculate_di(
                smoothed_dm=self._smoothed_plus_dm,
                smoothed_tr=self._smoothed_tr,
            )

            minus_di = self._calculate_di(
                smoothed_dm=self._smoothed_minus_dm,
                smoothed_tr=self._smoothed_tr,
            )

            dx = self._calculate_dx(
                plus_di=plus_di,
                minus_di=minus_di,
            )

            self._dx_history.append(dx)

            return ADXResult(
                adx=0.0,
                plus_di=plus_di,
                minus_di=minus_di,
                trend_strength=0.0,
            )

        self._smoothed_tr = self._wilder_smoothing(
            previous_value=self._smoothed_tr,
            new_value=true_range,
            period=self._period,
        )

        self._smoothed_plus_dm = self._wilder_smoothing(
            previous_value=self._smoothed_plus_dm,
            new_value=plus_dm,
            period=self._period,
        )

        self._smoothed_minus_dm = self._wilder_smoothing(
            previous_value=self._smoothed_minus_dm,
            new_value=minus_dm,
            period=self._period,
        )

        plus_di = self._calculate_di(
            smoothed_dm=self._smoothed_plus_dm,
            smoothed_tr=self._smoothed_tr,
        )

        minus_di = self._calculate_di(
            smoothed_dm=self._smoothed_minus_dm,
            smoothed_tr=self._smoothed_tr,
        )

        dx = self._calculate_dx(
            plus_di=plus_di,
            minus_di=minus_di,
        )

        self._dx_history.append(dx)

        if len(self._dx_history) < self._period:
            return ADXResult(
                adx=0.0,
                plus_di=plus_di,
                minus_di=minus_di,
                trend_strength=0.0,
            )

        if self._adx == 0.0:
            self._adx = (
                sum(self._dx_history)
                / len(self._dx_history)
            )
        else:
            self._adx = self._smooth_adx(
                previous_adx=self._adx,
                new_dx=dx,
                period=self._period,
            )

        return ADXResult(
            adx=self._adx,
            plus_di=plus_di,
            minus_di=minus_di,
            trend_strength=self._adx / 100.0,
        )



    def is_ready(self) -> bool:
        """
        Return True when enough history exists to compute ADX.
        """

        return len(self._history) >= self._period + 1
    

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
    

    def _initialize_smoothing(
        self,
    ) -> None:
        """
        Initialize Wilder's smoothed values using the first
        ``period`` True Range and Directional Movement values.
        """

        tr_sum = 0.0
        plus_sum = 0.0
        minus_sum = 0.0

        for index in range(1, len(self._history)):
            previous_high, previous_low, previous_close = (
                self._history[index - 1]
            )

            current_high, current_low, _ = (
                self._history[index]
            )

            tr_sum += self._true_range(
                previous_close=previous_close,
                high=current_high,
                low=current_low,
            )

            plus_dm, minus_dm = self._directional_movement(
                previous_high=previous_high,
                previous_low=previous_low,
                current_high=current_high,
                current_low=current_low,
            )

            plus_sum += plus_dm
            minus_sum += minus_dm

        self._smoothed_tr = tr_sum
        self._smoothed_plus_dm = plus_sum
        self._smoothed_minus_dm = minus_sum

        self._initialized = True


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
    
    @staticmethod
    def _smooth_adx(
        previous_adx: float,
        new_dx: float,
        period: int,
    ) -> float:
        """
        Apply Wilder's smoothing to the ADX average.
        """

        return (
            (
                previous_adx
                * (period - 1)
            )
            + new_dx
        ) / period