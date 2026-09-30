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
        self._peer_files: dict[str, str] = {}
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

    def reap_stale_peers(self) -> list[str]:
        with self._lock:
            stale_peer_ids = self._registry.reap_stale_peers()

            for peer_id in stale_peer_ids:
                file_id = self._peer_files.pop(peer_id, None)

                if file_id is not None:
                    self._swarms.remove_peer(file_id, peer_id)

            return stale_peer_ids

    def _handle_announce(
        self,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        self.reap_stale_peers()

        required_fields = [
            "peer_id",
            "ip",
            "port",
            "file_id",
            "left",
            "uploaded",
            "downloaded",
            "is_seeder",
        ]

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
        left = request["left"]
        uploaded = request["uploaded"]
        downloaded = request["downloaded"]
        is_seeder = request["is_seeder"]

        if not isinstance(peer_id, str) or not peer_id.strip():
            return {"ok": False, "error": "INVALID_FIELD", "field": "peer_id"}

        if not isinstance(ip, str) or not ip.strip():
            return {"ok": False, "error": "INVALID_FIELD", "field": "ip"}

        if (
            not isinstance(port, int)
            or isinstance(port, bool)
            or not 1 <= port <= 65535
        ):
            return {
                "ok": False,
                "error": "INVALID_FIELD",
                "field": "port",
            }

        if not isinstance(file_id, str) or not file_id.strip():
            return {"ok": False, "error": "INVALID_FIELD", "field": "file_id"}

        if not isinstance(left, int) or isinstance(left, bool) or left < 0:
            return {"ok": False, "error": "INVALID_FIELD", "field": "left"}

        if not isinstance(uploaded, int) or isinstance(uploaded, bool) or uploaded < 0:
            return {"ok": False, "error": "INVALID_FIELD", "field": "uploaded"}

        if not isinstance(downloaded, int) or isinstance(downloaded, bool) or downloaded < 0:
            return {"ok": False, "error": "INVALID_FIELD", "field": "downloaded"}

        if not isinstance(is_seeder, bool):
            return {"ok": False, "error": "INVALID_FIELD", "field": "is_seeder"}

        peer = PeerInfo(
            peer_id=peer_id,
            ip=ip,
            port=port,
        )

        with self._lock:
            old_file_id = self._peer_files.get(peer_id)

            self._registry.register_peer(
                peer,
                left=left,
                uploaded=uploaded,
                downloaded=downloaded,
                is_seeder=is_seeder,
            )
            self._swarms.move_peer(
                old_file_id,
                file_id,
                peer,
            )
            self._peer_files[peer_id] = file_id

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
        self.reap_stale_peers()

        peer_id = request.get("peer_id")
        file_id = request.get("file_id")

        if (
            not isinstance(peer_id, str)
            or not peer_id.strip()
        ):
            return {
                "ok": False,
                "error": "INVALID_FIELD",
                "field": "peer_id",
            }

        if (
            not isinstance(file_id, str)
            or not file_id.strip()
        ):
            return {
                "ok": False,
                "error": "INVALID_FIELD",
                "field": "file_id",
            }

        peers = self._swarms.get_peers(file_id)
        peers = [
            peer
            for peer in peers
            if peer.peer_id != peer_id
        ]
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
        self.reap_stale_peers()

        records = self._registry.get_records()

        return {
            "ok": True,
            "type": "STATS_RESPONSE",
            "peer_count": len(records),
            "seeder_count": sum(
                1 for record in records if record.is_seeder
            ),
            "leecher_count": sum(
                1 for record in records if not record.is_seeder
            ),
            "uploaded": sum(
                record.uploaded for record in records
            ),
            "downloaded": sum(
                record.downloaded for record in records
            ),
        }