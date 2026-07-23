"""Research-only outcome models for observational strategy candidates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from math import isfinite
from uuid import UUID


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
