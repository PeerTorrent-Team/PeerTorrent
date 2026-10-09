"""HTTP client for the PeerTorrent tracker API."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.common.constants import (
    DEFAULT_TRACKER_HOST,
    DEFAULT_TRACKER_PORT,
    ENCODING,
)


class TrackerClient:
    """Talk to the tracker over HTTP using JSON request/response bodies.

    The constructor keeps the existing ``host, port, peer_id, ip, peer_port,
    file_id`` argument order so peer startup code does not need to change.
    The tracker host should be a hostname or IP address without a URL scheme.
    """

    def __init__(
        self,
        host: str = DEFAULT_TRACKER_HOST,
        port: int = DEFAULT_TRACKER_PORT,
        peer_id: str = "",
        ip: str = "127.0.0.1",
        peer_port: int = 0,
        file_id: str = "",
        timeout: float = 5.0,
    ) -> None:
        self.host = host
        self.port = port
        self.peer_id = peer_id
        self.ip = ip
        self.peer_port = peer_port
        self.file_id = file_id
        self.timeout = timeout

    def _base_url(self) -> str:
        host = self.host.strip()
        if not host:
            raise ValueError("Tracker host must not be empty")

        # Bracket IPv6 literals when building an authority, e.g. ::1 -> [::1].
        if ":" in host and not (host.startswith("[") and host.endswith("]")):
            host = f"[{host}]"

        if not isinstance(self.port, int) or isinstance(self.port, bool):
            raise ValueError("Tracker port must be an integer")
        if not 1 <= self.port <= 65535:
            raise ValueError("Tracker port must be between 1 and 65535")

        return f"http://{host}:{self.port}"

    @staticmethod
    def _parse_response(raw: bytes) -> dict[str, Any]:
        try:
            parsed = json.loads(raw.decode(ENCODING))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Tracker returned an invalid JSON response") from exc

        if not isinstance(parsed, dict):
            raise RuntimeError("Tracker returned a non-object JSON response")
        return parsed

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        query: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        url = self._base_url() + path
        if query:
            url += "?" + urlencode(query)

        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode(ENCODING)
            headers["Content-Type"] = "application/json; charset=utf-8"

        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                parsed = self._parse_response(response.read())
        except HTTPError as exc:
            parsed = self._parse_response(exc.read())
            detail = parsed.get("error", f"HTTP_{exc.code}")
            field = parsed.get("field")
            if field:
                detail = f"{detail}: {field}"
            raise RuntimeError(str(detail)) from exc
        except (URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            raise ConnectionError(
                f"Could not contact HTTP tracker at {url}: {reason}"
            ) from exc

        if not parsed.get("ok", False):
            detail = parsed.get("error", "TRACKER_ERROR")
            field = parsed.get("field")
            if field:
                detail = f"{detail}: {field}"
            raise RuntimeError(str(detail))
        return parsed

    @staticmethod
    def _peer_list(response: dict[str, Any]) -> list[dict[str, Any]]:
        peers = response.get("peers", [])
        if not isinstance(peers, list):
            raise RuntimeError("Tracker response field 'peers' must be a list")
        return peers

    def announce(
        self,
        *,
        left: int,
        uploaded: int,
        downloaded: int,
        is_seeder: bool,
    ) -> list[dict[str, Any]]:
        response = self._request(
            "POST",
            "/announce",
            payload={
                "peer_id": self.peer_id,
                "ip": self.ip,
                "port": self.peer_port,
                "file_id": self.file_id,
                "left": left,
                "uploaded": uploaded,
                "downloaded": downloaded,
                "is_seeder": is_seeder,
            },
        )
        return self._peer_list(response)

    def get_peers(self) -> list[dict[str, Any]]:
        response = self._request(
            "GET",
            "/peers",
            query={"peer_id": self.peer_id, "file_id": self.file_id},
        )
        return self._peer_list(response)

    def get_stats(self) -> dict[str, Any]:
        """Return tracker-wide peer, seeder, leecher, and transfer counters."""
        return self._request("GET", "/stats")
