from dataclasses import dataclass
from collections import deque


@dataclass(frozen=True)
class EMASlopeResult:
    """
    Represents how fast the EMA is changing.

    slope:
        Positive = rising EMA
        Negative = falling EMA
    """
    slope: float


class EMASlopeIndicator:
    """
    Measures the rate of change of an EMA series.

    This indicator does NOT use price.
    It operates purely on EMA values to measure:
        "How fast is the EMA moving?"
    """

    def __init__(self, period: int):
        self._period = period
        self._ema_history: deque[float] = deque(maxlen=period + 1)

    def is_ready(self) -> bool:
        """
        Consistent with ATR / Momentum / Efficiency Ratio:
        require full lookback window.
        """
        return len(self._ema_history) >= self._period + 1

    def history_size(self) -> int:
        """
        Returns actual number of stored EMA values.
        """
        return len(self._ema_history)

    def update(self, ema: float) -> EMASlopeResult:
        """
        Update EMA history and compute slope.
        """
        self._ema_history.append(ema)

        if not self.is_ready():
            return EMASlopeResult(slope=0.0)

        current = self._ema_history[-1]
        previous = self._ema_history[-2]

        slope = current - previous

        return EMASlopeResult(slope=slope)