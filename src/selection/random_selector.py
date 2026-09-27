import random

from .selector import Selector


class RandomSelector(Selector):

    def select_piece(self, missing_pieces, availability):
        available = [
            piece
            for piece in missing_pieces
            if availability.get(piece, 0) > 0
        ]

        if not available:
            return None

        return random.choice(available)