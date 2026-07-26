from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from math import inf, nan

import pytest

from core.strategies.methodology_models import (
    MethodologyCondition,
    MethodologyDirection,
    MethodologyEvaluationStatus,
    MethodologyIdentifier,
    MethodologyResult,
)


NOW = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)


def _condition(
    code: str,
    *,
    required: bool = True,
    source_capability: str | None = None,
) -> MethodologyCondition:
    return MethodologyCondition(
        code=code,
        description=f"Description for {code}.",
        required=required,
        source_capability=source_capability,
        evidence_reference="shared_context",
    )


def _confirmed_result(**overrides: object) -> MethodologyResult:
    values: dict[str, object] = {
        "methodology": MethodologyIdentifier.SMC,
        "timestamp": NOW,
        "evaluation_status": MethodologyEvaluationStatus.CONFIRMED,
        "direction": MethodologyDirection.BULLISH,
        "satisfied_conditions": (_condition("HTF_BIAS_ALIGNED"),),
        "failed_conditions": (),
        "unavailable_conditions": (),
        "reason_codes": ("SMC_CONFIRMED",),
        "reason": "All required SMC conditions are satisfied.",
        "confidence": None,
        "missing_capabilities": (),
        "metadata": {"rule_set_version": "1"},
    }
    values.update(overrides)
    return MethodologyResult(**values)


def test_constructs_valid_confirmed_result() -> None:
    result = _confirmed_result()

    assert result.methodology is MethodologyIdentifier.SMC
    assert result.evaluation_status is MethodologyEvaluationStatus.CONFIRMED
    assert result.direction is MethodologyDirection.BULLISH
    assert result.confidence is None
    assert result.timestamp.tzinfo is UTC


def test_supports_ict_identifier() -> None:
    result = _confirmed_result(
        methodology=MethodologyIdentifier.ICT,
        reason_codes=("ICT_CONFIRMED",),
    )
    assert result.methodology is MethodologyIdentifier.ICT


def test_condition_and_result_are_immutable() -> None:
    condition = _condition("STRUCTURE_CONFIRMED")
    result = _confirmed_result(satisfied_conditions=(condition,))

    with pytest.raises(FrozenInstanceError):
        condition.code = "CHANGED"  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        result.reason = "Changed"  # type: ignore[misc]


def test_metadata_is_immutable_and_copied() -> None:
    source = {"rule_set_version": "1"}
    result = _confirmed_result(metadata=source)
    source["rule_set_version"] = "2"

    assert result.metadata["rule_set_version"] == "1"
    with pytest.raises(TypeError):
        result.metadata["new"] = "value"  # type: ignore[index]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("methodology", "SMC", "methodology must be MethodologyIdentifier"),
        (
            "evaluation_status",
            "CONFIRMED",
            "evaluation_status must be MethodologyEvaluationStatus",
        ),
        ("direction", "BULLISH", "direction must be MethodologyDirection"),
    ],
)
def test_rejects_non_enum_core_fields(
    field: str,
    value: object,
    message: str,
) -> None:
    with pytest.raises(TypeError, match=message):
        _confirmed_result(**{field: value})


def test_normalizes_timestamp_to_utc() -> None:
    timestamp = datetime(
        2026,
        7,
        25,
        19,
        0,
        tzinfo=timezone(timedelta(hours=7)),
    )
    result = _confirmed_result(timestamp=timestamp)
    assert result.timestamp == NOW
    assert result.timestamp.tzinfo is UTC


def test_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timestamp must be timezone-aware"):
        _confirmed_result(timestamp=datetime(2026, 7, 25, 12, 0))


def test_rejects_non_datetime_timestamp() -> None:
    with pytest.raises(TypeError, match="timestamp must be a datetime"):
        _confirmed_result(timestamp="2026-07-25")  # type: ignore[arg-type]


@pytest.mark.parametrize("value", ["", " ", "lowercase", "HAS-DASH"])
def test_rejects_invalid_condition_codes(value: str) -> None:
    with pytest.raises((TypeError, ValueError)):
        MethodologyCondition(code=value, description="Valid description.")


def test_rejects_empty_condition_description() -> None:
    with pytest.raises(
        ValueError,
        match="description must be a non-empty string",
    ):
        MethodologyCondition(code="VALID_CODE", description=" ")


def test_rejects_non_boolean_required_flag() -> None:
    with pytest.raises(TypeError, match="required must be a boolean"):
        MethodologyCondition(
            code="VALID_CODE",
            description="Valid description.",
            required=1,  # type: ignore[arg-type]
        )


def test_rejects_empty_optional_provenance_strings() -> None:
    with pytest.raises(
        ValueError,
        match="source_capability must be a non-empty string",
    ):
        MethodologyCondition(
            code="VALID_CODE",
            description="Valid description.",
            source_capability=" ",
        )

    with pytest.raises(
        ValueError,
        match="evidence_reference must be a non-empty string",
    ):
        MethodologyCondition(
            code="VALID_CODE",
            description="Valid description.",
            evidence_reference=" ",
        )


