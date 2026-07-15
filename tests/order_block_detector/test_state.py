"""
Unit tests for the Order Block detector state.
"""

from __future__ import annotations

from core.order_block_detector.state import (
    OrderBlockDetectorState,
)


def test_state_initializes_empty() -> None:
    """
    Newly created state should be empty.
    """

    state = OrderBlockDetectorState()

    assert state.confirmed_order_blocks == []
    assert state.active_order_blocks == []
    assert state.mitigated_order_blocks == []
    assert state.invalidated_order_blocks == []
    assert state.expired_order_blocks == []

    assert state.pending_candidates == []

    assert state.confirmed_events == []

    assert state.last_event is None

    assert state.processed_break_count == 0

    assert state.next_block_id == 1


def test_reset_restores_initial_state() -> None:
    """
    reset() should restore the initial runtime state.
    """

    state = OrderBlockDetectorState()

    state.processed_break_count = 25
    state.next_block_id = 10

    state.reset()

    assert state.confirmed_order_blocks == []
    assert state.active_order_blocks == []
    assert state.mitigated_order_blocks == []
    assert state.invalidated_order_blocks == []
    assert state.expired_order_blocks == []

    assert state.pending_candidates == []

    assert state.confirmed_events == []

    assert state.last_event is None

    assert state.processed_break_count == 0

    assert state.next_block_id == 1