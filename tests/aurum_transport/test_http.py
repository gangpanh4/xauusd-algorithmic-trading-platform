from __future__ import annotations

import inspect
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from http.client import HTTPConnection
from threading import Thread
from unittest.mock import Mock, patch

import pytest

import core.aurum_transport.http as transport_http
from core.aurum_presentation.enums import AurumDataMode, AurumOperatorState
from core.aurum_presentation.models import (
    AiV1,
    AurumReadModelV1,
    BarsV1,
    ConfluenceV1,
    DecisionV1,
    DiagnosticStatusV1,
    ExecutionConfigV1,
    ExecutionStateV1,
    ExecutionV1,
    FeaturesV1,
    HealthV1,
    IntelligenceDiagnosticsV1,
    MarketV1,
    MetaV1,
    MethodologyV1,
    MultiTimeframeV1,
    NewsV1,
    OperatorStateV1,
    PipelineAuditV1,
    PipelineConsistencyV1,
    PriceActionV1,
    ProbabilityV1,
    QuoteV1,
    RegimeV1,
    ResearchV1,
    RiskV1,
    SignalV1,
    StrategyV1,
    StructureV1,
    SymbolSpecificationV1,
    TimeframeMapV1,
    TradePlanV1,
    TradeQualityV1,
)
from core.aurum_presentation.publication import AurumSnapshotPublication
from core.aurum_presentation.serializer import to_json
from core.aurum_transport.http import (
    AURUM_LATEST_PATH,
    DEFAULT_AURUM_HTTP_HOST,
    DEFAULT_AURUM_HTTP_PORT,
    AurumSnapshotHttpTransport,
)

_HTTP_BASE = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)


def _snapshot(
    tag: str,
    *,
    direction: str,
    ready: bool = False,
    decision_available_at: datetime | None = None,
    quote_timestamp: datetime | None = None,
) -> AurumReadModelV1:
    timestamp = _HTTP_BASE
    decision_available = decision_available_at or timestamp
    observed_quote_at = quote_timestamp or timestamp
    frames = TimeframeMapV1(
        W1=None,
        D1=None,
        H4=None,
        H1=None,
        M15=None,
        M5=None,
    )
    unavailable = DiagnosticStatusV1(
        available=False,
        classification="UNAVAILABLE",
    )
    return AurumReadModelV1(
        meta=MetaV1(
            schema_name="AURUM_READ_MODEL_V1",
            schema_version="1",
            backend_repository="gangpanh4/xauusd-algorithmic-trading-platform",
            backend_commit="a" * 40,
            generated_at_utc=timestamp,
            data_mode=AurumDataMode.REAL_READ_ONLY,
            read_only=True,
            decision_timeframe="M5",
            observation_time_utc=timestamp,
            decision_available_at_utc=decision_available,
            snapshot_id=f"snapshot-{tag}",
            observation_id=f"observation-{tag}",
            freshness_policy_id=None,
            capabilities=(),
        ),
        market=MarketV1(
            symbol="XAUUSD",
            analysis_price=4402.0 if direction == "BUY" else 4398.0,
            analysis_timestamp_utc=timestamp,
            symbol_spec=SymbolSpecificationV1(available=False),
        ),
        quote=QuoteV1(available=True, observed_at_utc=observed_quote_at),
        bars=BarsV1(frames=frames),
        multi_timeframe=MultiTimeframeV1(
            timestamp_utc=timestamp,
            overall_bias=direction,
            overall_alignment="ALIGNED",
            confidence=0.5,
            frames=frames,
        ),
        structure=StructureV1(available=False, frames=frames),
        price_action=PriceActionV1(available=False, frames=frames),
        regime=RegimeV1(available=False),
        features=FeaturesV1(available=False),
        methodology=MethodologyV1(
            available=False,
            smc=unavailable,
            ict=unavailable,
        ),
        intelligence_diagnostics=IntelligenceDiagnosticsV1(
            available=False,
            classification="UNAVAILABLE",
        ),
        confluence=ConfluenceV1(available=False),
        probability=ProbabilityV1(available=False),
        decision=DecisionV1(available=False),
        signal=SignalV1(available=False),
        trade_quality=TradeQualityV1(available=False),
        pipeline_audit=PipelineAuditV1(available=False),
        pipeline_consistency=PipelineConsistencyV1(
            pipeline_result_approved=False,
            pipeline_audit_accepted=False,
            approval_consistent=True,
        ),
        strategy=StrategyV1(available=False),
        risk=RiskV1(available=False),
        trade_plan=TradePlanV1(
            source_present=False,
            risk_approved=False,
            geometry_valid=False,
            direction_consistent=False,
            actionable=False,
            suppression_code=f"SUPPRESSED_{tag}",
            suppression_reason=f"snapshot {tag}",
        ),
        operator_state=OperatorStateV1(
            state=(
                AurumOperatorState.READY_BUY
                if ready and direction == "BUY"
                else AurumOperatorState.READY_SELL
                if ready
                else AurumOperatorState.BLOCKED
            ),
            direction=direction if ready else None,
            ready=ready,
            blocked=not ready,
            reason_code=None if ready else f"BLOCKED_{tag}",
            reason=None if ready else f"snapshot {tag}",
            blocking_stage=None,
        ),
        execution=ExecutionV1(
            available=False,
            read_only=True,
            can_submit_order=False,
            state=ExecutionStateV1(available=False),
            config=ExecutionConfigV1(available=False),
        ),
        health=HealthV1(
            atomic_observation_valid=False,
            causal_timestamp_valid=False,
            pipeline_consistency_valid=False,
            freshness_valid=False,
            runtime_safety_valid=False,
            reason_codes=(f"HEALTH_{tag}",),
        ),
        research=ResearchV1(available=False, complete=False),
        news=NewsV1(),
        ai=AiV1(),
    )


