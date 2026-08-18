"""Local read-only HTTP delivery for the latest published Aurum snapshot."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock, Thread

from core.aurum_presentation.live_freshness import (
    evaluate_live_snapshot_currentness,
)
from core.aurum_presentation.publication import AurumSnapshotPublication
from core.aurum_presentation.serializer import to_json

logger = logging.getLogger(__name__)

DEFAULT_AURUM_HTTP_HOST = "127.0.0.1"
DEFAULT_AURUM_HTTP_PORT = 8765
AURUM_LATEST_PATH = "/aurum/v1/latest"


def _utc_now() -> datetime:
    return datetime.now(UTC)


class _AurumThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class AurumSnapshotHttpTransport:
    """Serve the latest already-published Aurum snapshot on loopback only."""

    def __init__(
        self,
        publication: AurumSnapshotPublication,
        *,
        host: str = DEFAULT_AURUM_HTTP_HOST,
        port: int = DEFAULT_AURUM_HTTP_PORT,
        allowed_origin: str | None = None,
    ) -> None:
        if host != DEFAULT_AURUM_HTTP_HOST:
            raise ValueError(
                "Aurum HTTP transport must bind to 127.0.0.1"
            )
        if isinstance(port, bool) or not isinstance(port, int):
            raise TypeError("port must be an integer")
        if not 0 <= port <= 65535:
            raise ValueError("port must be between 0 and 65535")
        if allowed_origin is not None:
            if allowed_origin == "*":
                raise ValueError("wildcard CORS origin is not permitted")
            if not allowed_origin or allowed_origin.strip() != allowed_origin:
                raise ValueError("allowed_origin must be one exact origin")

        self._publication = publication
        self._host = host
        self._port = port
        self._allowed_origin = allowed_origin
        self._server: _AurumThreadingHTTPServer | None = None
        self._thread: Thread | None = None
        self._lifecycle_lock = Lock()

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        """Return the configured port, or the assigned port after binding to 0."""

        server = self._server
        if server is None:
            return self._port
        return int(server.server_address[1])

    def start(self) -> None:
        """Bind and start the local HTTP server."""

        with self._lifecycle_lock:
            if self._server is not None:
                return

            server = _AurumThreadingHTTPServer(
                (self._host, self._port),
                self._build_handler(),
            )
            thread = Thread(
                target=server.serve_forever,
                name="aurum-snapshot-http",
                daemon=True,
            )
            try:
                thread.start()
            except Exception:
                server.server_close()
                raise

            self._server = server
            self._thread = thread

    def stop(self) -> None:
        """Best-effort-compatible shutdown; callers may isolate any failure."""

        with self._lifecycle_lock:
            server = self._server
            thread = self._thread
            self._server = None
            self._thread = None

        if server is None:
            return

        first_error: Exception | None = None
        try:
            server.shutdown()
        # Arbitrary cleanup failures must not block best-effort shutdown.
        except Exception as exc:  # noqa: BLE001
            first_error = exc
        try:
            server.server_close()
        # Arbitrary cleanup failures must not block best-effort shutdown.
        except Exception as exc:  # noqa: BLE001
            if first_error is None:
                first_error = exc
        if thread is not None:
            thread.join(timeout=5.0)
            if thread.is_alive() and first_error is None:
                first_error = RuntimeError(
                    "Aurum HTTP server thread did not stop"
                )

        if first_error is not None:
            raise RuntimeError("Aurum HTTP transport shutdown failed") from first_error

    def _build_handler(self) -> type[BaseHTTPRequestHandler]:
        publication = self._publication
        allowed_origin = self._allowed_origin

        class AurumSnapshotRequestHandler(BaseHTTPRequestHandler):
            server_version = "AurumSnapshotHTTP/1.0"
            sys_version = ""

            def log_message(self, format: str, *args: object) -> None:
                logger.debug("Aurum HTTP: " + format, *args)

            def do_GET(self) -> None:
                if self.path != AURUM_LATEST_PATH:
                    self._send_json(
                        HTTPStatus.NOT_FOUND,
                        '{"error":"AURUM_SNAPSHOT_NOT_FOUND"}',
                    )
                    return

                try:
                    snapshot = publication.latest()
                    if snapshot is None:
                        self._send_json(
                            HTTPStatus.SERVICE_UNAVAILABLE,
                            '{"error":"AURUM_SNAPSHOT_UNAVAILABLE"}',
                        )
                        return
                    currentness = evaluate_live_snapshot_currentness(
                        snapshot,
                        now_utc=_utc_now(),
                    )
                    if not currentness.current:
                        self._send_json(
                            HTTPStatus.SERVICE_UNAVAILABLE,
                            json.dumps(
                                {
                                    "error": "AURUM_SNAPSHOT_NOT_CURRENT",
                                    "reason_code": currentness.reason_code,
                                },
                                separators=(",", ":"),
                            ),
                        )
                        return
                    payload = to_json(snapshot)
                except Exception:
                    logger.exception("Aurum HTTP snapshot request failed")
                    self._send_json(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        '{"error":"AURUM_SNAPSHOT_TRANSPORT_ERROR"}',
                    )
                    return

                self._send_json(HTTPStatus.OK, payload)

            def do_POST(self) -> None:
                self._method_not_allowed()

            def do_PUT(self) -> None:
                self._method_not_allowed()

            def do_PATCH(self) -> None:
                self._method_not_allowed()

            def do_DELETE(self) -> None:
                self._method_not_allowed()

            def do_HEAD(self) -> None:
                self._method_not_allowed()

            def _method_not_allowed(self) -> None:
                self._send_json(
                    HTTPStatus.METHOD_NOT_ALLOWED,
                    '{"error":"METHOD_NOT_ALLOWED"}',
                    allow="GET",
                )

            def _send_json(
                self,
                status: HTTPStatus,
                payload: str,
                *,
                allow: str | None = None,
            ) -> None:
                body = payload.encode("utf-8")
                try:
                    self.send_response(status.value)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(body)))
                    if allow is not None:
                        self.send_header("Allow", allow)
                    origin = self.headers.get("Origin")
                    if allowed_origin is not None and origin == allowed_origin:
                        self.send_header(
                            "Access-Control-Allow-Origin",
                            allowed_origin,
                        )
                    self.end_headers()
                    if self.command != "HEAD":
                        self.wfile.write(body)
                except OSError:
                    logger.debug(
                        "Aurum HTTP response socket closed during write",
                        exc_info=True,
                    )

        return AurumSnapshotRequestHandler
