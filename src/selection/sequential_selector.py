from .selector import Selector


class SequentialSelector(Selector):

    def select_piece(self, missing_pieces, availability):
        if not missing_pieces:
            return None

        return min(missing_pieces)