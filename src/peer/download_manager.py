from __future__ import annotations

from typing import Any

from src.pieces.verifier import verify_piece
from src.protocol.message import Message
from src.protocol.message_types import MessageType
from src.storage.piece_storage import PieceStorage


class DownloadManager:
    """Handles downloading and processing pieces from remote peers."""

    def __init__(
        self,
        piece_manager,
        storage: PieceStorage,
        state,
    ) -> None:
        self._piece_manager = piece_manager
        self._storage = storage
        self._state = state

    def request_piece(self, connection, piece_index: int) -> None:
        """Request a specific piece from a remote peer."""

        if self._piece_manager.has_piece(piece_index):
            return
        #Creating a request message to send to the peer for the specific piece
        message = Message(
            type=MessageType.REQUEST,
            payload={
                "piece_index": piece_index,
            },
        )
        # Send request message to the peer
        connection.send_message(message)

        # Mark the piece as requested in the PeerState
        self._state.mark_requested(piece_index)

    def handle_piece(self, piece: Message | dict[str, Any]) -> bool:
        """
        Process a received PIECE message.

        Returns True when the piece is valid and successfully stored.
        Returns False when verification fails.
        """

        if isinstance(piece, Message):
            if piece.type != MessageType.PIECE:
                raise ValueError("Expected a PIECE message")

            payload = piece.payload
        elif isinstance(piece, dict):
            payload = piece
        else:
            raise TypeError("piece must be a Message or dictionary")

        if "piece_index" not in payload or "data" not in payload:
            raise ValueError(
                "PIECE message requires piece_index and data"
            )

        piece_index = payload["piece_index"]
        data = payload["data"]

        if not isinstance(piece_index, int):
            raise ValueError("piece_index must be an integer")

        if not isinstance(data, bytes):
            raise TypeError("piece data must be bytes")

        # Ignore pieces that we already have
        if self._piece_manager.has_piece(piece_index):
            self._state.clear_requested(piece_index)
            return True

        piece_info = self._piece_manager.get_piece(piece_index)

        # Verify against the expected SHA-256 hash
        valid = verify_piece(
            data,
            piece_info.expected_hash,
        )

        if not valid:
            self._state.clear_requested(piece_index)
            return False

        # Save only verified data
        self._storage.save_piece(piece_index, data)

        # Update PieceManager
        piece_info.data = data
        self._piece_manager.mark_piece_complete(piece_index)

        # Update PeerState
        self._state.add_piece(piece_index)
        self._state.clear_requested(piece_index)

        return True