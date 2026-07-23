"""Research-only outcome models for observational strategy candidates."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Mapping
from uuid import UUID

from core.multi_timeframe.enums import Timeframe
from core.strategies import SetupDirection


class CandidateOutcome(Enum):
    """Terminal or unresolved observational candidate outcome."""

    TARGET_REACHED = "TARGET_REACHED"
    STOP_REACHED = "STOP_REACHED"
    AMBIGUOUS_SAME_BAR = "AMBIGUOUS_SAME_BAR"
    UNRESOLVED = "UNRESOLVED"


@dataclass(slots=True, frozen=True)
class CandidateOutcomeEvaluation:
    """Measured post-candidate price behavior without simulated execution."""

    setup_id: UUID
    candidate_created_at: datetime
    evaluated_through: datetime
    outcome: CandidateOutcome
    outcome_timestamp: datetime | None
    entry_price: float
    stop_loss_price: float
    take_profit_prices: tuple[float, ...]
    highest_target_index_reached: int | None
    bars_evaluated: int
    maximum_favorable_excursion: float
    maximum_adverse_excursion: float
    maximum_favorable_r_multiple: float
    maximum_adverse_r_multiple: float
    strategy_id: str | None = None
    direction: SetupDirection | None = None
    setup_timeframe: Timeframe | None = None
    trigger_timeframe: Timeframe | None = None
    trigger_reason: str | None = None
    setup_metadata: Mapping[str, object] = field(default_factory=dict)
    trigger_metadata: Mapping[str, object] = field(default_factory=dict)
    candidate_metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.setup_id, UUID):
            raise TypeError("setup_id must be UUID")
        if not isinstance(self.outcome, CandidateOutcome):
            raise TypeError("outcome must be CandidateOutcome")
        if self.bars_evaluated < 0:
            raise ValueError("bars_evaluated cannot be negative")
        if self.highest_target_index_reached is not None:
            if self.highest_target_index_reached < 0:
                raise ValueError(
                    "highest_target_index_reached cannot be negative"
                )
            if self.highest_target_index_reached >= len(
                self.take_profit_prices
            ):
                raise ValueError(
                    "highest_target_index_reached is outside target range"
                )

        for name in (
            "entry_price",
            "stop_loss_price",
            "maximum_favorable_excursion",
            "maximum_adverse_excursion",
            "maximum_favorable_r_multiple",
            "maximum_adverse_r_multiple",
        ):
            value = getattr(self, name)
            if not isfinite(value):
                raise ValueError(f"{name} must be finite")
            if "excursion" in name or "multiple" in name:
                if value < 0.0:
                    raise ValueError(f"{name} cannot be negative")

        created = self.candidate_created_at
        through = self.evaluated_through
        if created.tzinfo is None or created.utcoffset() is None:
            raise ValueError("candidate_created_at must be timezone-aware")
        if through.tzinfo is None or through.utcoffset() is None:
            raise ValueError("evaluated_through must be timezone-aware")
        object.__setattr__(
            self,
            "candidate_created_at",
            created.astimezone(UTC),
        )
        object.__setattr__(
            self,
            "evaluated_through",
            through.astimezone(UTC),
        )

        if self.outcome_timestamp is not None:
            timestamp = self.outcome_timestamp
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError(
                    "outcome_timestamp must be timezone-aware"
                )
            object.__setattr__(
                self,
                "outcome_timestamp",
                timestamp.astimezone(UTC),
            )

        if self.strategy_id is not None:
            if not isinstance(self.strategy_id, str) or not self.strategy_id.strip():
                raise ValueError(
                    "strategy_id must be a non-empty string or None"
                )
            object.__setattr__(
                self,
                "strategy_id",
                self.strategy_id.strip(),
            )

        if self.direction is not None and not isinstance(
            self.direction,
            SetupDirection,
        ):
            raise TypeError("direction must be SetupDirection or None")
        if self.setup_timeframe is not None and not isinstance(
            self.setup_timeframe,
            Timeframe,
        ):
            raise TypeError("setup_timeframe must be Timeframe or None")
        if self.trigger_timeframe is not None and not isinstance(
            self.trigger_timeframe,
            Timeframe,
        ):
            raise TypeError("trigger_timeframe must be Timeframe or None")

        if self.trigger_reason is not None:
            if (
                not isinstance(self.trigger_reason, str)
                or not self.trigger_reason.strip()
            ):
                raise ValueError(
                    "trigger_reason must be a non-empty string or None"
                )
            object.__setattr__(
                self,
                "trigger_reason",
                self.trigger_reason.strip(),
            )

        for field_name in (
            "setup_metadata",
            "trigger_metadata",
            "candidate_metadata",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, Mapping):
                raise TypeError(f"{field_name} must be a mapping")
            object.__setattr__(
                self,
                field_name,
                MappingProxyType(dict(value)),
            )
