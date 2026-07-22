from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class EMAResult:
    """
    Result returned after computing EMA.
    """

    ema: float


class EMAIndicator:
    """
    Stateful Exponential Moving Average calculator.
    """

    def __init__(
        self,
        period: int = 20,
    ) -> None:

        self._period = period
        self._history = deque(maxlen=period)

        self._ema = 0.0
        self._initialized = False

    def is_ready(self) -> bool:
        """
        Return True once enough data has been collected.
        """
        return len(self._history) >= self._period

    def history_size(self) -> int:
        """
        Return the number of values currently stored.
        """
        return len(self._history)
    

    def update(
    self,
    close: float,
    ) -> EMAResult:
        """
        Update the indicator with one completed closing price.
        """

        self._history.append(close)

        if not self.is_ready():
            return EMAResult(
                ema=0.0,
            )
        
        if not self._initialized:
            self._initialize()

            return EMAResult(
                ema=self._ema,
            )
        
        self._ema = self._calculate_ema(
            previous_ema=self._ema,
            close=close,
            period=self._period,
        )

        return EMAResult(
            ema=self._ema,
        )

    def _initialize(
        self,
    ) -> None:
        """
        Initialize the EMA using the Simple Moving Average.
        """

        self._ema = sum(self._history) / len(self._history)

        self._initialized = True

    @staticmethod
    def _calculate_ema(
        previous_ema: float,
        close: float,
        period: int,
    ) -> float:
        """
        Calculate the next EMA value.
        """

        multiplier = 2.0 / (period + 1)

        return (
            close * multiplier
            + previous_ema * (1.0 - multiplier)
        )