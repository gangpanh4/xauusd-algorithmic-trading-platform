"""Read-only adapter from authoritative Aurum facts into A1 evidence."""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime
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


class EvidenceSnapshotContractError(ValueError):
    """Raised when one snapshot cannot be represented without contract violation."""


class _NodeCollector:
    def __init__(self, source: SourceIdentity, available_at: datetime) -> None:
        self.source = source
        self.available_at = available_at
        self.nodes: dict[str, EvidenceNode] = {}
        self.relations: dict[tuple[str, str, DependencyEdgeType], DependencyRelation] = {}

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
        parents: tuple[tuple[str, DependencyEdgeType], ...] = (),
    ) -> str:
        identity_basis = {
            "family": family,
            "kind": kind,
            "upstream_id": upstream_id,
            "timeframe": timeframe,
            "source": self.source,
        }
        evidence_id = deterministic_id("evidence", identity_basis)
        factual_basis = {
            **identity_basis,
            "direction": direction,
            "event_time": event_time,
            "available_at": self.available_at,
            "payload": payload,
        }
        evidence_fingerprint = fingerprint(factual_basis)
        edges = tuple(
            DependencyEdge(parent_evidence_id=parent_id, edge_type=edge_type)
            for parent_id, edge_type in sorted(parents, key=lambda item: (item[0], item[1].value))
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
            confirmed_at_utc=None,
            available_at_utc=self.available_at,
            source_identity=self.source,
            status=EvidenceStatus.AVAILABLE,
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
            if existing.node_role is EvidenceNodeRole.LINEAGE_ONLY and role is EvidenceNodeRole.PRIMARY:
                node = replace(node, node_role=EvidenceNodeRole.PRIMARY)
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

    def boundary(self, child_id: str, parent_ids: tuple[str, ...]) -> None:
        for parent_id in parent_ids:
            key = (child_id, parent_id, DependencyEdgeType.BOUNDARY_ONLY)
            self.relations[key] = DependencyRelation(
                child_evidence_id=child_id,
                parent_evidence_id=parent_id,
                edge_type=DependencyEdgeType.BOUNDARY_ONLY,
            )


def _source_identity(model: AurumReadModelV1) -> SourceIdentity:
    return SourceIdentity(
        repository=model.meta.backend_repository,
        platform_commit=model.meta.backend_commit,
        symbol=model.market.symbol,
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
    values = (quote.observed_at_utc, quote.bid, quote.ask, quote.mid, quote.spread_price)
    if any(value is None for value in values):
        return None
    timestamp = quote.observed_at_utc
    assert timestamp is not None
    payload = {
        "symbol": model.market.symbol,
        "timestamp_utc": timestamp,
        "bid": quote.bid,
        "ask": quote.ask,
        "mid": quote.mid,
        "spread_price": quote.spread_price,
        "source_identity": source,
    }
    return MarketQuoteEvidence(
        evidence_id=deterministic_id("quote", payload),
        evidence_fingerprint=fingerprint(payload),
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


def _record_id(kind: str, timeframe: str, value: Any) -> str:
    return deterministic_id(
        "upstream-record",
        {"kind": kind, "timeframe": timeframe, "value": value},
    )


def _add_swing(
    collector: _NodeCollector,
    timeframe: str,
    swing: Any,
    role: EvidenceNodeRole,
) -> str:
    payload = asdict(swing)
    return collector.add(
        family="STRUCTURE_SWING",
        kind="SwingV1",
        upstream_id=_record_id("SwingV1", timeframe, payload),
        timeframe=timeframe,
        direction=swing.swing_type,
        role=role,
        event_time=swing.timestamp_utc,
        payload=payload,
    )


def _add_break(
    collector: _NodeCollector,
    timeframe: str,
    event: Any,
    role: EvidenceNodeRole,
) -> str:
    swing_id = _add_swing(collector, timeframe, event.swing_point, EvidenceNodeRole.LINEAGE_ONLY)
    payload = asdict(event)
    payload.pop("swing_point", None)
    return collector.add(
        family=f"STRUCTURE_{event.break_type}",
        kind="BreakV1",
        upstream_id=_record_id("BreakV1", timeframe, asdict(event)),
        timeframe=timeframe,
        direction=event.direction,
        role=role,
        event_time=event.timestamp_utc,
        payload=payload,
        parents=((swing_id, DependencyEdgeType.CONTENT_CAUSAL),),
    )


def _add_liquidity_level(
    collector: _NodeCollector,
    timeframe: str,
    level: Any,
    role: EvidenceNodeRole,
) -> str:
    swing_id = _add_swing(collector, timeframe, level.swing_point, EvidenceNodeRole.LINEAGE_ONLY)
    payload = asdict(level)
    payload.pop("swing_point", None)
    return collector.add(
        family="LIQUIDITY_LEVEL",
        kind="LiquidityLevelV1",
        upstream_id=_record_id("LiquidityLevelV1", timeframe, asdict(level)),
        timeframe=timeframe,
        direction=level.side,
        role=role,
        event_time=level.timestamp_utc,
        payload=payload,
        parents=((swing_id, DependencyEdgeType.CONTENT_CAUSAL),),
    )


def _add_liquidity_sweep(
    collector: _NodeCollector,
    timeframe: str,
    sweep: Any,
    role: EvidenceNodeRole,
) -> str:
    level_id = _add_liquidity_level(
        collector, timeframe, sweep.liquidity_level, EvidenceNodeRole.LINEAGE_ONLY
    )
    payload = asdict(sweep)
    payload.pop("liquidity_level", None)
    return collector.add(
        family="LIQUIDITY_SWEEP",
        kind="LiquiditySweepV1",
        upstream_id=_record_id("LiquiditySweepV1", timeframe, asdict(sweep)),
        timeframe=timeframe,
        direction=sweep.liquidity_level.side,
        role=role,
        event_time=sweep.timestamp_utc,
        payload=payload,
        parents=((level_id, DependencyEdgeType.CONTENT_CAUSAL),),
    )


def _add_order_block(
    collector: _NodeCollector,
    timeframe: str,
    block: Any,
) -> str:
    origin_id = _add_swing(
        collector, timeframe, block.origin_swing, EvidenceNodeRole.LINEAGE_ONLY
    )
    break_id = _add_break(
        collector, timeframe, block.trigger_break, EvidenceNodeRole.LINEAGE_ONLY
    )
    parents: list[tuple[str, DependencyEdgeType]] = [
        (origin_id, DependencyEdgeType.CONTENT_CAUSAL),
        (break_id, DependencyEdgeType.CONTENT_CAUSAL),
    ]
    if block.trigger_liquidity is not None:
        liquidity_id = _add_liquidity_sweep(
            collector,
            timeframe,
            block.trigger_liquidity,
            EvidenceNodeRole.LINEAGE_ONLY,
        )
        parents.append((liquidity_id, DependencyEdgeType.CONTENT_CAUSAL))
    payload = asdict(block)
    payload.pop("origin_swing", None)
    payload.pop("trigger_break", None)
    payload.pop("trigger_liquidity", None)
    return collector.add(
        family="ORDER_BLOCK",
        kind="OrderBlockV1",
        upstream_id=_record_id("OrderBlockV1", timeframe, asdict(block)),
        timeframe=timeframe,
        direction=block.block_type,
        role=EvidenceNodeRole.PRIMARY,
        event_time=block.timestamp_utc,
        payload=payload,
        parents=tuple(parents),
    )


def _collect_nodes(
    model: AurumReadModelV1,
    source: SourceIdentity,
) -> tuple[tuple[EvidenceNode, ...], tuple[DependencyRelation, ...]]:
    collector = _NodeCollector(source, model.meta.decision_available_at_utc)
    for timeframe in _TIMEFRAMES:
        frame_ids: list[str] = []
        mtf = getattr(model.multi_timeframe.frames, timeframe)
        if mtf is not None:
            mtf_id = collector.add(
                family="MTF_CONTEXT",
                kind="MultiTimeframeFrameV1",
                upstream_id=_record_id("MultiTimeframeFrameV1", timeframe, asdict(mtf)),
                timeframe=timeframe,
                direction=mtf.bias,
                role=EvidenceNodeRole.CONTEXT_PROJECTION,
                event_time=mtf.timestamp_utc,
                payload=asdict(mtf),
            )
            frame_ids.append(mtf_id)

        structure = getattr(model.structure.frames, timeframe)
        structure_primary: list[str] = []
        if structure is not None and structure.available:
            if structure.last_swing is not None:
                structure_primary.append(
                    _add_swing(
                        collector, timeframe, structure.last_swing, EvidenceNodeRole.PRIMARY
                    )
                )
            if structure.last_bos is not None:
                structure_primary.append(
                    _add_break(
                        collector, timeframe, structure.last_bos, EvidenceNodeRole.PRIMARY
                    )
                )
            if structure.last_choch is not None:
                structure_primary.append(
                    _add_break(
                        collector, timeframe, structure.last_choch, EvidenceNodeRole.PRIMARY
                    )
                )
            if structure.latest_liquidity_sweep is not None:
                structure_primary.append(
                    _add_liquidity_sweep(
                        collector,
                        timeframe,
                        structure.latest_liquidity_sweep,
                        EvidenceNodeRole.PRIMARY,
                    )
                )
            for level in structure.tracked_liquidity_levels:
                structure_primary.append(
                    _add_liquidity_level(
                        collector, timeframe, level, EvidenceNodeRole.PRIMARY
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
            context_id = collector.add(
                family="STRUCTURE_CONTEXT",
                kind="StructureFrameV1",
                upstream_id=_record_id("StructureFrameV1", timeframe, structure_payload),
                timeframe=timeframe,
                direction=structure.current_trend,
                role=EvidenceNodeRole.CONTEXT_PROJECTION,
                event_time=structure.timestamp_utc,
                payload=structure_payload,
            )
            collector.boundary(context_id, tuple(structure_primary))
            frame_ids.extend(structure_primary)
            frame_ids.append(context_id)

        price_action = getattr(model.price_action.frames, timeframe)
        price_primary: list[str] = []
        if price_action is not None and price_action.available:
            if price_action.fair_value_gap is not None:
                fvg = price_action.fair_value_gap
                price_primary.append(
                    collector.add(
                        family="FAIR_VALUE_GAP",
                        kind="FairValueGapV1",
                        upstream_id=_record_id("FairValueGapV1", timeframe, asdict(fvg)),
                        timeframe=timeframe,
                        direction=fvg.gap_type,
                        role=EvidenceNodeRole.PRIMARY,
                        event_time=fvg.timestamp_utc,
                        payload=asdict(fvg),
                    )
                )
            if price_action.order_block is not None:
                price_primary.append(
                    _add_order_block(collector, timeframe, price_action.order_block)
                )
            context_payload = asdict(price_action)
            context_payload.pop("fair_value_gap", None)
            context_payload.pop("order_block", None)
            context_id = collector.add(
                family="PRICE_ACTION_CONTEXT",
                kind="PriceActionFrameV1",
                upstream_id=_record_id("PriceActionFrameV1", timeframe, context_payload),
                timeframe=timeframe,
                direction=None,
                role=EvidenceNodeRole.CONTEXT_PROJECTION,
                event_time=price_action.timestamp_utc,
                payload=context_payload,
            )
            collector.boundary(context_id, tuple(price_primary))
            frame_ids.extend(price_primary)
            frame_ids.append(context_id)

        if mtf is not None:
            collector.boundary(mtf_id, tuple(item for item in frame_ids if item != mtf_id))

    if model.regime.available:
        regime_payload = asdict(model.regime)
        event_time = model.regime.observation_time_utc
        collector.add(
            family="REGIME_CONTEXT",
            kind="RegimeV1",
            upstream_id=_record_id("RegimeV1", "GLOBAL", regime_payload),
            timeframe=None,
            direction=model.regime.primary_regime,
            role=EvidenceNodeRole.CONTEXT_PROJECTION,
            event_time=event_time,
            payload=regime_payload,
        )

    return (
        tuple(sorted(collector.nodes.values(), key=lambda node: node.evidence_id)),
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
                detail="requested source symbol differs from authoritative snapshot source",
            )
        )
    spec = model.market.symbol_spec
    if spec.available and spec.name is not None and spec.name != actual_symbol:
        readiness.append(
            ReadinessRecord(
                code="SOURCE_MISMATCH",
                ready=False,
                detail=f"market symbol {actual_symbol!r} != symbol-spec name {spec.name!r}",
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
    missing = tuple(manifest.timeframe for manifest in manifests if manifest.bar_count == 0)
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
    if model.meta.data_mode is AurumDataMode.REAL_READ_ONLY:
        if model.meta.freshness_policy_id != AURUM_LIVE_FRESHNESS_V1:
            readiness.append(
                ReadinessRecord(
                    code="BLOCKED_UPSTREAM",
                    ready=False,
                    detail="live snapshot does not identify the sanctioned freshness policy",
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
    expected_source_symbol: str | None = None,
) -> MarketEvidenceSnapshot:
    """Construct one immutable point-in-time evidence cut without recomputation."""
    if not configuration_identity.strip():
        raise EvidenceSnapshotContractError("configuration_identity must be non-empty")
    if not model.meta.read_only:
        raise EvidenceSnapshotContractError("A1 accepts read-only platform snapshots only")
    if model.meta.decision_available_at_utc > model.meta.generated_at_utc:
        raise EvidenceSnapshotContractError(
            "decision availability cannot be later than snapshot generation"
        )

    source = _source_identity(model)
    freshness = _freshness(model)
    manifests = _timeframe_manifests(model, source)
    for manifest in manifests:
        if (
            manifest.last_bar_time_utc is not None
            and manifest.last_bar_time_utc > model.meta.decision_available_at_utc
        ):
            raise EvidenceSnapshotContractError(
                f"{manifest.timeframe} contains future bar evidence beyond the legal boundary"
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
    quote_time = quote.available_at_utc if quote is not None else model.meta.decision_available_at_utc
    as_of = max(model.meta.decision_available_at_utc, quote_time)
    if as_of > model.meta.generated_at_utc:
        raise EvidenceSnapshotContractError("evidence is not available at snapshot generation time")

    try:
        nodes, relations = _collect_nodes(model, source)
        for node in nodes:
            if node.available_at_utc > as_of:
                raise FatalLineageError(f"future evidence node {node.evidence_id}")
            if node.event_time_utc is not None and node.event_time_utc > as_of:
                raise FatalLineageError(f"future event time for {node.evidence_id}")
        nodes, groups = classify_dependencies(nodes, relations)
    except FatalLineageError as exc:
        raise EvidenceSnapshotContractError(str(exc)) from exc

    readiness, conflicts = _readiness(
        model,
        expected_source_symbol=expected_source_symbol,
        manifests=manifests,
        quote=quote,
        freshness=freshness,
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
