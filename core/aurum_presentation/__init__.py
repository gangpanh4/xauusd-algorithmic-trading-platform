"""Pure, read-only Aurum presentation projection package."""

from .builder import AurumReadModelBuilder, AurumSnapshotInputs
from .enums import AurumDataMode, AurumOperatorState
from .freshness import FreshnessAssessment, FreshnessContext, FreshnessPolicy
from .identity import build_observation_id, build_snapshot_id
from .models import AurumReadModelV1, ResearchProvenanceV1
from .publication import AurumSnapshotPublication
from .serializer import to_json, to_jsonable

__all__ = [
    "AurumDataMode",
    "AurumOperatorState",
    "AurumReadModelBuilder",
    "AurumReadModelV1",
    "AurumSnapshotInputs",
    "AurumSnapshotPublication",
    "FreshnessAssessment",
    "FreshnessContext",
    "FreshnessPolicy",
    "ResearchProvenanceV1",
    "build_observation_id",
    "build_snapshot_id",
    "to_json",
    "to_jsonable",
]
