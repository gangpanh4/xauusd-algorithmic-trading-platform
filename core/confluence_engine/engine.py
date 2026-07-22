"""
Confluence Engine.

Combines execution-timeframe market facts with higher-timeframe directional
agreement into a normalized confluence score.
"""

from __future__ import annotations

from math import isfinite
from typing import Iterable

from core.confluence_engine.config import ConfluenceEngineConfig
from core.confluence_engine.models import (
    ConfluenceFactor,
    ConfluenceResult,
    EvidenceContext,
)
from core.confluence_engine.state import ConfluenceEngineState
from core.fair_value_gap_detector.enums import FairValueGapType
from core.market_structure.enums import (
    MarketTrend,
    OrderBlockType,
    TrendDirection,
)
from core.market_structure.models import MarketStructureResult
from core.multi_timeframe.enums import MarketBias, TimeframeAlignment
from core.multi_timeframe.models import MultiTimeframeResult, TimeframeState


class ConfluenceEngine:
    """Score institutional confluence on a stable 0-100 scale."""

    _HIGHER_TIMEFRAME_WEIGHTS: tuple[tuple[str, float], ...] = (
        ("weekly", 0.35),
        ("daily", 0.25),
        ("h4", 0.25),
        ("h1", 0.15),
    )

    def __init__(
        self,
        config: ConfluenceEngineConfig | None = None,
    ) -> None:
        self.config = config or ConfluenceEngineConfig()
        self._validate_config(self.config)
        self.state = ConfluenceEngineState()

    def reset(self) -> None:
        """Reset runtime state."""

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
        """Evaluate the legacy boolean confluence contract."""

        checks = (
            ("Liquidity", liquidity, self.config.liquidity_weight),
            ("Break of Structure", bos, self.config.bos_weight),
            ("Change of Character", choch, self.config.choch_weight),
            ("Order Block", order_block, self.config.order_block_weight),
            (
                "Fair Value Gap",
                fair_value_gap,
                self.config.fair_value_gap_weight,
            ),
            ("Trend", trend, self.config.trend_weight),
        )

        factors: list[ConfluenceFactor] = []
        score = 0.0
        for name, passed, weight in checks:
            if type(passed) is not bool:
                raise TypeError(f"{name} evidence must be bool")
            score += self._evaluate_factor(
                factors=factors,
                name=name,
                quality=1.0 if passed else 0.0,
                weight=weight,
            )

        return self._build_result(score=score, factors=factors)

    def evaluate_multi_timeframe(
        self,
        multi_timeframe: MultiTimeframeResult,
    ) -> ConfluenceResult:
        """
        Evaluate synchronized multi-timeframe evidence.

        Execution evidence comes from M5. The trend factor represents actual
        higher-timeframe directional agreement with the newest M5 structural
        break (or M5 bias when no break exists).
        """

        self._validate_multi_timeframe(multi_timeframe)

        execution = multi_timeframe.m5
        structure = execution.market_structure
        price_action = execution.price_action
        execution_direction = self._execution_direction(execution)

        factors: list[ConfluenceFactor] = []
        score = 0.0

        score += self._evaluate_factor(
            factors=factors,
            name="Liquidity",
            weight=self.config.liquidity_weight,
            quality=self._liquidity_quality(structure),
        )
        score += self._evaluate_factor(
            factors=factors,
            name="Break of Structure",
            weight=self.config.bos_weight,
            quality=self._bos_quality(structure),
        )
        score += self._evaluate_factor(
            factors=factors,
            name="Change of Character",
            weight=self.config.choch_weight,
            quality=self._choch_quality(structure),
        )
        score += self._evaluate_factor(
            factors=factors,
            name="Order Block",
            weight=self.config.order_block_weight,
            quality=self._order_block_quality(
                execution=execution,
                execution_direction=execution_direction,
            ),
        )
        score += self._evaluate_factor(
            factors=factors,
            name="Fair Value Gap",
            weight=self.config.fair_value_gap_weight,
            quality=self._fair_value_gap_quality(
                execution=execution,
                execution_direction=execution_direction,
            ),
        )
        score += self._evaluate_factor(
            factors=factors,
            name="Higher-Timeframe Agreement",
            weight=self.config.trend_weight,
            quality=self._higher_timeframe_agreement(
                multi_timeframe=multi_timeframe,
                execution_direction=execution_direction,
            ),
        )

        return self._build_result(score=score, factors=factors)

    def evaluate_evidence(
        self,
        evidence: EvidenceContext,
    ) -> ConfluenceResult:
        """Evaluate the legacy normalized evidence contract."""

        if not isinstance(evidence, EvidenceContext):
            raise TypeError("evidence must be EvidenceContext")

        qualities = {
            "structure_quality": evidence.structure_quality,
            "liquidity_quality": evidence.liquidity_quality,
            "order_block_quality": evidence.order_block_quality,
            "fair_value_gap_quality": evidence.fair_value_gap_quality,
            "trend_quality": evidence.trend_quality,
        }
        for name, value in qualities.items():
            self._validate_unit_interval(value, name=name)

        factors: list[ConfluenceFactor] = []
        score = 0.0

        # The legacy model exposes one combined structure quality. Preserve its
        # total 25-point influence while making the duplication explicit.
        score += self._evaluate_factor(
            factors=factors,
            name="Market Structure (BOS share)",
            weight=self.config.bos_weight,
            quality=evidence.structure_quality,
        )
        score += self._evaluate_factor(
            factors=factors,
            name="Market Structure (CHOCH share)",
            weight=self.config.choch_weight,
            quality=evidence.structure_quality,
        )
        score += self._evaluate_factor(
            factors=factors,
            name="Liquidity",
            weight=self.config.liquidity_weight,
            quality=evidence.liquidity_quality,
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

        return self._build_result(score=score, factors=factors)

    def _build_result(
        self,
        *,
        score: float,
        factors: list[ConfluenceFactor],
    ) -> ConfluenceResult:
        """Build a result and update runtime counters atomically."""

        if not isfinite(score) or score < 0.0:
            raise ValueError("score must be finite and non-negative")
        if score > self.config.maximum_score + 1e-9:
            raise ValueError("score exceeds configured maximum")

        confidence = score / self.config.maximum_score
        approved = confidence >= self.config.approval_ratio

        result = ConfluenceResult(
            score=round(score, 6),
            maximum_score=self.config.maximum_score,
            confidence=round(confidence, 6),
            approved=approved,
            factors=factors,
        )

        self.state.processed_count += 1
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
        """Evaluate one normalized confluence factor."""

        self._validate_unit_interval(quality, name=f"{name} quality")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("factor name must be non-empty")
        if not isfinite(weight) or weight < 0.0:
            raise ValueError("factor weight must be finite and non-negative")

        score = weight * quality
        factors.append(
            ConfluenceFactor(
                name=name,
                passed=quality > 0.0,
                score=round(score, 6),
                weight=weight,
                reason=(
                    f"Quality: {quality:.4f}; contribution: {score:.4f}"
                    if quality > 0.0
                    else "No evidence"
                ),
            )
        )
        return score

    def _bos_quality(self, structure: MarketStructureResult | None) -> float:
        if structure is None or structure.last_bos is None:
            return 0.0
        event = structure.last_bos
        freshness = self._event_freshness(
            explicit=structure.bos_freshness,
            age=event.age,
            decay=structure.freshness_decay_bars,
        )
        return self._mean_unit(
            (event.quality, event.strength, event.structure_score, event.power_score)
        ) * freshness

    def _choch_quality(self, structure: MarketStructureResult | None) -> float:
        if structure is None or structure.last_choch is None:
            return 0.0
        event = structure.last_choch
        freshness = self._event_freshness(
            explicit=structure.choch_freshness,
            age=event.age,
            decay=structure.freshness_decay_bars,
        )
        return self._mean_unit(
            (event.quality, event.strength, event.structure_score, event.power_score)
        ) * freshness

    def _liquidity_quality(
        self,
        structure: MarketStructureResult | None,
    ) -> float:
        if structure is None or structure.last_liquidity is None:
            return 0.0
        event = structure.last_liquidity
        freshness = self._event_freshness(
            explicit=structure.liquidity_freshness,
            age=event.age,
            decay=structure.freshness_decay_bars,
        )
        return self._mean_unit(
            (
                event.quality,
                event.sweep_strength,
                event.reaction_strength,
                event.reclaim_strength,
                event.density,
            )
        ) * freshness

    def _order_block_quality(
        self,
        *,
        execution: TimeframeState,
        execution_direction: MarketBias,
    ) -> float:
        price_action = execution.price_action
        if price_action is None or price_action.last_order_block is None:
            return 0.0

        block = price_action.last_order_block
        block_direction = (
            MarketBias.BULLISH
            if block.block_type is OrderBlockType.BULLISH
            else MarketBias.BEARISH
        )
        if (
            execution_direction is not MarketBias.NEUTRAL
            and block_direction is not execution_direction
        ):
            return 0.0

        confidence = price_action.price_action_confidence
        self._validate_unit_interval(
            confidence,
            name="price_action_confidence",
        )
        return confidence

    def _fair_value_gap_quality(
        self,
        *,
        execution: TimeframeState,
        execution_direction: MarketBias,
    ) -> float:
        price_action = execution.price_action
        if price_action is None or price_action.last_fair_value_gap is None:
            return 0.0

        gap = price_action.last_fair_value_gap
        gap_type = gap.gap_type
        gap_direction = (
            MarketBias.BULLISH
            if gap_type is FairValueGapType.BULLISH
            else MarketBias.BEARISH
        )
        if (
            execution_direction is not MarketBias.NEUTRAL
            and gap_direction is not execution_direction
        ):
            return 0.0

        raw_value = gap.quality_score
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
            raise TypeError("fair_value_gap quality must be numeric")
        raw_quality = float(raw_value)
        if not isfinite(raw_quality):
            raise ValueError("fair_value_gap quality must be finite")
        if raw_quality < 0.0 or raw_quality > 100.0:
            raise ValueError(
                "fair_value_gap quality must be within [0, 1] or [0, 100]"
            )
        quality = (
            raw_quality / 100.0
            if raw_quality > 1.0
            else raw_quality
        )
        age = int(getattr(gap, "age", 0))
        if age < 0:
            raise ValueError("fair_value_gap age must be non-negative")
        freshness = 0.5 ** (age / 8.0)
        return quality * freshness

    def _higher_timeframe_agreement(
        self,
        *,
        multi_timeframe: MultiTimeframeResult,
        execution_direction: MarketBias,
    ) -> float:
        if execution_direction is MarketBias.NEUTRAL:
            return 0.0

        agreement_weight = 0.0
        directional_coverage = 0.0
        for attribute, weight in self._HIGHER_TIMEFRAME_WEIGHTS:
            state = getattr(multi_timeframe, attribute)
            if state.bias is MarketBias.NEUTRAL:
                continue
            directional_coverage += weight
            if state.bias is execution_direction:
                agreement_weight += weight

        if directional_coverage <= 0.0:
            return 0.0

        agreement_ratio = agreement_weight / directional_coverage
        coverage_ratio = directional_coverage / sum(
            weight for _, weight in self._HIGHER_TIMEFRAME_WEIGHTS
        )

        alignment_multiplier = {
            TimeframeAlignment.ALIGNED: 1.0,
            TimeframeAlignment.PARTIAL: 0.85,
            TimeframeAlignment.CONFLICT: 0.50,
        }[multi_timeframe.overall_alignment]

        confidence = multi_timeframe.confidence
        self._validate_unit_interval(confidence, name="multi_timeframe confidence")
        return min(
            1.0,
            agreement_ratio
            * coverage_ratio
            * alignment_multiplier
            * confidence,
        )

    def _execution_direction(self, execution: TimeframeState) -> MarketBias:
        structure = execution.market_structure
        if structure is not None:
            events = [
                event
                for event in (structure.last_bos, structure.last_choch)
                if event is not None
            ]
            if events:
                newest = max(
                    events,
                    key=lambda event: (
                        event.confirmation_index,
                        event.timestamp,
                    ),
                )
                if newest.direction is TrendDirection.BULLISH:
                    return MarketBias.BULLISH
                if newest.direction is TrendDirection.BEARISH:
                    return MarketBias.BEARISH

            if structure.current_trend is MarketTrend.BULLISH:
                return MarketBias.BULLISH
            if structure.current_trend is MarketTrend.BEARISH:
                return MarketBias.BEARISH

        return execution.bias

    def _event_freshness(
        self,
        *,
        explicit: float,
        age: int,
        decay: int,
    ) -> float:
        self._validate_unit_interval(explicit, name="event freshness")
        if age < 0:
            raise ValueError("event age must be non-negative")
        if decay <= 0:
            raise ValueError("freshness_decay_bars must be positive")
        calculated = max(0.0, 1.0 - (age / decay))
        return min(explicit, calculated)

    def _mean_unit(self, values: Iterable[float]) -> float:
        validated: list[float] = []
        for value in values:
            self._validate_unit_interval(value, name="evidence component")
            validated.append(float(value))
        if not validated:
            return 0.0
        return sum(validated) / len(validated)

    def _validate_multi_timeframe(
        self,
        multi_timeframe: MultiTimeframeResult,
    ) -> None:
        if not isinstance(multi_timeframe, MultiTimeframeResult):
            raise TypeError("multi_timeframe must be MultiTimeframeResult")
        if not isinstance(multi_timeframe.overall_bias, MarketBias):
            raise TypeError("overall_bias must be MarketBias")
        if not isinstance(
            multi_timeframe.overall_alignment,
            TimeframeAlignment,
        ):
            raise TypeError("overall_alignment must be TimeframeAlignment")
        self._validate_unit_interval(
            multi_timeframe.confidence,
            name="multi_timeframe confidence",
        )
        for attribute in ("weekly", "daily", "h4", "h1", "m15", "m5"):
            state = getattr(multi_timeframe, attribute)
            if not isinstance(state, TimeframeState):
                raise TypeError(f"{attribute} must be TimeframeState")
            if not isinstance(state.bias, MarketBias):
                raise TypeError(f"{attribute}.bias must be MarketBias")
            self._validate_unit_interval(
                state.confidence,
                name=f"{attribute}.confidence",
            )

    def _validate_config(self, config: ConfluenceEngineConfig) -> None:
        if not isinstance(config, ConfluenceEngineConfig):
            raise TypeError("config must be ConfluenceEngineConfig")
        weights = (
            config.liquidity_weight,
            config.bos_weight,
            config.choch_weight,
            config.order_block_weight,
            config.fair_value_gap_weight,
            config.trend_weight,
        )
        for weight in weights:
            if isinstance(weight, bool) or not isfinite(weight) or weight < 0.0:
                raise ValueError("confluence weights must be finite and non-negative")
        if config.maximum_score <= 0.0:
            raise ValueError("maximum confluence score must be positive")
        if (
            isinstance(config.minimum_approval_score, bool)
            or not isfinite(config.minimum_approval_score)
            or not 0.0 <= config.minimum_approval_score <= config.maximum_score
        ):
            raise ValueError(
                "minimum_approval_score must be within [0, maximum_score]"
            )
        if type(config.debug_logging) is not bool:
            raise TypeError("debug_logging must be bool")

    @staticmethod
    def _validate_unit_interval(value: float, *, name: str) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be numeric")
        numeric = float(value)
        if not isfinite(numeric) or not 0.0 <= numeric <= 1.0:
            raise ValueError(f"{name} must be finite and within [0, 1]")