@contextmanager
def _running_transport(
    publication: AurumSnapshotPublication,
    *,
    allowed_origin: str | None = None,
    clock: Mock | None = None,
) -> Iterator[AurumSnapshotHttpTransport]:
    transport = AurumSnapshotHttpTransport(
        publication,
        port=0,
        allowed_origin=allowed_origin,
    )
    effective_clock = clock or Mock(return_value=_HTTP_BASE)
    with patch.object(transport_http, "_utc_now", effective_clock):
        transport.start()
        try:
            yield transport
        finally:
            transport.stop()


def _request(
    transport: AurumSnapshotHttpTransport,
    *,
    path: str = AURUM_LATEST_PATH,
    method: str = "GET",
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    connection = HTTPConnection(transport.host, transport.port, timeout=2.0)
    try:
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        body = response.read()
        return response.status, dict(response.getheaders()), body
    finally:
        connection.close()


def test_no_snapshot_returns_503_transport_error() -> None:
    publication = AurumSnapshotPublication()

    with _running_transport(publication) as transport:
        status, headers, body = _request(transport)

    assert status == 503
    assert headers["Content-Type"] == "application/json"
    assert headers["Cache-Control"] == "no-store"
    assert json.loads(body) == {"error": "AURUM_SNAPSHOT_UNAVAILABLE"}
    assert publication.latest() is None


def test_published_snapshot_returns_exact_existing_serializer_representation() -> None:
    publication = AurumSnapshotPublication()
    snapshot = _snapshot("A", direction="BUY")
    publication.publish(snapshot)

    with _running_transport(publication) as transport:
        status, headers, body = _request(transport)

    assert status == 200
    assert headers["Content-Type"] == "application/json"
    assert headers["Cache-Control"] == "no-store"
    assert body.decode("utf-8") == to_json(snapshot)
    assert json.loads(body) == json.loads(to_json(snapshot))


def test_request_calls_latest_once_then_existing_serializer_with_same_snapshot() -> None:
    publication = Mock(spec=AurumSnapshotPublication)
    snapshot = _snapshot("call-path", direction="BUY")
    publication.latest.return_value = snapshot

    with (
        patch(
            "core.aurum_transport.http.to_json",
            wraps=to_json,
        ) as serializer,
        _running_transport(publication) as transport,
    ):
        status, _, body = _request(transport)

    assert status == 200
    publication.latest.assert_called_once_with()
    serializer.assert_called_once_with(snapshot)
    assert body.decode("utf-8") == to_json(snapshot)


def test_snapshot_and_observation_ids_are_preserved_exactly() -> None:
    publication = AurumSnapshotPublication()
    snapshot = _snapshot("identity", direction="BUY")
    publication.publish(snapshot)

    with _running_transport(publication) as transport:
        status, _, body = _request(transport)

    payload = json.loads(body)
    assert status == 200
    assert payload["meta"]["snapshot_id"] == snapshot.meta.snapshot_id
    assert payload["meta"]["observation_id"] == snapshot.meta.observation_id
    assert payload["meta"]["snapshot_id"] == "snapshot-identity"
    assert payload["meta"]["observation_id"] == "observation-identity"


def test_later_read_returns_whole_snapshot_b_without_domain_merge() -> None:
    publication = AurumSnapshotPublication()
    snapshot_a = _snapshot("A", direction="BUY")
    snapshot_b = _snapshot("B", direction="SELL")

    publication.publish(snapshot_a)
    with _running_transport(publication) as transport:
        status_a, _, body_a = _request(transport)
        publication.publish(snapshot_b)
        status_b, _, body_b = _request(transport)

    assert status_a == 200
    assert status_b == 200
    assert body_a.decode("utf-8") == to_json(snapshot_a)
    assert body_b.decode("utf-8") == to_json(snapshot_b)
    assert json.loads(body_b) == json.loads(to_json(snapshot_b))
    assert json.loads(body_b) != json.loads(to_json(snapshot_a))


def test_concurrent_publication_and_http_reads_never_mix_snapshots() -> None:
    publication = AurumSnapshotPublication()
    snapshot_a = _snapshot("A", direction="BUY")
    snapshot_b = _snapshot("B", direction="SELL")
    expected = {to_json(snapshot_a), to_json(snapshot_b)}
    publication.publish(snapshot_a)

    def writer() -> None:
        for index in range(300):
            publication.publish(snapshot_a if index % 2 == 0 else snapshot_b)

    with _running_transport(publication) as transport:
        writer_thread = Thread(target=writer)
        writer_thread.start()
        observed = {
            _request(transport)[2].decode("utf-8")
            for _ in range(80)
        }
        writer_thread.join()

    assert observed
    assert observed <= expected


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "HEAD"])
def test_unsupported_application_methods_do_not_mutate_publication(
    method: str,
) -> None:
    publication = AurumSnapshotPublication()
    snapshot = _snapshot("readonly", direction="BUY")
    publication.publish(snapshot)

    with _running_transport(publication) as transport:
        status, headers, _ = _request(transport, method=method)

    assert status == 405
    assert headers["Allow"] == "GET"
    assert publication.latest() is snapshot


