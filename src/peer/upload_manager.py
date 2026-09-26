from __future__ import annotations

from src.protocol.message import Message
from src.protocol.message_types import MessageType
from src.storage.piece_storage import PieceStorage


class UploadManager:
    """Handles requests from remote peers."""

    def __init__(
        self,
        storage: PieceStorage,
        state,
    ) -> None:
        self._storage = storage
        self._state = state

    def handle_request(self, peer, piece_index: int) -> bool:
        """
        Handle a request from another peer.

        Returns True if the piece was sent successfully.
        """

        if not isinstance(piece_index, int):
            raise ValueError("piece_index must be an integer")

        if not self._state.has_piece(piece_index):
            return False

        if not self._storage.has_piece(piece_index):
            return False

        self.send_piece(peer, piece_index)
        return True

    def send_piece(self, peer, piece_index: int) -> None:
        """Read a local piece and send it to a remote peer."""

        data = self._storage.load_piece(piece_index)

        message = Message(
            type=MessageType.PIECE,
            payload={
                "piece_index": piece_index,
                "data": data,
            },
        )

        peer.send_message(message)