@pytest.mark.parametrize(
    "field",
    [
        "satisfied_conditions",
        "failed_conditions",
        "unavailable_conditions",
    ],
)
def test_condition_collections_must_be_tuples(field: str) -> None:
    with pytest.raises(TypeError, match=f"{field} must be a tuple"):
        _confirmed_result(**{field: []})


def test_condition_collections_require_condition_instances() -> None:
    with pytest.raises(
        TypeError,
        match="satisfied_conditions must contain MethodologyCondition instances",
    ):
        _confirmed_result(satisfied_conditions=("HTF_BIAS_ALIGNED",))


def test_rejects_duplicate_codes_within_collection() -> None:
    duplicate = _condition("DUPLICATE")
    with pytest.raises(
        ValueError,
        match="satisfied_conditions cannot contain duplicate condition codes",
    ):
        _confirmed_result(satisfied_conditions=(duplicate, duplicate))


@pytest.mark.parametrize(
    ("satisfied", "failed", "unavailable", "message"),
    [
        (
            (_condition("DUPLICATE"),),
            (_condition("DUPLICATE"),),
            (),
            "both satisfied and failed",
        ),
        (
            (_condition("DUPLICATE"),),
            (),
            (_condition("DUPLICATE"),),
            "both satisfied and unavailable",
        ),
        (
            (),
            (_condition("DUPLICATE"),),
            (_condition("DUPLICATE"),),
            "both failed and unavailable",
        ),
    ],
)
def test_condition_codes_are_mutually_exclusive(
    satisfied: tuple[MethodologyCondition, ...],
    failed: tuple[MethodologyCondition, ...],
    unavailable: tuple[MethodologyCondition, ...],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        _confirmed_result(
            satisfied_conditions=satisfied,
            failed_conditions=failed,
            unavailable_conditions=unavailable,
        )


def test_reason_codes_are_required_unique_and_uppercase() -> None:
    with pytest.raises(ValueError, match="reason_codes cannot be empty"):
        _confirmed_result(reason_codes=())

    with pytest.raises(
        ValueError,
        match="reason_codes cannot contain duplicates",
    ):
        _confirmed_result(reason_codes=("SAME_CODE", "SAME_CODE"))

    with pytest.raises(ValueError, match="reason_codes must be uppercase"):
        _confirmed_result(reason_codes=("lowercase",))


def test_reason_must_be_non_empty() -> None:
    with pytest.raises(ValueError, match="reason must be a non-empty string"):
        _confirmed_result(reason=" ")


@pytest.mark.parametrize("value", [True, "0.5"])
def test_rejects_non_numeric_confidence(value: object) -> None:
    with pytest.raises(TypeError, match="confidence must be numeric or None"):
        _confirmed_result(confidence=value)


@pytest.mark.parametrize("value", [nan, inf, -inf])
def test_rejects_non_finite_confidence(value: float) -> None:
    with pytest.raises(ValueError, match="confidence must be finite"):
        _confirmed_result(confidence=value)


@pytest.mark.parametrize("value", [-0.01, 1.01])
def test_rejects_out_of_range_confidence(value: float) -> None:
    with pytest.raises(
        ValueError,
        match="confidence must be between 0.0 and 1.0",
    ):
        _confirmed_result(confidence=value)


@pytest.mark.parametrize("value", [0.0, 0.5, 1.0])
def test_accepts_bounded_confidence(value: float) -> None:
    assert _confirmed_result(confidence=value).confidence == value


def test_missing_capabilities_must_be_unique_non_empty_strings() -> None:
    unavailable = _condition(
        "DISPLACEMENT_UNAVAILABLE",
        source_capability="displacement_detection",
    )
    result = MethodologyResult(
        methodology=MethodologyIdentifier.ICT,
        timestamp=NOW,
        evaluation_status=MethodologyEvaluationStatus.INCOMPLETE,
        direction=MethodologyDirection.UNKNOWN,
        unavailable_conditions=(unavailable,),
        reason_codes=("ICT_INCOMPLETE",),
        reason="Displacement evidence is unavailable.",
        missing_capabilities=("displacement_detection",),
    )
    assert result.missing_capabilities == ("displacement_detection",)

    with pytest.raises(
        ValueError,
        match="missing_capabilities cannot contain duplicates",
    ):
        MethodologyResult(
            methodology=MethodologyIdentifier.ICT,
            timestamp=NOW,
            evaluation_status=MethodologyEvaluationStatus.INCOMPLETE,
            direction=MethodologyDirection.UNKNOWN,
            unavailable_conditions=(unavailable,),
            reason_codes=("ICT_INCOMPLETE",),
            reason="Displacement evidence is unavailable.",
            missing_capabilities=(
                "displacement_detection",
                "displacement_detection",
            ),
        )

    with pytest.raises(
        ValueError,
        match="missing_capabilities must be a non-empty string",
    ):
        MethodologyResult(
            methodology=MethodologyIdentifier.ICT,
            timestamp=NOW,
            evaluation_status=MethodologyEvaluationStatus.INCOMPLETE,
            direction=MethodologyDirection.UNKNOWN,
            unavailable_conditions=(unavailable,),
            reason_codes=("ICT_INCOMPLETE",),
            reason="Displacement evidence is unavailable.",
            missing_capabilities=(" ",),
        )


def test_confirmed_requires_required_satisfied_condition() -> None:
    with pytest.raises(
        ValueError,
        match="CONFIRMED requires at least one required satisfied condition",
    ):
        _confirmed_result(satisfied_conditions=())


def test_confirmed_rejects_required_failed_condition() -> None:
    with pytest.raises(
        ValueError,
        match="CONFIRMED cannot contain required failed conditions",
    ):
        _confirmed_result(
            failed_conditions=(_condition("STRUCTURE_FAILED"),),
        )


def test_confirmed_rejects_required_unavailable_condition() -> None:
    with pytest.raises(
        ValueError,
        match="CONFIRMED cannot contain required unavailable conditions",
    ):
        _confirmed_result(
            unavailable_conditions=(_condition("SESSION_UNAVAILABLE"),),
        )


def test_not_confirmed_requires_required_failure() -> None:
    with pytest.raises(
        ValueError,
        match="NOT_CONFIRMED requires at least one required failed condition",
    ):
        _confirmed_result(
            evaluation_status=MethodologyEvaluationStatus.NOT_CONFIRMED,
            satisfied_conditions=(),
        )


def test_not_confirmed_accepts_failure_and_unavailable_evidence() -> None:
    result = MethodologyResult(
        methodology=MethodologyIdentifier.SMC,
        timestamp=NOW,
        evaluation_status=MethodologyEvaluationStatus.NOT_CONFIRMED,
        direction=MethodologyDirection.NEUTRAL,
        failed_conditions=(_condition("HTF_BIAS_FAILED"),),
        unavailable_conditions=(_condition("REGIME_UNAVAILABLE"),),
        reason_codes=("SMC_NOT_CONFIRMED",),
        reason="Bias failed and regime evidence is unavailable.",
        missing_capabilities=("market_regime",),
    )
    assert result.evaluation_status is MethodologyEvaluationStatus.NOT_CONFIRMED


def test_incomplete_requires_required_unavailable_condition() -> None:
    with pytest.raises(
        ValueError,
        match="INCOMPLETE requires at least one required unavailable condition",
    ):
        _confirmed_result(
            evaluation_status=MethodologyEvaluationStatus.INCOMPLETE,
            satisfied_conditions=(),
        )


def test_incomplete_rejects_required_failure() -> None:
    with pytest.raises(
        ValueError,
        match="INCOMPLETE cannot contain required failed conditions",
    ):
        MethodologyResult(
            methodology=MethodologyIdentifier.ICT,
            timestamp=NOW,
            evaluation_status=MethodologyEvaluationStatus.INCOMPLETE,
            direction=MethodologyDirection.UNKNOWN,
            failed_conditions=(_condition("STRUCTURE_FAILED"),),
            unavailable_conditions=(_condition("SESSION_UNAVAILABLE"),),
            reason_codes=("ICT_INCOMPLETE",),
            reason="Context is incomplete.",
        )


def test_optional_failed_or_unavailable_conditions_do_not_block_confirmation() -> None:
    result = MethodologyResult(
        methodology=MethodologyIdentifier.SMC,
        timestamp=NOW,
        evaluation_status=MethodologyEvaluationStatus.CONFIRMED,
        direction=MethodologyDirection.BULLISH,
        satisfied_conditions=(_condition("REQUIRED_SATISFIED"),),
        failed_conditions=(_condition("OPTIONAL_FAILED", required=False),),
        unavailable_conditions=(
            _condition("OPTIONAL_UNAVAILABLE", required=False),
        ),
        reason_codes=("SMC_CONFIRMED",),
        reason="All required conditions are satisfied.",
    )
    assert result.evaluation_status is MethodologyEvaluationStatus.CONFIRMED


def test_contract_has_no_trade_or_execution_authority_fields() -> None:
    prohibited = {
        "entry_price",
        "entry_zone",
        "stop_loss",
        "stop_loss_price",
        "target",
        "target_price",
        "take_profit",
        "position_size",
        "risk_amount",
        "risk_percent",
        "signal",
        "approved",
        "authorized",
        "executable",
        "order_type",
        "execution_status",
    }

    assert prohibited.isdisjoint(MethodologyResult.__dataclass_fields__)


def test_module_has_no_runtime_execution_imports() -> None:
    import core.strategies.methodology_models as module

    imported_modules = {
        value.__module__
        for value in vars(module).values()
        if isinstance(value, type)
    }
    prohibited_prefixes = (
        "core.trading_pipeline",
        "core.risk_manager",
        "core.live_trading",
        "core.mt5_execution",
        "core.signal_generator",
    )

    assert not any(
        imported.startswith(prohibited_prefixes)
        for imported in imported_modules
    )
