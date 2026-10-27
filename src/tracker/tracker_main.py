"""Run the PeerTorrent tracker over HTTP."""

from __future__ import annotations

import json
import argparse
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

from src.common.constants import (
    DEFAULT_TRACKER_HOST,
    DEFAULT_TRACKER_PORT,
    ENCODING,
    MAX_TRACKER_REQUEST_BYTES,
)
from src.tracker.peer_registry import PeerRegistry
from src.tracker.swarm_manager import SwarmManager
from src.tracker.tracker_server import TrackerServer


class TrackerRequestHandler(BaseHTTPRequestHandler):
    """HTTP JSON API: POST /announce, GET /peers, and GET /stats."""

    server: "TrackerHTTPServer"
    server_version = "PeerTorrentTracker/1.0"

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API name
        parsed_url = urlsplit(self.path)
        path = parsed_url.path

        if path == "/health":
            self._send_json(200, {"ok": True, "service": "peertorrent-tracker"})
            return

        if path == "/stats":
            response = self.server.tracker.handle_request({"type": "STATS"})
            self._send_json(200 if response.get("ok") else 400, response)
            return

        if path == "/peers":
            query = parse_qs(parsed_url.query, keep_blank_values=True)
            peer_id = self._single_query_value(query, "peer_id")
            file_id = self._single_query_value(query, "file_id")
            if peer_id is None or file_id is None:
                self._send_json(
                    400,
                    {
                        "ok": False,
                        "error": "MISSING_FIELD",
                        "field": "peer_id" if peer_id is None else "file_id",
                    },
                )
                return

            response = self.server.tracker.handle_request(
                {"type": "GET_PEERS", "peer_id": peer_id, "file_id": file_id}
            )
            self._send_json(200 if response.get("ok") else 400, response)
            return

        if path == "/announce":
            self._send_json(
                405,
                {"ok": False, "error": "METHOD_NOT_ALLOWED", "allow": "POST"},
                extra_headers={"Allow": "POST"},
            )
            return

        self._send_json(404, {"ok": False, "error": "NOT_FOUND"})

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API name
        path = urlsplit(self.path).path
        if path != "/announce":
            self._send_json(404, {"ok": False, "error": "NOT_FOUND"})
            return

        request = self._read_json_object()
        if request is None:
            return

        # The endpoint determines the operation; callers cannot smuggle a
        # different logical operation through the /announce route.
        request["type"] = "ANNOUNCE"
        response = self.server.tracker.handle_request(request)
        self._send_json(200 if response.get("ok") else 400, response)

    def do_PUT(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API name
        self._method_not_allowed()

    def do_DELETE(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API name
        self._method_not_allowed()

    def do_PATCH(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API name
        self._method_not_allowed()

    def _method_not_allowed(self) -> None:
        self._send_json(
            405,
            {"ok": False, "error": "METHOD_NOT_ALLOWED"},
            extra_headers={"Allow": "GET, POST"},
        )

    @staticmethod
    def _single_query_value(
        query: dict[str, list[str]], key: str
    ) -> str | None:
        values = query.get(key)
        if not values or len(values) != 1 or not values[0].strip():
            return None
        return values[0]

    def _read_json_object(self) -> dict[str, Any] | None:
        content_length = self.headers.get("Content-Length")
        if content_length is None:
            self._send_json(411, {"ok": False, "error": "CONTENT_LENGTH_REQUIRED"})
            return None

        try:
            length = int(content_length)
        except ValueError:
            self._send_json(400, {"ok": False, "error": "BAD_CONTENT_LENGTH"})
            return None

        if length < 0:
            self._send_json(400, {"ok": False, "error": "BAD_CONTENT_LENGTH"})
            return None
        if length > MAX_TRACKER_REQUEST_BYTES:
            self._send_json(413, {"ok": False, "error": "REQUEST_TOO_LARGE"})
            return None

        raw_body = self.rfile.read(length)
        if len(raw_body) != length:
            self._send_json(400, {"ok": False, "error": "INCOMPLETE_BODY"})
            return None

        try:
            payload = json.loads(raw_body.decode(ENCODING))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(400, {"ok": False, "error": "BAD_JSON"})
            return None

        if not isinstance(payload, dict):
            self._send_json(400, {"ok": False, "error": "BAD_REQUEST"})
            return None
        return payload

    def _send_json(
        self,
        status_code: int,
        payload: dict[str, Any],
        *,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        raw = json.dumps(payload, separators=(",", ":")).encode(ENCODING)
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, format_string: str, *args: Any) -> None:
        # Keep standard access logging, but make it easy to identify as HTTP.
        super().log_message(format_string, *args)


class TrackerHTTPServer(ThreadingHTTPServer):
    """Threaded HTTP server that delegates API operations to TrackerServer."""

    allow_reuse_address = True
    daemon_threads = True
    request_queue_size = 64

    def __init__(self, server_address: tuple[str, int], tracker: TrackerServer):
        self.tracker = tracker
        super().__init__(server_address, TrackerRequestHandler)


def _reap_stale_peers_loop(tracker: TrackerServer) -> None:
    while True:
        tracker.reap_stale_peers()
        time.sleep(30)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the PeerTorrent HTTP tracker.")
    parser.add_argument("--host", default=DEFAULT_TRACKER_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_TRACKER_PORT)
    args = parser.parse_args()
    registry = PeerRegistry()
    swarms = SwarmManager(registry)
    tracker = TrackerServer(registry, swarms)

    reap_thread = threading.Thread(
        target=_reap_stale_peers_loop,
        args=(tracker,),
        daemon=True,
        name="tracker-stale-peer-reaper",
    )
    reap_thread.start()

    server = TrackerHTTPServer(
        (args.host, args.port),
        tracker,
    )
    print(
        "HTTP tracker listening at "
        f"http://{args.host}:{args.port}"
    )
    print("Endpoints: POST /announce, GET /peers, GET /stats, GET /health")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nTracker shutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
