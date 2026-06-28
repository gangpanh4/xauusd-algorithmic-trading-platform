"""
Efficiency Ratio (ER) indicator implementation.

This module computes Kaufman's Efficiency Ratio used by the
Market Regime Detector.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class EfficiencyRatioResult:
    """
    Result returned after computing the Efficiency Ratio.
    """

    efficiency_ratio: float


class EfficiencyRatioIndicator:
    """
    Stateful Kaufman Efficiency Ratio calculator.
    """

    def __init__(
        self,
        period: int = 14,
    ) -> None:

        self._period = period
        self._history = deque(maxlen=period + 1)



    def is_ready(self) -> bool:
        """
        Return True when enough history exists to compute ER.
        """

        return len(self._history) >= self._period + 1

    def history_size(self) -> int:
        """
        Return the number of stored closing prices.
        """

        return len(self._history)
    


    def update(
        self,
        close: float,
    ) -> EfficiencyRatioResult:
        """
        Update the indicator with one completed closing price.
        """

        self._history.append(close)

        if not self.is_ready():
            return EfficiencyRatioResult(
                efficiency_ratio=0.0,
            )
        
        first_close = self._history[0]

        last_close = self._history[-1]

        net_change = abs(
            last_close - first_close
        )


        total_movement = 0.0

        for i in range(1, len(self._history)):
            total_movement += abs(
                self._history[i]
                - self._history[i - 1]
            )

        if total_movement <= 0.0:
            return EfficiencyRatioResult(
                efficiency_ratio=0.0,
            )
        
        efficiency_ratio = (
            net_change / total_movement
        )

        return EfficiencyRatioResult(
            efficiency_ratio=efficiency_ratio,
        )