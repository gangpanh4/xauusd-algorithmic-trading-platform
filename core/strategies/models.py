"""Typed strategy-domain contracts.

These models define setup, trigger, and candidate-trade lifecycles. They do not
score opportunities, calculate account risk, place orders, or manage positions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from math import isfinite
from types import MappingProxyType
from typing import Mapping
from uuid import UUID

from core.market_structure.models import StructureState
from core.multi_timeframe.enums import Timeframe

from .enums import (
    EntryTriggerStatus,
    EntryTriggerType,
    PriceReferenceType,
    SetupDirection,
    SetupInvalidationReason,
    SetupStatus,
)


def _require_aware_utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def _require_price(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    normalized = float(value)
    if not isfinite(normalized) or normalized <= 0.0:
        raise ValueError(f"{name} must be finite and greater than zero")
    return normalized


def _freeze_metadata(
    value: Mapping[str, object],
    name: str,
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return MappingProxyType(dict(value))


@dataclass(slots=True, frozen=True)
class PriceReference:
    """Absolute price plus the market fact that gives it meaning."""

    reference_type: PriceReferenceType
    price: float
    timeframe: Timeframe
    source: str

    def __post_init__(self) -> None:
        if not isinstance(self.reference_type, PriceReferenceType):
            raise TypeError("reference_type must be PriceReferenceType")
        object.__setattr__(self, "price", _require_price(self.price, "price"))
        if not isinstance(self.timeframe, Timeframe):
            raise TypeError("timeframe must be Timeframe")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source must be a non-empty string")
        object.__setattr__(self, "source", self.source.strip())


@dataclass(slots=True, frozen=True)
class TradingSetup:
    """A strategy thesis detected from confirmed market facts."""

    setup_id: UUID
    strategy_id: str
    direction: SetupDirection
    status: SetupStatus
    setup_timeframe: Timeframe
    trigger_timeframe: Timeframe
    detected_at: datetime
    expires_at: datetime
    structure_state: StructureState
    invalidation: PriceReference
    stop_reference: PriceReference
    target_references: tuple[PriceReference, ...]
    required_conditions: tuple[str, ...]
    invalidation_reason: SetupInvalidationReason | None = None
    cooldown_until: datetime | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.setup_id, UUID):
            raise TypeError("setup_id must be UUID")
        if not isinstance(self.strategy_id, str) or not self.strategy_id.strip():
            raise ValueError("strategy_id must be a non-empty string")
        object.__setattr__(self, "strategy_id", self.strategy_id.strip())

        if not isinstance(self.direction, SetupDirection):
            raise TypeError("direction must be SetupDirection")
        if not isinstance(self.status, SetupStatus):
            raise TypeError("status must be SetupStatus")
        if not isinstance(self.setup_timeframe, Timeframe):
            raise TypeError("setup_timeframe must be Timeframe")
        if not isinstance(self.trigger_timeframe, Timeframe):
            raise TypeError("trigger_timeframe must be Timeframe")
        if not isinstance(self.structure_state, StructureState):
            raise TypeError("structure_state must be StructureState")

        detected_at = _require_aware_utc(self.detected_at, "detected_at")
        expires_at = _require_aware_utc(self.expires_at, "expires_at")
        if expires_at <= detected_at:
            raise ValueError("expires_at must be after detected_at")
        object.__setattr__(self, "detected_at", detected_at)
        object.__setattr__(self, "expires_at", expires_at)

        if self.cooldown_until is not None:
            object.__setattr__(
                self,
                "cooldown_until",
                _require_aware_utc(self.cooldown_until, "cooldown_until"),
            )

        if not isinstance(self.invalidation, PriceReference):
            raise TypeError("invalidation must be PriceReference")
        if not isinstance(self.stop_reference, PriceReference):
            raise TypeError("stop_reference must be PriceReference")
        if not self.target_references:
            raise ValueError("target_references cannot be empty")
        if any(
            not isinstance(item, PriceReference)
            for item in self.target_references
        ):
            raise TypeError(
                "target_references must contain PriceReference instances"
            )

        if not self.required_conditions:
            raise ValueError("required_conditions cannot be empty")
        normalized_conditions: list[str] = []
        for condition in self.required_conditions:
            if not isinstance(condition, str) or not condition.strip():
                raise ValueError(
                    "required_conditions must contain non-empty strings"
                )
            normalized_conditions.append(condition.strip())
        object.__setattr__(
            self,
            "required_conditions",
            tuple(normalized_conditions),
        )

        terminal = {
            SetupStatus.INVALIDATED,
            SetupStatus.EXPIRED,
            SetupStatus.CANCELLED,
        }
        if self.status in terminal and self.invalidation_reason is None:
            raise ValueError(
                "terminal invalid setup statuses require invalidation_reason"
            )
        if self.status not in terminal and self.invalidation_reason is not None:
            raise ValueError(
                "invalidation_reason is valid only for invalidated, expired, "
                "or cancelled setups"
            )
        if (
            self.invalidation_reason is not None
            and not isinstance(
                self.invalidation_reason,
                SetupInvalidationReason,
            )
        ):
            raise TypeError(
                "invalidation_reason must be SetupInvalidationReason or None"
            )

        entry_side = self.stop_reference.price - self.invalidation.price
        if self.direction is SetupDirection.BUY:
            if self.stop_reference.price > self.invalidation.price:
                raise ValueError(
                    "BUY stop_reference cannot be above invalidation price"
                )
            if any(
                target.price <= self.invalidation.price
                for target in self.target_references
            ):
                raise ValueError(
                    "BUY targets must be above invalidation price"
                )
        else:
            if self.stop_reference.price < self.invalidation.price:
                raise ValueError(
                    "SELL stop_reference cannot be below invalidation price"
                )
            if any(
                target.price >= self.invalidation.price
                for target in self.target_references
            ):
                raise ValueError(
                    "SELL targets must be below invalidation price"
                )
        _ = entry_side

        object.__setattr__(
            self,
            "metadata",
            _freeze_metadata(self.metadata, "metadata"),
        )

    def is_active_at(self, timestamp: datetime) -> bool:
        """Return whether this setup can still await an entry trigger."""

        current = _require_aware_utc(timestamp, "timestamp")
        return (
            self.status is SetupStatus.ACTIVE
            and self.detected_at <= current < self.expires_at
            and (
                self.cooldown_until is None
                or current >= self.cooldown_until
            )
        )


@dataclass(slots=True, frozen=True)
class EntryTrigger:
    """A confirmed or pending lower-timeframe entry event."""

    setup_id: UUID
    trigger_type: EntryTriggerType
    status: EntryTriggerStatus
    timeframe: Timeframe
    observed_at: datetime
    trigger_price: float
    confirmation_bar_index: int
    reason: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.setup_id, UUID):
            raise TypeError("setup_id must be UUID")
        if not isinstance(self.trigger_type, EntryTriggerType):
            raise TypeError("trigger_type must be EntryTriggerType")
        if not isinstance(self.status, EntryTriggerStatus):
            raise TypeError("status must be EntryTriggerStatus")
        if not isinstance(self.timeframe, Timeframe):
            raise TypeError("timeframe must be Timeframe")
        object.__setattr__(
            self,
            "observed_at",
            _require_aware_utc(self.observed_at, "observed_at"),
        )
        object.__setattr__(
            self,
            "trigger_price",
            _require_price(self.trigger_price, "trigger_price"),
        )
        if isinstance(self.confirmation_bar_index, bool) or not isinstance(
            self.confirmation_bar_index,
            int,
        ):
            raise TypeError("confirmation_bar_index must be an integer")
        if self.confirmation_bar_index < 0:
            raise ValueError("confirmation_bar_index cannot be negative")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be a non-empty string")
        object.__setattr__(self, "reason", self.reason.strip())
        object.__setattr__(
            self,
            "metadata",
            _freeze_metadata(self.metadata, "metadata"),
        )


@dataclass(slots=True, frozen=True)
class CandidateTrade:
    """Executable geometry produced only after a setup trigger is confirmed.

    Account balance, position size, monetary risk, and broker-order parameters
    are deliberately absent. Those remain RiskManager and execution concerns.
    """

    setup: TradingSetup
    trigger: EntryTrigger
    created_at: datetime
    entry_price: float
    stop_loss_price: float
    take_profit_prices: tuple[float, ...]
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.setup, TradingSetup):
            raise TypeError("setup must be TradingSetup")
        if not isinstance(self.trigger, EntryTrigger):
            raise TypeError("trigger must be EntryTrigger")
        if self.trigger.setup_id != self.setup.setup_id:
            raise ValueError("trigger and setup must share the same setup_id")
        if self.setup.status is not SetupStatus.TRIGGERED:
            raise ValueError("candidate trade requires a TRIGGERED setup")
        if self.trigger.status is not EntryTriggerStatus.CONFIRMED:
            raise ValueError("candidate trade requires a CONFIRMED trigger")
        if self.trigger.timeframe is not self.setup.trigger_timeframe:
            raise ValueError(
                "trigger timeframe must match setup trigger_timeframe"
            )

        created_at = _require_aware_utc(self.created_at, "created_at")
        if created_at < self.trigger.observed_at:
            raise ValueError(
                "created_at cannot be before trigger.observed_at"
            )
        object.__setattr__(self, "created_at", created_at)

        entry = _require_price(self.entry_price, "entry_price")
        stop = _require_price(self.stop_loss_price, "stop_loss_price")
        targets = tuple(
            _require_price(value, "take_profit_price")
            for value in self.take_profit_prices
        )
        if not targets:
            raise ValueError("take_profit_prices cannot be empty")

        if self.setup.direction is SetupDirection.BUY:
            if stop >= entry:
                raise ValueError("BUY stop_loss_price must be below entry_price")
            if any(target <= entry for target in targets):
                raise ValueError(
                    "BUY take_profit_prices must be above entry_price"
                )
        else:
            if stop <= entry:
                raise ValueError("SELL stop_loss_price must be above entry_price")
            if any(target >= entry for target in targets):
                raise ValueError(
                    "SELL take_profit_prices must be below entry_price"
                )

        object.__setattr__(self, "entry_price", entry)
        object.__setattr__(self, "stop_loss_price", stop)
        object.__setattr__(self, "take_profit_prices", targets)
        object.__setattr__(
            self,
            "metadata",
            _freeze_metadata(self.metadata, "metadata"),
        )

    @property
    def initial_risk_distance(self) -> float:
        return abs(self.entry_price - self.stop_loss_price)

    @property
    def reward_risk_ratios(self) -> tuple[float, ...]:
        risk = self.initial_risk_distance
        return tuple(
            abs(target - self.entry_price) / risk
            for target in self.take_profit_prices
        )
