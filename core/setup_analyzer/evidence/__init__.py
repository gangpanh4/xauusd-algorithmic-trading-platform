"""Immutable read-only evidence foundation for Analyzer A1."""

from .adapter import (
    SCHEMA_VERSION,
    EvidenceSnapshotContractError,
    build_market_evidence_snapshot,
)
from .dependency import FatalLineageError, classify_dependencies, validate_lineage
from .enums import (
    DependencyEdgeType,
    EvidenceNodeRole,
    EvidenceStatus,
    IndependenceClass,
    LineageStatus,
)
from .models import (
    CandleBundleManifest,
    ConflictRecord,
    DependencyGroup,
    DependencyRelation,
    EvidenceNode,
    FreshnessEvidence,
    MarketEvidenceSnapshot,
    MarketQuoteEvidence,
    ReadinessRecord,
    SourceIdentity,
    TimeframeManifest,
)

__all__ = [
    "SCHEMA_VERSION",
    "CandleBundleManifest",
    "ConflictRecord",
    "DependencyEdgeType",
    "DependencyGroup",
    "DependencyRelation",
    "EvidenceNode",
    "EvidenceNodeRole",
    "EvidenceSnapshotContractError",
    "EvidenceStatus",
    "FatalLineageError",
    "FreshnessEvidence",
    "IndependenceClass",
    "LineageStatus",
    "MarketEvidenceSnapshot",
    "MarketQuoteEvidence",
    "ReadinessRecord",
    "SourceIdentity",
    "TimeframeManifest",
    "build_market_evidence_snapshot",
    "classify_dependencies",
    "validate_lineage",
]
