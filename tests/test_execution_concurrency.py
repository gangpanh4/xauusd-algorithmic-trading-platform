from __future__ import annotations

import json

import pytest

from core.live_trading.execution_concurrency import (
    ExecutionConcurrencyError,
    LocalExecutionLock,
)


def test_competing_owners_fail_closed_then_unrelated_owner_can_acquire(
    tmp_path,
) -> None:
    path = tmp_path / "broker-submission.lock"
    first = LocalExecutionLock(path, purpose="broker submission")
    contender = LocalExecutionLock(path, purpose="broker submission")

    first_owner = first.acquire()
    with pytest.raises(ExecutionConcurrencyError, match="held or stale"):
        contender.acquire()
    assert path.is_dir()

    first.release(first_owner)
    next_owner = contender.acquire()
    assert next_owner.owner_id != first_owner.owner_id
    contender.release(next_owner)
    assert not path.exists()


def test_simulated_process_crash_remains_fail_closed(tmp_path) -> None:
    path = tmp_path / "broker-submission.lock"
    crashed_process = LocalExecutionLock(path, purpose="broker submission")
    restarted_process = LocalExecutionLock(path, purpose="broker submission")

    crashed_process.acquire()

    with pytest.raises(ExecutionConcurrencyError, match="held or stale"):
        restarted_process.acquire()
    assert path.is_dir()
    assert restarted_process.owner_path.is_file()


def test_incomplete_owner_metadata_is_never_treated_as_stale_safe(
    tmp_path,
) -> None:
    path = tmp_path / "broker-submission.lock"
    path.mkdir()
    lock = LocalExecutionLock(path, purpose="broker submission")

    with pytest.raises(ExecutionConcurrencyError, match="held or stale"):
        lock.acquire()
    assert path.is_dir()
    assert not lock.owner_path.exists()


def test_changed_owner_metadata_prevents_release(tmp_path) -> None:
    path = tmp_path / "broker-submission.lock"
    lock = LocalExecutionLock(path, purpose="broker submission")
    owner = lock.acquire()
    payload = owner.to_payload()
    payload["owner_id"] = "foreign-owner"
    lock.owner_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ExecutionConcurrencyError, match="foreign or changed"):
        lock.release(owner)
    assert path.is_dir()
    assert lock.owner_path.is_file()
