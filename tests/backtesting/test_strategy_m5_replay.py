from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from core.backtesting.engine import BacktestingEngine


def _bar(minute: int):
    return SimpleNamespace(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC)
        + timedelta(minutes=minute)
    )


class _Coordinator:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def process(self, snapshot):
        self.calls.append(snapshot)
        return SimpleNamespace(snapshot=snapshot)


def _engine():
    engine = object.__new__(BacktestingEngine)
    engine._last_strategy_m5_end = 0
    engine._mtf_close_times = {
        "m5": tuple(
            datetime(2026, 1, 1, tzinfo=UTC)
            + timedelta(minutes=minute)
            for minute in (5, 10, 15)
        )
    }
    coordinator = _Coordinator()
    engine.pipeline = SimpleNamespace(multi_timeframe=coordinator)
    observed: list[tuple[object, object, object | None]] = []
    engine._observe_strategy = lambda **kwargs: observed.append(
        (
            kwargs["multi_timeframe"],
            kwargs["observation_bar"],
            kwargs.get("market_regime"),
        )
    )
    engine._strategy_mtf_snapshot = lambda **kwargs: {
        "m5_end": kwargs["m5_end"],
        "boundary": kwargs["boundary"],
    }
    return engine, coordinator, observed


def test_replays_intermediate_bars_and_defers_latest_for_pipeline_regime() -> None:
    engine, coordinator, observed = _engine()
    context = SimpleNamespace(m5_bars=(_bar(0), _bar(5), _bar(10)))

    result = engine._observe_new_strategy_m5_bars(
        context=context,
        visible_m5_end=3,
    )

    assert [call["m5_end"] for call in coordinator.calls] == [1, 2, 3]
    assert [bar for _, bar, _ in observed] == list(context.m5_bars[:2])
    assert all(regime is None for _, _, regime in observed)
    assert result.snapshot["m5_end"] == 3
    assert engine._last_strategy_m5_end == 2


def test_latest_bar_receives_exact_pipeline_regime_once() -> None:
    engine, _, observed = _engine()
    context = SimpleNamespace(m5_bars=(_bar(0), _bar(5), _bar(10)))
    mtf_result = engine._observe_new_strategy_m5_bars(
        context=context,
        visible_m5_end=3,
    )
    regime = SimpleNamespace(
        observation_timestamp=context.m5_bars[2].timestamp
    )
    pipeline_result = SimpleNamespace(regime=regime)

    engine._complete_latest_strategy_observation(
        multi_timeframe=mtf_result,
        observation_bar=context.m5_bars[2],
        pipeline_result=pipeline_result,
        visible_m5_end=3,
    )

    assert [bar for _, bar, _ in observed] == list(context.m5_bars)
    assert observed[-1][2] is regime
    assert engine._last_strategy_m5_end == 3


def test_none_pipeline_result_does_not_publish_or_advance_latest_bar() -> None:
    engine, _, observed = _engine()
    context = SimpleNamespace(m5_bars=(_bar(0), _bar(5), _bar(10)))
    mtf_result = engine._observe_new_strategy_m5_bars(
        context=context,
        visible_m5_end=3,
    )

    result = engine._complete_latest_strategy_observation(
        multi_timeframe=mtf_result,
        observation_bar=context.m5_bars[2],
        pipeline_result=None,
        visible_m5_end=3,
    )

    assert result is None
    assert [bar for _, bar, _ in observed] == list(context.m5_bars[:2])
    assert engine._last_strategy_m5_end == 2


def test_legacy_pipeline_result_without_regime_remains_compatible() -> None:
    engine, _, observed = _engine()
    context = SimpleNamespace(m5_bars=(_bar(0), _bar(5), _bar(10)))
    mtf_result = engine._observe_new_strategy_m5_bars(
        context=context,
        visible_m5_end=3,
    )

    engine._complete_latest_strategy_observation(
        multi_timeframe=mtf_result,
        observation_bar=context.m5_bars[2],
        pipeline_result=SimpleNamespace(),
        visible_m5_end=3,
    )

    assert observed[-1][2] is None
    assert engine._last_strategy_m5_end == 3


def test_does_not_observe_same_m5_bar_twice() -> None:
    engine, coordinator, observed = _engine()
    context = SimpleNamespace(m5_bars=(_bar(0), _bar(5), _bar(10)))

    mtf_result = engine._observe_new_strategy_m5_bars(
        context=context,
        visible_m5_end=3,
    )
    engine._complete_latest_strategy_observation(
        multi_timeframe=mtf_result,
        observation_bar=context.m5_bars[2],
        pipeline_result=SimpleNamespace(regime=None),
        visible_m5_end=3,
    )
    engine._observe_new_strategy_m5_bars(
        context=context,
        visible_m5_end=3,
    )

    assert [bar for _, bar, _ in observed] == list(context.m5_bars)
    assert len(coordinator.calls) == 4
    assert coordinator.calls[-1]["m5_end"] == 3


def test_incomplete_warmup_bar_is_not_replayed_with_future_facts() -> None:
    engine, coordinator, observed = _engine()
    context = SimpleNamespace(m5_bars=(_bar(0), _bar(5), _bar(10)))
    engine._strategy_mtf_snapshot = lambda **kwargs: (
        None
        if kwargs["m5_end"] < 3
        else {
            "m5_end": kwargs["m5_end"],
            "boundary": kwargs["boundary"],
        }
    )

    result = engine._observe_new_strategy_m5_bars(
        context=context,
        visible_m5_end=3,
    )

    assert [call["m5_end"] for call in coordinator.calls] == [3]
    assert observed == []
    assert result.snapshot["m5_end"] == 3
    assert engine._last_strategy_m5_end == 2


def test_rejects_backwards_visible_m5_history() -> None:
    engine, _, _ = _engine()
    engine._last_strategy_m5_end = 3
    context = SimpleNamespace(m5_bars=(_bar(0), _bar(5), _bar(10)))

    with pytest.raises(ValueError, match="moved backwards"):
        engine._observe_new_strategy_m5_bars(
            context=context,
            visible_m5_end=2,
        )
