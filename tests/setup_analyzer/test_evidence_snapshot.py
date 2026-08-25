from __future__ import annotations

import ast
import inspect
from dataclasses import replace
from datetime import timedelta

import pytest

from core.aurum_presentation import AurumReadModelBuilder
from core.setup_analyzer.evidence import adapter as adapter_module
from core.setup_analyzer.evidence.adapter import build_market_evidence_snapshot
from core.setup_analyzer.evidence.dependency import (
    FatalLineageError,
    classify_dependencies,
    validate_lineage,
)
from core.setup_analyzer.evidence.enums import (
    DependencyEdgeType,
    EvidenceNodeRole,
    EvidenceStatus,
    IndependenceClass,
)
from core.setup_analyzer.evidence.identity import deterministic_id, fingerprint
from core.setup_analyzer.evidence.models import (
    DependencyRelation,
    EvidenceNode,
    SourceIdentity,
)
from tests.aurum_presentation.conftest import T, make_inputs

_SOURCE_INSTANCE = "fixture-source"


def _model(**kwargs: object):
    return AurumReadModelBuilder.build(make_inputs(**kwargs))


def _snapshot(model=None, **kwargs: object):
    return build_market_evidence_snapshot(
        model or _model(),
        configuration_identity="cfg-v1",
        source_instance_identity=_SOURCE_INSTANCE,
        **kwargs,
    )


def _source(symbol: str = "XAUUSD") -> SourceIdentity:
    return SourceIdentity(
        "repo",
        "commit",
        symbol,
        _SOURCE_INSTANCE,
        "RESEARCH_REPLAY",
        "obs",
    )


def _node(
    name: str,
    *,
    role: EvidenceNodeRole = EvidenceNodeRole.PRIMARY,
    source: SourceIdentity | None = None,
    available_offset: int = 0,
    node_fingerprint: str | None = None,
) -> EvidenceNode:
    source = source or _source()
    evidence_id = f"e:{name}"
    return EvidenceNode(
        evidence_id=evidence_id,
        evidence_fingerprint=node_fingerprint or fingerprint((name, source)),
        evidence_family="TEST",
        upstream_record_kind="fixture",
        upstream_record_id=name,
        timeframe="M5",
        direction=None,
        node_role=role,
        event_time_utc=T,
        confirmed_at_utc=None,
        available_at_utc=T + timedelta(minutes=available_offset),
        source_identity=source,
        status=EvidenceStatus.AVAILABLE,
        freshness_status=None,
        parent_evidence_ids=(),
        dependency_root_ids=(),
        dependency_edges=(),
        independence_class=IndependenceClass.NOT_EVALUABLE,
        conflict_group_ids=(),
        payload=(("name", name),),
    )


def test_deterministic_snapshot_and_evidence_identity() -> None:
    model = _model()
    first = _snapshot(model)
    second = _snapshot(model)
    assert first.snapshot_id == second.snapshot_id
    assert first.snapshot_fingerprint == second.snapshot_fingerprint
    assert [node.evidence_id for node in first.evidence_nodes] == [
        node.evidence_id for node in second.evidence_nodes
    ]
    assert [node.evidence_fingerprint for node in first.evidence_nodes] == [
        node.evidence_fingerprint for node in second.evidence_nodes
    ]


def test_source_instance_is_part_of_deterministic_identity() -> None:
    model = _model()
    first = _snapshot(model)
    second = build_market_evidence_snapshot(
        model,
        configuration_identity="cfg-v1",
        source_instance_identity="other-terminal-history",
    )
    assert first.source_identity.source_instance_identity == _SOURCE_INSTANCE
    assert first.snapshot_fingerprint != second.snapshot_fingerprint
    assert first.candle_bundle_fingerprint != second.candle_bundle_fingerprint


def test_source_instance_identity_is_mandatory() -> None:
    with pytest.raises(ValueError, match="source_instance_identity"):
        build_market_evidence_snapshot(
            _model(),
            configuration_identity="cfg-v1",
            source_instance_identity="",
        )


