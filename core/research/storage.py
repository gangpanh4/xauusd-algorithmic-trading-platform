from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.research.models import (
    Experiment,
    ExperimentResult,
    PromotionReport,
    ResearchSummary,
)


class ResearchStorage:
    """
    Persistence layer for the Quantitative Research Framework.

    Responsibilities
    ----------------
    - Save experiments
    - Save experiment results
    - Save promotion reports
    - Load previously saved objects

    Notes
    -----
    JSON is intentionally used for Sprint 2.

    Future versions can replace this implementation with
    SQLite/PostgreSQL without changing the rest of the
    research framework.
    """

    def __init__(
        self,
        root_directory: str | Path = "research/results",
    ) -> None:

        self.root = Path(root_directory)

        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

    # =====================================================
    # Internal Helpers
    # =====================================================

    def _write_json(
        self,
        filename: str,
        data: dict[str, Any],
    ) -> Path:

        path = self.root / filename

        with path.open(
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                data,
                file,
                indent=4,
                default=str,
            )

        return path

    def _read_json(
        self,
        filename: str,
    ) -> dict[str, Any]:

        path = self.root / filename

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(file)

    # =====================================================
    # Save
    # =====================================================

    def save_experiment(
        self,
        experiment: Experiment,
    ) -> Path:

        filename = (
            f"{experiment.experiment_id}_experiment.json"
        )

        return self._write_json(
            filename,
            asdict(experiment),
        )

    def save_result(
        self,
        result: ExperimentResult,
    ) -> Path:

        filename = (
            f"{result.experiment_id}_result.json"
        )

        return self._write_json(
            filename,
            asdict(result),
        )

    def save_promotion(
        self,
        report: PromotionReport,
    ) -> Path:

        filename = (
            f"{report.experiment_id}_promotion.json"
        )

        return self._write_json(
            filename,
            asdict(report),
        )

    def save_summary(
        self,
        summary: ResearchSummary,
    ) -> Path:

        timestamp = datetime.now(
            UTC
        ).strftime("%Y%m%d_%H%M%S")

        filename = (
            f"research_summary_{timestamp}.json"
        )

        return self._write_json(
            filename,
            asdict(summary),
        )

    # =====================================================
    # Load
    # =====================================================

    def load(
        self,
        filename: str,
    ) -> dict[str, Any]:

        return self._read_json(filename)

    # =====================================================
    # Listing
    # =====================================================

    def list_files(self) -> list[Path]:

        return sorted(
            self.root.glob("*.json")
        )

    # =====================================================
    # Cleanup
    # =====================================================

    def delete(
        self,
        filename: str,
    ) -> None:

        path = self.root / filename

        if path.exists():
            path.unlink()

    def clear(self) -> None:

        for file in self.root.glob("*.json"):
            file.unlink()