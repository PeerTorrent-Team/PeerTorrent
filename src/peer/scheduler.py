from __future__ import annotations


class Scheduler:
    """Choose a request using local piece state and known swarm availability.

    Rarity is calculated over every connected peer with known availability,
    including peers that currently have us choked. The request source, however,
    must be connected and currently unchoked. Separating these two concepts
    prevents a peer's transient choke state from distorting piece rarity.
    """

    def __init__(self, state, selector) -> None:
        self._state = state
        self._selector = selector
        self._round_robin = 0

    def schedule(self):
        """Return ``(peer_id, piece_index)`` or ``None`` if none is schedulable."""
        missing_pieces = [
            piece
            for piece in self._state.get_missing_pieces()
            if not self._state.is_requested(piece)
        ]
        if not missing_pieces:
            return None

        connected = set(self._state.get_connected_peers())
        peer_pieces = self._state.get_all_peer_pieces()
        known_peer_pieces = {
            peer_id: pieces
            for peer_id, pieces in peer_pieces.items()
            if peer_id in connected
        }
        requestable_peer_pieces = {
            peer_id: pieces
            for peer_id, pieces in known_peer_pieces.items()
            if not self._state.is_choked(peer_id)
        }

        if not requestable_peer_pieces:
            return None

        # Count availability across all known connected peers (including
        # currently choked peers) for an accurate rarest-first ranking.
        availability: dict[int, int] = {piece: 0 for piece in missing_pieces}
        for pieces in known_peer_pieces.values():
            for piece in pieces:
                if piece in availability:
                    availability[piece] += 1

        requestable_pieces = {
            piece
            for pieces in requestable_peer_pieces.values()
            for piece in pieces
            if piece in availability
        }
        available_missing = [
            piece for piece in missing_pieces if piece in requestable_pieces
        ]
        if not available_missing:
            return None

        selected_piece = self._selector.select_piece(
            available_missing,
            availability,
        )
        if selected_piece is None:
            return None

        candidate_peers = sorted(
            peer_id
            for peer_id, pieces in requestable_peer_pieces.items()
            if selected_piece in pieces
        )
        if not candidate_peers:
            return None

        selected_peer = candidate_peers[self._round_robin % len(candidate_peers)]
        self._round_robin += 1
        return selected_peer, selected_piece