def test_runtime_generated_at_does_not_contaminate_factual_identity() -> None:
    model = _model()
    later = replace(
        model,
        meta=replace(
            model.meta,
            generated_at_utc=model.meta.generated_at_utc + timedelta(seconds=1),
        ),
    )
    first = _snapshot(model)
    second = _snapshot(later)
    assert first.generated_at_utc != second.generated_at_utc
    assert first.snapshot_fingerprint == second.snapshot_fingerprint
    assert first.snapshot_id == second.snapshot_id


def test_source_identity_is_preserved_and_mismatch_fails_closed() -> None:
    snapshot = _snapshot(expected_source_symbol="XAUUSDm")
    assert snapshot.source_identity.symbol == "XAUUSD"
    assert snapshot.symbol == "XAUUSD"
    assert any(
        item.code == "SOURCE_MISMATCH" and not item.ready
        for item in snapshot.readiness
    )
    assert any(item.code == "SOURCE_MISMATCH" for item in snapshot.conflicts)


def test_available_at_is_conservative_decision_boundary_and_not_backdated() -> None:
    snapshot = _snapshot()
    assert snapshot.evidence_nodes
    assert all(
        node.available_at_utc == snapshot.decision_available_at_utc
        for node in snapshot.evidence_nodes
    )
    assert all(node.confirmed_at_utc is None for node in snapshot.evidence_nodes)
    assert all(
        node.available_at_utc <= snapshot.as_of_utc
        for node in snapshot.evidence_nodes
    )


def test_mixed_m5_frontier_remains_auditable_non_readiness() -> None:
    snapshot = _snapshot(_model(m5_time=T - timedelta(minutes=5)))
    assert any(
        item.code == "BLOCKED_UPSTREAM"
        and "M5" in item.detail
        and not item.ready
        for item in snapshot.readiness
    )


def test_same_legal_prefix_is_replay_equivalent() -> None:
    model = _model()
    snapshots = [_snapshot(model) for _ in range(3)]
    assert len({item.snapshot_fingerprint for item in snapshots}) == 1
    assert len({item.candle_bundle_fingerprint for item in snapshots}) == 1


def test_boundary_only_does_not_create_substantive_dependency_root() -> None:
    parent = _node("parent")
    child = _node("child")
    relation = DependencyRelation(
        child.evidence_id,
        parent.evidence_id,
        DependencyEdgeType.BOUNDARY_ONLY,
    )
    classified, _ = classify_dependencies((parent, child), (relation,))
    roots = {node.evidence_id: node.dependency_root_ids for node in classified}
    assert roots[child.evidence_id] == (child.evidence_id,)


def test_context_projection_and_lineage_only_are_not_independent_confluence() -> None:
    projection = _node("projection", role=EvidenceNodeRole.CONTEXT_PROJECTION)
    lineage = _node("lineage", role=EvidenceNodeRole.LINEAGE_ONLY)
    classified, _ = classify_dependencies((projection, lineage), ())
    by_id = {node.evidence_id: node for node in classified}
    assert (
        by_id[projection.evidence_id].independence_class
        is IndependenceClass.REDUNDANT
    )
    assert (
        by_id[lineage.evidence_id].independence_class
        is IndependenceClass.NOT_EVALUABLE
    )
    assert by_id[lineage.evidence_id].node_role is EvidenceNodeRole.LINEAGE_ONLY


def test_shared_substantive_root_is_redundant() -> None:
    root = _node("root", role=EvidenceNodeRole.LINEAGE_ONLY)
    first = _node("first")
    second = _node("second")
    relations = (
        DependencyRelation(
            first.evidence_id,
            root.evidence_id,
            DependencyEdgeType.CONTENT_CAUSAL,
        ),
        DependencyRelation(
            second.evidence_id,
            root.evidence_id,
            DependencyEdgeType.STATE_LINEAGE,
        ),
    )
    classified, _ = classify_dependencies((root, first, second), relations)
    primaries = [
        node for node in classified if node.node_role is EvidenceNodeRole.PRIMARY
    ]
    assert all(
        node.independence_class is IndependenceClass.REDUNDANT
        for node in primaries
    )


