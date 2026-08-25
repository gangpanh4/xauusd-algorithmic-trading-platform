"""Read-only adapter from authoritative Aurum facts into A1 evidence.

Logical upstream-record identity intentionally excludes mutable factual values.
The supported record keys are:

* quote: source + quote timestamp;
* SwingV1: timeframe + pivot timestamp/index/type;
* BreakV1: timeframe + event timestamp/break type/confirmation index + swing key;
* LiquidityLevelV1: timeframe + level timestamp + source swing key;
* LiquiditySweepV1: timeframe + event timestamp/confirmation index + level key;
* FairValueGapV1: timeframe + gap timestamp + gap type;
* OrderBlockV1: timeframe + origin timestamp/creation index/confirmation index +
  origin-swing and trigger-break keys;
* MultiTimeframeFrameV1, StructureFrameV1, PriceActionFrameV1: timeframe +
  projected frame timestamp;
* ProtectedStructureReferenceV1: timeframe + structure-frame timestamp +
  protected-high/protected-low reference role;
* RegimeV1: regime observation timestamp + upstream computation timestamp.

All remaining factual content belongs to ``evidence_fingerprint`` rather than
``evidence_id``. Availability is taken from record-specific upstream temporal
evidence when it can be proven from the projected completed-bar bundle. When
that proof is unavailable, ``available_at_utc`` is ``None`` and the node is
explicitly ``BLOCKED_UPSTREAM`` rather than backdated to the current analysis
boundary.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timedelta
from typing import Any

from core.aurum_presentation.enums import AurumDataMode
from core.aurum_presentation.live_freshness import AURUM_LIVE_FRESHNESS_V1
from core.aurum_presentation.models import AurumReadModelV1

from .dependency import FatalLineageError, classify_dependencies
from .enums import (
    DependencyEdgeType,
    EvidenceNodeRole,
    EvidenceStatus,
    IndependenceClass,
    LineageStatus,
)
from .identity import deterministic_id, fingerprint
from .models import (
    CandleBundleManifest,
    ConflictRecord,
    DependencyEdge,
    DependencyRelation,
    EvidenceNode,
    FreshnessEvidence,
    MarketEvidenceSnapshot,
    MarketQuoteEvidence,
    ReadinessRecord,
    SourceIdentity,
    TimeframeManifest,
)

SCHEMA_VERSION = "ANALYZER_A1_EVIDENCE_SNAPSHOT_V1"
_TIMEFRAMES = ("W1", "D1", "H4", "H1", "M15", "M5")
_TIMEFRAME_DURATIONS = {
    "W1": timedelta(days=7),
    "D1": timedelta(days=1),
    "H4": timedelta(hours=4),
    "H1": timedelta(hours=1),
    "M15": timedelta(minutes=15),
    "M5": timedelta(minutes=5),
}


class EvidenceSnapshotContractError(ValueError):
    """Raised when one snapshot cannot be represented without contract violation."""


def _stable_source_key(source: SourceIdentity) -> dict[str, str]:
    """Return source identity stable across later observation cuts."""

    return {
        "repository": source.repository,
        "platform_commit": source.platform_commit,
        "symbol": source.symbol,
        "source_instance_identity": source.source_instance_identity,
        "data_mode": source.data_mode,
    }


class _NodeCollector:
    def __init__(self, source: SourceIdentity) -> None:
        self.source = source
        self.nodes: dict[str, EvidenceNode] = {}
        self.relations: dict[
            tuple[str, str, DependencyEdgeType], DependencyRelation
        ] = {}

    def add(
        self,
        *,
        family: str,
        kind: str,
        upstream_id: str,
        timeframe: str | None,
        direction: str | None,
        role: EvidenceNodeRole,
        event_time: datetime | None,
        payload: dict[str, Any],
        available_at: datetime | None,
        confirmed_at: datetime | None = None,
        parents: tuple[tuple[str, DependencyEdgeType], ...] = (),
    ) -> str:
        if (
            confirmed_at is not None
            and available_at is not None
            and confirmed_at > available_at
        ):
            raise FatalLineageError(
                f"confirmation after availability for upstream record {upstream_id}"
            )
        identity_basis = {
            "family": family,
            "kind": kind,
            "upstream_id": upstream_id,
            "timeframe": timeframe,
            "source": _stable_source_key(self.source),
        }
        evidence_id = deterministic_id("evidence", identity_basis)
        factual_basis = {
            **identity_basis,
            "direction": direction,
            "event_time": event_time,
            "confirmed_at": confirmed_at,
            "available_at": available_at,
            "payload": payload,
        }
        evidence_fingerprint = fingerprint(factual_basis)
        edges = tuple(
            DependencyEdge(parent_evidence_id=parent_id, edge_type=edge_type)
            for parent_id, edge_type in sorted(
                parents,
                key=lambda item: (item[0], item[1].value),
            )
        )
        status = (
            EvidenceStatus.AVAILABLE
            if available_at is not None
            else EvidenceStatus.BLOCKED_UPSTREAM
        )
        node = EvidenceNode(
            evidence_id=evidence_id,
            evidence_fingerprint=evidence_fingerprint,
            evidence_family=family,
            upstream_record_kind=kind,
            upstream_record_id=upstream_id,
            timeframe=timeframe,
            direction=direction,
            node_role=role,
            event_time_utc=event_time,
            confirmed_at_utc=confirmed_at,
            available_at_utc=available_at,
            source_identity=self.source,
            status=status,
            freshness_status=None,
            parent_evidence_ids=tuple(parent_id for parent_id, _ in parents),
            dependency_root_ids=(),
            dependency_edges=edges,
            independence_class=IndependenceClass.NOT_EVALUABLE,
            conflict_group_ids=(),
            payload=tuple(sorted(payload.items())),
        )
        existing = self.nodes.get(evidence_id)
        if existing is not None:
            if existing.evidence_fingerprint != evidence_fingerprint:
                raise FatalLineageError(
                    f"contradictory fingerprint for evidence identity {evidence_id}"
                )
            if (
                existing.node_role is EvidenceNodeRole.LINEAGE_ONLY
                and role is EvidenceNodeRole.PRIMARY
            ):
                node = replace(existing, node_role=EvidenceNodeRole.PRIMARY)
            else:
                node = existing
        self.nodes[evidence_id] = node
        for parent_id, edge_type in parents:
            key = (evidence_id, parent_id, edge_type)
            self.relations[key] = DependencyRelation(
                child_evidence_id=evidence_id,
                parent_evidence_id=parent_id,
                edge_type=edge_type,
            )
        return evidence_id

    def node(self, evidence_id: str) -> EvidenceNode:
        return self.nodes[evidence_id]


def _source_identity(
    model: AurumReadModelV1,
    source_instance_identity: str,
) -> SourceIdentity:
    return SourceIdentity(
        repository=model.meta.backend_repository,
        platform_commit=model.meta.backend_commit,
        symbol=model.market.symbol,
        source_instance_identity=source_instance_identity,
        data_mode=model.meta.data_mode.value,
        observation_id=model.meta.observation_id,
    )


def _freshness(model: AurumReadModelV1) -> FreshnessEvidence:
    return FreshnessEvidence(
        policy_id=model.meta.freshness_policy_id,
        valid=model.health.freshness_valid,
        reason_codes=tuple(
            code for code in model.health.reason_codes if code.startswith("LIVE_")
        ),
    )


def _timeframe_manifests(
    model: AurumReadModelV1,
    source: SourceIdentity,
) -> tuple[TimeframeManifest, ...]:
    manifests: list[TimeframeManifest] = []
    for timeframe in _TIMEFRAMES:
        bucket = getattr(model.bars.frames, timeframe)
        if bucket is None:
            manifests.append(
                TimeframeManifest(
                    timeframe=timeframe,
                    source_identity=source,
                    completed_only=False,
                    first_bar_time_utc=None,
                    last_bar_time_utc=None,
                    bar_count=0,
                    content_fingerprint=fingerprint(()),
                )
            )
            continue
        items = tuple(bucket.items)
        manifests.append(
            TimeframeManifest(
                timeframe=timeframe,
                source_identity=source,
                completed_only=bucket.completed_only,
                first_bar_time_utc=items[0].timestamp_utc if items else None,
                last_bar_time_utc=items[-1].timestamp_utc if items else None,
                bar_count=len(items),
                content_fingerprint=fingerprint(items),
            )
        )
    return tuple(manifests)


def _quote(
    model: AurumReadModelV1,
    source: SourceIdentity,
    freshness: FreshnessEvidence,
) -> MarketQuoteEvidence | None:
    quote = model.quote
    if not quote.available:
        return None
    values = (
        quote.observed_at_utc,
        quote.bid,
        quote.ask,
        quote.mid,
        quote.spread_price,
    )
    if any(value is None for value in values):
        return None
    timestamp = quote.observed_at_utc
    assert timestamp is not None
    identity_basis = {
        "symbol": model.market.symbol,
        "timestamp_utc": timestamp,
        "source": _stable_source_key(source),
    }
    factual_basis = {
        **identity_basis,
        "bid": quote.bid,
        "ask": quote.ask,
        "mid": quote.mid,
        "spread_price": quote.spread_price,
    }
    return MarketQuoteEvidence(
        evidence_id=deterministic_id("quote", identity_basis),
        evidence_fingerprint=fingerprint(factual_basis),
        symbol=model.market.symbol,
        timestamp_utc=timestamp,
        bid=float(quote.bid),
        ask=float(quote.ask),
        mid=float(quote.mid),
        spread_price=float(quote.spread_price),
        source_identity=source,
        available_at_utc=timestamp,
        freshness=freshness,
    )


def _record_id(kind: str, timeframe: str, logical_key: Any) -> str:
    """Build a stable logical upstream-record id from immutable key fields."""

    return deterministic_id(
        "upstream-record",
        {"kind": kind, "timeframe": timeframe, "logical_key": logical_key},
    )


def _swing_key(swing: Any) -> dict[str, Any]:
    return {
        "timestamp_utc": swing.timestamp_utc,
        "index": swing.index,
        "swing_type": swing.swing_type,
    }


def _break_key(event: Any) -> dict[str, Any]:
    return {
        "timestamp_utc": event.timestamp_utc,
        "break_type": event.break_type,
        "confirmation_index": event.confirmation_index,
        "swing": _swing_key(event.swing_point),
    }


def _liquidity_level_key(level: Any) -> dict[str, Any]:
    return {
        "timestamp_utc": level.timestamp_utc,
        "swing": _swing_key(level.swing_point),
    }


def _liquidity_sweep_key(sweep: Any) -> dict[str, Any]:
    return {
        "timestamp_utc": sweep.timestamp_utc,
        "confirmation_index": sweep.confirmation_index,
        "liquidity_level": _liquidity_level_key(sweep.liquidity_level),
    }


def _fvg_key(fvg: Any) -> dict[str, Any]:
    return {"timestamp_utc": fvg.timestamp_utc, "gap_type": fvg.gap_type}


def _order_block_key(block: Any) -> dict[str, Any]:
    return {
        "timestamp_utc": block.timestamp_utc,
        "creation_index": block.creation_index,
        "confirmation_index": block.confirmation_index,
        "origin_swing": _swing_key(block.origin_swing),
        "trigger_break": _break_key(block.trigger_break),
    }


def _bucket_items(model: AurumReadModelV1, timeframe: str) -> tuple[Any, ...]:
    bucket = getattr(model.bars.frames, timeframe)
    if bucket is None or not bucket.completed_only:
        return ()
    return tuple(bucket.items)


def _bar_close(timestamp: datetime, timeframe: str) -> datetime:
    return timestamp + _TIMEFRAME_DURATIONS[timeframe]


def _legal_bar_close(
    model: AurumReadModelV1,
    timeframe: str,
    timestamp: datetime,
) -> datetime | None:
    close = _bar_close(timestamp, timeframe)
    if close > model.meta.decision_available_at_utc:
        return None
    return close


def _bar_close_for_timestamp(
    model: AurumReadModelV1,
    timeframe: str,
    timestamp: datetime | None,
) -> datetime | None:
    if timestamp is None:
        return None
    matches = [
        item
        for item in _bucket_items(model, timeframe)
        if item.timestamp_utc == timestamp
    ]
    if len(matches) != 1:
        return None
    return _legal_bar_close(model, timeframe, matches[0].timestamp_utc)


def _confirmation_times(
    model: AurumReadModelV1,
    timeframe: str,
    *,
    confirmation_index: int,
    event_timestamp: datetime | None = None,
    event_index: int | None = None,
    age: int = 0,
) -> tuple[datetime | None, datetime | None]:
    items = _bucket_items(model, timeframe)
    if not items:
        return None, None
    if event_index is not None:
        if event_index < 0 or event_index >= len(items):
            return None, None
        if (
            event_timestamp is None
            or items[event_index].timestamp_utc != event_timestamp
        ):
            return None, None
    if confirmation_index < 0 or confirmation_index >= len(items):
        return None, None
    if (
        event_index is None
        and event_timestamp is not None
        and items[confirmation_index].timestamp_utc != event_timestamp
    ):
        return None, None
    confirmed_at = _legal_bar_close(
        model,
        timeframe,
        items[confirmation_index].timestamp_utc,
    )
    target_index = confirmation_index + max(0, age)
    if target_index >= len(items):
        return confirmed_at, None
    available_at = _legal_bar_close(
        model,
        timeframe,
        items[target_index].timestamp_utc,
    )
    return confirmed_at, available_at


def _fvg_availability(
    model: AurumReadModelV1,
    timeframe: str,
    fvg: Any,
) -> tuple[datetime | None, datetime | None]:
    items = _bucket_items(model, timeframe)
    matching_indexes = [
        index
        for index, item in enumerate(items)
        if item.timestamp_utc == fvg.timestamp_utc
    ]
    if len(matching_indexes) != 1:
        return None, None
    origin_index = matching_indexes[0]
    if fvg.kind == "CANDIDATE":
        available = _legal_bar_close(
            model,
            timeframe,
            items[origin_index].timestamp_utc,
        )
        return None, available
    if fvg.kind != "CONFIRMED":
        return None, None
    confirmation_index = origin_index + 1
    if confirmation_index >= len(items):
        return None, None
    confirmed_at = _legal_bar_close(
        model,
        timeframe,
        items[confirmation_index].timestamp_utc,
    )
    target_index = origin_index + max(1, int(fvg.age))
    if target_index >= len(items):
        return confirmed_at, None
    available_at = _legal_bar_close(
        model,
        timeframe,
        items[target_index].timestamp_utc,
    )
    return confirmed_at, available_at


def _all_known_max(values: tuple[datetime | None, ...]) -> datetime | None:
    if any(value is None for value in values):
        return None
    return max(value for value in values if value is not None)


def _add_swing(
    collector: _NodeCollector,
    model: AurumReadModelV1,
    timeframe: str,
    swing: Any,
    role: EvidenceNodeRole,
) -> str:
    payload = asdict(swing)
    confirmed_at, available_at = _confirmation_times(
        model,
        timeframe,
        confirmation_index=swing.confirmation_index,
        event_timestamp=swing.timestamp_utc,
        event_index=swing.index,
    )
    return collector.add(
        family="STRUCTURE_SWING",
        kind="SwingV1",
        upstream_id=_record_id("SwingV1", timeframe, _swing_key(swing)),
        timeframe=timeframe,
        direction=swing.swing_type,
        role=role,
        event_time=swing.timestamp_utc,
        confirmed_at=confirmed_at,
        available_at=available_at,
        payload=payload,
    )


def _add_break(
    collector: _NodeCollector,
    model: AurumReadModelV1,
    timeframe: str,
    event: Any,
    role: EvidenceNodeRole,
) -> str:
    swing_id = _add_swing(
        collector,
        model,
        timeframe,
        event.swing_point,
        EvidenceNodeRole.LINEAGE_ONLY,
    )
    payload = asdict(event)
    payload.pop("swing_point", None)
    confirmed_at, event_available = _confirmation_times(
        model,
        timeframe,
        confirmation_index=event.confirmation_index,
        event_timestamp=event.timestamp_utc,
        age=event.age,
    )
    available_at = _all_known_max(
        (event_available, collector.node(swing_id).available_at_utc)
    )
    return collector.add(
        family=f"STRUCTURE_{event.break_type}",
        kind="BreakV1",
        upstream_id=_record_id("BreakV1", timeframe, _break_key(event)),
        timeframe=timeframe,
        direction=event.direction,
        role=role,
        event_time=event.timestamp_utc,
        confirmed_at=confirmed_at,
        available_at=available_at,
        payload=payload,
        parents=((swing_id, DependencyEdgeType.CONTENT_CAUSAL),),
    )


def _add_liquidity_level(
    collector: _NodeCollector,
    model: AurumReadModelV1,
    timeframe: str,
    level: Any,
    role: EvidenceNodeRole,
) -> str:
    swing_id = _add_swing(
        collector,
        model,
        timeframe,
        level.swing_point,
        EvidenceNodeRole.LINEAGE_ONLY,
    )
    payload = asdict(level)
    payload.pop("swing_point", None)
    available_at = collector.node(swing_id).available_at_utc
    return collector.add(
        family="LIQUIDITY_LEVEL",
        kind="LiquidityLevelV1",
        upstream_id=_record_id(
            "LiquidityLevelV1",
            timeframe,
            _liquidity_level_key(level),
        ),
        timeframe=timeframe,
        direction=level.side,
        role=role,
        event_time=level.timestamp_utc,
        available_at=available_at,
        payload=payload,
        parents=((swing_id, DependencyEdgeType.CONTENT_CAUSAL),),
    )


def _add_liquidity_sweep(
    collector: _NodeCollector,
    model: AurumReadModelV1,
    timeframe: str,
    sweep: Any,
    role: EvidenceNodeRole,
) -> str:
    level_id = _add_liquidity_level(
        collector,
        model,
        timeframe,
        sweep.liquidity_level,
        EvidenceNodeRole.LINEAGE_ONLY,
    )
    payload = asdict(sweep)
    payload.pop("liquidity_level", None)
    confirmed_at, event_available = _confirmation_times(
        model,
        timeframe,
        confirmation_index=sweep.confirmation_index,
        event_timestamp=sweep.timestamp_utc,
        age=sweep.age,
    )
    available_at = _all_known_max(
        (event_available, collector.node(level_id).available_at_utc)
    )
    return collector.add(
        family="LIQUIDITY_SWEEP",
        kind="LiquiditySweepV1",
        upstream_id=_record_id(
            "LiquiditySweepV1",
            timeframe,
            _liquidity_sweep_key(sweep),
        ),
        timeframe=timeframe,
        direction=sweep.liquidity_level.side,
        role=role,
        event_time=sweep.timestamp_utc,
        confirmed_at=confirmed_at,
        available_at=available_at,
        payload=payload,
        parents=((level_id, DependencyEdgeType.CONTENT_CAUSAL),),
    )


def _add_order_block(
    collector: _NodeCollector,
    model: AurumReadModelV1,
    timeframe: str,
    block: Any,
) -> str:
    origin_id = _add_swing(
        collector,
        model,
        timeframe,
        block.origin_swing,
        EvidenceNodeRole.LINEAGE_ONLY,
    )
    break_id = _add_break(
        collector,
        model,
        timeframe,
        block.trigger_break,
        EvidenceNodeRole.LINEAGE_ONLY,
    )
    parents: list[tuple[str, DependencyEdgeType]] = [
        (origin_id, DependencyEdgeType.CONTENT_CAUSAL),
        (break_id, DependencyEdgeType.CONTENT_CAUSAL),
    ]
    parent_availability: list[datetime | None] = [
        collector.node(origin_id).available_at_utc,
        collector.node(break_id).available_at_utc,
    ]
    if block.trigger_liquidity is not None:
        liquidity_id = _add_liquidity_sweep(
            collector,
            model,
            timeframe,
            block.trigger_liquidity,
            EvidenceNodeRole.LINEAGE_ONLY,
        )
        parents.append((liquidity_id, DependencyEdgeType.CONTENT_CAUSAL))
        parent_availability.append(collector.node(liquidity_id).available_at_utc)
    payload = asdict(block)
    payload.pop("origin_swing", None)
    payload.pop("trigger_break", None)
    payload.pop("trigger_liquidity", None)
    confirmed_at, record_available = _confirmation_times(
        model,
        timeframe,
        confirmation_index=block.confirmation_index,
        event_timestamp=block.trigger_break.timestamp_utc,
    )
    available_at = _all_known_max(
        (record_available, *tuple(parent_availability))
    )
    return collector.add(
        family="ORDER_BLOCK",
        kind="OrderBlockV1",
        upstream_id=_record_id(
            "OrderBlockV1",
            timeframe,
            _order_block_key(block),
        ),
        timeframe=timeframe,
        direction=block.block_type,
        role=EvidenceNodeRole.PRIMARY,
        event_time=block.timestamp_utc,
        confirmed_at=confirmed_at,
        available_at=available_at,
        payload=payload,
        parents=tuple(parents),
    )


def _add_protected_reference(
    collector: _NodeCollector,
    model: AurumReadModelV1,
    timeframe: str,
    structure: Any,
    *,
    reference_role: str,
    swing: Any,
) -> str:
    swing_id = _add_swing(
        collector,
        model,
        timeframe,
        swing,
        EvidenceNodeRole.LINEAGE_ONLY,
    )
    state_available = _bar_close_for_timestamp(
        model,
        timeframe,
        structure.timestamp_utc,
    )
    available_at = _all_known_max(
        (state_available, collector.node(swing_id).available_at_utc)
    )
    payload = {
        "reference_role": reference_role,
        "target_evidence_id": swing_id,
    }
    return collector.add(
        family=f"{reference_role}_REFERENCE",
        kind="ProtectedStructureReferenceV1",
        upstream_id=_record_id(
            "ProtectedStructureReferenceV1",
            timeframe,
            {
                "structure_timestamp_utc": structure.timestamp_utc,
                "reference_role": reference_role,
            },
        ),
        timeframe=timeframe,
        direction=swing.swing_type,
        role=EvidenceNodeRole.CONTEXT_PROJECTION,
        event_time=structure.timestamp_utc,
        available_at=available_at,
        payload=payload,
        parents=((swing_id, DependencyEdgeType.STATE_LINEAGE),),
    )


def _collect_nodes(
    model: AurumReadModelV1,
    source: SourceIdentity,
) -> tuple[tuple[EvidenceNode, ...], tuple[DependencyRelation, ...]]:
    collector = _NodeCollector(source)
    for timeframe in _TIMEFRAMES:
        structure_context_id: str | None = None
        price_context_id: str | None = None

        structure = getattr(model.structure.frames, timeframe)
        structure_parent_ids: list[str] = []
        if structure is not None and structure.available:
            if structure.last_swing is not None:
                structure_parent_ids.append(
                    _add_swing(
                        collector,
                        model,
                        timeframe,
                        structure.last_swing,
                        EvidenceNodeRole.PRIMARY,
                    )
                )
            if structure.last_bos is not None:
                structure_parent_ids.append(
                    _add_break(
                        collector,
                        model,
                        timeframe,
                        structure.last_bos,
                        EvidenceNodeRole.PRIMARY,
                    )
                )
            if structure.last_choch is not None:
                structure_parent_ids.append(
                    _add_break(
                        collector,
                        model,
                        timeframe,
                        structure.last_choch,
                        EvidenceNodeRole.PRIMARY,
                    )
                )
            if structure.latest_liquidity_sweep is not None:
                structure_parent_ids.append(
                    _add_liquidity_sweep(
                        collector,
                        model,
                        timeframe,
                        structure.latest_liquidity_sweep,
                        EvidenceNodeRole.PRIMARY,
                    )
                )
            for level in structure.tracked_liquidity_levels:
                structure_parent_ids.append(
                    _add_liquidity_level(
                        collector,
                        model,
                        timeframe,
                        level,
                        EvidenceNodeRole.PRIMARY,
                    )
                )
            if structure.protected_high is not None:
                structure_parent_ids.append(
                    _add_protected_reference(
                        collector,
                        model,
                        timeframe,
                        structure,
                        reference_role="PROTECTED_HIGH",
                        swing=structure.protected_high,
                    )
                )
            if structure.protected_low is not None:
                structure_parent_ids.append(
                    _add_protected_reference(
                        collector,
                        model,
                        timeframe,
                        structure,
                        reference_role="PROTECTED_LOW",
                        swing=structure.protected_low,
                    )
                )
            structure_payload = asdict(structure)
            for nested in (
                "last_swing",
                "last_bos",
                "last_choch",
                "protected_high",
                "protected_low",
                "latest_liquidity_sweep",
                "tracked_liquidity_levels",
            ):
                structure_payload.pop(nested, None)
            structure_frame_available = _bar_close_for_timestamp(
                model,
                timeframe,
                structure.timestamp_utc,
            )
            structure_context_available = _all_known_max(
                (
                    structure_frame_available,
                    *(
                        collector.node(item).available_at_utc
                        for item in structure_parent_ids
                    ),
                )
            )
            structure_context_id = collector.add(
                family="STRUCTURE_CONTEXT",
                kind="StructureFrameV1",
                upstream_id=_record_id(
                    "StructureFrameV1",
                    timeframe,
                    {"timestamp_utc": structure.timestamp_utc},
                ),
                timeframe=timeframe,
                direction=structure.current_trend,
                role=EvidenceNodeRole.CONTEXT_PROJECTION,
                event_time=structure.timestamp_utc,
                available_at=structure_context_available,
                payload=structure_payload,
                parents=tuple(
                    (item, DependencyEdgeType.CONTEXT_PROJECTION)
                    for item in structure_parent_ids
                ),
            )

        price_action = getattr(model.price_action.frames, timeframe)
        price_primary: list[str] = []
        if price_action is not None and price_action.available:
            if price_action.fair_value_gap is not None:
                fvg = price_action.fair_value_gap
                confirmed_at, available_at = _fvg_availability(
                    model,
                    timeframe,
                    fvg,
                )
                price_primary.append(
                    collector.add(
                        family="FAIR_VALUE_GAP",
                        kind="FairValueGapV1",
                        upstream_id=_record_id(
                            "FairValueGapV1",
                            timeframe,
                            _fvg_key(fvg),
                        ),
                        timeframe=timeframe,
                        direction=fvg.gap_type,
                        role=EvidenceNodeRole.PRIMARY,
                        event_time=fvg.timestamp_utc,
                        confirmed_at=confirmed_at,
                        available_at=available_at,
                        payload=asdict(fvg),
                    )
                )
            if price_action.order_block is not None:
                price_primary.append(
                    _add_order_block(
                        collector,
                        model,
                        timeframe,
                        price_action.order_block,
                    )
                )
            context_payload = asdict(price_action)
            context_payload.pop("fair_value_gap", None)
            context_payload.pop("order_block", None)
            price_frame_available = _bar_close_for_timestamp(
                model,
                timeframe,
                price_action.timestamp_utc,
            )
            price_context_available = _all_known_max(
                (
                    price_frame_available,
                    *(
                        collector.node(item).available_at_utc
                        for item in price_primary
                    ),
                )
            )
            price_context_id = collector.add(
                family="PRICE_ACTION_CONTEXT",
                kind="PriceActionFrameV1",
                upstream_id=_record_id(
                    "PriceActionFrameV1",
                    timeframe,
                    {"timestamp_utc": price_action.timestamp_utc},
                ),
                timeframe=timeframe,
                direction=None,
                role=EvidenceNodeRole.CONTEXT_PROJECTION,
                event_time=price_action.timestamp_utc,
                available_at=price_context_available,
                payload=context_payload,
                parents=tuple(
                    (item, DependencyEdgeType.CONTEXT_PROJECTION)
                    for item in price_primary
                ),
            )

        mtf = getattr(model.multi_timeframe.frames, timeframe)
        if mtf is not None:
            mtf_parents = tuple(
                (item, DependencyEdgeType.CONTEXT_PROJECTION)
                for item in (structure_context_id, price_context_id)
                if item is not None
            )
            mtf_frame_available = _bar_close_for_timestamp(
                model,
                timeframe,
                mtf.timestamp_utc,
            )
            mtf_available = _all_known_max(
                (
                    mtf_frame_available,
                    *(
                        collector.node(parent_id).available_at_utc
                        for parent_id, _ in mtf_parents
                    ),
                )
            )
            collector.add(
                family="MTF_CONTEXT",
                kind="MultiTimeframeFrameV1",
                upstream_id=_record_id(
                    "MultiTimeframeFrameV1",
                    timeframe,
                    {"timestamp_utc": mtf.timestamp_utc},
                ),
                timeframe=timeframe,
                direction=mtf.bias,
                role=EvidenceNodeRole.CONTEXT_PROJECTION,
                event_time=mtf.timestamp_utc,
                available_at=mtf_available,
                payload=asdict(mtf),
                parents=mtf_parents,
            )

    if model.regime.available:
        regime_payload = asdict(model.regime)
        event_time = model.regime.observation_time_utc
        collector.add(
            family="REGIME_CONTEXT",
            kind="RegimeV1",
            upstream_id=_record_id(
                "RegimeV1",
                "GLOBAL",
                {
                    "observation_time_utc": event_time,
                    "computation_time_utc": model.regime.computation_time_utc,
                },
            ),
            timeframe=None,
            direction=model.regime.primary_regime,
            role=EvidenceNodeRole.CONTEXT_PROJECTION,
            event_time=event_time,
            available_at=model.regime.computation_time_utc,
            payload=regime_payload,
        )

    return (
        tuple(
            sorted(
                collector.nodes.values(),
                key=lambda node: node.evidence_id,
            )
        ),
        tuple(
            sorted(
                collector.relations.values(),
                key=lambda relation: (
                    relation.child_evidence_id,
                    relation.parent_evidence_id,
                    relation.edge_type.value,
                ),
            )
        ),
    )


def _readiness(
    model: AurumReadModelV1,
    *,
    expected_source_symbol: str | None,
    manifests: tuple[TimeframeManifest, ...],
    quote: MarketQuoteEvidence | None,
    freshness: FreshnessEvidence,
    nodes: tuple[EvidenceNode, ...],
) -> tuple[tuple[ReadinessRecord, ...], tuple[ConflictRecord, ...]]:
    readiness: list[ReadinessRecord] = []
    conflicts: list[ConflictRecord] = []
    actual_symbol = model.market.symbol
    if expected_source_symbol is not None and actual_symbol != expected_source_symbol:
        readiness.append(
            ReadinessRecord(
                code="SOURCE_MISMATCH",
                ready=False,
                detail=f"expected {expected_source_symbol!r}, got {actual_symbol!r}",
            )
        )
        conflicts.append(
            ConflictRecord(
                code="SOURCE_MISMATCH",
                detail=(
                    "requested source symbol differs from authoritative snapshot source"
                ),
            )
        )
    spec = model.market.symbol_spec
    if spec.available and spec.name is not None and spec.name != actual_symbol:
        readiness.append(
            ReadinessRecord(
                code="SOURCE_MISMATCH",
                ready=False,
                detail=(
                    f"market symbol {actual_symbol!r} != "
                    f"symbol-spec name {spec.name!r}"
                ),
            )
        )
        conflicts.append(
            ConflictRecord(
                code="SOURCE_MISMATCH",
                detail="authoritative market and symbol-spec identities disagree",
            )
        )
    if quote is None:
        readiness.append(
            ReadinessRecord(
                code="NOT_YET_AVAILABLE",
                ready=False,
                detail="authoritative quote evidence is unavailable or incomplete",
            )
        )
    missing = tuple(
        manifest.timeframe for manifest in manifests if manifest.bar_count == 0
    )
    if missing:
        readiness.append(
            ReadinessRecord(
                code="BLOCKED_UPSTREAM",
                ready=False,
                detail=f"completed-bar evidence missing for: {', '.join(missing)}",
            )
        )
    m5 = next(manifest for manifest in manifests if manifest.timeframe == "M5")
    if m5.last_bar_time_utc != model.meta.observation_time_utc:
        readiness.append(
            ReadinessRecord(
                code="BLOCKED_UPSTREAM",
                ready=False,
                detail="latest M5 bar does not match authoritative observation frontier",
            )
        )
    unresolved = tuple(
        node.evidence_id
        for node in nodes
        if node.available_at_utc is None
        or node.status is not EvidenceStatus.AVAILABLE
    )
    if unresolved:
        readiness.append(
            ReadinessRecord(
                code="BLOCKED_UPSTREAM",
                ready=False,
                detail=(
                    "record-specific availability cannot be proven from the "
                    "authoritative projected evidence"
                ),
                evidence_ids=unresolved,
            )
        )
    if model.meta.data_mode is AurumDataMode.REAL_READ_ONLY:
        if model.meta.freshness_policy_id != AURUM_LIVE_FRESHNESS_V1:
            readiness.append(
                ReadinessRecord(
                    code="BLOCKED_UPSTREAM",
                    ready=False,
                    detail=(
                        "live snapshot does not identify the sanctioned freshness policy"
                    ),
                )
            )
        if not freshness.valid:
            readiness.append(
                ReadinessRecord(
                    code="BLOCKED_UPSTREAM",
                    ready=False,
                    detail="sanctioned upstream live freshness verdict is not valid",
                )
            )
    if not readiness:
        readiness.append(
            ReadinessRecord(
                code="READY",
                ready=True,
                detail="A1 evidence cut is complete and causally visible",
            )
        )
    return tuple(readiness), tuple(conflicts)


def build_market_evidence_snapshot(
    model: AurumReadModelV1,
    *,
    configuration_identity: str,
    source_instance_identity: str,
    expected_source_symbol: str | None = None,
) -> MarketEvidenceSnapshot:
    """Construct one immutable point-in-time evidence cut without recomputation."""
    if not configuration_identity.strip():
        raise EvidenceSnapshotContractError(
            "configuration_identity must be non-empty"
        )
    if not source_instance_identity.strip():
        raise EvidenceSnapshotContractError(
            "source_instance_identity must be non-empty"
        )
    if not model.meta.read_only:
        raise EvidenceSnapshotContractError(
            "A1 accepts read-only platform snapshots only"
        )
    if model.meta.decision_available_at_utc > model.meta.generated_at_utc:
        raise EvidenceSnapshotContractError(
            "decision availability cannot be later than snapshot generation"
        )

    source = _source_identity(model, source_instance_identity)
    freshness = _freshness(model)
    manifests = _timeframe_manifests(model, source)
    for manifest in manifests:
        if (
            manifest.last_bar_time_utc is not None
            and manifest.last_bar_time_utc > model.meta.decision_available_at_utc
        ):
            raise EvidenceSnapshotContractError(
                f"{manifest.timeframe} contains future bar evidence beyond "
                "the legal boundary"
            )
    candle_basis = {
        "symbol": model.market.symbol,
        "source_identity": source,
        "timeframes": manifests,
    }
    candle_fingerprint = fingerprint(candle_basis)
    candle_bundle = CandleBundleManifest(
        candle_bundle_id=deterministic_id("candle-bundle", candle_basis),
        candle_bundle_fingerprint=candle_fingerprint,
        symbol=model.market.symbol,
        source_identity=source,
        timeframes=manifests,
    )
    quote = _quote(model, source, freshness)
    quote_time = (
        quote.available_at_utc
        if quote is not None
        else model.meta.decision_available_at_utc
    )
    as_of = max(model.meta.decision_available_at_utc, quote_time)
    if as_of > model.meta.generated_at_utc:
        raise EvidenceSnapshotContractError(
            "evidence is not available at snapshot generation time"
        )

    try:
        nodes, relations = _collect_nodes(model, source)
        for node in nodes:
            if (
                node.available_at_utc is not None
                and node.available_at_utc > as_of
            ):
                raise FatalLineageError(f"future evidence node {node.evidence_id}")
            if node.event_time_utc is not None and node.event_time_utc > as_of:
                raise FatalLineageError(
                    f"future event time for {node.evidence_id}"
                )
        nodes, groups = classify_dependencies(nodes, relations)
    except FatalLineageError as exc:
        raise EvidenceSnapshotContractError(str(exc)) from exc

    readiness, conflicts = _readiness(
        model,
        expected_source_symbol=expected_source_symbol,
        manifests=manifests,
        quote=quote,
        freshness=freshness,
        nodes=nodes,
    )
    lineage_status = (
        LineageStatus.VALID
        if all(record.ready for record in readiness)
        else LineageStatus.NON_READY
    )
    factual_basis = {
        "schema_version": SCHEMA_VERSION,
        "symbol": model.market.symbol,
        "as_of_utc": as_of,
        "decision_available_at_utc": model.meta.decision_available_at_utc,
        "platform_commit": model.meta.backend_commit,
        "configuration_identity": configuration_identity,
        "source_identity": source,
        "quote": quote,
        "timeframe_manifests": manifests,
        "evidence_nodes": nodes,
        "dependency_relations": relations,
        "dependency_groups": groups,
        "conflicts": conflicts,
        "readiness": readiness,
        "freshness": freshness,
        "candle_bundle_fingerprint": candle_bundle.candle_bundle_fingerprint,
        "lineage_status": lineage_status,
    }
    snapshot_fingerprint = fingerprint(factual_basis)
    snapshot_id = deterministic_id("market-evidence-snapshot", factual_basis)
    return MarketEvidenceSnapshot(
        schema_version=SCHEMA_VERSION,
        snapshot_id=snapshot_id,
        snapshot_fingerprint=snapshot_fingerprint,
        symbol=model.market.symbol,
        as_of_utc=as_of,
        generated_at_utc=model.meta.generated_at_utc,
        decision_available_at_utc=model.meta.decision_available_at_utc,
        platform_commit=model.meta.backend_commit,
        configuration_identity=configuration_identity,
        source_identity=source,
        quote=quote,
        timeframe_manifests=manifests,
        evidence_nodes=nodes,
        dependency_relations=relations,
        dependency_groups=groups,
        conflicts=conflicts,
        readiness=readiness,
        freshness=freshness,
        candle_bundle_id=candle_bundle.candle_bundle_id,
        candle_bundle_fingerprint=candle_bundle.candle_bundle_fingerprint,
        macro_snapshot_id=None,
        lineage_status=lineage_status,
    )
