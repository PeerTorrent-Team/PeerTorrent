from __future__ import annotations

from email.mime import message
import threading
import time

from src.network import connection
from src.protocol.message import Message
from src.protocol.message_types import MessageType
from src.storage.piece_storage import PieceStorage


class UploadManager:
    """Handles requests from remote peers."""

    def __init__(self,storage: PieceStorage,state,upload_rate_limit: int | None = None,) -> None:
        self._storage = storage
        self._state = state
        if upload_rate_limit is not None and upload_rate_limit <= 0:
         raise ValueError("upload_rate_limit must be positive")
        self._upload_rate_limit = upload_rate_limit
        self._lock = threading.RLock()
        self._uploads: dict[str, set[int]] = {}

    def handle_request(
        self,
        peer_id: str,
        connection,
        piece_index: int,
    ) -> int:
        """
        Handle a request from another peer.

        Returns the number of bytes sent for the upload, or 0 if the request
        was rejected.
        """

        if (
            not isinstance(piece_index, int)
            or isinstance(piece_index, bool)
        ):
            raise ValueError("piece_index must be an integer")

        if self._state.is_choking(peer_id):
            return 0

        if not self._state.has_piece(piece_index):
            return 0

        if not self._storage.has_piece(piece_index):
            return 0

        with self._lock:
            self._uploads.setdefault(peer_id, set()).add(piece_index)

        try:
            data = self.send_piece(connection, piece_index)
            return len(data)
        finally:
            with self._lock:
                peer_uploads = self._uploads.get(peer_id)
                if peer_uploads is not None:
                    peer_uploads.discard(piece_index)
                    if not peer_uploads:
                        self._uploads.pop(peer_id, None)

    def cancel_upload(self, peer_id: str, piece_index: int) -> None:
        with self._lock:
            peer_uploads = self._uploads.setdefault(peer_id, set())
            peer_uploads.discard(piece_index)
            if not peer_uploads:
                self._uploads.pop(peer_id, None)

    def send_piece(self, connection, piece_index) -> bytes:
     """Read a local piece and send it to a remote peer."""
     data = self._storage.load_piece(piece_index)

     # Simulate upload bandwidth limits for experiments.
     if self._upload_rate_limit is not None:
        time.sleep(len(data) / self._upload_rate_limit)

     message = Message(
        type=MessageType.PIECE,
        payload={"piece_index": piece_index, "data": data},
     )
     connection.send_message(message)
     return data