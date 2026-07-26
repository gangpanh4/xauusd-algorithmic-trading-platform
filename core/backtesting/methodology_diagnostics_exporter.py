"""Deterministic research exports for observational SMC/ICT diagnostics."""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final

from .methodology_observer import MethodologyObservation
from core.strategies.methodology_models import MethodologyResult


class MethodologyDiagnosticsExporter:
    """Write methodology diagnostics without changing execution reports."""

    _COLUMNS: Final[tuple[str, ...]] = (
        "Observation Number",
        "Timestamp",
        "Current Bar Index",
        "Current Price",
        "Higher Timeframe Bias",
        "Session",
        "Regime",
        "Regime Confidence",
        "Price Location",
        "Dealing Range High",
        "Dealing Range Low",
        "Dealing Range Equilibrium",
        "Dealing Range Timeframe",
        "Displacement Present",
        "Displacement Direction",
        "Displacement Timeframe",
        "Displacement ATR Multiple",
        "Latest Structure Event Timeframe",
        "Latest Liquidity Sweep Timeframe",
        "Opposing Liquidity Timeframe",
        "Active FVG Timeframe",
        "Active Order Block Timeframe",
        "Missing Capabilities",
        "SMC Status",
        "SMC Direction",
        "SMC Reason Codes",
        "SMC Reason",
        "SMC Satisfied Conditions",
        "SMC Failed Conditions",
        "SMC Unavailable Conditions",
        "ICT Status",
        "ICT Direction",
        "ICT Reason Codes",
        "ICT Reason",
        "ICT Satisfied Conditions",
        "ICT Failed Conditions",
        "ICT Unavailable Conditions",
    )

    def __init__(
        self,
        output_directory: str | Path = "output/backtests",
    ) -> None:
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)

    def export_observations(
        self,
        observations: Sequence[MethodologyObservation],
    ) -> Path:
        """Export one deterministic CSV row per completed methodology candle."""

        validated = self._validate_observations(observations)
        path = self.output_directory / "methodology_observations.csv"

        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=list(self._COLUMNS),
                extrasaction="raise",
            )
            writer.writeheader()
            for index, observation in enumerate(validated, start=1):
                writer.writerow(self._row(index, observation))

        return path

    def export_summary(
        self,
        summary: Mapping[str, int],
        *,
        total_observations: int,
    ) -> Path:
        """Export deterministic aggregate methodology-status counts."""

        validated_summary = self._validate_summary(summary)
        if isinstance(total_observations, bool) or not isinstance(
            total_observations,
            int,
        ):
            raise TypeError("total_observations must be an integer")
        if total_observations < 0:
            raise ValueError("total_observations cannot be negative")

        per_methodology = {
            "SMC": {
                "CONFIRMED": validated_summary.get("SMC:CONFIRMED", 0),
                "NOT_CONFIRMED": validated_summary.get(
                    "SMC:NOT_CONFIRMED",
                    0,
                ),
                "INCOMPLETE": validated_summary.get("SMC:INCOMPLETE", 0),
            },
            "ICT": {
                "CONFIRMED": validated_summary.get("ICT:CONFIRMED", 0),
                "NOT_CONFIRMED": validated_summary.get(
                    "ICT:NOT_CONFIRMED",
                    0,
                ),
                "INCOMPLETE": validated_summary.get("ICT:INCOMPLETE", 0),
            },
        }
        for methodology, counts in per_methodology.items():
            if sum(counts.values()) != total_observations:
                raise ValueError(
                    f"{methodology} summary count must equal total_observations"
                )

        payload = {
            "total_observations": total_observations,
            "status_counts": dict(sorted(validated_summary.items())),
            "methodologies": per_methodology,
            "observational_only": True,
            "trade_authority": False,
        }
        path = self.output_directory / "methodology_summary.json"
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path

    @classmethod
    def _row(
        cls,
        index: int,
        observation: MethodologyObservation,
    ) -> dict[str, object]:
        context = observation.context
        return {
            "Observation Number": index,
            "Timestamp": observation.timestamp.isoformat(),
            "Current Bar Index": context.current_bar_index,
            "Current Price": context.current_price,
            "Higher Timeframe Bias": context.higher_timeframe_bias.value,
            "Session": context.session_name or "",
            "Regime": context.regime_name or "",
            "Regime Confidence": cls._cell(context.regime_confidence),
            "Price Location": context.price_location.name,
            "Dealing Range High": cls._cell(context.dealing_range_high),
            "Dealing Range Low": cls._cell(context.dealing_range_low),
            "Dealing Range Equilibrium": cls._cell(
                context.dealing_range_equilibrium
            ),
            "Dealing Range Timeframe": cls._enum_cell(
                context.dealing_range_timeframe
            ),
            "Displacement Present": cls._cell(
                context.displacement_present
            ),
            "Displacement Direction": cls._enum_cell(
                context.displacement_direction
            ),
            "Displacement Timeframe": cls._enum_cell(
                context.displacement_timeframe
            ),
            "Displacement ATR Multiple": cls._cell(
                context.displacement_atr_multiple
            ),
            "Latest Structure Event Timeframe": cls._enum_cell(
                context.latest_structure_event_timeframe
            ),
            "Latest Liquidity Sweep Timeframe": cls._enum_cell(
                context.latest_liquidity_sweep_timeframe
            ),
            "Opposing Liquidity Timeframe": cls._enum_cell(
                context.opposing_liquidity_timeframe
            ),
            "Active FVG Timeframe": cls._enum_cell(
                context.active_fair_value_gap_timeframe
            ),
            "Active Order Block Timeframe": cls._enum_cell(
                context.active_order_block_timeframe
            ),
            "Missing Capabilities": cls._join(context.missing_capabilities),
            **cls._result_cells("SMC", observation.smc),
            **cls._result_cells("ICT", observation.ict),
        }

    @classmethod
    def _result_cells(
        cls,
        prefix: str,
        result: MethodologyResult,
    ) -> dict[str, object]:
        return {
            f"{prefix} Status": result.evaluation_status.value,
            f"{prefix} Direction": result.direction.value,
            f"{prefix} Reason Codes": cls._join(result.reason_codes),
            f"{prefix} Reason": result.reason,
            f"{prefix} Satisfied Conditions": cls._condition_codes(
                result.satisfied_conditions
            ),
            f"{prefix} Failed Conditions": cls._condition_codes(
                result.failed_conditions
            ),
            f"{prefix} Unavailable Conditions": cls._condition_codes(
                result.unavailable_conditions
            ),
        }

    @staticmethod
    def _condition_codes(conditions: tuple[object, ...]) -> str:
        return "|".join(getattr(condition, "code") for condition in conditions)

    @staticmethod
    def _join(values: tuple[str, ...]) -> str:
        return "|".join(values)

    @staticmethod
    def _enum_cell(value: object | None) -> str:
        if value is None:
            return ""
        return str(getattr(value, "value"))

    @staticmethod
    def _cell(value: object | None) -> object:
        return "" if value is None else value

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
    def _validate_summary(summary: Mapping[str, int]) -> dict[str, int]:
        if not isinstance(summary, Mapping):
            raise TypeError("summary must be a mapping")
        validated: dict[str, int] = {}
        allowed = {
            f"{methodology}:{status}"
            for methodology in ("SMC", "ICT")
            for status in ("CONFIRMED", "NOT_CONFIRMED", "INCOMPLETE")
        }
        for key, value in summary.items():
            if not isinstance(key, str) or key not in allowed:
                raise ValueError(f"unsupported methodology summary key: {key!r}")
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError("methodology summary counts must be integers")
            if value < 0:
                raise ValueError(
                    "methodology summary counts cannot be negative"
                )
            validated[key] = value
        return validated
