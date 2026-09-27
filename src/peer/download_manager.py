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
        request_manager=None,
    ) -> None:
        self._piece_manager = piece_manager
        self._storage = storage
        self._state = state
        self._request_manager = request_manager

    def request_piece(self, connection, piece_index: int, peer_id: str | None = None) -> None:
        """Request a specific piece from a remote peer."""

        if self._piece_manager.has_piece(piece_index):
            return

        if self._request_manager is not None:
            if not self._request_manager.add(piece_index, peer_id or "unknown"):
                return

        self._state.mark_requested(piece_index)

        message = Message(
            type=MessageType.REQUEST,
            payload={
                "piece_index": piece_index,
            },
        )

        try:
            connection.send_message(message)
        except Exception:
            if self._request_manager is not None:
                self._request_manager.cancel(piece_index)
            self._state.clear_requested(piece_index)
            raise

    def handle_piece(self, peer_id: str, piece: Message | dict[str, Any]) -> bool:
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

        if (
            not isinstance(piece_index, int)
            or isinstance(piece_index, bool)
        ):
            raise ValueError("piece_index must be an integer")

        if not isinstance(data, bytes):
            raise TypeError("piece data must be bytes")

        if self._request_manager is not None:
            pending = self._request_manager.get(piece_index)
            if pending is None or pending.peer_id != peer_id:
                return False

        if (
            not self._piece_manager.has_piece(piece_index)
            and not self._state.is_requested(piece_index)
        ):
            return False

        if self._piece_manager.has_piece(piece_index):
            if self._request_manager is not None:
                self._request_manager.complete(piece_index)
            self._state.clear_requested(piece_index)
            return True

        piece_info = self._piece_manager.get_piece(piece_index)

        if len(data) != piece_info.size:
            if self._request_manager is not None:
                self._request_manager.complete(piece_index)
            self._state.clear_requested(piece_index)
            return False

        valid = verify_piece(
            data,
            piece_info.expected_hash,
        )

        if not valid:
            if self._request_manager is not None:
                self._request_manager.complete(piece_index)
            self._state.clear_requested(piece_index)
            return False

        self._storage.save_piece(piece_index, data)

        piece_info.data = data
        self._piece_manager.mark_piece_complete(piece_index)

        self._state.add_piece(piece_index)
        if self._request_manager is not None:
            self._request_manager.complete(piece_index)
        self._state.clear_requested(piece_index)

        return True