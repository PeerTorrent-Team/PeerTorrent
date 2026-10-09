"""Rarest-first piece selection with randomized tie-breaking."""

from __future__ import annotations

import random

from .selector import Selector


class RarestFirstSelector(Selector):
    def select_piece(self, missing_pieces, availability):
        available_pieces = [
            piece
            for piece in missing_pieces
            if availability.get(piece, 0) > 0
        ]
        if not available_pieces:
            return None

        lowest_availability = min(availability[piece] for piece in available_pieces)
        rarest_pieces = [
            piece
            for piece in available_pieces
            if availability[piece] == lowest_availability
        ]
        # Random tie-breaking avoids quietly turning rarest-first into
        # sequential selection when all known pieces have equal availability.
        return random.choice(rarest_pieces)