def test_options_is_not_an_application_command_and_does_not_mutate() -> None:
    publication = AurumSnapshotPublication()
    snapshot = _snapshot("options", direction="BUY")
    publication.publish(snapshot)

    with _running_transport(publication) as transport:
        status, _, _ = _request(transport, method="OPTIONS")

    assert status == 501
    assert publication.latest() is snapshot


@pytest.mark.parametrize(
    "path",
    ["/", "/aurum/v1", "/aurum/v1/latest/", "/aurum/v1/snapshot"],
)
def test_unknown_paths_are_not_snapshot_resources(path: str) -> None:
    publication = AurumSnapshotPublication()
    publication.publish(_snapshot("path", direction="BUY"))

    with _running_transport(publication) as transport:
        status, _, body = _request(transport, path=path)

    assert status == 404
    assert json.loads(body) == {"error": "AURUM_SNAPSHOT_NOT_FOUND"}


def test_default_bind_and_port_are_local_and_stable() -> None:
    transport = AurumSnapshotHttpTransport(AurumSnapshotPublication())

    assert transport.host == DEFAULT_AURUM_HTTP_HOST == "127.0.0.1"
    assert transport.port == DEFAULT_AURUM_HTTP_PORT == 8765


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.20", "localhost"])
def test_non_exact_loopback_bind_is_rejected(host: str) -> None:
    with pytest.raises(ValueError, match="127.0.0.1"):
        AurumSnapshotHttpTransport(
            AurumSnapshotPublication(),
            host=host,
        )


def test_wildcard_cors_configuration_is_rejected() -> None:
    with pytest.raises(ValueError, match="wildcard"):
        AurumSnapshotHttpTransport(
            AurumSnapshotPublication(),
            allowed_origin="*",
        )


def test_no_cors_header_is_emitted_without_configuration() -> None:
    publication = AurumSnapshotPublication()
    publication.publish(_snapshot("cors-none", direction="BUY"))

    with _running_transport(publication) as transport:
        status, headers, _ = _request(
            transport,
            headers={"Origin": "https://frontend.example"},
        )

    assert status == 200
    assert "Access-Control-Allow-Origin" not in headers


def test_exact_configured_origin_is_emitted_only_for_exact_match() -> None:
    publication = AurumSnapshotPublication()
    publication.publish(_snapshot("cors-exact", direction="BUY"))
    allowed_origin = "https://frontend.example"

    with _running_transport(
        publication,
        allowed_origin=allowed_origin,
    ) as transport:
        matched_status, matched_headers, _ = _request(
            transport,
            headers={"Origin": allowed_origin},
        )
        unmatched_status, unmatched_headers, _ = _request(
            transport,
            headers={"Origin": "https://other.example"},
        )

    assert matched_status == 200
    assert matched_headers["Access-Control-Allow-Origin"] == allowed_origin
    assert unmatched_status == 200
    assert "Access-Control-Allow-Origin" not in unmatched_headers
    assert "Access-Control-Allow-Credentials" not in matched_headers


