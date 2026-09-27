from .selector import Selector


class SequentialSelector(Selector):

    def select_piece(self, missing_pieces, availability):
        available = [
            piece
            for piece in missing_pieces
            if availability.get(piece, 0) > 0
        ]

        if not available:
            return None

        return min(available)