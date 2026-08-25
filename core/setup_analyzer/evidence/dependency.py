"""Fail-closed lineage validation and dependency classification."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

from .enums import DependencyEdgeType, EvidenceNodeRole, IndependenceClass
from .identity import deterministic_id
from .models import DependencyGroup, DependencyRelation, EvidenceNode

_SUBSTANTIVE = frozenset(
    {
        DependencyEdgeType.CONTENT_CAUSAL,
        DependencyEdgeType.STATE_LINEAGE,
        DependencyEdgeType.CONTEXT_PROJECTION,
    }
)


class FatalLineageError(ValueError):
    """Raised when required lineage cannot be accepted safely."""


def _node_map(nodes: tuple[EvidenceNode, ...]) -> dict[str, EvidenceNode]:
    result: dict[str, EvidenceNode] = {}
    for node in nodes:
        existing = result.get(node.evidence_id)
        if existing is not None and existing.evidence_fingerprint != node.evidence_fingerprint:
            raise FatalLineageError(
                f"contradictory fingerprint for evidence identity {node.evidence_id}"
            )
        result[node.evidence_id] = node
    return result


def validate_lineage(
    nodes: tuple[EvidenceNode, ...],
    relations: tuple[DependencyRelation, ...],
) -> None:
    """Validate required parents, time/source causality and substantive cycles."""
    by_id = _node_map(nodes)
    graph: dict[str, list[str]] = defaultdict(list)
    for relation in relations:
        child = by_id.get(relation.child_evidence_id)
        parent = by_id.get(relation.parent_evidence_id)
        if child is None:
            raise FatalLineageError(f"dependency child absent: {relation.child_evidence_id}")
        if parent is None:
            raise FatalLineageError(f"required parent absent: {relation.parent_evidence_id}")
        if relation.edge_type not in _SUBSTANTIVE:
            continue
        if parent.available_at_utc > child.available_at_utc:
            raise FatalLineageError(
                f"illegal future parent {parent.evidence_id} for {child.evidence_id}"
            )
        if parent.source_identity != child.source_identity:
            raise FatalLineageError(
                f"source contradiction between {parent.evidence_id} and {child.evidence_id}"
            )
        graph[child.evidence_id].append(parent.evidence_id)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise FatalLineageError(f"dependency cycle at {node_id}")
        if node_id in visited:
            return
        visiting.add(node_id)
        for parent_id in graph.get(node_id, ()):
            visit(parent_id)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in by_id:
        visit(node_id)


def _roots_for(
    node_id: str,
    graph: dict[str, tuple[str, ...]],
    memo: dict[str, tuple[str, ...]],
) -> tuple[str, ...]:
    cached = memo.get(node_id)
    if cached is not None:
        return cached
    parents = graph.get(node_id, ())
    if not parents:
        result = (node_id,)
    else:
        roots: set[str] = set()
        for parent_id in parents:
            roots.update(_roots_for(parent_id, graph, memo))
        result = tuple(sorted(roots))
    memo[node_id] = result
    return result


def classify_dependencies(
    nodes: tuple[EvidenceNode, ...],
    relations: tuple[DependencyRelation, ...],
) -> tuple[tuple[EvidenceNode, ...], tuple[DependencyGroup, ...]]:
    """Attach substantive roots and provenance-only independence classes."""
    validate_lineage(nodes, relations)
    graph_build: dict[str, list[str]] = defaultdict(list)
    for relation in relations:
        if relation.edge_type in _SUBSTANTIVE:
            graph_build[relation.child_evidence_id].append(relation.parent_evidence_id)
    graph = {key: tuple(sorted(set(value))) for key, value in graph_build.items()}
    memo: dict[str, tuple[str, ...]] = {}
    roots_by_id = {node.evidence_id: _roots_for(node.evidence_id, graph, memo) for node in nodes}

    primary = [node for node in nodes if node.node_role is EvidenceNodeRole.PRIMARY]
    updated: list[EvidenceNode] = []
    for node in nodes:
        roots = roots_by_id[node.evidence_id]
        if node.node_role is EvidenceNodeRole.CONTEXT_PROJECTION:
            classification = IndependenceClass.REDUNDANT
        elif node.node_role is EvidenceNodeRole.LINEAGE_ONLY:
            classification = IndependenceClass.NOT_EVALUABLE
        else:
            peers = [
                roots_by_id[peer.evidence_id]
                for peer in primary
                if peer.evidence_id != node.evidence_id
            ]
            root_set = set(roots)
            if any(root_set == set(peer_roots) for peer_roots in peers):
                classification = IndependenceClass.REDUNDANT
            elif any(root_set.intersection(peer_roots) for peer_roots in peers):
                classification = IndependenceClass.PARTIALLY_INDEPENDENT
            else:
                classification = IndependenceClass.INDEPENDENT
        updated.append(
            replace(
                node,
                dependency_root_ids=roots,
                independence_class=classification,
            )
        )

    grouped: dict[tuple[str, ...], list[EvidenceNode]] = defaultdict(list)
    for node in updated:
        if node.node_role is EvidenceNodeRole.PRIMARY:
            grouped[node.dependency_root_ids].append(node)
    groups = tuple(
        DependencyGroup(
            group_id=deterministic_id("dependency-group", roots),
            root_evidence_ids=roots,
            member_evidence_ids=tuple(sorted(node.evidence_id for node in members)),
            independence_class=(
                IndependenceClass.REDUNDANT
                if len(members) > 1
                else members[0].independence_class
            ),
        )
        for roots, members in sorted(grouped.items())
    )
    return tuple(updated), groups