def test_serializer_failure_is_request_local_and_publication_remains_usable() -> None:
    publication = AurumSnapshotPublication()
    snapshot = _snapshot("failure", direction="BUY")
    publication.publish(snapshot)

    with _running_transport(publication) as transport:
        with patch(
            "core.aurum_transport.http.to_json",
            side_effect=RuntimeError("serializer failed"),
        ):
            failed_status, failed_headers, failed_body = _request(transport)

        recovered_status, recovered_headers, recovered_body = _request(transport)

    assert failed_status == 500
    assert json.loads(failed_body) == {
        "error": "AURUM_SNAPSHOT_TRANSPORT_ERROR"
    }
    assert failed_headers["Cache-Control"] == "no-store"
    assert publication.latest() is snapshot
    assert recovered_status == 200
    assert recovered_headers["Cache-Control"] == "no-store"
    assert recovered_body.decode("utf-8") == to_json(snapshot)


def test_transport_module_has_no_trading_execution_or_mt5_authority() -> None:
    source = inspect.getsource(transport_http)
    prohibited_tokens = (
        "LiveTradingEngine",
        "TradingPipeline",
        "RiskManager",
        "Meta" + "Trader5",
        "execution_" + "adapter",
        "QuoteReader",
        "AurumReadModelBuilder",
        "order_" + "send",
        "order_" + "check",
        "positions_" + "get",
        "orders_" + "get",
        "mt5." + "initialize",
        "mt5." + "shutdown",
    )

    for prohibited in prohibited_tokens:
        assert prohibited not in source


def test_same_ready_snapshot_expires_at_read_time_without_mutation() -> None:
    publication = AurumSnapshotPublication()
    snapshot = _snapshot("expiring", direction="BUY", ready=True)
    publication.publish(snapshot)
    before = to_json(snapshot)
    clock = Mock(return_value=_HTTP_BASE + timedelta(seconds=10))

    with (
        patch(
            "core.aurum_transport.http.to_json",
            wraps=to_json,
        ) as serializer,
        _running_transport(publication, clock=clock) as transport,
    ):
        current_status, current_headers, current_body = _request(transport)
        clock.return_value = _HTTP_BASE + timedelta(seconds=16)
        expired_status, expired_headers, expired_body = _request(transport)

    assert serializer.call_count == 1
    assert current_status == 200
    assert current_headers["Cache-Control"] == "no-store"
    assert current_body.decode("utf-8") == before
    assert expired_status == 503
    assert expired_headers["Cache-Control"] == "no-store"
    assert json.loads(expired_body) == {
        "error": "AURUM_SNAPSHOT_NOT_CURRENT",
        "reason_code": "LIVE_QUOTE_STALE",
    }
    assert publication.latest() is snapshot
    assert to_json(snapshot) == before
    assert snapshot.meta.snapshot_id == "snapshot-expiring"
    assert snapshot.meta.observation_id == "observation-expiring"
    assert snapshot.operator_state.state is AurumOperatorState.READY_BUY
    assert snapshot.operator_state.ready is True


def test_no_snapshot_and_expired_snapshot_503_are_distinct() -> None:
    publication = AurumSnapshotPublication()
    clock = Mock(return_value=_HTTP_BASE + timedelta(seconds=16))

    with _running_transport(publication, clock=clock) as transport:
        missing_status, _, missing_body = _request(transport)
        publication.publish(_snapshot("stale", direction="BUY"))
        expired_status, _, expired_body = _request(transport)

    assert missing_status == 503
    assert json.loads(missing_body) == {"error": "AURUM_SNAPSHOT_UNAVAILABLE"}
    assert expired_status == 503
    assert json.loads(expired_body) == {
        "error": "AURUM_SNAPSHOT_NOT_CURRENT",
        "reason_code": "LIVE_QUOTE_STALE",
    }


def test_transport_m5_currentness_boundary_uses_sanctioned_evaluator() -> None:
    publication = AurumSnapshotPublication()
    boundary_now = _HTTP_BASE + timedelta(seconds=30)
    snapshot = _snapshot(
        "m5-boundary",
        direction="BUY",
        decision_available_at=_HTTP_BASE,
        quote_timestamp=boundary_now,
    )
    publication.publish(snapshot)
    clock = Mock(return_value=boundary_now)

    with _running_transport(publication, clock=clock) as transport:
        current_status, _, _ = _request(transport)
        clock.return_value = boundary_now + timedelta(microseconds=1)
        stale_status, _, stale_body = _request(transport)

    assert current_status == 200
    assert stale_status == 503
    assert json.loads(stale_body) == {
        "error": "AURUM_SNAPSHOT_NOT_CURRENT",
        "reason_code": "LIVE_M5_STALE",
    }


def test_http_uses_currentness_helper_without_threshold_ownership() -> None:
    source = inspect.getsource(transport_http)

    assert "evaluate_live_snapshot_currentness" in source
    assert "MAX_QUOTE_AGE_SECONDS" not in source
    assert "MAX_M5_DECISION_DELAY_SECONDS" not in source
    assert "15.0" not in source
    assert "30.0" not in source
