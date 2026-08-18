"""Pure, read-only Aurum presentation projection package."""

from .builder import AurumReadModelBuilder, AurumSnapshotInputs
from .enums import AurumDataMode, AurumOperatorState
from .freshness import FreshnessAssessment, FreshnessContext, FreshnessPolicy
from .identity import build_observation_id, build_snapshot_id
from .live_freshness import (
    AURUM_LIVE_FRESHNESS_V1,
    MAX_M5_DECISION_DELAY_SECONDS,
    MAX_QUOTE_AGE_SECONDS,
    AurumLiveFreshnessPolicyV1,
    SnapshotCurrentness,
    evaluate_live_snapshot_currentness,
)
from .models import AurumReadModelV1, ResearchProvenanceV1
from .publication import AurumSnapshotPublication
from .serializer import to_json, to_jsonable

__all__ = [
    "AURUM_LIVE_FRESHNESS_V1",
    "MAX_M5_DECISION_DELAY_SECONDS",
    "MAX_QUOTE_AGE_SECONDS",
    "AurumDataMode",
    "AurumLiveFreshnessPolicyV1",
    "AurumOperatorState",
    "AurumReadModelBuilder",
    "AurumReadModelV1",
    "AurumSnapshotInputs",
    "AurumSnapshotPublication",
    "FreshnessAssessment",
    "FreshnessContext",
    "FreshnessPolicy",
    "ResearchProvenanceV1",
    "SnapshotCurrentness",
    "build_observation_id",
    "build_snapshot_id",
    "evaluate_live_snapshot_currentness",
    "to_json",
    "to_jsonable",
]
