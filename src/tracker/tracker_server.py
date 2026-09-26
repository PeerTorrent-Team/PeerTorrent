import hashlib
import threading
from typing import Any

from src.common.constants import MAX_PEERS_RETURNED
from src.common.types import PeerInfo
from src.tracker.peer_registry import PeerRegistry
from src.tracker.swarm_manager import SwarmManager


class TrackerServer:
    def __init__(
        self,
        registry: PeerRegistry,
        swarms: SwarmManager,
    ):
        self._registry = registry
        self._swarms = swarms
        self._lock = threading.RLock()

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(request, dict):
            return {
                "ok": False,
                "error": "BAD_REQUEST",
            }

        request_type = request.get("type")

        if request_type == "ANNOUNCE":
            return self._handle_announce(request)

        if request_type == "GET_PEERS":
            return self._handle_get_peers(request)

        if request_type == "STATS":
            return self._handle_stats(request)

        return {
            "ok": False,
            "error": "UNKNOWN_TYPE",
        }

    def _handle_announce(
        self,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        required_fields = ["peer_id", "ip", "port", "file_id"]

        for field in required_fields:
            if field not in request:
                return {
                    "ok": False,
                    "error": "MISSING_FIELD",
                    "field": field,
                }

        peer_id = request["peer_id"]
        ip = request["ip"]
        port = request["port"]
        file_id = request["file_id"]

        if not isinstance(peer_id, str):
            return {"ok": False, "error": "INVALID_FIELD", "field": "peer_id"}

        if not isinstance(ip, str):
            return {"ok": False, "error": "INVALID_FIELD", "field": "ip"}

        if not isinstance(port, int):
            return {"ok": False, "error": "INVALID_FIELD", "field": "port"}

        if not isinstance(file_id, str):
            return {"ok": False, "error": "INVALID_FIELD", "field": "file_id"}

        peer = PeerInfo(
            peer_id=peer_id,
            ip=ip,
            port=port,
        )

        self._registry.register_peer(peer)
        self._swarms.add_peer(file_id, peer)

        peers = self._swarms.get_peers(file_id)

        peers = [
            discovered_peer
            for discovered_peer in peers
            if discovered_peer.peer_id != peer_id
        ]

        peers = peers[:MAX_PEERS_RETURNED]

        return {
            "ok": True,
            "type": "ANNOUNCE_RESPONSE",
            "peers": [
                {
                    "peer_id": discovered_peer.peer_id,
                    "ip": discovered_peer.ip,
                    "port": discovered_peer.port,
                }
                for discovered_peer in peers
            ],
        }

    def _handle_get_peers(
        self,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        file_id = request.get("file_id")

        if not isinstance(file_id, str):
            return {
                "ok": False,
                "error": "MISSING_FIELD",
                "field": "file_id",
            }

        peers = self._swarms.get_peers(file_id)
        peers = peers[:MAX_PEERS_RETURNED]

        return {
            "ok": True,
            "type": "GET_PEERS_RESPONSE",
            "peers": [
                {
                    "peer_id": peer.peer_id,
                    "ip": peer.ip,
                    "port": peer.port,
                }
                for peer in peers
            ],
        }

    def _handle_stats(
        self,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        peers = self._registry.get_peers()

        return {
            "ok": True,
            "type": "STATS_RESPONSE",
            "peer_count": len(peers),
        }