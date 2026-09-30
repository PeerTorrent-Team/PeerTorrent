import threading

from src.common.types import FileMetadata
from src.storage.piece_storage import PieceStorage
from .piece import Piece


class PieceManager:
    """Manages the complete set of pieces belonging to a file."""

    def __init__(self, metadata: FileMetadata, storage: PieceStorage) -> None:
        self._lock = threading.RLock()
        self._storage = storage
        self._pieces: list[Piece] = []

        # The metadata must contain exactly one sequential piece
        # for every index: 0, 1, 2, ..., piece_count - 1.
        if metadata.piece_count != len(metadata.pieces):
            raise ValueError(
                "metadata.piece_count does not match the number of pieces"
            )

        for expected_index, piece_info in enumerate(metadata.pieces):
            if piece_info.index != expected_index:
                raise ValueError(
                    f"Invalid piece index: expected {expected_index}, "
                    f"got {piece_info.index}"
                )

            self._pieces.append(
                Piece(
                    index=piece_info.index,
                    size=piece_info.size,
                    expected_hash=piece_info.hash,
                    data=None,
                    is_complete=False,
                )
            )

    def _validate_index(self, index: int) -> None:
        if not isinstance(index, int) or isinstance(index, bool):
            raise TypeError("piece index must be an integer")

        if index < 0 or index >= len(self._pieces):
            raise IndexError(
                f"Piece index out of range: {index}"
            )

    def get_missing_pieces(self) -> list[int]:
        """Returns the pieces that have not been downloaded yet."""
        with self._lock:
            return [piece.index for piece in self._pieces if not piece.is_complete]

    def has_piece(self, index: int) -> bool:
        """Checks whether the peer already has a particular piece."""
        self._validate_index(index)
        with self._lock:
            return self._pieces[index].is_complete

    def get_piece(self, index: int) -> Piece:
        """Returns information for the requested piece."""
        self._validate_index(index)
        with self._lock:
            return self._pieces[index]

    def set_piece_data(self, index: int, data: bytes) -> None:
        self._validate_index(index)
        if not isinstance(data, bytes):
            raise TypeError("piece data must be bytes")

        with self._lock:
            self._pieces[index].data = data

    def mark_piece_complete(self, index: int) -> None:
        """Marks a piece as successfully downloaded."""
        self._validate_index(index)
        with self._lock:
            self._pieces[index].is_complete = True

    def is_complete(self) -> bool:
        """Checks whether all pieces have been downloaded."""
        with self._lock:
            return all(piece.is_complete for piece in self._pieces)

    def piece_count(self) -> int:
        """Return the total number of pieces."""
        return len(self._pieces)

    @property
    def storage(self) -> PieceStorage:
        """Return the storage associated with this piece manager."""
        return self._storage
