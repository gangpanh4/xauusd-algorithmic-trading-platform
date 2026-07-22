"""
Confluence Engine runtime state.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.confluence_engine.models import (
    ConfluenceResult,
)


@dataclass(slots=True)
class ConfluenceEngineState:
    """
    Runtime state of the Confluence Engine.
    """

    processed_count: int = 0

    approved_count: int = 0

    rejected_count: int = 0

    @property
    def decision_count(
        self,
    ) -> int:
        """
        Return the total number of completed decisions.
        """

        return (
            self.approved_count
            + self.rejected_count
        )

    last_result: ConfluenceResult | None = None

    history: list[
        ConfluenceResult
    ] = field(default_factory=list)

    def reset(
        self,
    ) -> None:
        """
        Reset runtime state.
        """

        self.processed_count = 0

        self.approved_count = 0

        self.rejected_count = 0

        self.last_result = None

        self.history.clear()