from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

import core.platform.engine as platform_engine
from core.data.models import MarketBar
from core.live_trading.config import LiveTradingConfig
from core.live_trading.engine import LiveTradingEngine
from core.live_trading.models import LiveTradingResult
from core.multi_timeframe.enums import Timeframe
from core.platform.engine import TradingPlatform


def _bar(timestamp: datetime | None = None) -> MarketBar:
    return MarketBar(
        timestamp=timestamp or datetime(2026, 8, 16, 12, 0, tzinfo=UTC),
        open=4400.0,
        high=4405.0,
        low=4398.0,
        close=4402.0,
        tick_volume=100,
    )


def _live_publication_case() -> tuple[
    SimpleNamespace,
    dict[Timeframe, tuple[MarketBar, ...]],
    LiveTradingResult,
    SimpleNamespace,
    Mock,
]:
    observation_bar = _bar()
    bars = {Timeframe.M5: (observation_bar,)}
    mtf_result = SimpleNamespace(
        m5=SimpleNamespace(
            timestamp=observation_bar.timestamp,
            market_structure=SimpleNamespace(),
        )
    )
    pipeline_result = SimpleNamespace()
    audit = SimpleNamespace(timestamp=observation_bar.timestamp)
    risk_state = SimpleNamespace(
        emergency_stop=False,
        daily_loss_limit_hit=False,
    )
    config = SimpleNamespace(symbol="XAUUSD")
    pipeline = SimpleNamespace(
        config=SimpleNamespace(),
        last_observation_audit=audit,
        risk_manager=SimpleNamespace(state=risk_state),
    )
    live_state = SimpleNamespace(marker="unchanged")
    engine = SimpleNamespace(
        config=config,
        pipeline=pipeline,
        state=live_state,
    )
    live_result = LiveTradingResult(
        pipeline_result=pipeline_result,
        execution_result=None,
        trade_executed=False,
        multi_timeframe_result=mtf_result,
    )
    quote_reader = SimpleNamespace(read=Mock(return_value=SimpleNamespace()))
    publication = Mock()
    return engine, bars, live_result, quote_reader, publication


def test_process_multi_timeframe_reuses_exact_existing_mtf_result() -> None:
    engine = LiveTradingEngine(LiveTradingConfig())
    bar = _bar()
    bars = {Timeframe.M5: (bar,)}
    mtf_result = SimpleNamespace(
        m5=SimpleNamespace(
            timestamp=bar.timestamp,
            market_structure=SimpleNamespace(),
        )
    )
    pipeline_result = SimpleNamespace()
    finalized = LiveTradingResult(
        pipeline_result=pipeline_result,
        execution_result=None,
        trade_executed=False,
    )

    engine.pipeline.multi_timeframe.process = Mock(return_value=mtf_result)
    engine.pipeline.confluence_engine.evaluate_multi_timeframe = Mock(
        return_value=None
    )
    engine.pipeline.process_bar = Mock(return_value=pipeline_result)
    engine._finalize_observation = Mock(return_value=finalized)

    result = engine.process_multi_timeframe(
        bars,
        account_balance=1000.0,
        stop_loss_distance=1.0,
        pip_value=1.0,
    )

    assert engine.pipeline.multi_timeframe.process.call_count == 1
    assert result.multi_timeframe_result is mtf_result
    assert (
        engine.pipeline.process_bar.call_args.kwargs[
            "multi_timeframe_result"
        ]
        is mtf_result
    )


def test_publication_uses_same_observation_objects_without_mutation() -> None:
    engine, bars, live_result, quote_reader, publication = (
        _live_publication_case()
    )
    built_snapshot = SimpleNamespace()
    original_state = engine.state
    original_risk_state = engine.pipeline.risk_manager.state
    original_config = engine.config

    with (
        patch.object(
            platform_engine,
            "current_parity_provenance",
            return_value=SimpleNamespace(source_commit="a" * 40),
        ),
        patch.object(
            platform_engine.AurumReadModelBuilder,
            "build",
            return_value=built_snapshot,
        ) as build,
    ):
        TradingPlatform._publish_aurum_live_snapshot(
            engine=engine,
            bars_by_timeframe=bars,
            live_result=live_result,
            quote_reader=quote_reader,
            publication=publication,
        )

    assert build.call_count == 1
    assert publication.publish.call_count == 1
    assert publication.publish.call_args.args == (built_snapshot,)
    inputs = build.call_args.args[0]
    assert inputs.multi_timeframe_result is live_result.multi_timeframe_result
    assert inputs.pipeline_result is live_result.pipeline_result
    assert inputs.pipeline_audit is engine.pipeline.last_observation_audit
    assert inputs.risk_state is original_risk_state
    assert inputs.live_state is original_state
    assert inputs.live_config is original_config
    assert engine.state is original_state
    assert engine.pipeline.risk_manager.state is original_risk_state
    assert engine.config is original_config
    assert inputs.freshness.valid is False
    assert inputs.freshness.critical_failure is True
    assert (
        inputs.freshness.reason_code
        == "LIVE_FRESHNESS_POLICY_UNAVAILABLE"
    )


