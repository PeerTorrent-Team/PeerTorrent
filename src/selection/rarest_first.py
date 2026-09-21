from .selector import Selector


class RarestFirstSelector(Selector):

    def select_piece(self, missing_pieces, availability):
        if not missing_pieces:
            return None

        return min(
            missing_pieces,
            key=lambda piece: availability[piece]
        )