"""
Fair Value Gap Detection Engine.
"""

from __future__ import annotations

from core.data.models import (
    MarketBar,
)

from core.fair_value_gap_detector.config import (
    FairValueGapDetectorConfig,
)

from core.fair_value_gap_detector.enums import (
    FairValueGapStatus,
    FairValueGapType,
)

from core.fair_value_gap_detector.models import (
    FairValueGapCandidate,
)

from core.fair_value_gap_detector.state import (
    FairValueGapDetectorState,
)


class FairValueGapDetector:
    """
    Detect ICT Fair Value Gaps.

    Version 2

    • Bullish FVG
    • Bearish FVG
    • Premium / Discount
    • Initial Quality Score
    """

    def __init__(
        self,
        config: FairValueGapDetectorConfig | None = None,
    ) -> None:

        self.config = config or FairValueGapDetectorConfig()

        self.state = FairValueGapDetectorState()

    def reset(
        self,
    ) -> None:
        self.state.reset()

    def process(
        self,
        bars: list[MarketBar],
    ) -> FairValueGapCandidate | None:

        self.state.processed_count += 1

        if len(bars) < 3:
            return None

        candidate = self._detect_gap(
            first=bars[-3],
            middle=bars[-2],
            third=bars[-1],
        )

        if candidate is None:
            return None

        self.state.pending_candidates.append(candidate)

        return candidate

    def update(
        self,
        latest_bar: MarketBar,
    ) -> None:
        """
        Update all active Fair Value Gaps using the newest
        completed candle.
        """

        for gap in self.state.pending_candidates:

            if gap.status is not FairValueGapStatus.NEW:
                continue

            gap.status = FairValueGapStatus.ACTIVE

        for gap in self.state.confirmed_gaps:

            if not gap.is_active:
                continue

            gap.age += 1

            self._check_mitigation(
                gap=gap,
                latest_bar=latest_bar,
            )

        self._archive_old_gaps()

    def _detect_gap(
        self,
        *,
        first: MarketBar,
        middle: MarketBar,
        third: MarketBar,
    ) -> FairValueGapCandidate | None:

        # ----------------------------
        # Bullish
        # ----------------------------

        if first.high < third.low:

            gap = third.low - first.high

            if gap >= self.config.minimum_gap_size:

                equilibrium = (
                    third.low + first.high
                ) / 2.0

                return FairValueGapCandidate(
                    timestamp=third.timestamp,
                    gap_type=FairValueGapType.BULLISH,
                    top_price=third.low,
                    bottom_price=first.high,
                    first_bar=first,
                    middle_bar=middle,
                    third_bar=third,
                    equilibrium_price=equilibrium,
                    is_discount_zone=True,
                    is_premium_zone=False,
                    quality_score=self._quality_score(
                        gap,
                    ),
                )

        # ----------------------------
        # Bearish
        # ----------------------------

        if first.low > third.high:

            gap = first.low - third.high

            if gap >= self.config.minimum_gap_size:

                equilibrium = (
                    first.low + third.high
                ) / 2.0

                return FairValueGapCandidate(
                    timestamp=third.timestamp,
                    gap_type=FairValueGapType.BEARISH,
                    top_price=first.low,
                    bottom_price=third.high,
                    first_bar=first,
                    middle_bar=middle,
                    third_bar=third,
                    equilibrium_price=equilibrium,
                    is_discount_zone=False,
                    is_premium_zone=True,
                    quality_score=self._quality_score(
                        gap,
                    ),
                )

        return None

    def _quality_score(
        self,
        gap_size: float,
    ) -> float:
        """
        Initial quality score.

        Version 1 uses only gap size.
        """

        score = gap_size * 100.0

        return min(score, 100.0)

    def _check_mitigation(
        self,
        *,
        gap,
        latest_bar: MarketBar,
    ) -> None:
        """
        Detect whether an active Fair Value Gap has been
        mitigated.
        """

        if gap.gap_type is FairValueGapType.BULLISH:

            if latest_bar.low <= gap.equilibrium_price:

                gap.status = FairValueGapStatus.MITIGATED

                return

        if gap.gap_type is FairValueGapType.BEARISH:

            if latest_bar.high >= gap.equilibrium_price:

                gap.status = FairValueGapStatus.MITIGATED

    def _archive_old_gaps(
        self,
    ) -> None:
        """
        Archive very old mitigated gaps.
        """

        for gap in self.state.confirmed_gaps:

            if (
                gap.is_mitigated
                and gap.age >= 100
            ):
                gap.status = FairValueGapStatus.ARCHIVED

    def get_last_candidate(
        self,
    ) -> FairValueGapCandidate | None:

        if not self.state.pending_candidates:
            return None

        return self.state.pending_candidates[-1]