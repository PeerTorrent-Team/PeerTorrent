import threading
import time
from collections.abc import Callable

from src.common.types import PeerInfo


class PeerRecord:
    def __init__(
        self,
        peer: PeerInfo,
        *,
        last_seen: float,
        left: int = 0,
        uploaded: int = 0,
        downloaded: int = 0,
        is_seeder: bool = False,
    ):
        self.peer = peer
        self.last_seen = last_seen
        self.left = left
        self.uploaded = uploaded
        self.downloaded = downloaded
        self.is_seeder = is_seeder


class PeerRegistry:
    def __init__(
        self,
        *,
        peer_ttl: float = 90,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._peers: dict[str, PeerRecord] = {}
        self._lock = threading.RLock()
        self._peer_ttl = peer_ttl
        self._clock = clock

    def register_peer(self, peer: PeerInfo) -> None:
        now = self._clock()

        with self._lock:
            self._peers[peer.peer_id] = PeerRecord(
                peer,
                last_seen=now,
            )

    def remove_peer(self, peer_id: str) -> None:
        with self._lock:
            self._peers.pop(peer_id, None)

    def get_peer(self, peer_id: str) -> PeerInfo | None:
        with self._lock:
            record = self._peers.get(peer_id)

            if record is None:
                return None

            return record.peer

    def get_peers(self) -> list[PeerInfo]:
        with self._lock:
            return [record.peer for record in self._peers.values()]

    def reap_stale_peers(self) -> None:
        now = self._clock()

        with self._lock:
            stale_peer_ids = [
                peer_id
                for peer_id, record in self._peers.items()
                if now - record.last_seen > self._peer_ttl
            ]

            for peer_id in stale_peer_ids:
                del self._peers[peer_id]