"""Deterministic observational Smart Money Concepts methodology evaluator."""

from __future__ import annotations

from core.market_structure.enums import TrendDirection
from core.multi_timeframe.enums import MarketBias

from .methodology_models import (
    MethodologyCondition,
    MethodologyDirection,
    MethodologyEvaluationStatus,
    MethodologyIdentifier,
    MethodologyResult,
)
from .smc_ict_context import SMCICTContext


class SMCMethodologyEvaluator:
    """Interpret confirmed shared facts without creating strategy authority."""

    def evaluate(self, context: SMCICTContext) -> MethodologyResult:
        if not isinstance(context, SMCICTContext):
            raise TypeError("context must be SMCICTContext")

        satisfied: list[MethodologyCondition] = []
        failed: list[MethodologyCondition] = []
        unavailable: list[MethodologyCondition] = []

        direction = self._direction(context.higher_timeframe_bias)

        self._classify(
            condition=self._condition(
                "HTF_BIAS_ALIGNED",
                "H4 and H1 provide the same non-neutral directional bias.",
                evidence_reference="higher_timeframe_bias",
            ),
            state=(
                "satisfied"
                if direction in (
                    MethodologyDirection.BULLISH,
                    MethodologyDirection.BEARISH,
                )
                else "failed"
            ),
            satisfied=satisfied,
            failed=failed,
            unavailable=unavailable,
        )

        event = context.latest_structure_event
        self._classify(
            condition=self._condition(
                "STRUCTURE_EVENT_PRESENT",
                "A confirmed BOS or CHOCH market fact is available.",
                evidence_reference="latest_structure_event",
            ),
            state="satisfied" if event is not None else "failed",
            satisfied=satisfied,
            failed=failed,
            unavailable=unavailable,
        )

        if event is None:
            structure_alignment_state = "unavailable"
        else:
            expected = self._trend_direction(direction)
            structure_alignment_state = (
                "satisfied"
                if expected is not None and event.direction is expected
                else "failed"
            )
        self._classify(
            condition=self._condition(
                "STRUCTURE_EVENT_ALIGNED",
                "The latest BOS or CHOCH agrees with higher-timeframe bias.",
                evidence_reference="latest_structure_event.direction",
            ),
            state=structure_alignment_state,
            satisfied=satisfied,
            failed=failed,
            unavailable=unavailable,
        )

        sweep = context.latest_liquidity_sweep
        self._classify(
            condition=self._condition(
                "LIQUIDITY_SWEEP_PRESENT",
                "A confirmed liquidity sweep market fact is available.",
                evidence_reference="latest_liquidity_sweep",
            ),
            state="satisfied" if sweep is not None else "failed",
            satisfied=satisfied,
            failed=failed,
            unavailable=unavailable,
        )

        if sweep is None:
            sweep_compatibility_state = "unavailable"
        elif direction is MethodologyDirection.BULLISH:
            sweep_compatibility_state = (
                "satisfied"
                if not sweep.liquidity_level.is_buy_side
                else "failed"
            )
        elif direction is MethodologyDirection.BEARISH:
            sweep_compatibility_state = (
                "satisfied"
                if sweep.liquidity_level.is_buy_side
                else "failed"
            )
        else:
            sweep_compatibility_state = "failed"

        self._classify(
            condition=self._condition(
                "LIQUIDITY_SWEEP_COMPATIBLE",
                (
                    "Bullish interpretation requires a sell-side sweep; "
                    "bearish interpretation requires a buy-side sweep."
                ),
                evidence_reference=(
                    "latest_liquidity_sweep.liquidity_level.is_buy_side"
                ),
            ),
            state=sweep_compatibility_state,
            satisfied=satisfied,
            failed=failed,
            unavailable=unavailable,
        )

        self._classify(
            condition=self._condition(
                "OPPOSING_LIQUIDITY_PRESENT",
                "Opposing liquidity is available in the event source timeframe.",
                evidence_reference="opposing_liquidity_level",
            ),
            state=(
                "satisfied"
                if context.opposing_liquidity_level is not None
                else "failed"
            ),
            satisfied=satisfied,
            failed=failed,
            unavailable=unavailable,
        )

        self._classify(
            condition=self._condition(
                "FAIR_VALUE_GAP_PRESENT",
                "A chronology-safe Fair Value Gap fact is available.",
                required=False,
                evidence_reference="active_fair_value_gap",
            ),
            state=(
                "satisfied"
                if context.active_fair_value_gap is not None
                else "failed"
            ),
            satisfied=satisfied,
            failed=failed,
            unavailable=unavailable,
        )
        self._classify(
            condition=self._condition(
                "ORDER_BLOCK_PRESENT",
                "A chronology-safe Order Block fact is available.",
                required=False,
                evidence_reference="active_order_block",
            ),
            state=(
                "satisfied"
                if context.active_order_block is not None
                else "failed"
            ),
            satisfied=satisfied,
            failed=failed,
            unavailable=unavailable,
        )

        self._append_capability_conditions(
            context=context,
            unavailable=unavailable,
        )

        status = self._status(failed, unavailable)
        reason_codes = self._reason_codes(
            status=status,
            failed=failed,
            unavailable=unavailable,
        )

        return MethodologyResult(
            methodology=MethodologyIdentifier.SMC,
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
        *,
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

    @classmethod
    def _append_capability_conditions(
        cls,
        *,
        context: SMCICTContext,
        unavailable: list[MethodologyCondition],
    ) -> None:
        capability_conditions = (
            (
                "PRICE_LOCATION_UNAVAILABLE",
                "Dealing-range premium/discount location is unavailable.",
                "dealing_range_price_location",
                "price_location",
            ),
            (
                "DISPLACEMENT_UNAVAILABLE",
                "Displacement detection is unavailable.",
                "displacement_detection",
                "displacement_present",
            ),
            (
                "SESSION_CONTEXT_UNAVAILABLE",
                "Session context is unavailable.",
                "session_context",
                "session_name",
            ),
            (
                "MARKET_REGIME_UNAVAILABLE",
                "Market-regime context is unavailable.",
                "market_regime",
                "regime_name",
            ),
        )
        missing = set(context.missing_capabilities)
        for code, description, capability, reference in capability_conditions:
            if capability in missing:
                unavailable.append(
                    cls._condition(
                        code,
                        description,
                        required=False,
                        source_capability=capability,
                        evidence_reference=reference,
                    )
                )

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
            MethodologyEvaluationStatus.CONFIRMED: "SMC_CONFIRMED",
            MethodologyEvaluationStatus.NOT_CONFIRMED: "SMC_NOT_CONFIRMED",
            MethodologyEvaluationStatus.INCOMPLETE: "SMC_INCOMPLETE",
        }[status]
        detail_codes = tuple(
            f"{condition.code}_FAILED"
            for condition in failed
            if condition.required
        ) + tuple(
            condition.code
            for condition in unavailable
            if condition.required
        )
        return (primary, *detail_codes)

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
                f"{direction.value.title()} SMC methodology conditions are "
                "confirmed from the available market facts."
            )
        if status is MethodologyEvaluationStatus.INCOMPLETE:
            codes = ", ".join(
                condition.code
                for condition in unavailable
                if condition.required
            )
            return (
                "SMC methodology evaluation is incomplete because required "
                f"conditions are unavailable: {codes}."
            )
        codes = ", ".join(
            condition.code
            for condition in failed
            if condition.required
        )
        return (
            "SMC methodology is not confirmed because required conditions "
            f"failed: {codes}."
        )
