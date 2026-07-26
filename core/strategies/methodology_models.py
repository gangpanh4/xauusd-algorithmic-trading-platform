"""Immutable observational methodology-result contracts.

These contracts describe how a methodology interprets already-confirmed market
facts. They do not define strategy setups, entries, signals, risk, orders, or
execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Mapping


class MethodologyIdentifier(str, Enum):
    """Supported market methodologies."""

    SMC = "SMC"
    ICT = "ICT"


class MethodologyEvaluationStatus(str, Enum):
    """Aggregate evaluator outcome using explicit three-state semantics."""

    CONFIRMED = "CONFIRMED"
    NOT_CONFIRMED = "NOT_CONFIRMED"
    INCOMPLETE = "INCOMPLETE"


class MethodologyDirection(str, Enum):
    """Directional interpretation without signal or execution authority."""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


@dataclass(slots=True, frozen=True)
class MethodologyCondition:
    """One deterministic methodology rule and its evidence provenance."""

    code: str
    description: str
    required: bool = True
    source_capability: str | None = None
    evidence_reference: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _require_code(self.code, "code"))
        object.__setattr__(
            self,
            "description",
            _require_non_empty_string(self.description, "description"),
        )

        if not isinstance(self.required, bool):
            raise TypeError("required must be a boolean")

        if self.source_capability is not None:
            object.__setattr__(
                self,
                "source_capability",
                _require_non_empty_string(
                    self.source_capability,
                    "source_capability",
                ),
            )

        if self.evidence_reference is not None:
            object.__setattr__(
                self,
                "evidence_reference",
                _require_non_empty_string(
                    self.evidence_reference,
                    "evidence_reference",
                ),
            )


@dataclass(slots=True, frozen=True)
class MethodologyResult:
    """Immutable, observational interpretation of SMC or ICT market facts."""

    methodology: MethodologyIdentifier
    timestamp: datetime
    evaluation_status: MethodologyEvaluationStatus
    direction: MethodologyDirection
    satisfied_conditions: tuple[MethodologyCondition, ...] = ()
    failed_conditions: tuple[MethodologyCondition, ...] = ()
    unavailable_conditions: tuple[MethodologyCondition, ...] = ()
    reason_codes: tuple[str, ...] = ()
    reason: str = ""
    confidence: float | None = None
    missing_capabilities: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.methodology, MethodologyIdentifier):
            raise TypeError("methodology must be MethodologyIdentifier")
        if not isinstance(self.evaluation_status, MethodologyEvaluationStatus):
            raise TypeError(
                "evaluation_status must be MethodologyEvaluationStatus"
            )
        if not isinstance(self.direction, MethodologyDirection):
            raise TypeError("direction must be MethodologyDirection")

        object.__setattr__(
            self,
            "timestamp",
            _require_aware_utc(self.timestamp, "timestamp"),
        )

        satisfied = _require_conditions(
            self.satisfied_conditions,
            "satisfied_conditions",
        )
        failed = _require_conditions(
            self.failed_conditions,
            "failed_conditions",
        )
        unavailable = _require_conditions(
            self.unavailable_conditions,
            "unavailable_conditions",
        )

        _require_unique_condition_codes(satisfied, "satisfied_conditions")
        _require_unique_condition_codes(failed, "failed_conditions")
        _require_unique_condition_codes(
            unavailable,
            "unavailable_conditions",
        )
        _require_disjoint_condition_codes(
            satisfied=satisfied,
            failed=failed,
            unavailable=unavailable,
        )

        object.__setattr__(self, "satisfied_conditions", satisfied)
        object.__setattr__(self, "failed_conditions", failed)
        object.__setattr__(self, "unavailable_conditions", unavailable)

        reason_codes = _require_string_tuple(
            self.reason_codes,
            "reason_codes",
            code_format=True,
            require_non_empty=True,
        )
        if len(reason_codes) != len(set(reason_codes)):
            raise ValueError("reason_codes cannot contain duplicates")
        object.__setattr__(self, "reason_codes", reason_codes)

        object.__setattr__(
            self,
            "reason",
            _require_non_empty_string(self.reason, "reason"),
        )

        if self.confidence is not None:
            if isinstance(self.confidence, bool) or not isinstance(
                self.confidence,
                (int, float),
            ):
                raise TypeError("confidence must be numeric or None")
            confidence = float(self.confidence)
            if not isfinite(confidence):
                raise ValueError("confidence must be finite")
            if not 0.0 <= confidence <= 1.0:
                raise ValueError("confidence must be between 0.0 and 1.0")
            object.__setattr__(self, "confidence", confidence)

        missing_capabilities = _require_string_tuple(
            self.missing_capabilities,
            "missing_capabilities",
            code_format=False,
            require_non_empty=False,
        )
        if len(missing_capabilities) != len(set(missing_capabilities)):
            raise ValueError(
                "missing_capabilities cannot contain duplicates"
            )
        object.__setattr__(
            self,
            "missing_capabilities",
            missing_capabilities,
        )

        if not isinstance(self.metadata, Mapping):
            raise TypeError("metadata must be a mapping")
        object.__setattr__(
            self,
            "metadata",
            MappingProxyType(dict(self.metadata)),
        )

        self._validate_status_consistency()

    def _validate_status_consistency(self) -> None:
        required_satisfied = tuple(
            item for item in self.satisfied_conditions if item.required
        )
        required_failed = tuple(
            item for item in self.failed_conditions if item.required
        )
        required_unavailable = tuple(
            item for item in self.unavailable_conditions if item.required
        )

        if self.evaluation_status is MethodologyEvaluationStatus.CONFIRMED:
            if required_failed:
                raise ValueError(
                    "CONFIRMED cannot contain required failed conditions"
                )
            if required_unavailable:
                raise ValueError(
                    "CONFIRMED cannot contain required unavailable conditions"
                )
            if not required_satisfied:
                raise ValueError(
                    "CONFIRMED requires at least one required satisfied condition"
                )
            return

        if self.evaluation_status is MethodologyEvaluationStatus.NOT_CONFIRMED:
            if not required_failed:
                raise ValueError(
                    "NOT_CONFIRMED requires at least one required failed condition"
                )
            return

        if required_failed:
            raise ValueError(
                "INCOMPLETE cannot contain required failed conditions"
            )
        if not required_unavailable:
            raise ValueError(
                "INCOMPLETE requires at least one required unavailable condition"
            )


def _require_aware_utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def _require_non_empty_string(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} must be a non-empty string")
    return normalized


def _require_code(value: str, name: str) -> str:
    normalized = _require_non_empty_string(value, name)
    if normalized != normalized.upper():
        raise ValueError(f"{name} must be uppercase")
    if any(not (character.isalnum() or character == "_") for character in normalized):
        raise ValueError(
            f"{name} must contain only uppercase letters, digits, and underscores"
        )
    return normalized


def _require_conditions(
    value: tuple[MethodologyCondition, ...],
    name: str,
) -> tuple[MethodologyCondition, ...]:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be a tuple")
    if any(not isinstance(item, MethodologyCondition) for item in value):
        raise TypeError(
            f"{name} must contain MethodologyCondition instances"
        )
    return value


def _require_unique_condition_codes(
    conditions: tuple[MethodologyCondition, ...],
    name: str,
) -> None:
    codes = tuple(item.code for item in conditions)
    if len(codes) != len(set(codes)):
        raise ValueError(f"{name} cannot contain duplicate condition codes")


def _require_disjoint_condition_codes(
    *,
    satisfied: tuple[MethodologyCondition, ...],
    failed: tuple[MethodologyCondition, ...],
    unavailable: tuple[MethodologyCondition, ...],
) -> None:
    satisfied_codes = {item.code for item in satisfied}
    failed_codes = {item.code for item in failed}
    unavailable_codes = {item.code for item in unavailable}

    if satisfied_codes & failed_codes:
        raise ValueError(
            "condition codes cannot appear in both satisfied and failed conditions"
        )
    if satisfied_codes & unavailable_codes:
        raise ValueError(
            "condition codes cannot appear in both satisfied and unavailable conditions"
        )
    if failed_codes & unavailable_codes:
        raise ValueError(
            "condition codes cannot appear in both failed and unavailable conditions"
        )


def _require_string_tuple(
    value: tuple[str, ...],
    name: str,
    *,
    code_format: bool,
    require_non_empty: bool,
) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be a tuple")
    if require_non_empty and not value:
        raise ValueError(f"{name} cannot be empty")

    normalized: list[str] = []
    for item in value:
        normalized.append(
            _require_code(item, name)
            if code_format
            else _require_non_empty_string(item, name)
        )
    return tuple(normalized)
