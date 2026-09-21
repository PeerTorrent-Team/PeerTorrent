import random

from .selector import Selector


class RandomSelector(Selector):

    def select_piece(self, missing_pieces, availability):
        if not missing_pieces:
            return None

        return random.choice(missing_pieces)