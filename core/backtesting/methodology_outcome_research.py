"""Forward-horizon outcome research for observational SMC/ICT results."""

from __future__ import annotations

import csv
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from pathlib import Path
from typing import Final

from core.regime_detector.models import MarketBar
from core.strategies.methodology_models import (
    MethodologyDirection,
    MethodologyEvaluationStatus,
    MethodologyIdentifier,
)

from .methodology_observer import MethodologyObservation


@dataclass(frozen=True, slots=True)
class MethodologyOutcomeEvaluation:
    """Immutable forward-path measurement with no trade authority."""

    observation_timestamp: datetime
    methodology: MethodologyIdentifier
    evaluation_status: MethodologyEvaluationStatus
    direction: MethodologyDirection
    horizon_bars: int
    horizon_complete: bool
    source_price: float
    terminal_timestamp: datetime | None
    terminal_price: float | None
    directional_move: float | None
    directional_return_pct: float | None
    maximum_favorable_excursion: float | None
    maximum_adverse_excursion: float | None
    favorable_terminal_outcome: bool | None
    session_name: str | None
    regime_name: str | None

    def __post_init__(self) -> None:
        observation_timestamp = self._aware_utc(
            self.observation_timestamp,
            "observation_timestamp",
        )
        object.__setattr__(
            self,
            "observation_timestamp",
            observation_timestamp,
        )
        if not isinstance(self.methodology, MethodologyIdentifier):
            raise TypeError("methodology must be MethodologyIdentifier")
        if not isinstance(
            self.evaluation_status,
            MethodologyEvaluationStatus,
        ):
            raise TypeError(
                "evaluation_status must be MethodologyEvaluationStatus"
            )
        if not isinstance(self.direction, MethodologyDirection):
            raise TypeError("direction must be MethodologyDirection")
        if isinstance(self.horizon_bars, bool) or not isinstance(
            self.horizon_bars,
            int,
        ):
            raise TypeError("horizon_bars must be an integer")
        if self.horizon_bars <= 0:
            raise ValueError("horizon_bars must be greater than zero")
        if not isinstance(self.horizon_complete, bool):
            raise TypeError("horizon_complete must be a boolean")
        self._positive_finite(self.source_price, "source_price")

        if self.terminal_timestamp is not None:
            terminal_timestamp = self._aware_utc(
                self.terminal_timestamp,
                "terminal_timestamp",
            )
            if terminal_timestamp <= observation_timestamp:
                raise ValueError(
                    "terminal_timestamp must be after observation_timestamp"
                )
            object.__setattr__(
                self,
                "terminal_timestamp",
                terminal_timestamp,
            )

        optional_numeric = (
            ("terminal_price", self.terminal_price),
            ("directional_move", self.directional_move),
            ("directional_return_pct", self.directional_return_pct),
            (
                "maximum_favorable_excursion",
                self.maximum_favorable_excursion,
            ),
            (
                "maximum_adverse_excursion",
                self.maximum_adverse_excursion,
            ),
        )
        for name, value in optional_numeric:
            if value is not None:
                self._finite(value, name)

        if (
            self.maximum_favorable_excursion is not None
            and self.maximum_favorable_excursion < 0.0
        ):
            raise ValueError(
                "maximum_favorable_excursion cannot be negative"
            )
        if (
            self.maximum_adverse_excursion is not None
            and self.maximum_adverse_excursion < 0.0
        ):
            raise ValueError("maximum_adverse_excursion cannot be negative")
        if (
            self.favorable_terminal_outcome is not None
            and not isinstance(self.favorable_terminal_outcome, bool)
        ):
            raise TypeError(
                "favorable_terminal_outcome must be boolean or None"
            )

        outcome_values = (
            self.terminal_timestamp,
            self.terminal_price,
            self.directional_move,
            self.directional_return_pct,
            self.maximum_favorable_excursion,
            self.maximum_adverse_excursion,
            self.favorable_terminal_outcome,
        )
        if not self.horizon_complete:
            if any(value is not None for value in outcome_values):
                raise ValueError(
                    "incomplete horizons cannot contain outcome measurements"
                )
            return

        if self.terminal_timestamp is None or self.terminal_price is None:
            raise ValueError(
                "complete horizons require terminal timestamp and price"
            )

        directional = self.direction in {
            MethodologyDirection.BULLISH,
            MethodologyDirection.BEARISH,
        }
        directional_values = outcome_values[2:]
        if directional and any(value is None for value in directional_values):
            raise ValueError(
                "directional complete horizons require all measurements"
            )
        if not directional and any(
            value is not None for value in directional_values
        ):
            raise ValueError(
                "neutral or unknown directions cannot have directional outcomes"
            )

    @staticmethod
    def _aware_utc(value: datetime, name: str) -> datetime:
        if not isinstance(value, datetime):
            raise TypeError(f"{name} must be a datetime")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{name} must be timezone-aware")
        return value.astimezone(UTC)

    @staticmethod
    def _finite(value: float, name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be numeric")
        normalized = float(value)
        if not isfinite(normalized):
            raise ValueError(f"{name} must be finite")
        return normalized

    @classmethod
    def _positive_finite(cls, value: float, name: str) -> float:
        normalized = cls._finite(value, name)
        if normalized <= 0.0:
            raise ValueError(f"{name} must be greater than zero")
        return normalized


class MethodologyOutcomeResearch:
    """Evaluate fixed future M5 horizons after methodology observations."""

    DEFAULT_HORIZONS: Final[tuple[int, ...]] = (1, 3, 6, 12, 24)
    _CSV_COLUMNS: Final[tuple[str, ...]] = (
        "Observation Timestamp",
        "Methodology",
        "Evaluation Status",
        "Direction",
        "Horizon Bars",
        "Horizon Complete",
        "Source Price",
        "Terminal Timestamp",
        "Terminal Price",
        "Directional Move",
        "Directional Return Percent",
        "Maximum Favorable Excursion",
        "Maximum Adverse Excursion",
        "Favorable Terminal Outcome",
        "Session",
        "Regime",
    )

    def __init__(
        self,
        output_directory: str | Path = "output/backtests",
        *,
        horizons: Sequence[int] = DEFAULT_HORIZONS,
    ) -> None:
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)
        self.horizons = self._validate_horizons(horizons)

    def evaluate(
        self,
        observations: Sequence[MethodologyObservation],
        m5_bars: Sequence[MarketBar],
    ) -> tuple[MethodologyOutcomeEvaluation, ...]:
        """Measure future paths without feeding outcomes back into evaluation."""

        validated_observations = self._validate_observations(observations)
        validated_bars = self._validate_bars(m5_bars)
        bar_index = {
            bar.timestamp.astimezone(UTC): index
            for index, bar in enumerate(validated_bars)
        }

        evaluations: list[MethodologyOutcomeEvaluation] = []
        for observation in validated_observations:
            timestamp = observation.timestamp.astimezone(UTC)
            source_index = bar_index.get(timestamp)
            future_bars = (
                validated_bars[source_index + 1 :]
                if source_index is not None
                else tuple(
                    bar
                    for bar in validated_bars
                    if bar.timestamp.astimezone(UTC) > timestamp
                )
            )
            for result in (observation.smc, observation.ict):
                for horizon in self.horizons:
                    evaluations.append(
                        self._evaluate_one(
                            observation=observation,
                            methodology=result.methodology,
                            status=result.evaluation_status,
                            direction=result.direction,
                            future_bars=future_bars,
                            horizon=horizon,
                        )
                    )
        return tuple(evaluations)

    def export(
        self,
        evaluations: Sequence[MethodologyOutcomeEvaluation],
    ) -> tuple[Path, Path]:
        """Write raw forward outcomes and aggregate comparison statistics."""

        validated = self._validate_evaluations(evaluations)
        csv_path = self.output_directory / "methodology_outcomes.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=list(self._CSV_COLUMNS),
                extrasaction="raise",
            )
            writer.writeheader()
            for item in validated:
                writer.writerow(self._row(item))

        summary_path = self.output_directory / "methodology_outcome_summary.json"
        summary_path.write_text(
            json.dumps(self.summarize(validated), indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        return csv_path, summary_path

    @classmethod
    def summarize(
        cls,
        evaluations: Sequence[MethodologyOutcomeEvaluation],
    ) -> dict[str, object]:
        """Aggregate complete directional outcomes by stable research segments."""

        validated = cls._validate_evaluations(evaluations)
        groups: dict[str, dict[str, float | int]] = {}
        incomplete = 0
        nondirectional = 0

        for item in validated:
            if not item.horizon_complete:
                incomplete += 1
                continue
            if item.direction not in {
                MethodologyDirection.BULLISH,
                MethodologyDirection.BEARISH,
            }:
                nondirectional += 1
                continue

            key = "|".join(
                (
                    item.methodology.value,
                    item.evaluation_status.value,
                    item.direction.value,
                    str(item.horizon_bars),
                    item.session_name or "OFF_SESSION",
                    item.regime_name or "MISSING",
                )
            )
            bucket = groups.setdefault(
                key,
                {
                    "sample_count": 0,
                    "favorable_count": 0,
                    "directional_move_sum": 0.0,
                    "directional_return_pct_sum": 0.0,
                    "mfe_sum": 0.0,
                    "mae_sum": 0.0,
                },
            )
            bucket["sample_count"] = int(bucket["sample_count"]) + 1
            bucket["favorable_count"] = int(
                bucket["favorable_count"]
            ) + int(bool(item.favorable_terminal_outcome))
            bucket["directional_move_sum"] = float(
                bucket["directional_move_sum"]
            ) + float(item.directional_move)
            bucket["directional_return_pct_sum"] = float(
                bucket["directional_return_pct_sum"]
            ) + float(item.directional_return_pct)
            bucket["mfe_sum"] = float(bucket["mfe_sum"]) + float(
                item.maximum_favorable_excursion
            )
            bucket["mae_sum"] = float(bucket["mae_sum"]) + float(
                item.maximum_adverse_excursion
            )

        finalized: dict[str, dict[str, object]] = {}
        for key in sorted(groups):
            bucket = groups[key]
            sample_count = int(bucket["sample_count"])
            methodology, status, direction, horizon, session, regime = (
                key.split("|")
            )
            finalized[key] = {
                "methodology": methodology,
                "evaluation_status": status,
                "direction": direction,
                "horizon_bars": int(horizon),
                "session": session,
                "regime": regime,
                "sample_count": sample_count,
                "favorable_count": int(bucket["favorable_count"]),
                "favorable_rate": (
                    int(bucket["favorable_count"]) / sample_count
                ),
                "average_directional_move": (
                    float(bucket["directional_move_sum"]) / sample_count
                ),
                "average_directional_return_pct": (
                    float(bucket["directional_return_pct_sum"]) / sample_count
                ),
                "average_maximum_favorable_excursion": (
                    float(bucket["mfe_sum"]) / sample_count
                ),
                "average_maximum_adverse_excursion": (
                    float(bucket["mae_sum"]) / sample_count
                ),
            }

        return {
            "total_evaluations": len(validated),
            "complete_directional_evaluations": sum(
                int(item["sample_count"])
                for item in finalized.values()
            ),
            "incomplete_horizon_evaluations": incomplete,
            "complete_nondirectional_evaluations": nondirectional,
            "horizons": sorted({item.horizon_bars for item in validated}),
            "groups": finalized,
            "observational_only": True,
            "trade_authority": False,
            "future_information_used_for_research_only": True,
        }

    @staticmethod
    def _evaluate_one(
        *,
        observation: MethodologyObservation,
        methodology: MethodologyIdentifier,
        status: MethodologyEvaluationStatus,
        direction: MethodologyDirection,
        future_bars: tuple[MarketBar, ...],
        horizon: int,
    ) -> MethodologyOutcomeEvaluation:
        source_price = float(observation.context.current_price)
        if len(future_bars) < horizon:
            return MethodologyOutcomeEvaluation(
                observation_timestamp=observation.timestamp,
                methodology=methodology,
                evaluation_status=status,
                direction=direction,
                horizon_bars=horizon,
                horizon_complete=False,
                source_price=source_price,
                terminal_timestamp=None,
                terminal_price=None,
                directional_move=None,
                directional_return_pct=None,
                maximum_favorable_excursion=None,
                maximum_adverse_excursion=None,
                favorable_terminal_outcome=None,
                session_name=observation.context.session_name,
                regime_name=observation.context.regime_name,
            )

        bars = future_bars[:horizon]
        terminal = bars[-1]
        directional = direction in {
            MethodologyDirection.BULLISH,
            MethodologyDirection.BEARISH,
        }
        if not directional:
            return MethodologyOutcomeEvaluation(
                observation_timestamp=observation.timestamp,
                methodology=methodology,
                evaluation_status=status,
                direction=direction,
                horizon_bars=horizon,
                horizon_complete=True,
                source_price=source_price,
                terminal_timestamp=terminal.timestamp,
                terminal_price=terminal.close,
                directional_move=None,
                directional_return_pct=None,
                maximum_favorable_excursion=None,
                maximum_adverse_excursion=None,
                favorable_terminal_outcome=None,
                session_name=observation.context.session_name,
                regime_name=observation.context.regime_name,
            )

        if direction is MethodologyDirection.BULLISH:
            move = terminal.close - source_price
            favorable = max(
                max(0.0, bar.high - source_price)
                for bar in bars
            )
            adverse = max(
                max(0.0, source_price - bar.low)
                for bar in bars
            )
        else:
            move = source_price - terminal.close
            favorable = max(
                max(0.0, source_price - bar.low)
                for bar in bars
            )
            adverse = max(
                max(0.0, bar.high - source_price)
                for bar in bars
            )

        return MethodologyOutcomeEvaluation(
            observation_timestamp=observation.timestamp,
            methodology=methodology,
            evaluation_status=status,
            direction=direction,
            horizon_bars=horizon,
            horizon_complete=True,
            source_price=source_price,
            terminal_timestamp=terminal.timestamp,
            terminal_price=terminal.close,
            directional_move=move,
            directional_return_pct=(move / source_price) * 100.0,
            maximum_favorable_excursion=favorable,
            maximum_adverse_excursion=adverse,
            favorable_terminal_outcome=move > 0.0,
            session_name=observation.context.session_name,
            regime_name=observation.context.regime_name,
        )

    @staticmethod
    def _row(item: MethodologyOutcomeEvaluation) -> dict[str, object]:
        def cell(value: object | None) -> object:
            return "" if value is None else value

        return {
            "Observation Timestamp": item.observation_timestamp.isoformat(),
            "Methodology": item.methodology.value,
            "Evaluation Status": item.evaluation_status.value,
            "Direction": item.direction.value,
            "Horizon Bars": item.horizon_bars,
            "Horizon Complete": item.horizon_complete,
            "Source Price": item.source_price,
            "Terminal Timestamp": (
                item.terminal_timestamp.isoformat()
                if item.terminal_timestamp is not None
                else ""
            ),
            "Terminal Price": cell(item.terminal_price),
            "Directional Move": cell(item.directional_move),
            "Directional Return Percent": cell(
                item.directional_return_pct
            ),
            "Maximum Favorable Excursion": cell(
                item.maximum_favorable_excursion
            ),
            "Maximum Adverse Excursion": cell(
                item.maximum_adverse_excursion
            ),
            "Favorable Terminal Outcome": cell(
                item.favorable_terminal_outcome
            ),
            "Session": item.session_name or "",
            "Regime": item.regime_name or "",
        }

    @staticmethod
    def _validate_horizons(horizons: Sequence[int]) -> tuple[int, ...]:
        if isinstance(horizons, (str, bytes)) or not isinstance(
            horizons,
            Sequence,
        ):
            raise TypeError("horizons must be a sequence of integers")
        validated: list[int] = []
        for horizon in horizons:
            if isinstance(horizon, bool) or not isinstance(horizon, int):
                raise TypeError("horizons must contain integers")
            if horizon <= 0:
                raise ValueError("horizons must be greater than zero")
            validated.append(horizon)
        if not validated:
            raise ValueError("horizons cannot be empty")
        if len(validated) != len(set(validated)):
            raise ValueError("horizons cannot contain duplicates")
        return tuple(sorted(validated))

    @staticmethod
    def _validate_observations(
        observations: Sequence[MethodologyObservation],
    ) -> tuple[MethodologyObservation, ...]:
        if isinstance(observations, (str, bytes)) or not isinstance(
            observations,
            Sequence,
        ):
            raise TypeError(
                "observations must be a sequence of MethodologyObservation"
            )
        validated = tuple(observations)
        if any(
            not isinstance(item, MethodologyObservation)
            for item in validated
        ):
            raise TypeError(
                "observations must contain MethodologyObservation instances"
            )
        timestamps = tuple(item.timestamp for item in validated)
        if timestamps != tuple(sorted(timestamps)):
            raise ValueError(
                "methodology observations must be chronologically ordered"
            )
        if len(timestamps) != len(set(timestamps)):
            raise ValueError(
                "methodology observation timestamps must be unique"
            )
        return validated

    @staticmethod
    def _validate_bars(
        bars: Sequence[MarketBar],
    ) -> tuple[MarketBar, ...]:
        if isinstance(bars, (str, bytes)) or not isinstance(bars, Sequence):
            raise TypeError("m5_bars must be a sequence of MarketBar")
        validated = tuple(bars)
        previous: datetime | None = None
        for bar in validated:
            if not isinstance(bar, MarketBar):
                raise TypeError("m5_bars must contain MarketBar instances")
            timestamp = bar.timestamp
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError("M5 bar timestamps must be timezone-aware")
            timestamp = timestamp.astimezone(UTC)
            if previous is not None and timestamp <= previous:
                raise ValueError(
                    "M5 bar timestamps must be strictly increasing"
                )
            previous = timestamp
        return validated

    @staticmethod
    def _validate_evaluations(
        evaluations: Sequence[MethodologyOutcomeEvaluation],
    ) -> tuple[MethodologyOutcomeEvaluation, ...]:
        if isinstance(evaluations, (str, bytes)) or not isinstance(
            evaluations,
            Sequence,
        ):
            raise TypeError(
                "evaluations must be a sequence of "
                "MethodologyOutcomeEvaluation"
            )
        validated = tuple(evaluations)
        if any(
            not isinstance(item, MethodologyOutcomeEvaluation)
            for item in validated
        ):
            raise TypeError(
                "evaluations must contain MethodologyOutcomeEvaluation"
            )
        return validated