def test_missing_mandatory_parent_is_fatal() -> None:
    child = _node("child")
    relation = DependencyRelation(
        child.evidence_id,
        "e:missing",
        DependencyEdgeType.CONTENT_CAUSAL,
    )
    with pytest.raises(FatalLineageError, match="required parent absent"):
        validate_lineage((child,), (relation,))


def test_dependency_cycle_is_fatal() -> None:
    first = _node("first")
    second = _node("second")
    relations = (
        DependencyRelation(
            first.evidence_id,
            second.evidence_id,
            DependencyEdgeType.CONTENT_CAUSAL,
        ),
        DependencyRelation(
            second.evidence_id,
            first.evidence_id,
            DependencyEdgeType.CONTENT_CAUSAL,
        ),
    )
    with pytest.raises(FatalLineageError, match="dependency cycle"):
        validate_lineage((first, second), relations)


def test_contradictory_fingerprint_for_same_identity_is_fatal() -> None:
    first = _node("same", node_fingerprint="a")
    second = _node("same", node_fingerprint="b")
    with pytest.raises(FatalLineageError, match="contradictory fingerprint"):
        validate_lineage((first, second), ())


def test_future_parent_is_fatal() -> None:
    parent = _node("parent", available_offset=1)
    child = _node("child")
    relation = DependencyRelation(
        child.evidence_id,
        parent.evidence_id,
        DependencyEdgeType.CONTENT_CAUSAL,
    )
    with pytest.raises(FatalLineageError, match="illegal future parent"):
        validate_lineage((parent, child), (relation,))


def test_substantive_cross_source_parent_is_fatal() -> None:
    parent = _node("parent", source=_source("XAUUSDm"))
    child = _node("child", source=_source("XAUUSD"))
    relation = DependencyRelation(
        child.evidence_id,
        parent.evidence_id,
        DependencyEdgeType.CONTENT_CAUSAL,
    )
    with pytest.raises(FatalLineageError, match="source contradiction"):
        validate_lineage((parent, child), (relation,))


def test_candle_bundle_fingerprint_is_deterministic() -> None:
    model = _model()
    first = _snapshot(model)
    second = _snapshot(model)
    assert first.candle_bundle_id == second.candle_bundle_id
    assert first.candle_bundle_fingerprint == second.candle_bundle_fingerprint
    assert all(manifest.completed_only for manifest in first.timeframe_manifests)


def test_adapter_consumes_projected_facts_without_detector_recomputation() -> None:
    source = inspect.getsource(adapter_module)
    prohibited_imports = (
        "core.market_structure",
        "core.fair_value_gap_detector",
        "core.order_block_detector",
        "core.regime_detector",
        "core.multi_timeframe.models",
    )
    assert all(item not in source for item in prohibited_imports)
    snapshot = _snapshot()
    assert any(
        node.evidence_family == "STRUCTURE_BOS"
        for node in snapshot.evidence_nodes
    )
    assert any(
        node.evidence_family == "FAIR_VALUE_GAP"
        for node in snapshot.evidence_nodes
    )
    assert any(
        node.evidence_family == "ORDER_BLOCK"
        for node in snapshot.evidence_nodes
    )


def test_no_broker_mutation_or_execution_path_is_introduced() -> None:
    tree = ast.parse(inspect.getsource(adapter_module))
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.append(node.module)
    forbidden_prefixes = (
        "core.mt5_",
        "core.execution_",
        "core.live_trading",
        "core.position_manager",
    )
    assert not any(
        module.startswith(forbidden_prefixes) for module in imported_modules
    )


def test_freshness_authority_is_reused_without_threshold_duplication() -> None:
    source = inspect.getsource(adapter_module)
    assert "AURUM_LIVE_FRESHNESS_V1" in source
    assert "MAX_QUOTE_AGE_SECONDS" not in source
    assert "MAX_M5_DECISION_DELAY_SECONDS" not in source


def test_identity_canonicalization_is_order_invariant() -> None:
    assert fingerprint({"a": 1, "b": 2}) == fingerprint({"b": 2, "a": 1})
    assert deterministic_id("x", {"a": 1}) == deterministic_id("x", {"a": 1})
