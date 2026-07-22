"""
Fair Value Gap Detection Engine.
"""

from __future__ import annotations

from dataclasses import replace

from core.data.models import MarketBar
from core.fair_value_gap_detector.config import (
    FairValueGapDetectorConfig,
)
from core.fair_value_gap_detector.enums import (
    FairValueGapStatus,
    FairValueGapType,
)
from core.fair_value_gap_detector.models import (
    FairValueGap,
    FairValueGapCandidate,
)
from core.fair_value_gap_detector.state import (
    FairValueGapDetectorState,
)


class FairValueGapDetector:
    """
    Detect and manage ICT Fair Value Gaps.

    Detection uses the standard three-candle non-overlap rule.
    Domain models remain immutable. Lifecycle transitions create
    replacement snapshots inside detector-owned runtime state.
    """

    _ARCHIVE_AGE_BARS = 100

    def __init__(
        self,
        config: FairValueGapDetectorConfig | None = None,
    ) -> None:
        self.config = (
            config
            or FairValueGapDetectorConfig()
        )
        self.state = FairValueGapDetectorState()

    def reset(
        self,
    ) -> None:
        self.state.reset()

    def process(
        self,
        bars: list[MarketBar],
    ) -> FairValueGapCandidate | None:
        """
        Detect a candidate from the final three completed bars.
        """

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

        self.state.pending_candidates.append(
            candidate
        )
        self.state.last_gap = candidate

        return candidate

    def update(
        self,
        latest_bar: MarketBar,
    ) -> None:
        """
        Advance all candidate and confirmed-gap lifecycles.

        A candidate is promoted only after receiving a later
        completed bar. The confirming bar may immediately
        mitigate or invalidate the promoted gap.
        """

        self._promote_candidates(
            latest_bar=latest_bar,
        )
        self._update_confirmed_gaps(
            latest_bar=latest_bar,
        )
        self._synchronize_lifecycle_collections()
        self._refresh_last_gap()

    def _promote_candidates(
        self,
        *,
        latest_bar: MarketBar,
    ) -> None:
        """
        Promote eligible immutable candidates into confirmed gaps.
        """

        remaining: list[
            FairValueGapCandidate
        ] = []

        promoted: list[
            FairValueGap
        ] = []

        for candidate in (
            self.state.pending_candidates
        ):
            if (
                latest_bar.timestamp
                <= candidate.timestamp
            ):
                remaining.append(candidate)
                continue

            promoted.append(
                FairValueGap(
                    id=self.state.next_gap_id,
                    timestamp=candidate.timestamp,
                    gap_type=candidate.gap_type,
                    top_price=candidate.top_price,
                    bottom_price=(
                        candidate.bottom_price
                    ),
                    first_bar=candidate.first_bar,
                    middle_bar=candidate.middle_bar,
                    third_bar=candidate.third_bar,
                    equilibrium_price=(
                        candidate.equilibrium_price
                    ),
                    is_discount_zone=(
                        candidate.is_discount_zone
                    ),
                    is_premium_zone=(
                        candidate.is_premium_zone
                    ),
                    quality_score=(
                        candidate.quality_score
                    ),
                    age=0,
                    status=(
                        FairValueGapStatus.ACTIVE
                    ),
                )
            )

            self.state.next_gap_id += 1

        self.state.pending_candidates = (
            remaining
        )
        self.state.confirmed_gaps.extend(
            promoted
        )

    def _update_confirmed_gaps(
        self,
        *,
        latest_bar: MarketBar,
    ) -> None:
        """
        Update immutable confirmed-gap snapshots.
        """

        updated_gaps: list[
            FairValueGap
        ] = []

        for gap in self.state.confirmed_gaps:
            if (
                gap.status
                is FairValueGapStatus.ARCHIVED
            ):
                updated_gaps.append(gap)
                continue

            updated_gap = replace(
                gap,
                age=gap.age + 1,
            )

            if updated_gap.is_active:
                updated_gap = (
                    self._check_mitigation(
                        gap=updated_gap,
                        latest_bar=latest_bar,
                    )
                )

            updated_gaps.append(
                updated_gap
            )

        self.state.confirmed_gaps = (
            updated_gaps
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

            if (
                gap
                >= self.config.minimum_gap_size
            ):
                equilibrium = (
                    third.low
                    + first.high
                ) / 2.0

                return FairValueGapCandidate(
                    timestamp=third.timestamp,
                    gap_type=(
                        FairValueGapType.BULLISH
                    ),
                    top_price=third.low,
                    bottom_price=first.high,
                    first_bar=first,
                    middle_bar=middle,
                    third_bar=third,
                    equilibrium_price=equilibrium,
                    is_discount_zone=True,
                    is_premium_zone=False,
                    quality_score=(
                        self._quality_score(gap)
                    ),
                )

        # ----------------------------
        # Bearish
        # ----------------------------

        if first.low > third.high:
            gap = first.low - third.high

            if (
                gap
                >= self.config.minimum_gap_size
            ):
                equilibrium = (
                    first.low
                    + third.high
                ) / 2.0

                return FairValueGapCandidate(
                    timestamp=third.timestamp,
                    gap_type=(
                        FairValueGapType.BEARISH
                    ),
                    top_price=first.low,
                    bottom_price=third.high,
                    first_bar=first,
                    middle_bar=middle,
                    third_bar=third,
                    equilibrium_price=equilibrium,
                    is_discount_zone=False,
                    is_premium_zone=True,
                    quality_score=(
                        self._quality_score(gap)
                    ),
                )

        return None

    def _quality_score(
        self,
        gap_size: float,
    ) -> float:
        """
        Return the existing raw-price score on a 0..100 scale.

        This preserves current scoring behavior. ATR-normalized
        quality should be introduced as a separate later change.
        """

        score = gap_size * 100.0

        return min(score, 100.0)

    def _check_mitigation(
        self,
        *,
        gap: FairValueGap,
        latest_bar: MarketBar,
    ) -> FairValueGap:
        """
        Return an updated immutable lifecycle snapshot.

        Full boundary violation takes precedence over midpoint
        mitigation.
        """

        if (
            gap.gap_type
            is FairValueGapType.BULLISH
        ):
            if (
                latest_bar.low
                <= gap.bottom_price
            ):
                return replace(
                    gap,
                    status=(
                        FairValueGapStatus.INVALIDATED
                    ),
                )

            if (
                latest_bar.low
                <= gap.equilibrium_price
            ):
                return replace(
                    gap,
                    status=(
                        FairValueGapStatus.MITIGATED
                    ),
                )

        if (
            gap.gap_type
            is FairValueGapType.BEARISH
        ):
            if (
                latest_bar.high
                >= gap.top_price
            ):
                return replace(
                    gap,
                    status=(
                        FairValueGapStatus.INVALIDATED
                    ),
                )

            if (
                latest_bar.high
                >= gap.equilibrium_price
            ):
                return replace(
                    gap,
                    status=(
                        FairValueGapStatus.MITIGATED
                    ),
                )

        return gap

    def _archive_old_gaps(
        self,
    ) -> None:
        """
        Archive terminal gaps after the existing 100-bar age.
        """

        archived: list[
            FairValueGap
        ] = []

        for gap in self.state.confirmed_gaps:
            if (
                gap.status
                in {
                    FairValueGapStatus.MITIGATED,
                    FairValueGapStatus.INVALIDATED,
                }
                and gap.age
                >= self._ARCHIVE_AGE_BARS
            ):
                archived.append(
                    replace(
                        gap,
                        status=(
                            FairValueGapStatus.ARCHIVED
                        ),
                    )
                )
                continue

            archived.append(gap)

        self.state.confirmed_gaps = archived

    def _synchronize_lifecycle_collections(
        self,
    ) -> None:
        """
        Rebuild lifecycle indexes from confirmed-gap snapshots.
        """

        self.state.active_gaps = [
            gap
            for gap
            in self.state.confirmed_gaps
            if (
                gap.status
                is FairValueGapStatus.ACTIVE
            )
        ]

        self.state.mitigated_gaps = [
            gap
            for gap
            in self.state.confirmed_gaps
            if (
                gap.status
                is FairValueGapStatus.MITIGATED
            )
        ]

        self.state.invalidated_gaps = [
            gap
            for gap
            in self.state.confirmed_gaps
            if (
                gap.status
                is FairValueGapStatus.INVALIDATED
            )
        ]

        self.state.archived_gaps = [
            gap
            for gap
            in self.state.confirmed_gaps
            if (
                gap.status
                is FairValueGapStatus.ARCHIVED
            )
        ]

    def _refresh_last_gap(
        self,
    ) -> None:
        """
        Refresh the newest candidate or confirmed-gap reference.
        """

        gaps: list[
            FairValueGap
            | FairValueGapCandidate
        ] = [
            *self.state.confirmed_gaps,
            *self.state.pending_candidates,
        ]

        if not gaps:
            self.state.last_gap = None
            return

        self.state.last_gap = max(
            gaps,
            key=lambda gap: gap.timestamp,
        )

    def get_state(
        self,
    ) -> FairValueGapDetectorState:
        """
        Return detector runtime state.
        """

        return self.state

    def get_last_candidate(
        self,
    ) -> FairValueGapCandidate | None:
        """
        Return the newest unconfirmed candidate.
        """

        if not self.state.pending_candidates:
            return None

        return max(
            self.state.pending_candidates,
            key=lambda candidate: (
                candidate.timestamp
            ),
        )