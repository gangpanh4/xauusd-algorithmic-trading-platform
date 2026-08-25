"""Immutable A1 market-evidence contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .enums import (
    DependencyEdgeType,
    EvidenceNodeRole,
    EvidenceStatus,
    IndependenceClass,
    LineageStatus,
)


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    repository: str
    platform_commit: str
    symbol: str
    source_instance_identity: str
    data_mode: str
    observation_id: str


@dataclass(frozen=True, slots=True)
class FreshnessEvidence:
    policy_id: str | None
    valid: bool
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MarketQuoteEvidence:
    evidence_id: str
    evidence_fingerprint: str
    symbol: str
    timestamp_utc: datetime
    bid: float
    ask: float
    mid: float
    spread_price: float
    source_identity: SourceIdentity
    available_at_utc: datetime
    freshness: FreshnessEvidence


@dataclass(frozen=True, slots=True)
class TimeframeManifest:
    timeframe: str
    source_identity: SourceIdentity
    completed_only: bool
    first_bar_time_utc: datetime | None
    last_bar_time_utc: datetime | None
    bar_count: int
    content_fingerprint: str


@dataclass(frozen=True, slots=True)
class CandleBundleManifest:
    candle_bundle_id: str
    candle_bundle_fingerprint: str
    symbol: str
    source_identity: SourceIdentity
    timeframes: tuple[TimeframeManifest, ...]


@dataclass(frozen=True, slots=True)
class DependencyEdge:
    parent_evidence_id: str
    edge_type: DependencyEdgeType


@dataclass(frozen=True, slots=True)
class EvidenceNode:
    evidence_id: str
    evidence_fingerprint: str
    evidence_family: str
    upstream_record_kind: str
    upstream_record_id: str
    timeframe: str | None
    direction: str | None
    node_role: EvidenceNodeRole
    event_time_utc: datetime | None
    confirmed_at_utc: datetime | None
    available_at_utc: datetime
    source_identity: SourceIdentity
    status: EvidenceStatus
    freshness_status: str | None
    parent_evidence_ids: tuple[str, ...]
    dependency_root_ids: tuple[str, ...]
    dependency_edges: tuple[DependencyEdge, ...]
    independence_class: IndependenceClass
    conflict_group_ids: tuple[str, ...]
    payload: tuple[tuple[str, Any], ...]


@dataclass(frozen=True, slots=True)
class DependencyRelation:
    child_evidence_id: str
    parent_evidence_id: str
    edge_type: DependencyEdgeType


@dataclass(frozen=True, slots=True)
class DependencyGroup:
    group_id: str
    root_evidence_ids: tuple[str, ...]
    member_evidence_ids: tuple[str, ...]
    independence_class: IndependenceClass


@dataclass(frozen=True, slots=True)
class ConflictRecord:
    code: str
    detail: str
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReadinessRecord:
    code: str
    ready: bool
    detail: str
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MarketEvidenceSnapshot:
    schema_version: str
    snapshot_id: str
    snapshot_fingerprint: str
    symbol: str
    as_of_utc: datetime
    generated_at_utc: datetime
    decision_available_at_utc: datetime
    platform_commit: str
    configuration_identity: str
    source_identity: SourceIdentity
    quote: MarketQuoteEvidence | None
    timeframe_manifests: tuple[TimeframeManifest, ...]
    evidence_nodes: tuple[EvidenceNode, ...]
    dependency_relations: tuple[DependencyRelation, ...]
    dependency_groups: tuple[DependencyGroup, ...]
    conflicts: tuple[ConflictRecord, ...]
    readiness: tuple[ReadinessRecord, ...]
    freshness: FreshnessEvidence
    candle_bundle_id: str
    candle_bundle_fingerprint: str
    macro_snapshot_id: None
    lineage_status: LineageStatus
