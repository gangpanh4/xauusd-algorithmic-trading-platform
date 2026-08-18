from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

import core.platform.engine as platform_engine
from core.aurum_presentation import (
    AURUM_LIVE_FRESHNESS_V1,
    FreshnessAssessment,
    FreshnessContext,
)
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
    bars = {
        Timeframe.WEEKLY: (
            _bar(datetime(2026, 8, 3, 0, 0, tzinfo=UTC)),
        ),
        Timeframe.DAILY: (
            _bar(datetime(2026, 8, 15, 0, 0, tzinfo=UTC)),
        ),
        Timeframe.H4: (
            _bar(datetime(2026, 8, 3, 0, 0, tzinfo=UTC)),
            _bar(datetime(2026, 8, 10, 0, 0, tzinfo=UTC)),
            _bar(datetime(2026, 8, 15, 20, 0, tzinfo=UTC)),
            _bar(datetime(2026, 8, 16, 8, 0, tzinfo=UTC)),
        ),
        Timeframe.H1: (
            _bar(datetime(2026, 8, 16, 11, 0, tzinfo=UTC)),
        ),
        Timeframe.M15: (
            _bar(datetime(2026, 8, 16, 11, 45, tzinfo=UTC)),
        ),
        Timeframe.M5: (
            _bar(datetime(2026, 8, 16, 8, 0, tzinfo=UTC)),
            _bar(datetime(2026, 8, 16, 11, 0, tzinfo=UTC)),
            _bar(datetime(2026, 8, 16, 11, 45, tzinfo=UTC)),
            observation_bar,
        ),
    }
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
    quote_reader = SimpleNamespace(
        read=Mock(
            return_value=SimpleNamespace(
                timestamp_utc=observation_bar.timestamp + timedelta(minutes=5)
            )
        )
    )
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
    freshness = FreshnessAssessment(
        policy_id=AURUM_LIVE_FRESHNESS_V1,
        valid=True,
    )

    with (
        patch.object(
            platform_engine,
            "current_parity_provenance",
            return_value=SimpleNamespace(source_commit="a" * 40),
        ),
        patch.object(
            platform_engine.AurumLiveFreshnessPolicyV1,
            "evaluate",
            return_value=freshness,
        ) as evaluate_freshness,
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
    assert evaluate_freshness.call_count == 1
    assert quote_reader.read.call_count == 1
    assert inputs.freshness is freshness
    assert inputs.freshness.valid is True
    assert inputs.freshness.critical_failure is False
    assert inputs.freshness.policy_id == AURUM_LIVE_FRESHNESS_V1


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


def test_quote_failure_is_published_as_unavailable_after_trading_processing() -> None:
    engine, bars, live_result, quote_reader, publication = (
        _live_publication_case()
    )
    quote_reader.read.side_effect = RuntimeError("quote failed")
    built_snapshot = SimpleNamespace()
    original_state = engine.state
    original_mtf_result = live_result.multi_timeframe_result
    original_pipeline_result = live_result.pipeline_result

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
        TradingPlatform._try_publish_aurum_live_snapshot(
            engine=engine,
            bars_by_timeframe=bars,
            live_result=live_result,
            quote_reader=quote_reader,
            publication=publication,
        )

    assert engine.state is original_state
    assert live_result.multi_timeframe_result is original_mtf_result
    assert live_result.pipeline_result is original_pipeline_result
    assert quote_reader.read.call_count == 1
    assert build.call_count == 1
    inputs = build.call_args.args[0]
    assert inputs.quote is None
    assert inputs.freshness.policy_id == AURUM_LIVE_FRESHNESS_V1
    assert inputs.freshness.valid is False
    assert inputs.freshness.critical_failure is True
    assert inputs.freshness.reason_code == "LIVE_QUOTE_UNAVAILABLE"
    publication.publish.assert_called_once_with(built_snapshot)


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


def test_transport_receives_same_publication_instance_used_for_pass6d() -> None:
    publication = Mock()
    transport = Mock()

    with patch.object(
        platform_engine,
        "AurumSnapshotHttpTransport",
        return_value=transport,
    ) as transport_type:
        started = TradingPlatform._try_start_aurum_transport(publication)

    assert started is transport
    assert transport_type.call_count == 1
    assert transport_type.call_args.args[0] is publication
    transport.start.assert_called_once_with()

    run_live_source = inspect.getsource(TradingPlatform.run_live)
    assert run_live_source.count(
        "aurum_publication = AurumSnapshotPublication()"
    ) == 1
    assert (
        "self._try_start_aurum_transport(\n"
        "                aurum_publication\n"
        "            )"
        in run_live_source
    )
    assert "publication=aurum_publication" in run_live_source


def test_transport_startup_failure_is_isolated_from_live_processing() -> None:
    publication = Mock()
    transport = Mock()
    transport.start.side_effect = RuntimeError("bind failed")

    with patch.object(
        platform_engine,
        "AurumSnapshotHttpTransport",
        return_value=transport,
    ):
        started = TradingPlatform._try_start_aurum_transport(publication)

    assert started is None
    start_source = inspect.getsource(
        TradingPlatform._try_start_aurum_transport
    )
    stop_source = inspect.getsource(
        TradingPlatform._try_stop_aurum_transport
    )
    assert tuple(
        inspect.signature(
            TradingPlatform._try_start_aurum_transport
        ).parameters
    ) == ("publication",)
    assert tuple(
        inspect.signature(
            TradingPlatform._try_stop_aurum_transport
        ).parameters
    ) == ("transport",)
    assert "live_result" not in start_source
    assert "live_result" not in stop_source


def test_transport_shutdown_failure_is_best_effort() -> None:
    transport = Mock()
    transport.stop.side_effect = RuntimeError("shutdown failed")

    TradingPlatform._try_stop_aurum_transport(transport)

    transport.stop.assert_called_once_with()


def test_transport_lifecycle_starts_after_warmup_and_preserves_quote_reader() -> None:
    source = inspect.getsource(TradingPlatform.run_live)
    warmup_position = source.index("warmup=True")
    quote_reader_position = source.index("quote_reader = QuoteReader(")
    publication_position = source.index(
        "aurum_publication = AurumSnapshotPublication()"
    )
    transport_position = source.index("self._try_start_aurum_transport(")
    live_loop_position = source.index("while True:")

    assert (
        warmup_position
        < quote_reader_position
        < publication_position
        < transport_position
        < live_loop_position
    )
    assert source.count("quote_reader = QuoteReader(") == 1
    assert source.count("self._try_start_aurum_transport(") == 1
    assert source.count("self._try_stop_aurum_transport(") == 1


def test_pass6e_transport_adds_no_broker_or_mt5_authority() -> None:
    transport_source = inspect.getsource(
        platform_engine.AurumSnapshotHttpTransport
    )
    helper_source = inspect.getsource(
        TradingPlatform._try_start_aurum_transport
    ) + inspect.getsource(TradingPlatform._try_stop_aurum_transport)

    prohibited_tokens = (
        "order_" + "send",
        "order_" + "check",
        "positions_" + "get",
        "orders_" + "get",
        "mt5." + "initialize",
        "mt5." + "shutdown",
        "QuoteReader",
        "AurumReadModelBuilder",
    )
    for prohibited in prohibited_tokens:
        assert prohibited not in transport_source
        assert prohibited not in helper_source


def test_live_publication_uses_approved_freshness_policy() -> None:
    source = inspect.getsource(TradingPlatform._publish_aurum_live_snapshot)

    assert "LIVE_FRESHNESS_POLICY_UNAVAILABLE" not in source
    assert "AurumLiveFreshnessPolicyV1" in source
    assert "FreshnessContext" in source


def test_stale_quote_assessment_reaches_builder_without_extra_quote_read() -> None:
    engine, bars, live_result, quote_reader, publication = (
        _live_publication_case()
    )
    freshness = FreshnessAssessment(
        policy_id=AURUM_LIVE_FRESHNESS_V1,
        valid=False,
        critical_failure=True,
        reason_code="LIVE_QUOTE_STALE",
        reason="Live quote age exceeds 15 seconds.",
    )

    with (
        patch.object(
            platform_engine,
            "current_parity_provenance",
            return_value=SimpleNamespace(source_commit="a" * 40),
        ),
        patch.object(
            platform_engine.AurumLiveFreshnessPolicyV1,
            "evaluate",
            return_value=freshness,
        ),
        patch.object(
            platform_engine.AurumReadModelBuilder,
            "build",
            return_value=SimpleNamespace(),
        ) as build,
    ):
        TradingPlatform._publish_aurum_live_snapshot(
            engine=engine,
            bars_by_timeframe=bars,
            live_result=live_result,
            quote_reader=quote_reader,
            publication=publication,
        )

    assert quote_reader.read.call_count == 1
    assert build.call_args.args[0].freshness is freshness


def test_stale_m5_assessment_reaches_builder() -> None:
    engine, bars, live_result, quote_reader, publication = (
        _live_publication_case()
    )
    freshness = FreshnessAssessment(
        policy_id=AURUM_LIVE_FRESHNESS_V1,
        valid=False,
        critical_failure=True,
        reason_code="LIVE_M5_STALE",
        reason="M5 decision delay exceeds 30 seconds.",
    )

    with (
        patch.object(
            platform_engine,
            "current_parity_provenance",
            return_value=SimpleNamespace(source_commit="a" * 40),
        ),
        patch.object(
            platform_engine.AurumLiveFreshnessPolicyV1,
            "evaluate",
            return_value=freshness,
        ),
        patch.object(
            platform_engine.AurumReadModelBuilder,
            "build",
            return_value=SimpleNamespace(),
        ) as build,
    ):
        TradingPlatform._publish_aurum_live_snapshot(
            engine=engine,
            bars_by_timeframe=bars,
            live_result=live_result,
            quote_reader=quote_reader,
            publication=publication,
        )

    assert quote_reader.read.call_count == 1
    assert build.call_args.args[0].freshness is freshness


def test_freshness_context_uses_same_synchronized_bar_timestamps() -> None:
    engine, bars, live_result, quote_reader, publication = (
        _live_publication_case()
    )
    freshness = FreshnessAssessment(
        policy_id=AURUM_LIVE_FRESHNESS_V1,
        valid=True,
    )
    contexts: list[FreshnessContext] = []

    def evaluate(context: FreshnessContext) -> FreshnessAssessment:
        contexts.append(context)
        return freshness

    with (
        patch.object(
            platform_engine,
            "current_parity_provenance",
            return_value=SimpleNamespace(source_commit="a" * 40),
        ),
        patch.object(
            platform_engine.AurumLiveFreshnessPolicyV1,
            "evaluate",
            side_effect=evaluate,
        ),
        patch.object(
            platform_engine.AurumReadModelBuilder,
            "build",
            return_value=SimpleNamespace(),
        ),
    ):
        TradingPlatform._publish_aurum_live_snapshot(
            engine=engine,
            bars_by_timeframe=bars,
            live_result=live_result,
            quote_reader=quote_reader,
            publication=publication,
        )

    assert len(contexts) == 1
    context = contexts[0]
    assert context.bar_timestamps_by_timeframe == {
        timeframe: tuple(bar.timestamp for bar in timeframe_bars)
        for timeframe, timeframe_bars in bars.items()
    }
    assert context.observation_time_utc == bars[Timeframe.M5][-1].timestamp
    assert quote_reader.read.call_count == 1


def test_freshness_integration_adds_no_analysis_or_market_data_reads() -> None:
    helper_source = inspect.getsource(
        TradingPlatform._publish_aurum_live_snapshot
    )
    run_live_source = inspect.getsource(TradingPlatform.run_live)

    assert "process_multi_timeframe" not in helper_source
    assert "get_latest_closed_bar" not in helper_source
    assert "get_historical_bars" not in helper_source
    assert "MarketDataService" not in helper_source
    assert run_live_source.count("MarketDataService(") == 4
    assert "Timeframe.DAILY: MarketDataService(" not in run_live_source
    assert "Timeframe.WEEKLY: MarketDataService(" not in run_live_source


def test_freshness_integration_adds_no_mt5_lifecycle() -> None:
    helper_source = inspect.getsource(
        TradingPlatform._publish_aurum_live_snapshot
    )
    run_live_source = inspect.getsource(TradingPlatform.run_live)

    assert "mt5." not in helper_source
    assert run_live_source.count("mt5." + "initialize(") == 1
    assert run_live_source.count("mt5." + "shutdown(") == 1


def test_quote_unavailable_conversion_adds_no_second_read_or_reader() -> None:
    helper_source = inspect.getsource(
        TradingPlatform._publish_aurum_live_snapshot
    )

    assert helper_source.count("quote_reader.read()") == 1
    assert "QuoteReader(" not in helper_source
    assert "MarketDataService(" not in helper_source
    assert "process_multi_timeframe(" not in helper_source
