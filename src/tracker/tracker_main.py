import json
import socketserver

from src.common.constants import (
    DEFAULT_TRACKER_HOST,
    DEFAULT_TRACKER_PORT,
    ENCODING,
    MAX_REQUEST_BYTES,
)
from src.tracker.peer_registry import PeerRegistry
from src.tracker.swarm_manager import SwarmManager
from src.tracker.tracker_server import TrackerServer


class TrackerRequestHandler(socketserver.StreamRequestHandler):
    tracker: TrackerServer | None = None

    def handle(self) -> None:
        raw_request = self.rfile.readline(MAX_REQUEST_BYTES + 1)

        if len(raw_request) > MAX_REQUEST_BYTES:
            self._send_response({
                "ok": False,
                "error": "REQUEST_TOO_LARGE",
            })
            return

        try:
            request = json.loads(raw_request.decode(ENCODING))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_response({
                "ok": False,
                "error": "BAD_JSON",
            })
            return

        if self.tracker is None:
            self._send_response({
                "ok": False,
                "error": "INTERNAL",
            })
            return

        response = self.tracker.handle_request(request)
        self._send_response(response)

    def _send_response(self, response: dict) -> None:
        data = json.dumps(response).encode(ENCODING)
        self.wfile.write(data + b"\n")


class TrackerTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

    def __init__(self, server_address, handler_class, tracker):
        self.tracker = tracker
        super().__init__(server_address, handler_class)

        handler_class.tracker = tracker


def main() -> None:
    registry = PeerRegistry()
    swarms = SwarmManager(registry)
    tracker = TrackerServer(registry, swarms)

    server = TrackerTCPServer(
        (DEFAULT_TRACKER_HOST, DEFAULT_TRACKER_PORT),
        TrackerRequestHandler,
        tracker,
    )

    print(
        f"Tracker listening on "
        f"{DEFAULT_TRACKER_HOST}:{DEFAULT_TRACKER_PORT}"
    )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nTracker shutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()