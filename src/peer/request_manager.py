from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class PendingRequest:
    piece_index: int
    peer_id: str
    requested_at: float


class RequestManager:
    def __init__(self, timeout: float) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")

        self._timeout = timeout
        self._lock = threading.RLock()

        self._pending: dict[int, PendingRequest] = {}

    def add(self, piece_index: int, peer_id: str) -> bool:
        with self._lock:
            if piece_index in self._pending:
                return False

            self._pending[piece_index] = PendingRequest(
                piece_index=piece_index,
                peer_id=peer_id,
                requested_at=time.monotonic(),
            )

            return True

    def get(self, piece_index: int):
        with self._lock:
            return self._pending.get(piece_index)

    def complete(self, piece_index: int):
        with self._lock:
            return self._pending.pop(piece_index, None)

    def cancel(self, piece_index: int):
        return self.complete(piece_index)

    def count(self) -> int:
        with self._lock:
            return len(self._pending)

    def pending(self):
        with self._lock:
            return list(self._pending.values())

    def for_peer(self, peer_id: str):
        with self._lock:
            return [
                request
                for request in self._pending.values()
                if request.peer_id == peer_id
            ]

    def expire(self, now: float | None = None):
        now = time.monotonic() if now is None else now

        expired = []

        with self._lock:
            for piece_index, request in list(self._pending.items()):
                if now - request.requested_at >= self._timeout:
                    expired.append(request)
                    del self._pending[piece_index]

        return expired

    def clear_peer(self, peer_id: str):
        removed = []

        with self._lock:
            for piece_index, request in list(self._pending.items()):
                if request.peer_id == peer_id:
                    removed.append(request)
                    del self._pending[piece_index]

        return removed
