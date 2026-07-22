from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class MomentumResult:
    """
    Result returned after computing Momentum.
    """

    momentum: float


class MomentumIndicator:
    """
    Stateful Momentum calculator.
    """

    def __init__(
        self,
        period: int = 14,
    ) -> None:

        self._period = period
        self._history = deque(maxlen=period + 1)

    def is_ready(self) -> bool:
        return len(self._history) >= self._period + 1

    def history_size(self) -> int:
        return len(self._history)

    def update(
        self,
        close: float,
    ) -> MomentumResult:
        """
        Update the indicator with one completed closing price.
        """

        self._history.append(close)

        if not self.is_ready():
            return MomentumResult(
                momentum=0.0,
            )

        old_close = self._history[0]

        momentum = close - old_close

        return MomentumResult(
            momentum=momentum,
        )