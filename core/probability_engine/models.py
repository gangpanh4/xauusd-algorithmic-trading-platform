"""
Probability Engine models.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.feature_engineering.models import FeatureVector


@dataclass(slots=True)
class EvidenceScore:
    """
    Contribution from one evidence family.
    """

    family: str

    score: float

    confidence: float


@dataclass(slots=True)
class ProbabilityResult:
    """
    Output produced by the Probability Engine.
    """

    probability: float = 0.0

    confidence: float = 0.0

    accepted: bool = False

    reasons: list[str] = field(default_factory=list)

    evidence: list[EvidenceScore] = field(
        default_factory=list,
    )

    feature_vector: FeatureVector | None = None

    def add_reason(
        self,
        reason: str,
    ) -> None:
        """
        Add a human-readable reason if it is not already present.
        """

        if reason not in self.reasons:
            self.reasons.append(reason)