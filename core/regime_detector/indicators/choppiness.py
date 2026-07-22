from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ChoppinessResult:
    """
    Result returned after computing the Choppiness Index.
    """

    choppiness: float


class ChoppinessIndicator:
    """
    Stateful Choppiness Index calculator.
    """

    def __init__(
        self,
        period: int = 14,
    ) -> None:
        if period < 2:
            raise ValueError(
                "period must be at least 2."
            )

        self._period = period

        self._history: deque[tuple[float, float, float]] = deque(
            maxlen=period,
        )

    def is_ready(self) -> bool:
        """
        Return True when enough history exists.
        """

        return len(self._history) >= self._period

    def history_size(self) -> int:
        """
        Return the number of stored bars.
        """

        return len(self._history)

    def update(
        self,
        high: float,
        low: float,
        close: float,
    ) -> ChoppinessResult:
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

        if not self.is_ready():
            return ChoppinessResult(
                choppiness=0.0,
            )

        choppiness = self._calculate_choppiness()

        return ChoppinessResult(
            choppiness=choppiness,
        )

    def _calculate_choppiness(
        self,
    ) -> float:
        """
        Calculate the Choppiness Index from stored history.
        """

        history = list(self._history)

        highest_high = max(
            high
            for high, _, _ in history
        )

        lowest_low = min(
            low
            for _, low, _ in history
        )

        price_range = highest_high - lowest_low

        if price_range <= 0.0:
            return 100.0

        total_true_range = 0.0

        for index, (high, low, _close) in enumerate(history):
            if index == 0:
                true_range = high - low
            else:
                previous_close = history[index - 1][2]

                true_range = max(
                    high - low,
                    abs(high - previous_close),
                    abs(low - previous_close),
                )

            total_true_range += true_range

        if total_true_range <= 0.0:
            return 100.0

        choppiness = (
            100.0
            * math.log10(
                total_true_range / price_range
            )
            / math.log10(self._period)
        )

        return max(
            0.0,
            min(choppiness, 100.0),
        )