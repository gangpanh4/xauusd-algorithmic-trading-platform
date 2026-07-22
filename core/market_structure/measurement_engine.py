"""
Market Structure Measurement Engine.

Computes quantitative measurements from the latest market
structure events. The engine performs no detection and owns
no persistent state. It simply measures the current market
relative to the most recent confirmed structure events.
"""

from __future__ import annotations

from core.data.models import MarketBar

from core.market_structure.config import (
    MarketStructureConfig,
)
from core.market_structure.measurement_config import (
    MeasurementConfig,
)
from core.market_structure.measurements import (
    MarketStructureMeasurements,
)
from core.market_structure.models import (
    BOSEvent,
    CHOCHEvent,
    LiquiditySweepEvent,
    SwingPoint,
)


class MeasurementEngine:
    """
    Calculates quantitative market structure measurements.
    """

    def __init__(
        self,
        config: MeasurementConfig | None = None,
    ) -> None:

        self.config = config or MeasurementConfig()

    def calculate(
        self,
        current_bar: MarketBar,
        last_bos: BOSEvent | None,
        last_choch: CHOCHEvent | None,
        last_liquidity: LiquiditySweepEvent | None,
        last_swing: SwingPoint | None,
    ) -> MarketStructureMeasurements:
        """
        Calculate all quantitative measurements for the
        current market state.
        """

        measurements = MarketStructureMeasurements()

        #
        # BOS
        #
        if last_bos is not None:
            self._measure_bos(
                measurements,
                current_bar,
                last_bos,
            )

        #
        # CHOCH
        #
        if last_choch is not None:
            self._measure_choch(
                measurements,
                current_bar,
                last_choch,
            )

        #
        # Liquidity
        #
        if last_liquidity is not None:
            self._measure_liquidity(
                measurements,
                current_bar,
                last_liquidity,
            )

        #
        # Swing
        #
        if last_swing is not None:
            self._measure_swing(
                measurements,
                current_bar,
                last_swing,
            )

        return measurements

    def _measure_bos(
        self,
        measurements: MarketStructureMeasurements,
        current_bar: MarketBar,
        last_bos: BOSEvent,
    ) -> None:

        measurements.bos_distance = (
            current_bar.close - last_bos.break_price
        )

        measurements.bos_age = max(
            0,
            self._bar_distance(
                current_bar.timestamp,
                last_bos.timestamp,
            ),
        )

    def _measure_choch(
        self,
        measurements: MarketStructureMeasurements,
        current_bar: MarketBar,
        last_choch: CHOCHEvent,
    ) -> None:

        measurements.choch_distance = (
            current_bar.close - last_choch.break_price
        )

        measurements.choch_age = max(
            0,
            self._bar_distance(
                current_bar.timestamp,
                last_choch.timestamp,
            ),
        )

    def _measure_liquidity(
        self,
        measurements: MarketStructureMeasurements,
        current_bar: MarketBar,
        last_liquidity: LiquiditySweepEvent,
    ) -> None:

        measurements.liquidity_distance = (
            current_bar.close - last_liquidity.sweep_price
        )

        measurements.liquidity_age = max(
            0,
            self._bar_distance(
                current_bar.timestamp,
                last_liquidity.timestamp,
            ),
        )

    def _measure_swing(
        self,
        measurements: MarketStructureMeasurements,
        current_bar: MarketBar,
        last_swing: SwingPoint,
    ) -> None:

        measurements.swing_distance = (
            current_bar.close - last_swing.price
        )

        measurements.swing_age = max(
            0,
            self._bar_distance(
                current_bar.timestamp,
                last_swing.timestamp,
            ),
        )

    @staticmethod
    def _bar_distance(
        current_timestamp,
        previous_timestamp,
    ) -> int:
        """
        Calculate elapsed bars between two timestamps.

        Version 1 returns zero because timestamps alone cannot
        reliably determine the number of completed bars.
        This method exists so future versions can use the
        engine's bar history for exact bar counting.
        """

        _ = current_timestamp
        _ = previous_timestamp

        return 0