from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from core.market_structure.enums import TrendDirection
from core.signal_generator.detector import SignalGenerator
from core.signal_generator.models import SignalType


def _structure(*, bos=None, choch=None, bos_freshness=0.0, choch_freshness=0.0):
    return SimpleNamespace(
        last_bos=bos,
        last_choch=choch,
        bos_freshness=bos_freshness,
        choch_freshness=choch_freshness,
    )


def _event(timestamp: datetime, direction: TrendDirection):
    return SimpleNamespace(timestamp=timestamp, direction=direction)


def test_missing_structure_is_backward_compatible() -> None:
    assert SignalGenerator._structure_direction_agrees(
        candidate_signal=SignalType.BUY,
        market_structure=None,
    )


def test_expired_structure_does_not_veto() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    structure = _structure(
        choch=_event(now, TrendDirection.BEARISH),
        choch_freshness=0.0,
    )

    assert SignalGenerator._structure_direction_agrees(
        candidate_signal=SignalType.BUY,
        market_structure=structure,
    )


def test_fresh_opposing_choch_vetoes_buy() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    structure = _structure(
        choch=_event(now, TrendDirection.BEARISH),
        choch_freshness=1.0,
    )

    assert not SignalGenerator._structure_direction_agrees(
        candidate_signal=SignalType.BUY,
        market_structure=structure,
    )


def test_fresh_aligned_bos_allows_buy() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    structure = _structure(
        bos=_event(now, TrendDirection.BULLISH),
        bos_freshness=0.5,
    )

    assert SignalGenerator._structure_direction_agrees(
        candidate_signal=SignalType.BUY,
        market_structure=structure,
    )


def test_newest_active_event_is_directional_authority() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    structure = _structure(
        bos=_event(now, TrendDirection.BEARISH),
        choch=_event(now + timedelta(minutes=15), TrendDirection.BULLISH),
        bos_freshness=1.0,
        choch_freshness=1.0,
    )

    assert SignalGenerator._structure_direction_agrees(
        candidate_signal=SignalType.BUY,
        market_structure=structure,
    )
    assert not SignalGenerator._structure_direction_agrees(
        candidate_signal=SignalType.SELL,
        market_structure=structure,
    )
