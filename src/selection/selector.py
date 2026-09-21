from abc import ABC, abstractmethod


class Selector(ABC):

    @abstractmethod
    def select_piece(self, missing_pieces, availability):
        pass