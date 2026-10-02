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

    def move_peer(
        self,
        old_file_id: str | None,
        new_file_id: str,
        peer: PeerInfo,
    ) -> None:
        with self._lock:
            if old_file_id is not None and old_file_id != new_file_id:
                old_swarm = self._swarms.get(old_file_id)

                if old_swarm is not None:
                    old_swarm.discard(peer.peer_id)

                    if not old_swarm:
                        del self._swarms[old_file_id]

            self._swarms.setdefault(new_file_id, set()).add(peer.peer_id)

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
        stale_peer_ids = set()

        for peer_id in peer_ids:
            peer = self._registry.get_peer(peer_id)

            if peer is not None:
                peers.append(peer)
            else:
                stale_peer_ids.add(peer_id)

        # Remove peer IDs that no longer exist in the registry.
        if stale_peer_ids:
            with self._lock:
                swarm = self._swarms.get(file_id)

                if swarm is not None:
                    swarm.difference_update(stale_peer_ids)

                    if not swarm:
                        del self._swarms[file_id]

        return peers