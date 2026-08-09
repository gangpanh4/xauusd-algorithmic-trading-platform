from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.platform import engine as platform_engine


def test_platform_backtest_uses_pinned_profile_without_live_spec_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(platform_engine.mt5, "initialize", lambda: True)
    monkeypatch.setattr(
        platform_engine.mt5,
        "shutdown",
        lambda: captured.setdefault("shutdown", True),
    )
    monkeypatch.setattr(
        platform_engine,
        "get_live_symbol_specification",
        lambda symbol: pytest.fail(
            "historical backtest must not fetch current symbol metadata"
        ),
    )

    class Runner:
        def __init__(self, config) -> None:
            captured["config"] = config

        def run(self, **kwargs):
            captured["run"] = kwargs
            return SimpleNamespace()

        def generate_reports(self, result) -> None:
            captured["reports"] = result

    monkeypatch.setattr(platform_engine, "BacktestRunner", Runner)

    platform = platform_engine.TradingPlatform()
    platform.initialize()
    platform.run_backtest()

    config = captured["config"]
    profile = config.resolved_execution_profile()
    assert config.execution_profile is profile
    assert profile.instrument.symbol == "XAUUSD"
    assert profile.instrument.historical_specification_verified is False
    assert profile.instrument.contract_size is None
    assert captured["run"] == {
        "symbol": "XAUUSD",
        "timeframe": platform_engine.mt5.TIMEFRAME_M5,
        "bars": 50000,
    }
    assert captured["shutdown"] is True
