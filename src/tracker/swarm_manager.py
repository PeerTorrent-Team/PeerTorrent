import threading

from src.common.types import PeerInfo
from src.tracker.peer_registry import PeerRegistry


class SwarmManager:
    def __init__(self, registry: PeerRegistry):
        self._registry = registry
        self._swarms: dict[str, set[str]] = {}
        self._lock = threading.RLock()

    def add_peer(self, file_id: str, peer: PeerInfo) -> None:
        with self._lock:
            if file_id not in self._swarms:
                self._swarms[file_id] = set()

            self._swarms[file_id].add(peer.peer_id)

    def remove_peer(self, file_id: str, peer_id: str) -> None:
        with self._lock:
            peers = self._swarms.get(file_id)

            if peers is None:
                return

            peers.discard(peer_id)

            if not peers:
                del self._swarms[file_id]

    def get_peers(self, file_id: str) -> list[PeerInfo]:
        with self._lock:
            peer_ids = set(self._swarms.get(file_id, set()))

        peers = []

        for peer_id in peer_ids:
            peer = self._registry.get_peer(peer_id)

            if peer is not None:
                peers.append(peer)

        return peers