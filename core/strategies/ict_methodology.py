"""Deterministic observational Inner Circle Trader methodology evaluator."""

from __future__ import annotations

from core.fair_value_gap_detector.enums import FairValueGapType
from core.market_structure.enums import TrendDirection
from core.multi_timeframe.enums import MarketBias

from .methodology_models import (
    MethodologyCondition,
    MethodologyDirection,
    MethodologyEvaluationStatus,
    MethodologyIdentifier,
    MethodologyResult,
)
from .smc_ict_context import PriceLocation, SMCICTContext


class ICTMethodologyEvaluator:
    """Interpret chronology-safe ICT facts without creating trade authority."""

    def evaluate(self, context: SMCICTContext) -> MethodologyResult:
        if not isinstance(context, SMCICTContext):
            raise TypeError("context must be SMCICTContext")

        satisfied: list[MethodologyCondition] = []
        failed: list[MethodologyCondition] = []
        unavailable: list[MethodologyCondition] = []

        direction = self._direction(context.higher_timeframe_bias)

        self._classify(
            self._condition(
                "HTF_BIAS_ALIGNED",
                "H4 and H1 provide the same non-neutral directional bias.",
                evidence_reference="higher_timeframe_bias",
            ),
            self._known_direction_state(direction),
            satisfied,
            failed,
            unavailable,
        )

        event = context.latest_structure_event
        self._classify(
            self._condition(
                "STRUCTURE_SHIFT_PRESENT",
                "A confirmed BOS or CHOCH market fact is available.",
                evidence_reference="latest_structure_event",
            ),
            "satisfied" if event is not None else "failed",
            satisfied,
            failed,
            unavailable,
        )

        if event is None:
            event_alignment = "unavailable"
        else:
            expected = self._trend_direction(direction)
            event_alignment = (
                "satisfied"
                if expected is not None and event.direction is expected
                else "failed"
            )
        self._classify(
            self._condition(
                "STRUCTURE_SHIFT_ALIGNED",
                "The latest BOS or CHOCH agrees with higher-timeframe bias.",
                evidence_reference="latest_structure_event.direction",
            ),
            event_alignment,
            satisfied,
            failed,
            unavailable,
        )

        sweep = context.latest_liquidity_sweep
        self._classify(
            self._condition(
                "LIQUIDITY_SWEEP_PRESENT",
                "A confirmed liquidity sweep market fact is available.",
                evidence_reference="latest_liquidity_sweep",
            ),
            "satisfied" if sweep is not None else "failed",
            satisfied,
            failed,
            unavailable,
        )

        if sweep is None:
            sweep_state = "unavailable"
        elif direction is MethodologyDirection.BULLISH:
            sweep_state = (
                "satisfied"
                if not sweep.liquidity_level.is_buy_side
                else "failed"
            )
        elif direction is MethodologyDirection.BEARISH:
            sweep_state = (
                "satisfied"
                if sweep.liquidity_level.is_buy_side
                else "failed"
            )
        else:
            sweep_state = "failed"
        self._classify(
            self._condition(
                "LIQUIDITY_SWEEP_COMPATIBLE",
                (
                    "Bullish ICT interpretation requires a sell-side sweep; "
                    "bearish ICT interpretation requires a buy-side sweep."
                ),
                evidence_reference=(
                    "latest_liquidity_sweep.liquidity_level.is_buy_side"
                ),
            ),
            sweep_state,
            satisfied,
            failed,
            unavailable,
        )

        gap = context.active_fair_value_gap
        self._classify(
            self._condition(
                "FAIR_VALUE_GAP_PRESENT",
                "A chronology-safe Fair Value Gap fact is available.",
                evidence_reference="active_fair_value_gap",
            ),
            "satisfied" if gap is not None else "failed",
            satisfied,
            failed,
            unavailable,
        )

        if gap is None:
            gap_alignment = "unavailable"
        elif direction is MethodologyDirection.BULLISH:
            gap_alignment = (
                "satisfied"
                if gap.gap_type is FairValueGapType.BULLISH
                else "failed"
            )
        elif direction is MethodologyDirection.BEARISH:
            gap_alignment = (
                "satisfied"
                if gap.gap_type is FairValueGapType.BEARISH
                else "failed"
            )
        else:
            gap_alignment = "failed"
        self._classify(
            self._condition(
                "FAIR_VALUE_GAP_ALIGNED",
                "The Fair Value Gap direction agrees with higher-timeframe bias.",
                evidence_reference="active_fair_value_gap.gap_type",
            ),
            gap_alignment,
            satisfied,
            failed,
            unavailable,
        )

        self._evaluate_price_location(
            context,
            direction,
            satisfied,
            failed,
            unavailable,
        )
        self._evaluate_displacement(
            context,
            satisfied,
            failed,
            unavailable,
        )
        self._evaluate_session(
            context,
            satisfied,
            failed,
            unavailable,
        )

        self._classify(
            self._condition(
                "OPPOSING_LIQUIDITY_PRESENT",
                "Opposing liquidity is available as observational context.",
                required=False,
                evidence_reference="opposing_liquidity_level",
            ),
            (
                "satisfied"
                if context.opposing_liquidity_level is not None
                else "failed"
            ),
            satisfied,
            failed,
            unavailable,
        )
        self._classify(
            self._condition(
                "ORDER_BLOCK_PRESENT",
                "A chronology-safe Order Block fact is available.",
                required=False,
                evidence_reference="active_order_block",
            ),
            (
                "satisfied"
                if context.active_order_block is not None
                else "failed"
            ),
            satisfied,
            failed,
            unavailable,
        )
        self._evaluate_optional_regime(
            context,
            satisfied,
            unavailable,
        )

        status = self._status(failed, unavailable)
        reason_codes = self._reason_codes(
            status=status,
            failed=failed,
            unavailable=unavailable,
        )

        return MethodologyResult(
            methodology=MethodologyIdentifier.ICT,
            timestamp=context.timestamp,
            evaluation_status=status,
            direction=direction,
            satisfied_conditions=tuple(satisfied),
            failed_conditions=tuple(failed),
            unavailable_conditions=tuple(unavailable),
            reason_codes=reason_codes,
            reason=self._reason(
                status=status,
                direction=direction,
                failed=failed,
                unavailable=unavailable,
            ),
            confidence=None,
            missing_capabilities=context.missing_capabilities,
            metadata={
                "evaluator": type(self).__name__,
                "rule_set_version": "1",
                "observational_only": True,
            },
        )

    def _evaluate_price_location(
        self,
        context: SMCICTContext,
        direction: MethodologyDirection,
        satisfied: list[MethodologyCondition],
        failed: list[MethodologyCondition],
        unavailable: list[MethodologyCondition],
    ) -> None:
        condition = self._condition(
            "PRICE_LOCATION_ALIGNED",
            (
                "Bullish ICT interpretation requires discount pricing; "
                "bearish ICT interpretation requires premium pricing."
            ),
            source_capability="dealing_range_price_location",
            evidence_reference="price_location",
        )
        if (
            "dealing_range_price_location" in context.missing_capabilities
            or context.price_location is PriceLocation.UNKNOWN
        ):
            state = "unavailable"
        elif direction is MethodologyDirection.BULLISH:
            state = (
                "satisfied"
                if context.price_location is PriceLocation.DISCOUNT
                else "failed"
            )
        elif direction is MethodologyDirection.BEARISH:
            state = (
                "satisfied"
                if context.price_location is PriceLocation.PREMIUM
                else "failed"
            )
        else:
            state = "failed"
        self._classify(
            condition,
            state,
            satisfied,
            failed,
            unavailable,
        )

    def _evaluate_displacement(
        self,
        context: SMCICTContext,
        satisfied: list[MethodologyCondition],
        failed: list[MethodologyCondition],
        unavailable: list[MethodologyCondition],
    ) -> None:
        condition = self._condition(
            "DISPLACEMENT_PRESENT",
            "A confirmed displacement fact is present.",
            source_capability="displacement_detection",
            evidence_reference="displacement_present",
        )
        if (
            "displacement_detection" in context.missing_capabilities
            or context.displacement_present is None
        ):
            state = "unavailable"
        else:
            state = (
                "satisfied"
                if context.displacement_present
                else "failed"
            )
        self._classify(
            condition,
            state,
            satisfied,
            failed,
            unavailable,
        )

    def _evaluate_session(
        self,
        context: SMCICTContext,
        satisfied: list[MethodologyCondition],
        failed: list[MethodologyCondition],
        unavailable: list[MethodologyCondition],
    ) -> None:
        condition = self._condition(
            "SESSION_CONTEXT_PRESENT",
            "A named market session is available for ICT interpretation.",
            source_capability="session_context",
            evidence_reference="session_name",
        )
        if "session_context" in context.missing_capabilities:
            state = "unavailable"
        elif context.session_name is None:
            state = "failed"
        else:
            state = "satisfied"
        self._classify(
            condition,
            state,
            satisfied,
            failed,
            unavailable,
        )

    def _evaluate_optional_regime(
        self,
        context: SMCICTContext,
        satisfied: list[MethodologyCondition],
        unavailable: list[MethodologyCondition],
    ) -> None:
        condition = self._condition(
            "MARKET_REGIME_PRESENT",
            "Market-regime context is available as supporting evidence.",
            required=False,
            source_capability="market_regime",
            evidence_reference="regime_name",
        )
        if (
            "market_regime" in context.missing_capabilities
            or context.regime_name is None
        ):
            unavailable.append(condition)
        else:
            satisfied.append(condition)

    @staticmethod
    def _condition(
        code: str,
        description: str,
        *,
        required: bool = True,
        source_capability: str | None = None,
        evidence_reference: str | None = None,
    ) -> MethodologyCondition:
        return MethodologyCondition(
            code=code,
            description=description,
            required=required,
            source_capability=source_capability,
            evidence_reference=evidence_reference,
        )

    @staticmethod
    def _classify(
        condition: MethodologyCondition,
        state: str,
        satisfied: list[MethodologyCondition],
        failed: list[MethodologyCondition],
        unavailable: list[MethodologyCondition],
    ) -> None:
        if state == "satisfied":
            satisfied.append(condition)
            return
        if state == "failed":
            failed.append(condition)
            return
        if state == "unavailable":
            unavailable.append(condition)
            return
        raise ValueError(f"unsupported condition state: {state}")

    @staticmethod
    def _known_direction_state(direction: MethodologyDirection) -> str:
        return (
            "satisfied"
            if direction in (
                MethodologyDirection.BULLISH,
                MethodologyDirection.BEARISH,
            )
            else "failed"
        )

    @staticmethod
    def _direction(bias: MarketBias) -> MethodologyDirection:
        if bias is MarketBias.BULLISH:
            return MethodologyDirection.BULLISH
        if bias is MarketBias.BEARISH:
            return MethodologyDirection.BEARISH
        return MethodologyDirection.NEUTRAL

    @staticmethod
    def _trend_direction(
        direction: MethodologyDirection,
    ) -> TrendDirection | None:
        if direction is MethodologyDirection.BULLISH:
            return TrendDirection.BULLISH
        if direction is MethodologyDirection.BEARISH:
            return TrendDirection.BEARISH
        return None

    @staticmethod
    def _status(
        failed: list[MethodologyCondition],
        unavailable: list[MethodologyCondition],
    ) -> MethodologyEvaluationStatus:
        if any(condition.required for condition in failed):
            return MethodologyEvaluationStatus.NOT_CONFIRMED
        if any(condition.required for condition in unavailable):
            return MethodologyEvaluationStatus.INCOMPLETE
        return MethodologyEvaluationStatus.CONFIRMED

    @staticmethod
    def _reason_codes(
        *,
        status: MethodologyEvaluationStatus,
        failed: list[MethodologyCondition],
        unavailable: list[MethodologyCondition],
    ) -> tuple[str, ...]:
        primary = {
            MethodologyEvaluationStatus.CONFIRMED: "ICT_CONFIRMED",
            MethodologyEvaluationStatus.NOT_CONFIRMED: "ICT_NOT_CONFIRMED",
            MethodologyEvaluationStatus.INCOMPLETE: "ICT_INCOMPLETE",
        }[status]
        details = tuple(
            f"{condition.code}_FAILED"
            for condition in failed
            if condition.required
        ) + tuple(
            f"{condition.code}_UNAVAILABLE"
            for condition in unavailable
            if condition.required
        )
        return (primary, *details)

    @staticmethod
    def _reason(
        *,
        status: MethodologyEvaluationStatus,
        direction: MethodologyDirection,
        failed: list[MethodologyCondition],
        unavailable: list[MethodologyCondition],
    ) -> str:
        if status is MethodologyEvaluationStatus.CONFIRMED:
            return (
                f"{direction.value.title()} ICT methodology conditions are "
                "confirmed from the available market facts."
            )
        if status is MethodologyEvaluationStatus.INCOMPLETE:
            codes = ", ".join(
                condition.code
                for condition in unavailable
                if condition.required
            )
            return (
                "ICT methodology evaluation is incomplete because required "
                f"conditions are unavailable: {codes}."
            )
        codes = ", ".join(
            condition.code
            for condition in failed
            if condition.required
        )
        return (
            "ICT methodology is not confirmed because required conditions "
            f"failed: {codes}."
        )
