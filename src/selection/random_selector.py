import random

from .selector import Selector


class RandomSelector(Selector):
    def __init__(self, seed: int | None = None) -> None:
        self._random = random.Random(seed)

    def select_piece(self, missing_pieces, availability):
        available = [
            piece
            for piece in missing_pieces
            if availability.get(piece, 0) > 0
        ]

        if not available:
            return None

        return self._random.choice(available)