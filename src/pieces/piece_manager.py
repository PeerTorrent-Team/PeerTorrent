from src.common.types import FileMetadata
from src.storage.piece_storage import PieceStorage
from .piece import Piece


class PieceManager:
    """Manages the complete set of pieces belonging to a file."""

    def __init__(self, metadata: FileMetadata, storage: PieceStorage) -> None:
        self._storage = storage
        self._pieces: list[Piece] = []

        for piece_info in metadata.pieces:
            self._pieces.append(Piece(
                index=piece_info.index,
                size=piece_info.size,
                expected_hash=piece_info.hash,
                data=None,
                is_complete=False
            ))

    def _validate_index(self, index: int) -> None:
        if index < 0 or index >= len(self._pieces):
            raise IndexError(f"Piece index out of range: {index}")

    def get_missing_pieces(self) -> list[int]:
        """Returns the pieces that have not been downloaded yet."""
        return [piece.index for piece in self._pieces if not piece.is_complete]

    def has_piece(self, index: int) -> bool:
        """Checks whether the peer already has a particular piece."""
        self._validate_index(index)
        return self._pieces[index].is_complete

    def get_piece(self, index: int) -> Piece:
        """Returns information for the requested piece."""
        self._validate_index(index)
        return self._pieces[index]

    def mark_piece_complete(self, index: int) -> None:
        """Marks a piece as successfully downloaded."""
        self._validate_index(index)
        self._pieces[index].is_complete = True

    def is_complete(self) -> bool:
        """Checks whether all pieces have been downloaded."""
        return all(piece.is_complete for piece in self._pieces)

    def piece_count(self) -> int:
        """Return the total number of pieces."""
        return len(self._pieces)
