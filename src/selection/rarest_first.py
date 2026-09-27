from .selector import Selector


class RarestFirstSelector(Selector):

    def select_piece(self, missing_pieces, availability):
        if not missing_pieces:
            return None

        # Only consider pieces for which availability information exists.
        available_pieces = [
            piece
            for piece in missing_pieces
            if piece in availability and availability[piece] > 0
        ]

        if not available_pieces:
            return None

        return min(
            available_pieces,
            key=lambda piece: availability[piece]
        )