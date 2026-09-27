from __future__ import annotations


class Scheduler:
    """
    Decides which piece should be requested next.

    The scheduler coordinates PeerState and a piece-selection strategy.
    It does not perform network operations itself.
    """

    def __init__(self, state, selector) -> None:
        self._state = state
        self._selector = selector
        self._round_robin = 0

    def schedule(self):
        """
        Select the next peer and piece to download.

        Returns:
            (peer_id, piece_index)

        Returns None if no suitable request exists.
        """
        # Pieces that are missing and not currently requested.
        missing_pieces = [
            piece
            for piece in self._state.get_missing_pieces()
            if not self._state.is_requested(piece)
        ]

        if not missing_pieces:
            return None

        peer_pieces = self._state.get_all_peer_pieces()

        # Only connected, unchoked peers can currently serve pieces.
        available_peer_pieces = {
            peer_id: pieces
            for peer_id, pieces in peer_pieces.items()
            if peer_id in self._state.get_connected_peers()
            and not self._state.is_choked(peer_id)
        }

        availability: dict[int, int] = {
            piece: 0
            for piece in missing_pieces
        }

        for pieces in available_peer_pieces.values():
            for piece in pieces:
                if piece in availability:
                    availability[piece] += 1

        available_missing = [
            piece
            for piece in missing_pieces
            if availability.get(piece, 0) > 0
        ]

        if not available_missing:
            return None

        selected_piece = self._selector.select_piece(
            available_missing,
            availability,
        )

        if selected_piece is None:
            return None

        candidate_peers = [
            peer_id
            for peer_id, pieces in available_peer_pieces.items()
            if selected_piece in pieces
        ]

        if not candidate_peers:
            return None

        candidate_peers.sort()
        selected_peer = candidate_peers[
            self._round_robin % len(candidate_peers)
        ]
        self._round_robin += 1

        return selected_peer, selected_piece