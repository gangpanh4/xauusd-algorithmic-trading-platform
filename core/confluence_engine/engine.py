"""
Confluence Engine.

Combines multiple market structure signals into a
single confluence score.
"""

from __future__ import annotations

from core.confluence_engine.config import (
    ConfluenceEngineConfig,
)
from core.confluence_engine.models import (
    ConfluenceFactor,
    ConfluenceResult,
    EvidenceContext,
)
from core.confluence_engine.state import (
    ConfluenceEngineState,
)
from core.multi_timeframe.models import (
    MultiTimeframeResult,
)
from core.market_structure.models import (
    MarketStructureResult,
)


class ConfluenceEngine:
    """
    Scores institutional confluence.

    Version 1

    • Liquidity
    • BOS
    • CHOCH
    • Order Block
    • Fair Value Gap
    • Trend

    Future versions will include:

    • Session
    • ATR
    • Volume
    • SMT
    • Premium / Discount
    • Multi-timeframe agreement
    """

    def __init__(
        self,
        config: ConfluenceEngineConfig | None = None,
    ) -> None:

        self.config = (
            config
            or ConfluenceEngineConfig()
        )

        self.state = ConfluenceEngineState()

    def reset(
        self,
    ) -> None:
        """
        Reset runtime state.
        """

        self.state.reset()

    def evaluate(
        self,
        *,
        liquidity: bool,
        bos: bool,
        choch: bool,
        order_block: bool,
        fair_value_gap: bool,
        trend: bool,
    ) -> ConfluenceResult:
        """
        Evaluate overall confluence.
        """

        self.state.processed_count += 1

        factors: list[
            ConfluenceFactor
        ] = []

        checks = [
            (
                "Liquidity",
                liquidity,
                self.config.liquidity_weight,
            ),
            (
                "Break of Structure",
                bos,
                self.config.bos_weight,
            ),
            (
                "Change of Character",
                choch,
                self.config.choch_weight,
            ),
            (
                "Order Block",
                order_block,
                self.config.order_block_weight,
            ),
            (
                "Fair Value Gap",
                fair_value_gap,
                self.config.fair_value_gap_weight,
            ),
            (
                "Trend",
                trend,
                self.config.trend_weight,
            ),
        ]

        score = 0.0

        for name, passed, weight in checks:
            score += self._evaluate_factor(
                factors=factors,
                name=name,
                quality=1.0 if passed else 0.0,
                weight=weight,
            )

        return self._build_result(
            score=score,
            factors=factors,
        )

    def evaluate_multi_timeframe(
        self,
        multi_timeframe: MultiTimeframeResult,
    ) -> ConfluenceResult:
        """
        Version 2 entry point.

        Converts the aggregated multi-timeframe analysis into the
        existing Version 1 confluence model.

        This preserves the current scoring implementation while
        allowing the Trading Pipeline to operate on the richer
        Multi-Timeframe architecture.
        """

        #
        # Lowest timeframe contains the execution setup.
        #
        execution = multi_timeframe.m5

        structure = execution.market_structure
        price_action = execution.price_action

        #
        # Version 2 evidence evaluation.
        #

        evidence = EvidenceContext(
            structure_quality=(
                self._evaluate_market_structure(
                    structure,
                )
            ),

            liquidity_quality=(
                1.0
                if structure is not None
                and structure.last_liquidity is not None
                else 0.0
            ),

            order_block_quality=(
                1.0
                if price_action is not None
                and price_action.last_order_block is not None
                else 0.0
            ),

            fair_value_gap_quality=(
                1.0
                if price_action is not None
                and price_action.last_fair_value_gap is not None
                else 0.0
            ),

            trend_quality=(
                1.0
                if structure is not None
                and structure.current_trend is not None
                else 0.0
            ),
        )

        return self.evaluate_evidence(
            evidence,
        )

    def evaluate_evidence(
        self,
        evidence: EvidenceContext,
    ) -> ConfluenceResult:
        """
        Version 2 evidence-based evaluation.

        Scores normalized evidence directly instead of
        converting it back into boolean signals.
        """

        self.state.processed_count += 1

        factors: list[ConfluenceFactor] = []

        score = 0.0

        score += self._evaluate_factor(
            factors=factors,
            name="Liquidity",
            weight=self.config.liquidity_weight,
            quality=evidence.liquidity_quality,
        )

        score += self._evaluate_factor(
            factors=factors,
            name="Break of Structure",
            weight=self.config.bos_weight,
            quality=evidence.structure_quality,
        )

        score += self._evaluate_factor(
            factors=factors,
            name="Change of Character",
            weight=self.config.choch_weight,
            quality=evidence.structure_quality,
        )

        score += self._evaluate_factor(
            factors=factors,
            name="Order Block",
            weight=self.config.order_block_weight,
            quality=evidence.order_block_quality,
        )

        score += self._evaluate_factor(
            factors=factors,
            name="Fair Value Gap",
            weight=self.config.fair_value_gap_weight,
            quality=evidence.fair_value_gap_quality,
        )

        score += self._evaluate_factor(
            factors=factors,
            name="Trend",
            weight=self.config.trend_weight,
            quality=evidence.trend_quality,
        )

        return self._build_result(
            score=score,
            factors=factors,
        )

    def _build_result(
        self,
        *,
        score: float,
        factors: list[ConfluenceFactor],
    ) -> ConfluenceResult:
        """
        Build a confluence result and update engine state.
        """

        approved = (
            score
            >= self.config.minimum_approval_score
        )

        result = ConfluenceResult(
            score=score,
            maximum_score=self.config.maximum_score,
            confidence=(
                score
                / self.config.maximum_score
            ),
            approved=approved,
            factors=factors,
        )

        self.state.last_result = result
        self.state.history.append(result)

        if approved:
            self.state.approved_count += 1
        else:
            self.state.rejected_count += 1

        return result

    def _evaluate_factor(
        self,
        *,
        factors: list[ConfluenceFactor],
        name: str,
        weight: float,
        quality: float,
    ) -> float:
        """
        Evaluate one confluence factor.
        """

        quality = max(
            0.0,
            min(
                quality,
                1.0,
            ),
        )

        score = weight * quality

        passed = quality > 0.0

        factor = ConfluenceFactor(
            name=name,
            passed=passed,
            score=score,
            weight=weight,
            reason=(
                f"Quality: {quality:.2f}"
                if passed
                else "No evidence"
            ),
        )

        factors.append(factor)

        return score

    def _evaluate_market_structure(
        self,
        structure: MarketStructureResult | None,
    ) -> float:
        """
        Evaluate overall market structure quality.

        Version 2 begins consuming richer evidence instead
        of relying solely on boolean structure signals.

        Returns a normalized value between 0.0 and 1.0.
        """

        if structure is None:
            return 0.0

        return max(
            0.0,
            min(
                structure.structure_confidence,
                1.0,
            ),
        )