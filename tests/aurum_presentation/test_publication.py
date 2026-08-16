from __future__ import annotations

from threading import Thread

from core.aurum_presentation.builder import AurumReadModelBuilder
from core.aurum_presentation.publication import AurumSnapshotPublication

from .conftest import make_inputs


def test_initial_latest_is_none() -> None:
    publication = AurumSnapshotPublication()
    assert publication.latest() is None


def test_publish_replaces_whole_snapshot_reference_and_preserves_ids() -> None:
    publication = AurumSnapshotPublication()
    snapshot_a = AurumReadModelBuilder.build(make_inputs(direction="BUY"))
    snapshot_b = AurumReadModelBuilder.build(make_inputs(direction="SELL"))
    ids_a = (snapshot_a.meta.snapshot_id, snapshot_a.meta.observation_id)
    ids_b = (snapshot_b.meta.snapshot_id, snapshot_b.meta.observation_id)

    publication.publish(snapshot_a)
    assert publication.latest() is snapshot_a
    assert (snapshot_a.meta.snapshot_id, snapshot_a.meta.observation_id) == ids_a

    publication.publish(snapshot_b)
    assert publication.latest() is snapshot_b
    assert (snapshot_b.meta.snapshot_id, snapshot_b.meta.observation_id) == ids_b
    assert publication.latest() is not snapshot_a


def test_publication_does_not_mutate_immutable_snapshot() -> None:
    publication = AurumSnapshotPublication()
    snapshot = AurumReadModelBuilder.build(make_inputs())
    before = snapshot

    publication.publish(snapshot)

    assert publication.latest() is before
    assert publication.latest() == snapshot


def test_simple_concurrent_publish_and_read_never_exposes_partial_value() -> None:
    publication = AurumSnapshotPublication()
    snapshot_a = AurumReadModelBuilder.build(make_inputs(direction="BUY"))
    snapshot_b = AurumReadModelBuilder.build(make_inputs(direction="SELL"))
    seen: list[object] = []

    def writer() -> None:
        for index in range(200):
            publication.publish(snapshot_a if index % 2 == 0 else snapshot_b)

    def reader() -> None:
        for _ in range(200):
            value = publication.latest()
            if value is not None:
                seen.append(value)

    threads = [Thread(target=writer), Thread(target=reader), Thread(target=reader)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert seen
    assert all(value is snapshot_a or value is snapshot_b for value in seen)