def test_mtf_timestamp_mismatch_fails_before_quote_or_publication() -> None:
    engine, bars, live_result, quote_reader, publication = (
        _live_publication_case()
    )
    live_result.multi_timeframe_result.m5.timestamp = (
        bars[Timeframe.M5][-1].timestamp - timedelta(minutes=5)
    )

    with patch.object(
        platform_engine.AurumReadModelBuilder,
        "build",
    ) as build:
        try:
            TradingPlatform._publish_aurum_live_snapshot(
                engine=engine,
                bars_by_timeframe=bars,
                live_result=live_result,
                quote_reader=quote_reader,
                publication=publication,
            )
        except RuntimeError as exc:
            assert "MTF result" in str(exc)
        else:
            raise AssertionError("Expected same-observation MTF guard failure.")

    quote_reader.read.assert_not_called()
    build.assert_not_called()
    publication.publish.assert_not_called()


def test_audit_timestamp_mismatch_fails_before_quote_or_publication() -> None:
    engine, bars, live_result, quote_reader, publication = (
        _live_publication_case()
    )
    engine.pipeline.last_observation_audit.timestamp = (
        bars[Timeframe.M5][-1].timestamp - timedelta(minutes=5)
    )

    with patch.object(
        platform_engine.AurumReadModelBuilder,
        "build",
    ) as build:
        try:
            TradingPlatform._publish_aurum_live_snapshot(
                engine=engine,
                bars_by_timeframe=bars,
                live_result=live_result,
                quote_reader=quote_reader,
                publication=publication,
            )
        except RuntimeError as exc:
            assert "pipeline audit" in str(exc)
        else:
            raise AssertionError("Expected same-observation audit guard failure.")

    quote_reader.read.assert_not_called()
    build.assert_not_called()
    publication.publish.assert_not_called()


def test_warmup_has_no_aurum_publication_call_site() -> None:
    source = inspect.getsource(TradingPlatform.run_live)
    warmup_position = source.index("warmup=True")
    publication_position = source.index(
        "self._try_publish_aurum_live_snapshot("
    )

    assert source.count("self._try_publish_aurum_live_snapshot(") == 1
    assert publication_position > warmup_position


def test_quote_failure_is_isolated_after_trading_processing() -> None:
    engine, bars, live_result, quote_reader, publication = (
        _live_publication_case()
    )
    quote_reader.read.side_effect = RuntimeError("quote failed")
    original_state = engine.state

    TradingPlatform._try_publish_aurum_live_snapshot(
        engine=engine,
        bars_by_timeframe=bars,
        live_result=live_result,
        quote_reader=quote_reader,
        publication=publication,
    )

    assert engine.state is original_state
    publication.publish.assert_not_called()


def test_builder_failure_is_isolated_after_trading_processing() -> None:
    engine, bars, live_result, quote_reader, publication = (
        _live_publication_case()
    )
    original_state = engine.state

    with (
        patch.object(
            platform_engine,
            "current_parity_provenance",
            return_value=SimpleNamespace(source_commit="a" * 40),
        ),
        patch.object(
            platform_engine.AurumReadModelBuilder,
            "build",
            side_effect=RuntimeError("builder failed"),
        ),
    ):
        TradingPlatform._try_publish_aurum_live_snapshot(
            engine=engine,
            bars_by_timeframe=bars,
            live_result=live_result,
            quote_reader=quote_reader,
            publication=publication,
        )

    assert engine.state is original_state
    publication.publish.assert_not_called()


def test_publication_failure_is_isolated_after_trading_processing() -> None:
    engine, bars, live_result, quote_reader, publication = (
        _live_publication_case()
    )
    publication.publish.side_effect = RuntimeError("publication failed")
    original_state = engine.state

    with (
        patch.object(
            platform_engine,
            "current_parity_provenance",
            return_value=SimpleNamespace(source_commit="a" * 40),
        ),
        patch.object(
            platform_engine.AurumReadModelBuilder,
            "build",
            return_value=SimpleNamespace(),
        ),
    ):
        TradingPlatform._try_publish_aurum_live_snapshot(
            engine=engine,
            bars_by_timeframe=bars,
            live_result=live_result,
            quote_reader=quote_reader,
            publication=publication,
        )

    assert engine.state is original_state
    assert publication.publish.call_count == 1


def test_pass6d_adds_no_broker_mutation_or_mt5_lifecycle_calls() -> None:
    helper_source = inspect.getsource(
        TradingPlatform._publish_aurum_live_snapshot
    ) + inspect.getsource(TradingPlatform._try_publish_aurum_live_snapshot)
    process_source = inspect.getsource(
        LiveTradingEngine.process_multi_timeframe
    )
    run_live_source = inspect.getsource(TradingPlatform.run_live)

    prohibited_tokens = (
        "order_" + "send",
        "order_" + "check",
        "positions_" + "get",
        "orders_" + "get",
        "mt5." + "initialize",
        "mt5." + "shutdown",
    )
    for prohibited in prohibited_tokens:
        assert prohibited not in helper_source
        assert prohibited not in process_source

    assert run_live_source.count("mt5." + "initialize(") == 1
    assert run_live_source.count("mt5." + "shutdown(") == 1
