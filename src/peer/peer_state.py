from __future__ import annotations

import threading


class PeerState:
    """Stores the runtime state of a local PeerTorrent peer."""

    def __init__(self, total_pieces: int) -> None:
        if total_pieces < 0:
            raise ValueError("total_pieces must be non-negative")

        self._lock = threading.RLock()

        self.total_pieces = total_pieces

        # Pieces owned by the local peer
        self._owned_pieces: set[int] = set()

        # Pieces currently being requested from other peers
        self._requested_pieces: set[int] = set()

        # Peer availability:peer_id, set of piece indices
        self._peer_pieces: dict[str, set[int]] = {}

        # Connection state
        self._connected_peers: set[str] = set()

        # Choking state
        self._choked_by: dict[str, bool] = {}

    # Local piece state
    # Updating that new piece is added 
    def add_piece(self, piece_index: int) -> None:
        self._validate_piece_index(piece_index)

        with self._lock:
            self._owned_pieces.add(piece_index)
            self._requested_pieces.discard(piece_index)

    # Checking if piece is already owned
    def has_piece(self, piece_index: int) -> bool:
        self._validate_piece_index(piece_index)

        with self._lock:
            return piece_index in self._owned_pieces

    #Returns pieces owned by the local peer
    def get_owned_pieces(self) -> list[int]:
        with self._lock:
            return sorted(self._owned_pieces)

    # Returns pieces that are not owned by the local peer
    def get_missing_pieces(self) -> list[int]:
        with self._lock:
            return [
                index
                for index in range(self.total_pieces)
                if index not in self._owned_pieces
            ]

    # Returns True if the local peer has all pieces
    def is_complete(self) -> bool:
        with self._lock:
            return len(self._owned_pieces) == self.total_pieces

    # Requested pieces
    # Marking a piece as being requested currently
    def mark_requested(self, piece_index: int) -> None:
        self._validate_piece_index(piece_index)

        with self._lock:
            self._requested_pieces.add(piece_index)

    # Clearing request of a piece once acquired
    def clear_requested(self, piece_index: int) -> None:
        self._validate_piece_index(piece_index)

        with self._lock:
            self._requested_pieces.discard(piece_index)

    #Checking to prevent duplicate requests for the same piece from multiple peers
    def is_requested(self, piece_index: int) -> bool:
        self._validate_piece_index(piece_index)

        with self._lock:
            return piece_index in self._requested_pieces

    # Returns list of currently requested pieces
    def get_requested_pieces(self) -> list[int]:
        with self._lock:
            return sorted(self._requested_pieces)

    # Remote peer availability
    #Update pieces information of a remote peer
    def update_peer_pieces(
        self,
        peer_id: str,
        pieces: list[int] | set[int],
    ) -> None:
        validated = set()

        for piece_index in pieces:
            self._validate_piece_index(piece_index)
            validated.add(piece_index)

        with self._lock:
            self._peer_pieces[peer_id] = validated

    # Update availability information of a remote peer 
    def add_peer_piece(self, peer_id: str, piece_index: int) -> None:
        self._validate_piece_index(piece_index)

        with self._lock:
            self._peer_pieces.setdefault(peer_id, set()).add(piece_index)

    # Remove peer if unavailable or disconnected
    def remove_peer(self, peer_id: str) -> None:
        with self._lock:
            self._peer_pieces.pop(peer_id, None)
            self._connected_peers.discard(peer_id)
            self._choked_by.pop(peer_id, None)

    # Returns the set of pieces available from a remote peer
    def get_peer_pieces(self, peer_id: str) -> set[int]:
        with self._lock:
            return set(self._peer_pieces.get(peer_id, set()))

    # Returns a dictionary of peer IDs and their available pieces
    def get_all_peer_pieces(self) -> dict[str, set[int]]:
        with self._lock:
            return {
                peer_id: set(pieces)
                for peer_id, pieces in self._peer_pieces.items()
            }

    # Connections
    # Update information regarding connected peers
    def add_connected_peer(self, peer_id: str) -> None:
        with self._lock:
            self._connected_peers.add(peer_id)

    def remove_connected_peer(self, peer_id: str) -> None:
        with self._lock:
            self._connected_peers.discard(peer_id)

    def get_connected_peers(self) -> list[str]:
        with self._lock:
            return sorted(self._connected_peers)

    # Choking
    # Update choking state of a remote peer
    def set_choked(self, peer_id: str, choked: bool) -> None:
        with self._lock:
            self._choked_by[peer_id] = choked

    def is_choked(self, peer_id: str) -> bool:
        with self._lock:
            return self._choked_by.get(peer_id, False)

    #Helper method to validate piece index
    def _validate_piece_index(self, piece_index: int) -> None:
        if not isinstance(piece_index, int) or isinstance(piece_index, bool):
            raise TypeError("piece_index must be an integer")

        if piece_index < 0 or piece_index >= self.total_pieces:
            raise IndexError(
                f"piece index out of range: {piece_index}"
            )